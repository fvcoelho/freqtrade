"""Breakout indicators for TwinPenniesHybrid (LONG side only).

Donchian high / ATR / optional trend filter. All rolling windows are
shifted by 1 candle to prevent lookahead bias — we test the current close
against the high of the PREVIOUS N candles, never including the current bar.
"""
from __future__ import annotations

import numpy as np
from pandas import DataFrame


def compute(dataframe: DataFrame, cfg: dict) -> DataFrame:
    """Add breakout indicators to dataframe.

    Columns added:
        donchian_high   : rolling max(high, N) shifted 1 (prev N highs)
        donchian_low    : rolling min(low, N)  shifted 1
        atr             : ATR(period)
        atr_pct         : atr / close (relative volatility)
        atr_z           : z-score of atr_pct over atr_z_window
        breakout_long   : 1 when close > donchian_high
        breakout_strong : 1 when close > donchian_high + atr * min_atr_mult
        trend_up        : 1 when fast SMA > slow SMA (if use_trend_filter)
    """
    c = cfg.get("breakout", {})
    lookback = int(c.get("lookback", 24))
    atr_period = int(c.get("atr_period", 14))
    atr_z_window = int(c.get("atr_z_window", 144))
    min_atr_mult = float(c.get("min_breakout_atr_mult", 0.0))

    high = dataframe["high"]
    low = dataframe["low"]
    close = dataframe["close"]
    prev_close = close.shift(1)

    dataframe["donchian_high"] = high.rolling(lookback).max().shift(1)
    dataframe["donchian_low"] = low.rolling(lookback).min().shift(1)

    tr = np.maximum(
        high - low,
        np.maximum((high - prev_close).abs(), (low - prev_close).abs()),
    )
    atr = tr.rolling(atr_period).mean()
    dataframe["atr"] = atr
    atr_pct = (atr / close.replace(0, np.nan)).fillna(0.0)
    dataframe["atr_pct"] = atr_pct

    atr_pct_mean = atr_pct.rolling(atr_z_window).mean()
    atr_pct_std = atr_pct.rolling(atr_z_window).std().replace(0, np.nan)
    dataframe["atr_z"] = ((atr_pct - atr_pct_mean) / atr_pct_std).fillna(0.0)

    dataframe["breakout_long"] = (close > dataframe["donchian_high"]).astype(int)
    if min_atr_mult > 0:
        threshold = dataframe["donchian_high"] + atr * min_atr_mult
        dataframe["breakout_strong"] = (close > threshold).astype(int)
    else:
        dataframe["breakout_strong"] = dataframe["breakout_long"]

    if c.get("use_trend_filter", False):
        fast = int(c.get("trend_fast", 20))
        slow = int(c.get("trend_slow", 50))
        sma_fast = close.rolling(fast).mean()
        sma_slow = close.rolling(slow).mean()
        dataframe["trend_up"] = (sma_fast > sma_slow).astype(int)
    else:
        dataframe["trend_up"] = 1

    return dataframe
