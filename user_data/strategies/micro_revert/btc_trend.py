"""BTC trend detection from 1h candles.

Computes momentum, volatility (ATR z-score), and directional signals
(pump/dump/chaos) used as safety filters for entries and exits.

Outputs a dict of numpy arrays that gets mapped to the 5m pair dataframe
via forward-fill in map_to_timeframe().
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from pandas import DataFrame


def compute(btc_df: DataFrame, cfg: dict) -> dict:
    """Compute BTC trend signals from 1h candles.

    Returns dict with keys: dates, pump, dump, high_vol, vol_just_ended,
    btc_mom, btc_atr_z (all numpy arrays).
    """
    c = cfg["btc_trend"]

    mom_period = c["mom_period"]
    atr_period = c["atr_period"]
    atr_z_window = c["atr_z_window"]

    mom = btc_df["close"].pct_change(mom_period) * 100

    tr = np.maximum(
        btc_df["high"] - btc_df["low"],
        np.maximum(
            abs(btc_df["high"] - btc_df["close"].shift(1)),
            abs(btc_df["low"] - btc_df["close"].shift(1)),
        ),
    )
    atr = tr.rolling(atr_period).mean()
    atr_pct = atr / btc_df["close"] * 100
    atr_z = (
        (atr_pct - atr_pct.rolling(atr_z_window).mean())
        / atr_pct.rolling(atr_z_window).std().replace(0, np.nan)
    ).fillna(0)

    ve = c["vol_ended_threshold"]

    return {
        "dates": btc_df["date"].values,
        "pump": (mom > c["pump_threshold"]).values,
        "dump": (mom < c["dump_threshold"]).values,
        "high_vol": (atr_z > c["high_vol_threshold"]).values,
        "vol_just_ended": ((atr_z.shift(1) > ve) & (atr_z <= ve)).values,
        "btc_mom": mom.fillna(0.0).values,
        "btc_atr_z": atr_z.fillna(0.0).values,
    }


def map_to_timeframe(btc_state: dict, dataframe: DataFrame) -> DataFrame:
    """Map BTC 1h signals to pair's 5m timeframe via forward-fill."""
    if not btc_state:
        for col in ("btc_pump", "btc_dump", "btc_high_vol", "btc_vol_ended"):
            dataframe[col] = False
        for col in ("btc_mom", "btc_atr_z"):
            dataframe[col] = 0.0
        return dataframe

    signal_map = {
        "btc_pump": ("pump", False),
        "btc_dump": ("dump", False),
        "btc_high_vol": ("high_vol", False),
        "btc_vol_ended": ("vol_just_ended", False),
        "btc_mom": ("btc_mom", True),
        "btc_atr_z": ("btc_atr_z", True),
    }

    pair_dates = pd.to_datetime(dataframe["date"], utc=True)

    for col_name, (signal_key, numeric) in signal_map.items():
        btc_df = pd.DataFrame({
            "date": pd.to_datetime(btc_state["dates"], utc=True),
            signal_key: btc_state[signal_key],
        }).set_index("date")
        merged = btc_df.reindex(pair_dates, method="ffill")
        dataframe[col_name] = merged[signal_key].fillna(0.0 if numeric else False).values

    return dataframe
