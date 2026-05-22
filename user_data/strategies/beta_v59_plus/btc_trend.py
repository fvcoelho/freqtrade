"""BTC trend + regime detection for V59Plus.

Adds consolidation/trending regime detection via ADX, BB squeeze, ATR ratio.
These regimes are mapped to all pair timeframes and used to dynamically
adjust entry thresholds, leverage, and exit behavior.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pandas_ta as ta
from pandas import DataFrame


def compute(btc_df: DataFrame, cfg: dict) -> dict:
    """Compute BTC trend signals + regime from 1h candles.

    Returns dict with keys: dates, pump, dump, high_vol, vol_just_ended,
    btc_mom, btc_atr_z, is_consolidation, is_trending, adx, bb_width
    """
    c = cfg["btc_trend"]

    mom_period = c["mom_period"]
    atr_period = c["atr_period"]
    atr_z_window = c["atr_z_window"]

    # Momentum
    mom = btc_df["close"].pct_change(mom_period) * 100

    # ATR → z-score
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

    # ── Regime Detection ──
    regime_cfg = cfg.get("regime", {})
    adx_low = regime_cfg.get("adx_consolidation", 22)
    adx_high = regime_cfg.get("adx_trending", 28)
    bb_len = regime_cfg.get("bb_length", 20)
    bb_std = regime_cfg.get("bb_std", 2.0)
    bb_squeeze_pct = regime_cfg.get("bb_squeeze_percentile", 0.2)
    atr_consol_threshold = regime_cfg.get("atr_consolidation_threshold", 0.008)

    # ADX
    adx_result = ta.adx(btc_df["high"], btc_df["low"], btc_df["close"], length=14)
    adx_values = adx_result["ADX_14"].fillna(20).values if adx_result is not None else np.full(len(btc_df), 20.0)

    # Bollinger Band Width (squeeze = consolidation)
    bb = ta.bbands(btc_df["close"], length=bb_len, std=bb_std)
    if bb is not None:
        bb_upper = bb[f"BBU_{bb_len}_{bb_std}"]
        bb_lower = bb[f"BBL_{bb_len}_{bb_std}"]
        bb_mid = bb[f"BBM_{bb_len}_{bb_std}"]
        bb_width = ((bb_upper - bb_lower) / bb_mid.replace(0, np.nan)).fillna(0.05)
        bb_squeeze = bb_width < bb_width.rolling(50).quantile(bb_squeeze_pct)
    else:
        bb_width = pd.Series(0.05, index=btc_df.index)
        bb_squeeze = pd.Series(False, index=btc_df.index)

    # ATR ratio (normalized volatility)
    atr_ratio = (atr / btc_df["close"].rolling(50).mean()).fillna(0.01)

    # Regime classification
    is_consolidation = (
        (adx_values < adx_low) &
        (bb_squeeze.values | (atr_ratio.values < atr_consol_threshold))
    )
    is_trending = adx_values > adx_high

    return {
        "dates": btc_df["date"].values,
        "pump": (mom > c["pump_threshold"]).values,
        "dump": (mom < c["dump_threshold"]).values,
        "high_vol": (atr_z > c["high_vol_threshold"]).values,
        "vol_just_ended": ((atr_z.shift(1) > ve) & (atr_z <= ve)).values,
        "btc_mom": mom.fillna(0.0).values,
        "btc_atr_z": atr_z.fillna(0.0).values,
        # Regime
        "adx": adx_values,
        "bb_width": bb_width.values,
        "is_consolidation": is_consolidation,
        "is_trending": is_trending,
    }


def map_to_timeframe(btc_state: dict, dataframe: DataFrame) -> DataFrame:
    """Map BTC 1h signals + regime to pair's 5m timeframe via forward-fill."""
    if not btc_state:
        for col in ("btc_pump", "btc_dump", "btc_high_vol", "btc_vol_ended"):
            dataframe[col] = False
        for col in ("btc_mom", "btc_atr_z", "btc_adx", "btc_bb_width"):
            dataframe[col] = 0.0
        for col in ("is_consolidation", "is_trending"):
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
        "btc_bb_width": ("bb_width", True),
        "is_consolidation": ("is_consolidation", False),
        "is_trending": ("is_trending", False),
    }

    pair_dates = pd.to_datetime(dataframe["date"], utc=True)

    for col_name, (signal_key, numeric) in signal_map.items():
        if signal_key not in btc_state:
            dataframe[col_name] = 0.0 if numeric else False
            continue
        btc_df = pd.DataFrame({
            "date": pd.to_datetime(btc_state["dates"], utc=True),
            signal_key: btc_state[signal_key],
        }).set_index("date")
        merged = btc_df.reindex(pair_dates, method="ffill")
        dataframe[col_name] = merged[signal_key].fillna(0.0 if numeric else False).values

    return dataframe
