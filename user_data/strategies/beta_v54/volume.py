"""Volume filter — pure functional extraction from V51."""

import numpy as np
from pandas import DataFrame


def compute(dataframe: DataFrame, cfg: dict) -> DataFrame:
    """Add volume filter columns: vol_ratio, vol_ok.

    Config keys used: volume.vol_ma_window, vol_ok_threshold
    """
    c = cfg["volume"]
    vol_ma_window = c["vol_ma_window"]
    vol_ok_threshold = c["vol_ok_threshold"]

    vol_ma = dataframe["volume"].rolling(vol_ma_window).mean()
    dataframe["vol_ratio"] = (dataframe["volume"] / vol_ma.replace(0, np.nan)).fillna(1.0)
    dataframe["vol_ok"] = (dataframe["vol_ratio"] > vol_ok_threshold).astype(int)

    return dataframe
