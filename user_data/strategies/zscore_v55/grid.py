"""BTC MACD Recovery scalp for V55 — consolidation regime.

Enters when RSI was recently oversold and MACD crosses above signal
(recovery pattern). Only during BTC consolidation.
Inspired by macd_recovery strategy by Robert Roman.
"""
from __future__ import annotations

import numpy as np
from pandas import DataFrame


def compute_levels(dataframe: DataFrame, pair: str, cfg: dict, dp) -> DataFrame:
    """Compute MACD, RSI, and consolidation flag for BTC."""
    grid_cfg = cfg["grid"]
    btc_pair = cfg["groups"]["btc_ref"]

    if pair != btc_pair:
        return dataframe

    close = dataframe["close"]
    high = dataframe["high"]
    low = dataframe["low"]

    # MACD (12, 26, 9)
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    dataframe["macd"] = ema12 - ema26
    dataframe["macdsignal"] = dataframe["macd"].ewm(span=9).mean()
    dataframe["macdhist"] = dataframe["macd"] - dataframe["macdsignal"]

    # RSI
    rsi_period = grid_cfg.get("rsi_period", 14)
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(rsi_period).mean()
    loss_s = (-delta.where(delta < 0, 0.0)).rolling(rsi_period).mean()
    rs = gain / loss_s.replace(0, np.nan)
    dataframe["rsi"] = (100 - (100 / (1 + rs))).fillna(50)

    # RSI rolling min/max (recovery detection)
    rsi_window = grid_cfg.get("rsi_rolling_window", 8)
    dataframe["rsi_min8"] = dataframe["rsi"].rolling(rsi_window).min()
    dataframe["rsi_max8"] = dataframe["rsi"].rolling(rsi_window).max()

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
    """Generate MACD recovery signals for BTC during consolidation.

    Long: RSI was recently oversold + MACD crosses above signal
    Short: RSI was recently overbought + MACD crosses below signal
    """
    btc_pair = cfg["groups"]["btc_ref"]
    if pair != btc_pair:
        return dataframe

    if "is_consolidating_btc" not in dataframe.columns:
        return dataframe

    grid_cfg = cfg["grid"]
    cooldown = grid_cfg.get("cooldown_candles", 2)
    rsi_oversold = grid_cfg.get("rsi_oversold", 35)
    rsi_overbought = grid_cfg.get("rsi_overbought", 65)
    long_enabled = grid_cfg.get("long_enabled", True)
    short_enabled = grid_cfg.get("short_enabled", True)

    consolidating = dataframe["is_consolidating_btc"]
    no_chaos = ~dataframe["btc_high_vol"]

    no_long = dataframe["enter_long"] == 0
    no_short = dataframe["enter_short"] == 0

    macd = dataframe["macd"]
    signal = dataframe["macdsignal"]
    macd_prev = macd.shift(1)
    signal_prev = signal.shift(1)

    # MACD crosses
    macd_cross_up = (macd_prev <= signal_prev) & (macd > signal)
    macd_cross_down = (macd_prev >= signal_prev) & (macd < signal)

    # RSI recovery: was recently oversold/overbought
    rsi_was_oversold = dataframe["rsi_min8"] < rsi_oversold
    rsi_was_overbought = dataframe["rsi_max8"] > rsi_overbought

    # Long: RSI was oversold recently + MACD crosses up (recovery)
    if long_enabled:
        long_signal = (
            consolidating & no_chaos & no_long
            & rsi_was_oversold & macd_cross_up
        )
    else:
        long_signal = dataframe["close"] < 0

    # Short: RSI was overbought recently + MACD crosses down
    if short_enabled:
        short_signal = (
            consolidating & no_chaos & no_short
            & rsi_was_overbought & macd_cross_down
        )
    else:
        short_signal = dataframe["close"] < 0

    long_arr = long_signal.values.astype(bool).copy()
    short_arr = short_signal.values.astype(bool).copy()
    long_arr, short_arr = _apply_cooldown(long_arr, short_arr, cooldown)

    dataframe.loc[long_arr, "enter_long"] = 1
    dataframe.loc[short_arr, "enter_short"] = 1

    for i in range(len(dataframe)):
        if long_arr[i]:
            dataframe.iat[i, dataframe.columns.get_loc("enter_tag")] = "macd_rec_long"
        elif short_arr[i]:
            dataframe.iat[i, dataframe.columns.get_loc("enter_tag")] = "macd_rec_short"

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
