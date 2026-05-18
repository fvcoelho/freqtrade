"""Always-on queue with regime scoring for V59 — vectorized.

All pairs always in queues (LONG if z<0, SHORT if z>0).
Score = raw_score * regime_multiplier. Only #1 enters if score >= min_score.

This version computes queues for ALL candles at once (vectorized numpy),
making backtesting fast (~5s instead of 10min).
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
from pandas import DataFrame

logger = logging.getLogger(__name__)

# Module-level state for cooldown tracking (used in vectorized pass)
_score_cache: dict = {}


def reset():
    global _score_cache
    _score_cache = {}


def _get_regime_array(btc_mom: np.ndarray) -> np.ndarray:
    """Vectorized regime: 'bull' if mom>0, 'bear' if mom<=-1, else 'ranging'."""
    # Returns int: 0=bull, 1=ranging, 2=bear
    regime = np.ones(len(btc_mom), dtype=int)  # default ranging
    regime[btc_mom > 0.0] = 0   # bull
    regime[btc_mom <= -1.0] = 2  # bear
    return regime


def compute_queue_signals(
    pair_dfs: dict[str, DataFrame],
    btc_ref: str,
    cfg: dict,
    trade_ranges: Optional[dict[str, list]] = None,
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Compute entry signals for ALL pairs across ALL candles at once.

    For each candle, ranks all pairs into LONG/SHORT queues by adjusted score.
    Only the #1 pair in each queue gets a signal, if it passes min_score + safety.

    Parameters
    ----------
    pair_dfs : dict
        {pair: DataFrame} with columns: basket_z, vol_ratio, vol_ok,
        btc_mom, btc_atr_z, btc_pump, btc_dump, btc_high_vol
    btc_ref : str
        BTC reference pair name (excluded from trading)
    cfg : dict
        Full strategy config with "queue" section
    trade_ranges : dict, optional
        {pair: [{"entry_index": int, "exit_index": int}, ...]} from backtest.
        Used to exclude pairs with open trades. If None, no exclusion.

    Returns
    -------
    dict[str, (enter_long, enter_short)]
        {pair: (bool_array_long, bool_array_short)} same length as dataframes.
    """
    queue_cfg = cfg.get("queue", {})
    weights = queue_cfg.get("weights", {})
    w_bz = weights.get("basket_z", 0.5)
    w_vol = weights.get("vol_ratio", 0.2)
    w_vel = weights.get("spread_velocity", 0.2)
    w_cd = weights.get("cooldown", 0.1)
    min_score = queue_cfg.get("min_score", 0.45)
    cooldown_candles = queue_cfg.get("cooldown_candles", 36)

    mults = queue_cfg.get("regime_multipliers", {})
    # Multiplier table: [bull, ranging, bear] x [long, short]
    long_mults = np.array([mults.get("bull_long", 1.0), mults.get("ranging_long", 0.6), mults.get("bear_long", 0.3)])
    short_mults = np.array([mults.get("bull_short", 0.3), mults.get("ranging_short", 0.6), mults.get("bear_short", 1.0)])

    tradable = [p for p in pair_dfs if p != btc_ref]
    if not tradable:
        return {}

    # Find common length
    n = min(len(pair_dfs[p]) for p in tradable)
    if n < 4:
        return {p: (np.zeros(len(pair_dfs[p]), dtype=bool), np.zeros(len(pair_dfs[p]), dtype=bool)) for p in tradable}

    # Extract arrays for all pairs
    bz = {}       # basket_z
    vr = {}       # vol_ratio
    vol_ok = {}   # vol_ok (bool)
    for p in tradable:
        df = pair_dfs[p]
        pn = len(df)
        bz[p] = df["basket_z"].values[:pn] if "basket_z" in df.columns else np.zeros(pn)
        vr[p] = df["vol_ratio"].values[:pn] if "vol_ratio" in df.columns else np.ones(pn)
        vol_ok[p] = df["vol_ok"].values[:pn].astype(bool) if "vol_ok" in df.columns else np.ones(pn, dtype=bool)

    # BTC data (from any pair — btc columns are mapped to all)
    ref_df = pair_dfs[tradable[0]]
    btc_mom = ref_df["btc_mom"].values if "btc_mom" in ref_df.columns else np.zeros(len(ref_df))
    btc_pump = ref_df["btc_pump"].values.astype(bool) if "btc_pump" in ref_df.columns else np.zeros(len(ref_df), dtype=bool)
    btc_dump = ref_df["btc_dump"].values.astype(bool) if "btc_dump" in ref_df.columns else np.zeros(len(ref_df), dtype=bool)
    btc_hv = ref_df["btc_high_vol"].values.astype(bool) if "btc_high_vol" in ref_df.columns else np.zeros(len(ref_df), dtype=bool)

    regime = _get_regime_array(btc_mom)  # 0=bull, 1=ranging, 2=bear

    # Compute raw scores for all pairs (vectorized)
    raw_scores = {}
    for p in tradable:
        pn = len(bz[p])
        bz_abs = np.abs(bz[p])
        bz_norm = np.minimum(bz_abs, 4.0) / 4.0
        vol_norm = np.minimum(vr[p], 3.0) / 3.0

        # Spread velocity: |bz[i] - bz[i-3]|
        bz_prev3 = np.roll(bz[p], 3)
        bz_prev3[:3] = bz[p][:3]  # no lookback for first 3
        vel = np.abs(bz[p] - bz_prev3)
        vel_norm = np.minimum(vel, 2.0) / 2.0

        # Cooldown (simplified for vectorized: no per-trade tracking, use 1.0)
        # Full cooldown tracking would need trade_ranges iteration — skipped for speed
        cd_norm = np.ones(pn)

        raw_scores[p] = w_bz * bz_norm + w_vol * vol_norm + w_vel * vel_norm + w_cd * cd_norm

    # Apply regime multiplier → adjusted scores per side
    long_scores = {}   # {pair: float_array} — only for candles where bz < 0
    short_scores = {}  # {pair: float_array} — only for candles where bz > 0

    for p in tradable:
        pn = len(bz[p])
        regime_p = regime[:pn] if len(regime) >= pn else np.concatenate([regime, np.ones(pn - len(regime), dtype=int)])

        # Long adjusted score (only where bz < 0)
        l_mult = long_mults[regime_p]
        l_adj = raw_scores[p] * l_mult
        l_adj[bz[p] >= 0] = -1.0  # not a long candidate
        long_scores[p] = l_adj

        # Short adjusted score (only where bz > 0)
        s_mult = short_mults[regime_p]
        s_adj = raw_scores[p] * s_mult
        s_adj[bz[p] <= 0] = -1.0  # not a short candidate
        short_scores[p] = s_adj

    # Build open-trade mask if trade_ranges provided
    open_mask = {}  # {pair: bool_array} — True if pair has open trade at candle i
    if trade_ranges:
        for p in tradable:
            pn = len(bz[p])
            mask = np.zeros(pn, dtype=bool)
            for tr in trade_ranges.get(p, []):
                ei = tr.get("entry_index", 0)
                xi = tr.get("exit_index", pn - 1)
                mask[ei:xi + 1] = True
            open_mask[p] = mask

    # For each candle, find #1 in LONG queue and #1 in SHORT queue
    # Stack all pair scores into matrices for argmax
    pair_list = tradable
    np_pairs = len(pair_list)

    # Long matrix: (n_candles, n_pairs) — fill with -1 for non-candidates
    max_n = max(len(long_scores[p]) for p in pair_list)
    long_matrix = np.full((max_n, np_pairs), -1.0)
    short_matrix = np.full((max_n, np_pairs), -1.0)

    for j, p in enumerate(pair_list):
        pn = len(long_scores[p])
        long_matrix[:pn, j] = long_scores[p]
        short_matrix[:pn, j] = short_scores[p]

        # Zero out candles where pair has open trade
        if p in open_mask:
            om = open_mask[p]
            long_matrix[:len(om), j][om] = -1.0
            short_matrix[:len(om), j][om] = -1.0

        # Zero out candles where vol_ok is False
        vo = vol_ok[p]
        long_matrix[:len(vo), j][~vo] = -1.0
        short_matrix[:len(vo), j][~vo] = -1.0

    # Safety filters (applied to all pairs equally)
    for i in range(min(max_n, len(btc_hv))):
        if btc_hv[i]:
            long_matrix[i, :] = -1.0
            short_matrix[i, :] = -1.0
        if btc_dump[i]:
            long_matrix[i, :] = -1.0  # no longs during dump
        if btc_pump[i]:
            short_matrix[i, :] = -1.0  # no shorts during pump

    # Find #1 per candle (argmax along pair axis)
    long_best_idx = np.argmax(long_matrix, axis=1)   # index of best pair per candle
    long_best_score = np.max(long_matrix, axis=1)     # score of best pair per candle
    short_best_idx = np.argmax(short_matrix, axis=1)
    short_best_score = np.max(short_matrix, axis=1)

    # Generate entry signals: only #1 with score >= min_score
    result: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for j, p in enumerate(pair_list):
        pn = len(pair_dfs[p])
        enter_long = np.zeros(pn, dtype=bool)
        enter_short = np.zeros(pn, dtype=bool)

        # This pair is #1 LONG at candles where long_best_idx == j AND score >= min_score
        is_long_best = (long_best_idx[:pn] == j) & (long_best_score[:pn] >= min_score)
        enter_long[:len(is_long_best)] = is_long_best[:pn]

        is_short_best = (short_best_idx[:pn] == j) & (short_best_score[:pn] >= min_score)
        enter_short[:len(is_short_best)] = is_short_best[:pn]

        result[p] = (enter_long, enter_short)

    return result


def record_exit(pair: str, candle_index: int):
    """Record exit for cooldown. (Placeholder for live mode — vectorized mode doesn't use this.)"""
    pass
