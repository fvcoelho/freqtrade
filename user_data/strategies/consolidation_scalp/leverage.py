"""Dynamic leverage for Consolidation Scalp.

Leverage inversely proportional to range size:
    tight range (< 1%) → max leverage (6x)
    wide range (~3.5%)  → min leverage (2x)
"""
from __future__ import annotations


def compute(
    cfg: dict,
    dp,
    pair: str,
    timeframe: str,
    max_leverage: float,
) -> float:
    """Compute leverage based on current range size."""
    lev_cfg = cfg["leverage"]
    lev_min = lev_cfg["min_leverage"]
    lev_max = lev_cfg["max_leverage"]
    range_pct_max = lev_cfg["range_pct_max"]

    # Get current range_pct from analyzed dataframe
    dataframe, _ = dp.get_analyzed_dataframe(pair, timeframe)
    if dataframe is None or dataframe.empty:
        return lev_min

    range_pct = float(dataframe.iloc[-1].get("range_pct", range_pct_max))

    # Linear interpolation: tight range → high lev, wide range → low lev
    if range_pct <= 0:
        lev = lev_max
    elif range_pct >= range_pct_max:
        lev = lev_min
    else:
        t = range_pct / range_pct_max
        lev = lev_max - t * (lev_max - lev_min)

    lev = round(max(lev_min, min(lev, lev_max, max_leverage)), 1)
    return lev


def stake_amount(cfg: dict, max_stake: float) -> float:
    """Return fixed stake per position."""
    return min(cfg["stake_per_position"], max_stake)
