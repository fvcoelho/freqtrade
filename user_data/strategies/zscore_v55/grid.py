"""BTC Grid scalp for V55 — consolidation regime.

Buys at bottom zone and sells at top zone of BTC rolling range
during consolidation. Simple price-action grid.
"""
from __future__ import annotations

import numpy as np
from pandas import DataFrame


def compute_levels(dataframe: DataFrame, pair: str, cfg: dict, dp) -> DataFrame:
    """Compute grid levels and consolidation flag for BTC."""
    grid_cfg = cfg["grid"]
    btc_pair = cfg["groups"]["btc_ref"]

    if pair != btc_pair:
        return dataframe

    close = dataframe["close"]
    high = dataframe["high"]
    low = dataframe["low"]

    range_window = grid_cfg.get("range_window", 48)

    rolling_high = high.rolling(range_window).max()
    rolling_low = low.rolling(range_window).min()
    range_size = rolling_high - rolling_low

    dataframe["grid_rolling_high"] = rolling_high
    dataframe["grid_rolling_low"] = rolling_low
    dataframe["grid_pos"] = (
        (close - rolling_low) / range_size.replace(0, np.nan)
    ).fillna(0.5)

    if "rsi" not in dataframe.columns:
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0).rolling(14).mean()
        loss_s = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
        rs = gain / loss_s.replace(0, np.nan)
        dataframe["rsi"] = (100 - (100 / (1 + rs))).fillna(50)

    # BTC consolidation detection
    atr_period = grid_cfg.get("atr_period", 14)
    atr_z_window = grid_cfg.get("atr_z_window", 48)
    atr_z_max = grid_cfg.get("atr_z_max", 0.0)
    mom_window = grid_cfg.get("mom_window", 12)
    mom_max = grid_cfg.get("mom_max", 0.008)

    prev_close = close.shift(1)
    tr = np.maximum(
        high - low,
        np.maximum(abs(high - prev_close), abs(low - prev_close)),
    )
    atr = tr.rolling(atr_period).mean()
    atr_mean = atr.rolling(atr_z_window).mean()
    atr_std = atr.rolling(atr_z_window).std()
    atr_z = ((atr - atr_mean) / atr_std.replace(0, np.nan)).fillna(0)
    momentum = close.pct_change(mom_window).abs()

    dataframe["is_consolidating_btc"] = (atr_z < atr_z_max) & (momentum < mom_max)

    return dataframe


def generate(dataframe: DataFrame, pair: str, cfg: dict) -> DataFrame:
    """Generate grid signals for BTC during consolidation.

    Buy when price crosses into bottom zone.
    Sell when price crosses into top zone.
    """
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

    entering_buy = (pos_prev > buy_zone) & (pos <= buy_zone)
    entering_sell = (pos_prev < sell_zone) & (pos >= sell_zone)

    if long_enabled:
        long_signal = consolidating & no_chaos & entering_buy & bullish & no_long
    else:
        long_signal = dataframe["close"] < 0

    if short_enabled:
        short_signal = consolidating & no_chaos & entering_sell & bearish & no_short
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
