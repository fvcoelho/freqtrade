"""Grid trading module for ZScore V55 — consolidation regime.

Computes dynamic grid levels within the consolidation range and
generates buy/sell signals when price crosses levels.
"""
from __future__ import annotations

import numpy as np
from pandas import DataFrame


def compute_levels(dataframe: DataFrame, cfg: dict) -> DataFrame:
    """Add grid level columns and position-in-range to dataframe."""
    grid_cfg = cfg["grid"]
    n_levels = grid_cfg["n_levels"]
    regime_cfg = cfg["regime"]

    close = dataframe["close"]
    high = dataframe["high"]
    low = dataframe["low"]

    range_window = regime_cfg.get("consolidation_range_window",
                                   cfg.get("consolidation", {}).get("range_window", 96))

    rolling_high = high.rolling(range_window).max()
    rolling_low = low.rolling(range_window).min()
    range_size = rolling_high - rolling_low

    dataframe["grid_rolling_high"] = rolling_high
    dataframe["grid_rolling_low"] = rolling_low
    dataframe["pos_in_range"] = (
        (close - rolling_low) / range_size.replace(0, np.nan)
    ).fillna(0.5)

    for i in range(n_levels + 1):
        frac = i / n_levels
        dataframe[f"grid_level_{i}"] = rolling_low + frac * range_size

    if "rsi" not in dataframe.columns:
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0).rolling(14).mean()
        loss_s = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
        rs = gain / loss_s.replace(0, np.nan)
        dataframe["rsi"] = (100 - (100 / (1 + rs))).fillna(50)

    return dataframe


def generate(
    dataframe: DataFrame,
    pair: str,
    cfg: dict,
    group_sub1: list[str],
    group_sub2: list[str],
    group_name: str,
) -> DataFrame:
    """Generate grid entry signals during consolidation."""
    grid_cfg = cfg["grid"]
    n_levels = grid_cfg["n_levels"]
    cooldown = grid_cfg["cooldown_candles"]
    require_confirm = grid_cfg["require_confirmation"]
    use_rsi = grid_cfg["rsi_filter"]
    rsi_oversold = grid_cfg["rsi_oversold"]
    rsi_overbought = grid_cfg["rsi_overbought"]

    is_a = pair in group_sub1
    is_b = pair in group_sub2
    if not is_a and not is_b:
        return dataframe

    consolidating = dataframe["is_consolidating"]

    no_chaos = ~dataframe["btc_high_vol"]
    safe_long = ~dataframe["btc_dump"] & no_chaos
    safe_short = ~dataframe["btc_pump"] & no_chaos
    vol = dataframe["vol_ok"] == 1

    if require_confirm:
        bullish = dataframe["close"] > dataframe["open"]
        bearish = dataframe["close"] < dataframe["open"]
    else:
        bullish = True
        bearish = True

    if use_rsi:
        rsi_long_ok = dataframe["rsi"] < rsi_oversold
        rsi_short_ok = dataframe["rsi"] > rsi_overbought
    else:
        rsi_long_ok = True
        rsi_short_ok = True

    no_long = dataframe["enter_long"] == 0
    no_short = dataframe["enter_short"] == 0

    pos = dataframe["pos_in_range"]
    pos_prev = pos.shift(1)

    long_cross = np.zeros(len(dataframe), dtype=bool)
    short_cross = np.zeros(len(dataframe), dtype=bool)
    cross_level = np.zeros(len(dataframe), dtype=int)

    for lv in range(1, n_levels):
        frac = lv / n_levels
        crossed_down = (pos_prev > frac) & (pos <= frac)
        crossed_up = (pos_prev < frac) & (pos >= frac)

        down_mask = crossed_down.values.astype(bool)
        up_mask = crossed_up.values.astype(bool)

        long_cross = long_cross | down_mask
        short_cross = short_cross | up_mask
        cross_level[down_mask | up_mask] = lv

    gn = group_name

    long_signal = (
        consolidating & vol & safe_long & bullish & rsi_long_ok
        & long_cross & no_long
    )
    short_signal = (
        consolidating & vol & safe_short & bearish & rsi_short_ok
        & short_cross & no_short
    )

    long_arr = long_signal.values.astype(bool).copy()
    short_arr = short_signal.values.astype(bool).copy()
    long_arr, short_arr = _apply_cooldown(long_arr, short_arr, cooldown)

    dataframe.loc[long_arr, "enter_long"] = 1
    dataframe.loc[long_arr, "enter_tag"] = ""
    dataframe.loc[short_arr, "enter_short"] = 1
    dataframe.loc[short_arr, "enter_tag"] = ""

    for i in range(len(dataframe)):
        if long_arr[i]:
            dataframe.iat[i, dataframe.columns.get_loc("enter_tag")] = (
                f"grid_long_L{cross_level[i]}_{gn}"
            )
        elif short_arr[i]:
            dataframe.iat[i, dataframe.columns.get_loc("enter_tag")] = (
                f"grid_short_L{cross_level[i]}_{gn}"
            )

    return dataframe


def _apply_cooldown(long_arr, short_arr, cooldown):
    """Suppress signals within cooldown candles of previous signal."""
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
