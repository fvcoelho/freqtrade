"""Leverage sizing and stake amount for ZScore V52."""
from __future__ import annotations

import math
from typing import Optional


def _snapshot_features(last) -> list[float]:
    """Extract feature snapshot from the last candle row."""
    return [
        abs(float(last.get("spread_zscore", 0.0))),
        float(last.get("rolling_corr", 0.0)),
        float(last.get("vol_ratio", 1.0)),
        float(last.get("btc_mom", 0.0)),
        float(last.get("btc_atr_z", 0.0)),
    ]


def compute(
    pair: str,
    cfg: dict,
    dp,
    timeframe: str,
    entry_tag: Optional[str],
    side: str,
    max_leverage: float,
    pending_features: dict,
) -> tuple[float, list[float]]:
    """Compute leverage and snapshot features.

    Returns (leverage_value, features_list).
    Features: [spread_z, rolling_corr, vol_ratio, btc_mom, btc_atr_z]
    """
    lv = cfg["leverage"]
    lev_base = lv["base_multiplier"]

    dataframe, _ = dp.get_analyzed_dataframe(pair, timeframe)
    if dataframe is not None and not dataframe.empty:
        last = dataframe.iloc[-1]
        features = _snapshot_features(last)
        pending_features[pair] = features
    else:
        return min(lev_base, max_leverage), []

    last = dataframe.iloc[-1]
    spread_z = abs(float(last.get("spread_zscore", 0.0)))
    pair_z = abs(float(last.get("pair_zscore", 0.0)))
    signal_strength = max(spread_z, pair_z)

    lev_aggression = lv["signal_aggression"]
    lev_divisor = lv["signal_divisor"]
    lev_min = lv["min"]
    lev_max = lv["max"]
    lev_consol_max = lv["consol_max"]
    lev_btc_hv_max = lv["btc_high_vol_max"]
    lev_btc_pd_mult = lv["btc_pump_dump_multiplier"]
    lev_floor = lv["floor"]

    lev = lev_base * math.exp(signal_strength * lev_aggression / lev_divisor)
    lev = max(lev_min, min(lev, lev_max, max_leverage))

    if entry_tag and entry_tag.startswith("consol_"):
        lev = min(lev, lev_consol_max)

    if last.get("btc_high_vol", False):
        lev = min(lev, lev_btc_hv_max)
    elif last.get("btc_pump", False) or last.get("btc_dump", False):
        lev *= lev_btc_pd_mult

    lev = round(max(lev_floor, min(lev, max_leverage)), 1)
    return lev, features


def stake_amount(cfg: dict, max_stake: float) -> float:
    """Return fixed stake per position."""
    return min(cfg["stake_per_position"], max_stake)
