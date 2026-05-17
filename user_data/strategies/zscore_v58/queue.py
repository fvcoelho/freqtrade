"""Queue-based scoring and confirmation for V58.

Each candle, all pairs receive a multi-factor score. Top-K pairs per side
(long/short) enter a confirmation queue. A pair must stay in top-K for N
consecutive candles before it can trade.

State is module-level (persisted across candles within a single run).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ── Module-level state ──
_confirm_long: dict[str, int] = {}
_confirm_short: dict[str, int] = {}
_last_exit_candle: dict[str, int] = {}
_candle_count: int = 0

# Cache: scores computed once per candle cycle, reused across pairs
_score_cache: dict = {}  # {"cycle": int, "scores": {}, "ready": []}


def reset():
    """Reset all queue state. Called on strategy init."""
    global _confirm_long, _confirm_short, _last_exit_candle, _candle_count, _score_cache
    _confirm_long = {}
    _confirm_short = {}
    _last_exit_candle = {}
    _candle_count = 0
    _score_cache = {}


def compute_scores(
    pair_data: dict[str, dict],
    cfg: dict,
    candle_index: int,
) -> dict[str, float]:
    """Compute composite score for each pair.

    Parameters
    ----------
    pair_data : dict
        {pair: {basket_z, basket_z_prev3, vol_ratio, vol_ok, btc_mom, ...}}
    cfg : dict
        Full strategy config with "queue" section.
    candle_index : int
        Current candle index (for cooldown check).

    Returns
    -------
    dict[str, float]
        {pair: score} where score is 0.0-1.0.
    """
    weights = cfg["queue"]["weights"]
    w_bz = weights.get("basket_z", 0.5)
    w_vol = weights.get("vol_ratio", 0.2)
    w_vel = weights.get("spread_velocity", 0.2)
    w_cd = weights.get("cooldown", 0.1)
    cooldown_candles = cfg["queue"].get("cooldown_candles", 36)

    scores: dict[str, float] = {}

    for pair, d in pair_data.items():
        bz = abs(d.get("basket_z", 0.0))
        vr = d.get("vol_ratio", 1.0)
        bz_prev = d.get("basket_z_prev3", d.get("basket_z", 0.0))
        velocity = abs(d.get("basket_z", 0.0) - bz_prev)

        # Normalize to 0-1
        bz_norm = min(bz, 4.0) / 4.0
        vol_norm = min(vr, 3.0) / 3.0
        vel_norm = min(velocity, 2.0) / 2.0

        # Cooldown: 1.0 if no recent exit, 0.0 if within cooldown window
        last_exit = _last_exit_candle.get(pair, -999)
        cd_norm = 0.0 if (candle_index - last_exit) < cooldown_candles else 1.0

        score = w_bz * bz_norm + w_vol * vol_norm + w_vel * vel_norm + w_cd * cd_norm
        scores[pair] = round(score, 6)

    return scores


def build_queues(
    scores: dict[str, float],
    pair_data: dict[str, dict],
    cfg: dict,
    open_pairs: set[str],
) -> tuple[list[str], list[str]]:
    """Build long and short queues from scored pairs.

    Filters by entry_z threshold, BTC regime, safety, and vol.
    Excludes pairs with open trades.
    Returns top-K pairs per queue, sorted by score descending.
    """
    basket_cfg = cfg["basket"]
    entry_z = basket_cfg.get("entry_z", 2.0)
    bull_th = basket_cfg.get("bull_mom_threshold", 0.0)
    bear_th = basket_cfg.get("bear_mom_threshold", -1.0)
    top_k = cfg["queue"].get("top_k", 3)

    long_candidates = []
    short_candidates = []

    for pair, d in pair_data.items():
        if pair in open_pairs:
            continue
        if not d.get("vol_ok", False):
            continue
        if d.get("btc_high_vol", False):
            continue

        bz = d.get("basket_z", 0.0)
        btc_mom = d.get("btc_mom", 0.0)
        score = scores.get(pair, 0.0)

        # Long: pair lagging (z < -entry_z), bull regime, no dump
        if bz < -entry_z and btc_mom > bull_th and not d.get("btc_dump", False):
            long_candidates.append((pair, score))

        # Short: pair leading (z > entry_z), bear regime, no pump
        if bz > entry_z and btc_mom < bear_th and not d.get("btc_pump", False):
            short_candidates.append((pair, score))

    # Sort by score descending, keep top-K
    long_candidates.sort(key=lambda x: x[1], reverse=True)
    short_candidates.sort(key=lambda x: x[1], reverse=True)

    long_queue = [p for p, _ in long_candidates[:top_k]]
    short_queue = [p for p, _ in short_candidates[:top_k]]

    return long_queue, short_queue


def update_confirmation(
    long_queue: list[str],
    short_queue: list[str],
    cfg: dict,
) -> list[tuple[str, str]]:
    """Update confirmation counters and return ready-to-enter pairs.

    A pair must stay in its queue's top-K for `confirm_candles` consecutive
    candles. If it drops out, its counter resets to 0.

    Returns list of (pair, side) tuples that are confirmed and ready.
    """
    confirm_needed = cfg["queue"].get("confirm_candles", 3)
    ready: list[tuple[str, str]] = []

    long_set = set(long_queue)
    short_set = set(short_queue)

    # Update long confirmations
    for pair in list(_confirm_long.keys()):
        if pair not in long_set:
            _confirm_long[pair] = 0
    for pair in long_queue:
        _confirm_long[pair] = _confirm_long.get(pair, 0) + 1
        if _confirm_long[pair] >= confirm_needed:
            ready.append((pair, "long"))

    # Update short confirmations
    for pair in list(_confirm_short.keys()):
        if pair not in short_set:
            _confirm_short[pair] = 0
    for pair in short_queue:
        _confirm_short[pair] = _confirm_short.get(pair, 0) + 1
        if _confirm_short[pair] >= confirm_needed:
            ready.append((pair, "short"))

    return ready


def record_exit(pair: str, candle_index: int):
    """Record that a trade on this pair exited at the given candle.

    Used by cooldown_bonus scoring factor.
    """
    _last_exit_candle[pair] = candle_index
    # Also reset confirmation counters for this pair
    _confirm_long[pair] = 0
    _confirm_short[pair] = 0
