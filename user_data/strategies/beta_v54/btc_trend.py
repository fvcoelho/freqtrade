"""BTC trend + ADX regime detection for V54."""

import numpy as np
import pandas as pd
import pandas_ta as ta
from pandas import DataFrame


def compute(btc_df: DataFrame, cfg: dict) -> dict:
    """Compute BTC trend signals + ADX regime from 1h candles.

    Returns dict with keys: dates, pump, dump, high_vol, vol_just_ended,
    btc_mom, btc_atr_z, adx, adx_ranging, adx_trending.
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
    atr_z = ((atr_pct - atr_pct.rolling(atr_z_window).mean()) /
             atr_pct.rolling(atr_z_window).std().replace(0, np.nan)).fillna(0)

    ve = c["vol_ended_threshold"]

    # ── ADX Regime Detection ──
    adx_cfg = cfg.get("adx_regime", {})
    adx_ranging_thresh = adx_cfg.get("adx_ranging_threshold", 20)
    adx_trending_thresh = adx_cfg.get("adx_trending_threshold", 25)
    persist_win = adx_cfg.get("persistence_window", 3)
    persist_thresh = adx_cfg.get("persistence_threshold", 0.6)

    adx_result = ta.adx(btc_df["high"], btc_df["low"], btc_df["close"], length=14)
    if adx_result is not None:
        adx_values = adx_result["ADX_14"].fillna(20).values
    else:
        adx_values = np.full(len(btc_df), 20.0)

    raw_ranging = adx_values < adx_ranging_thresh
    # Persistence filter: require majority of recent candles to agree
    adx_ranging = pd.Series(raw_ranging).rolling(persist_win).mean().values >= persist_thresh
    adx_trending = adx_values > adx_trending_thresh

    return {
        "dates": btc_df["date"].values,
        "pump": (mom > c["pump_threshold"]).values,
        "dump": (mom < c["dump_threshold"]).values,
        "high_vol": (atr_z > c["high_vol_threshold"]).values,
        "vol_just_ended": ((atr_z.shift(1) > ve) & (atr_z <= ve)).values,
        "btc_mom": mom.fillna(0.0).values,
        "btc_atr_z": atr_z.fillna(0.0).values,
        "adx": adx_values,
        "adx_ranging": adx_ranging,
        "adx_trending": adx_trending,
    }


def map_to_timeframe(btc_state: dict, dataframe: DataFrame) -> DataFrame:
    """Map BTC 1h signals to pair's timeframe via forward-fill.

    Adds columns: btc_pump, btc_dump, btc_high_vol, btc_vol_ended, btc_mom, btc_atr_z
    """
    if not btc_state:
        for col in ("btc_pump", "btc_dump", "btc_high_vol", "btc_vol_ended"):
            dataframe[col] = False
        for col in ("btc_mom", "btc_atr_z", "btc_adx"):
            dataframe[col] = 0.0
        for col in ("adx_ranging", "adx_trending"):
            dataframe[col] = False
        return dataframe

    signal_map = {
        "btc_pump": ("pump", False),
        "btc_dump": ("dump", False),
        "btc_high_vol": ("high_vol", False),
        "btc_vol_ended": ("vol_just_ended", False),
        "btc_mom": ("btc_mom", True),
        "btc_atr_z": ("btc_atr_z", True),
        "btc_adx": ("adx", True),
        "adx_ranging": ("adx_ranging", False),
        "adx_trending": ("adx_trending", False),
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
