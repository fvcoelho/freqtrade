"""BTC Grid scalp for V55 — rolling range consolidation detection.

Detects consolidation directly on 5m using rolling range %.
When range is tight (< threshold), buys at bottom and sells at top.
No dependency on BTC 1h for consolidation detection.
"""
from __future__ import annotations

import numpy as np
from pandas import DataFrame


def compute_levels(dataframe: DataFrame, pair: str, cfg: dict, dp) -> DataFrame:
    """Compute rolling range and grid levels for BTC on 5m."""
    grid_cfg = cfg["grid"]
    btc_pair = cfg["groups"]["btc_ref"]

    if pair != btc_pair:
        return dataframe

    close = dataframe["close"]
    high = dataframe["high"]
    low = dataframe["low"]

    range_window = grid_cfg.get("range_window", 48)
    range_max_pct = grid_cfg.get("range_max_pct", 0.015)

    rolling_high = high.rolling(range_window).max()
    rolling_low = low.rolling(range_window).min()
    range_size = rolling_high - rolling_low
    range_pct = (range_size / close).fillna(1)

    dataframe["grid_rolling_high"] = rolling_high
    dataframe["grid_rolling_low"] = rolling_low
    dataframe["grid_range_pct"] = range_pct
    dataframe["grid_pos"] = (
        (close - rolling_low) / range_size.replace(0, np.nan)
    ).fillna(0.5)

    # Consolidation = rolling range < threshold (pure 5m, no 1h dependency)
    dataframe["is_consolidating_btc"] = range_pct < range_max_pct

    return dataframe


def generate(dataframe: DataFrame, pair: str, cfg: dict) -> DataFrame:
    """Generate grid signals when BTC range is tight."""
    btc_pair = cfg["groups"]["btc_ref"]
    if pair != btc_pair:
        return dataframe

    if "is_consolidating_btc" not in dataframe.columns:
        return dataframe

    grid_cfg = cfg["grid"]
    n_levels = grid_cfg.get("n_levels", 5)
    cooldown = grid_cfg.get("cooldown_candles", 1)
    long_enabled = grid_cfg.get("long_enabled", True)
    short_enabled = grid_cfg.get("short_enabled", True)

    consolidating = dataframe["is_consolidating_btc"]
    no_chaos = ~dataframe["btc_high_vol"]

    no_long = dataframe["enter_long"] == 0
    no_short = dataframe["enter_short"] == 0

    pos = dataframe["grid_pos"]
    pos_prev = pos.shift(1)

    bullish = dataframe["close"] > dataframe["open"]
    bearish = dataframe["close"] < dataframe["open"]

    buy_zone = 1 / n_levels
    sell_zone = 1 - (1 / n_levels)

    in_buy_zone = pos <= buy_zone
    in_sell_zone = pos >= sell_zone

    if long_enabled:
        long_signal = consolidating & no_chaos & in_buy_zone & bullish & no_long
    else:
        long_signal = dataframe["close"] < 0

    if short_enabled:
        short_signal = consolidating & no_chaos & in_sell_zone & bearish & no_short
    else:
        short_signal = dataframe["close"] < 0

    long_arr = long_signal.values.astype(bool).copy()
    short_arr = short_signal.values.astype(bool).copy()
    long_arr, short_arr = _apply_cooldown(long_arr, short_arr, cooldown)

    levels = np.round(pos.values * n_levels).astype(int)

    dataframe.loc[long_arr, "enter_long"] = 1
    dataframe.loc[short_arr, "enter_short"] = 1

    for i in range(len(dataframe)):
        if long_arr[i]:
            dataframe.iat[i, dataframe.columns.get_loc("enter_tag")] = (
                f"grid_long_L{levels[i]}"
            )
        elif short_arr[i]:
            dataframe.iat[i, dataframe.columns.get_loc("enter_tag")] = (
                f"grid_short_L{levels[i]}"
            )

    return dataframe


def _apply_cooldown(long_arr, short_arr, cooldown):
    last_long = -cooldown - 1
    last_short = -cooldown - 1
    for i in range(len(long_arr)):
        if long_arr[i]:
            if i - last_long <= cooldown:
                long_arr[i] = False
            else:
                last_long = i
        if short_arr[i]:
            if i - last_short <= cooldown:
                short_arr[i] = False
            else:
                last_short = i
    return long_arr, short_arr
