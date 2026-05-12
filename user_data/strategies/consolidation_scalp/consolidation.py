"""Consolidation regime filter.

Adds columns:
    - atr: ATR(period)
    - atr_zscore: z-score of ATR over window
    - range_pct: (rolling_max - rolling_min) / close
    - momentum: abs(close.pct_change(window))
    - vol_zscore: z-score of volume over window
    - is_consolidating: bool — all criteria met
    - is_breakout: bool — kill switch triggered
"""
from __future__ import annotations

import numpy as np
from pandas import DataFrame


def compute(dataframe: DataFrame, cfg: dict) -> DataFrame:
    """Add consolidation columns to dataframe. Mutates and returns dataframe."""
    c = cfg["consolidation"]

    # ATR
    high = dataframe["high"]
    low = dataframe["low"]
    close = dataframe["close"]
    prev_close = close.shift(1)

    tr = np.maximum(
        high - low,
        np.maximum(abs(high - prev_close), abs(low - prev_close)),
    )
    atr = tr.rolling(c["atr_period"]).mean()
    dataframe["atr"] = atr

    # ATR z-score
    atr_mean = atr.rolling(c["atr_zscore_window"]).mean()
    atr_std = atr.rolling(c["atr_zscore_window"]).std()
    dataframe["atr_zscore"] = (atr - atr_mean) / atr_std.replace(0, np.nan)
    dataframe["atr_zscore"] = dataframe["atr_zscore"].fillna(0)

    # Range percent
    rw = c["range_window"]
    rolling_high = high.rolling(rw).max()
    rolling_low = low.rolling(rw).min()
    dataframe["range_pct"] = (rolling_high - rolling_low) / close
    dataframe["rolling_high"] = rolling_high
    dataframe["rolling_low"] = rolling_low

    # Momentum
    mw = c["momentum_window"]
    dataframe["momentum"] = close.pct_change(mw).abs()

    # Volume z-score
    vol = dataframe["volume"]
    vw = c["volume_zscore_window"]
    vol_mean = vol.rolling(vw).mean()
    vol_std = vol.rolling(vw).std()
    dataframe["vol_zscore"] = (vol - vol_mean) / vol_std.replace(0, np.nan)
    dataframe["vol_zscore"] = dataframe["vol_zscore"].fillna(0)

    # Consolidation flag
    vz_min, vz_max = c["volume_zscore_range"]
    dataframe["is_consolidating"] = (
        (dataframe["atr_zscore"] < c["atr_zscore_max"])
        & (dataframe["range_pct"] < c["range_pct_max"])
        & (dataframe["momentum"] < c["momentum_max"])
        & (dataframe["vol_zscore"] >= vz_min)
        & (dataframe["vol_zscore"] <= vz_max)
    )

    # Breakout kill switch
    dataframe["is_breakout"] = (
        (dataframe["atr_zscore"] > c["breakout_atr_z"])
        | (dataframe["momentum"] > c["breakout_momentum"])
    )

    return dataframe
