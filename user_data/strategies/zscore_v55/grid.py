"""BTC BB Bounce scalp for V55 — consolidation regime.

Simple mean-reversion: buy when price drops below BB lower band,
TP at BB middle band. No time stop — lets trade run.
Inspired by mark_strat strategy.
"""
from __future__ import annotations

import numpy as np
from pandas import DataFrame


def compute_levels(dataframe: DataFrame, pair: str, cfg: dict, dp) -> DataFrame:
    """Compute Bollinger Bands and consolidation flag for BTC."""
    grid_cfg = cfg["grid"]
    btc_pair = cfg["groups"]["btc_ref"]

    if pair != btc_pair:
        return dataframe

    close = dataframe["close"]
    high = dataframe["high"]
    low = dataframe["low"]

    # Bollinger Bands
    bb_window = grid_cfg.get("bb_window", 20)
    bb_std = grid_cfg.get("bb_std", 2.0)
    sma = close.rolling(bb_window).mean()
    std = close.rolling(bb_window).std()
    dataframe["bb_upper"] = sma + bb_std * std
    dataframe["bb_lower"] = sma - bb_std * std
    dataframe["bb_mid"] = sma

    # RSI
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
    """Generate BB bounce signals for BTC during consolidation.

    Long: price < BB lower (oversold bounce)
    Short: price > BB upper (overbought rejection)
    No time stop — exits via ROI, trailing, or BB mid TP.
    """
    btc_pair = cfg["groups"]["btc_ref"]
    if pair != btc_pair:
        return dataframe

    if "is_consolidating_btc" not in dataframe.columns:
        return dataframe

    grid_cfg = cfg["grid"]
    cooldown = grid_cfg.get("cooldown_candles", 3)
    long_enabled = grid_cfg.get("long_enabled", True)
    short_enabled = grid_cfg.get("short_enabled", True)

    consolidating = dataframe["is_consolidating_btc"]
    no_chaos = ~dataframe["btc_high_vol"]

    no_long = dataframe["enter_long"] == 0
    no_short = dataframe["enter_short"] == 0

    close = dataframe["close"]

    # Long: price below BB lower band (mark_strat style — simple)
    if long_enabled:
        long_signal = consolidating & no_chaos & no_long & (close < dataframe["bb_lower"])
    else:
        long_signal = dataframe["close"] < 0

    # Short: price above BB upper band
    if short_enabled:
        short_signal = consolidating & no_chaos & no_short & (close > dataframe["bb_upper"])
    else:
        short_signal = dataframe["close"] < 0

    long_arr = long_signal.values.astype(bool).copy()
    short_arr = short_signal.values.astype(bool).copy()
    long_arr, short_arr = _apply_cooldown(long_arr, short_arr, cooldown)

    dataframe.loc[long_arr, "enter_long"] = 1
    dataframe.loc[short_arr, "enter_short"] = 1

    for i in range(len(dataframe)):
        if long_arr[i]:
            dataframe.iat[i, dataframe.columns.get_loc("enter_tag")] = "bb_bounce_long"
        elif short_arr[i]:
            dataframe.iat[i, dataframe.columns.get_loc("enter_tag")] = "bb_bounce_short"

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
