"""Always-on queue with regime scoring — vectorized."""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
from pandas import DataFrame

logger = logging.getLogger(__name__)

_score_cache: dict = {}


def reset():
    global _score_cache
    _score_cache = {}


def _get_regime_array(btc_mom: np.ndarray) -> np.ndarray:
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
    queue_cfg = cfg.get("queue", {})
    weights = queue_cfg.get("weights", {})
    w_bz = weights.get("basket_z", 0.5)
    w_vol = weights.get("vol_ratio", 0.2)
    w_vel = weights.get("spread_velocity", 0.2)
    w_cd = weights.get("cooldown", 0.1)
    min_score = queue_cfg.get("min_score", 0.45)

    mults = queue_cfg.get("regime_multipliers", {})
    long_mults = np.array([mults.get("bull_long", 1.0), mults.get("ranging_long", 0.6), mults.get("bear_long", 0.3)])
    short_mults = np.array([mults.get("bull_short", 0.3), mults.get("ranging_short", 0.6), mults.get("bear_short", 1.0)])

    tradable = [p for p in pair_dfs if p != btc_ref]
    if not tradable:
        return {}

    n = min(len(pair_dfs[p]) for p in tradable)
    if n < 4:
        return {p: (np.zeros(len(pair_dfs[p]), dtype=bool), np.zeros(len(pair_dfs[p]), dtype=bool)) for p in tradable}

    bz, vr, vol_ok = {}, {}, {}
    for p in tradable:
        df = pair_dfs[p]
        pn = len(df)
        bz[p] = df["basket_z"].values[:pn] if "basket_z" in df.columns else np.zeros(pn)
        vr[p] = df["vol_ratio"].values[:pn] if "vol_ratio" in df.columns else np.ones(pn)
        vol_ok[p] = df["vol_ok"].values[:pn].astype(bool) if "vol_ok" in df.columns else np.ones(pn, dtype=bool)

    ref_df = pair_dfs[tradable[0]]
    btc_mom = ref_df["btc_mom"].values if "btc_mom" in ref_df.columns else np.zeros(len(ref_df))
    btc_pump = ref_df["btc_pump"].values.astype(bool) if "btc_pump" in ref_df.columns else np.zeros(len(ref_df), dtype=bool)
    btc_dump = ref_df["btc_dump"].values.astype(bool) if "btc_dump" in ref_df.columns else np.zeros(len(ref_df), dtype=bool)
    btc_hv = ref_df["btc_high_vol"].values.astype(bool) if "btc_high_vol" in ref_df.columns else np.zeros(len(ref_df), dtype=bool)

    regime = _get_regime_array(btc_mom)

    raw_scores = {}
    for p in tradable:
        pn = len(bz[p])
        bz_norm = np.minimum(np.abs(bz[p]), 4.0) / 4.0
        vol_norm = np.minimum(vr[p], 3.0) / 3.0
        bz_prev3 = np.roll(bz[p], 3)
        bz_prev3[:3] = bz[p][:3]
        vel_norm = np.minimum(np.abs(bz[p] - bz_prev3), 2.0) / 2.0
        cd_norm = np.ones(pn)
        raw_scores[p] = w_bz * bz_norm + w_vol * vol_norm + w_vel * vel_norm + w_cd * cd_norm

    long_scores, short_scores = {}, {}
    for p in tradable:
        pn = len(bz[p])
        regime_p = regime[:pn] if len(regime) >= pn else np.concatenate([regime, np.ones(pn - len(regime), dtype=int)])
        l_adj = raw_scores[p] * long_mults[regime_p]
        l_adj[bz[p] >= 0] = -1.0
        long_scores[p] = l_adj
        s_adj = raw_scores[p] * short_mults[regime_p]
        s_adj[bz[p] <= 0] = -1.0
        short_scores[p] = s_adj

    open_mask = {}
    if trade_ranges:
        for p in tradable:
            pn = len(bz[p])
            mask = np.zeros(pn, dtype=bool)
            for tr in trade_ranges.get(p, []):
                ei, xi = tr.get("entry_index", 0), tr.get("exit_index", pn - 1)
                mask[ei:xi + 1] = True
            open_mask[p] = mask

    pair_list = tradable
    max_n = max(len(long_scores[p]) for p in pair_list)
    long_matrix = np.full((max_n, len(pair_list)), -1.0)
    short_matrix = np.full((max_n, len(pair_list)), -1.0)

    for j, p in enumerate(pair_list):
        pn = len(long_scores[p])
        long_matrix[:pn, j] = long_scores[p]
        short_matrix[:pn, j] = short_scores[p]
        if p in open_mask:
            om = open_mask[p]
            long_matrix[:len(om), j][om] = -1.0
            short_matrix[:len(om), j][om] = -1.0
        vo = vol_ok[p]
        long_matrix[:len(vo), j][~vo] = -1.0
        short_matrix[:len(vo), j][~vo] = -1.0

    for i in range(min(max_n, len(btc_hv))):
        if btc_hv[i]:
            long_matrix[i, :] = -1.0
            short_matrix[i, :] = -1.0
        if btc_dump[i]:
            long_matrix[i, :] = -1.0
        if btc_pump[i]:
            short_matrix[i, :] = -1.0

    long_best_idx = np.argmax(long_matrix, axis=1)
    long_best_score = np.max(long_matrix, axis=1)
    short_best_idx = np.argmax(short_matrix, axis=1)
    short_best_score = np.max(short_matrix, axis=1)

    result: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for j, p in enumerate(pair_list):
        pn = len(pair_dfs[p])
        enter_long = np.zeros(pn, dtype=bool)
        enter_short = np.zeros(pn, dtype=bool)
        is_long_best = (long_best_idx[:pn] == j) & (long_best_score[:pn] >= min_score)
        enter_long[:len(is_long_best)] = is_long_best[:pn]
        is_short_best = (short_best_idx[:pn] == j) & (short_best_score[:pn] >= min_score)
        enter_short[:len(is_short_best)] = is_short_best[:pn]
        result[p] = (enter_long, enter_short)
    return result
