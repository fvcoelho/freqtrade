"""Momentum features: RSI, MACD, ADX, EMA slopes, ROC, StochRSI."""
from __future__ import annotations

import numpy as np
import talib.abstract as ta
from pandas import DataFrame


def compute(df: DataFrame, cfg: dict) -> DataFrame:
    """Add momentum features to dataframe. All prefixed with %-."""

    # 1. RSI (14)
    df["%-rsi"] = ta.RSI(df, timeperiod=14)

    # 2-3. MACD signal + histogram
    macd, macd_signal, macd_hist = ta.MACD(
        df, fastperiod=12, slowperiod=26, signalperiod=9
    )
    df["%-macd_signal"] = macd_signal
    df["%-macd_hist"] = macd_hist

    # 4. ADX (14)
    df["%-adx"] = ta.ADX(df, timeperiod=14)

    # 5-7. EMA slopes (8, 21, 55)
    for period in [8, 21, 55]:
        ema = ta.EMA(df, timeperiod=period)
        df[f"%-ema_slope_{period}"] = ema.pct_change(3) * 100

    # 8. Rate of change (12)
    df["%-roc"] = ta.ROC(df, timeperiod=12)

    return df
