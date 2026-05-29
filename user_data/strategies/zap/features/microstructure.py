"""Microstructure features: funding rate, OI, volume profile, CVD."""
from __future__ import annotations

import numpy as np
from pandas import DataFrame


def compute(df: DataFrame, cfg: dict) -> DataFrame:
    """Add microstructure features. All prefixed with %-.

    Note: funding_rate and open_interest columns may not be available
    in all data sources. Features default to 0.0 if missing.
    """
    # 1. Funding rate (if available from exchange data)
    if "funding_rate" in df.columns:
        df["%-funding_rate"] = df["funding_rate"]
        # 2. Funding rate delta
        df["%-funding_delta"] = df["funding_rate"].diff(3)
    else:
        df["%-funding_rate"] = 0.0
        df["%-funding_delta"] = 0.0

    # 3. Open interest delta (if available)
    if "open_interest" in df.columns:
        df["%-oi_delta"] = df["open_interest"].pct_change(6)
    else:
        df["%-oi_delta"] = 0.0

    # 4. VWAP deviation (intra-session proxy)
    typical = (df["high"] + df["low"] + df["close"]) / 3
    cum_tp_vol = (typical * df["volume"]).rolling(48, min_periods=1).sum()
    cum_vol = df["volume"].rolling(48, min_periods=1).sum()
    vwap = cum_tp_vol / (cum_vol + 1e-10)
    df["%-vwap_dev"] = (df["close"] - vwap) / (vwap + 1e-10) * 100

    # 5. CVD (cumulative volume delta) — approximated from candle direction
    direction = np.where(df["close"] >= df["open"], 1.0, -1.0)
    vol_delta = df["volume"].values * direction
    df["%-cvd"] = np.cumsum(vol_delta)
    # Normalize CVD as z-score over rolling window
    cvd_series = df["%-cvd"]
    cvd_mean = cvd_series.rolling(144, min_periods=20).mean()
    cvd_std = cvd_series.rolling(144, min_periods=20).std()
    df["%-cvd"] = ((cvd_series - cvd_mean) / (cvd_std + 1e-10)).values

    # 6. Volume ratio (current vs rolling average)
    vol_avg = df["volume"].rolling(48, min_periods=1).mean()
    df["%-vol_ratio"] = df["volume"] / (vol_avg + 1e-10)

    return df
