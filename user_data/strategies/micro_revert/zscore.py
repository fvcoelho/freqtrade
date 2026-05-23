"""Individual Z-Score — price deviation from its own EMA.

Unlike basket z-score which compares pairs against each other,
this computes how far each pair's price deviates from its own
exponential moving average. Fast-reacting signal suitable for
ultra-short scalps.

    ema = close.ewm(span=ema_window).mean()
    std = close.rolling(zscore_window).std()
    z = (close - ema) / std

    z << 0 -> price below its mean -> LONG (mean reversion up)
    z >> 0 -> price above its mean -> SHORT (mean reversion down)
"""
from __future__ import annotations

import numpy as np
from pandas import DataFrame


def compute(dataframe: DataFrame, cfg: dict) -> DataFrame:
    """Compute individual z-score for a single pair.

    Adds columns: ind_z, ind_ema, ind_std

    Config keys used from cfg["zscore"]:
        ema_window: int — EMA span for mean (default 30)
        zscore_window: int — rolling window for std (default 30)
    """
    c = cfg["zscore"]
    ema_window = c.get("ema_window", 30)
    zscore_window = c.get("zscore_window", 30)

    close = dataframe["close"]
    ema = close.ewm(span=ema_window, adjust=False).mean()
    std = close.rolling(window=zscore_window).std()

    z = ((close - ema) / std.replace(0, np.nan)).fillna(0.0)

    dataframe["ind_z"] = z
    dataframe["ind_ema"] = ema
    dataframe["ind_std"] = std

    return dataframe
