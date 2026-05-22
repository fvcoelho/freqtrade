"""Volume filter for entry signal validation."""
from __future__ import annotations

import numpy as np
from pandas import DataFrame


def compute(dataframe: DataFrame, cfg: dict) -> DataFrame:
    """Add volume filter columns: vol_ratio, vol_ok."""
    c = cfg["volume"]
    vol_ma = dataframe["volume"].rolling(c["vol_ma_window"]).mean()
    dataframe["vol_ratio"] = (dataframe["volume"] / vol_ma.replace(0, np.nan)).fillna(1.0)
    dataframe["vol_ok"] = (dataframe["vol_ratio"] > c["vol_ok_threshold"]).astype(int)
    return dataframe
