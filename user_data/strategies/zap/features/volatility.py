"""Volatility features: ATR, BB width, realized vol, Keltner, vol ratio."""
from __future__ import annotations

import numpy as np
import talib.abstract as ta
from pandas import DataFrame
from technical import qtpylib


def compute(df: DataFrame, cfg: dict) -> DataFrame:
    """Add volatility features. All prefixed with %-."""

    # 1. ATR (14)
    df["%-atr"] = ta.ATR(df, timeperiod=14)

    # 2. Bollinger Band width
    bb = qtpylib.bollinger_bands(qtpylib.typical_price(df), window=20, stds=2.0)
    bb_width = (bb["upper"] - bb["lower"]) / (bb["mid"] + 1e-10)
    df["%-bb_width"] = bb_width

    # 3. Realized volatility (close-close, 20-period)
    log_ret = np.log(df["close"] / df["close"].shift(1))
    df["%-realized_vol"] = log_ret.rolling(20, min_periods=5).std() * np.sqrt(288)

    # 4. Volume-weighted volatility
    vol_weight = df["volume"] / (df["volume"].rolling(20, min_periods=1).mean() + 1e-10)
    df["%-vol_weighted_vol"] = (log_ret.abs() * vol_weight).rolling(20, min_periods=5).mean()

    # 5. Keltner Channel squeeze (BB inside Keltner = 1, else 0)
    atr = df["%-atr"]
    ema20 = ta.EMA(df, timeperiod=20)
    kc_upper = ema20 + 1.5 * atr
    kc_lower = ema20 - 1.5 * atr
    df["%-keltner_squeeze"] = ((bb["lower"] > kc_lower) & (bb["upper"] < kc_upper)).astype(float)

    # 6. Volatility ratio (short/long ATR)
    atr_short = ta.ATR(df, timeperiod=7)
    atr_long = ta.ATR(df, timeperiod=28)
    df["%-vol_ratio_sl"] = atr_short / (atr_long + 1e-10)

    # 7. Parkinson volatility (high-low based)
    hl_ratio = np.log(df["high"] / (df["low"] + 1e-10))
    df["%-parkinson_vol"] = (hl_ratio.pow(2).rolling(20, min_periods=5).mean() / (4 * np.log(2))).pow(0.5)

    # 8. ATR percentile rank (current ATR vs 288-candle history)
    atr_series = df["%-atr"]
    df["%-atr_pctile"] = atr_series.rolling(288, min_periods=20).apply(
        lambda x: (x.iloc[-1] <= x).mean() if len(x) > 0 else 0.5, raw=False,
    )

    return df
