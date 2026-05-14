"""BTC CombinedBinHAndCluc scalp for V55 — consolidation regime.

Ultra-selective entries: only when price is deeply below BB lower band.
Two entry patterns (BinHV45 + ClucMay72018). Exit at BB middle band.
No time stop — progressive stoploss protects.
"""
from __future__ import annotations

import numpy as np
from pandas import DataFrame


def bollinger_bands(close, window, num_std):
    rolling_mean = close.rolling(window=window).mean()
    rolling_std = close.rolling(window=window).std()
    lower = rolling_mean - rolling_std * num_std
    return rolling_mean, np.nan_to_num(lower)


def compute_levels(dataframe: DataFrame, pair: str, cfg: dict, dp) -> DataFrame:
    """Compute BB indicators for BTC."""
    grid_cfg = cfg["grid"]
    btc_pair = cfg["groups"]["btc_ref"]

    if pair != btc_pair:
        return dataframe

    close = dataframe["close"]
    high = dataframe["high"]
    low = dataframe["low"]

    # BinHV45 Bollinger (40, 2)
    mid40, lower40 = bollinger_bands(close, 40, 2)
    dataframe["bb_lower40"] = lower40
    dataframe["bbdelta"] = abs(mid40 - lower40)
    dataframe["closedelta"] = abs(close - close.shift(1))
    dataframe["tail"] = abs(close - low)

    # ClucMay72018 Bollinger (20, 2) + EMA50
    mid20, lower20 = bollinger_bands(close, 20, 2)
    dataframe["bb_lower20"] = lower20
    dataframe["bb_mid20"] = mid20
    dataframe["ema50"] = close.ewm(span=50).mean()
    dataframe["vol_mean30"] = dataframe["volume"].rolling(30).mean()

    # Consolidation: rolling range < threshold
    range_window = grid_cfg.get("range_window", 48)
    range_max_pct = grid_cfg.get("range_max_pct", 0.03)
    rolling_high = high.rolling(range_window).max()
    rolling_low = low.rolling(range_window).min()
    range_pct = ((rolling_high - rolling_low) / close).fillna(1)
    dataframe["is_consolidating_btc"] = range_pct < range_max_pct

    dataframe["grid_rolling_high"] = rolling_high
    dataframe["grid_rolling_low"] = rolling_low
    dataframe["grid_pos"] = (
        (close - rolling_low) / (rolling_high - rolling_low).replace(0, np.nan)
    ).fillna(0.5)

    return dataframe


def generate(dataframe: DataFrame, pair: str, cfg: dict) -> DataFrame:
    """Generate ultra-selective entry signals for BTC during consolidation.

    BinHV45: oversold panic candle below BB(40) lower
    ClucMay72018: price 1.5% below BB(20) lower + below EMA50
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
    buy_bbdelta = grid_cfg.get("buy_bbdelta", 0.008)
    buy_closedelta = grid_cfg.get("buy_closedelta", 0.0175)
    buy_tail = grid_cfg.get("buy_tail", 0.25)
    buy_low = grid_cfg.get("buy_low", 0.985)

    consolidating = dataframe["is_consolidating_btc"]
    no_chaos = ~dataframe["btc_high_vol"]
    no_long = dataframe["enter_long"] == 0
    no_short = dataframe["enter_short"] == 0

    close = dataframe["close"]

    # BinHV45: panic oversold candle
    bhv45 = (
        (dataframe["bb_lower40"].shift(1) > 0)
        & (dataframe["bbdelta"] > close * buy_bbdelta)
        & (dataframe["closedelta"] > close * buy_closedelta)
        & (dataframe["tail"] < dataframe["bbdelta"] * buy_tail)
        & (close < dataframe["bb_lower40"].shift(1))
        & (close <= close.shift(1))
    )

    # ClucMay72018: deep below BB + EMA
    cluc = (
        (close < dataframe["ema50"])
        & (close < buy_low * dataframe["bb_lower20"])
        & (dataframe["volume"] < dataframe["vol_mean30"].shift(1) * 20)
    )

    if long_enabled:
        long_signal = no_chaos & no_long & (bhv45 | cluc)
    else:
        long_signal = close < 0

    # Short: mirror — price above BB upper (not implemented, long-only for now)
    if short_enabled:
        short_signal = close < 0  # disabled
    else:
        short_signal = close < 0

    long_arr = long_signal.values.astype(bool).copy()
    short_arr = short_signal.values.astype(bool).copy()
    long_arr, short_arr = _apply_cooldown(long_arr, short_arr, cooldown)

    dataframe.loc[long_arr, "enter_long"] = 1

    for i in range(len(dataframe)):
        if long_arr[i]:
            dataframe.iat[i, dataframe.columns.get_loc("enter_tag")] = "cluc_long"

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
