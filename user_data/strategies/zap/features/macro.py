"""Macro features: BTC trend, momentum, dominance, alt correlation."""
from __future__ import annotations

import numpy as np
import talib.abstract as ta
from pandas import DataFrame


def compute(df: DataFrame, btc_df: DataFrame | None, cfg: dict) -> DataFrame:
    """Add macro features. All prefixed with %-."""
    rcfg = cfg.get("regime", {})
    mom_window = rcfg.get("btc_momentum_window", 48)

    if btc_df is not None and len(btc_df) >= len(df):
        btc_close = btc_df["close"].values[-len(df):]
        btc_series = DataFrame({
            "open": btc_df["open"].values[-len(df):],
            "high": btc_df["high"].values[-len(df):],
            "low": btc_df["low"].values[-len(df):],
            "close": btc_close,
            "volume": btc_df["volume"].values[-len(df):],
        })

        # 1. BTC trend direction (EMA21 slope sign)
        btc_ema = ta.EMA(btc_series, timeperiod=21)
        btc_slope = btc_ema.pct_change(3)
        df["%-btc_trend"] = np.sign(btc_slope.fillna(0)).values

        # 2. BTC momentum (ROC)
        df["%-btc_momentum"] = ta.ROC(btc_series, timeperiod=mom_window).values

        # 3. BTC ADX
        df["%-btc_adx"] = ta.ADX(btc_series, timeperiod=14).values

        # 4. BTC dominance delta (BTC strength vs pair)
        btc_ret = np.diff(np.log(btc_close + 1e-10), prepend=0)
        pair_ret = np.diff(np.log(df["close"].values + 1e-10), prepend=0)
        dom_delta = btc_ret - pair_ret
        df["%-btc_dom_delta"] = DataFrame({"d": dom_delta})["d"].rolling(mom_window, min_periods=5).mean().values

        # 5. Market volatility index (BTC ATR normalized)
        btc_atr = ta.ATR(btc_series, timeperiod=14)
        df["%-mkt_vol_index"] = (btc_atr / (btc_series["close"] + 1e-10) * 100).values

        # 6. Alt-BTC rolling correlation
        pair_rets = df["close"].pct_change().fillna(0).values
        btc_rets = np.diff(btc_close, prepend=btc_close[0]) / (btc_close + 1e-10)
        corr_window = mom_window
        rolling_corr = np.full(len(df), 0.0)
        for i in range(corr_window, len(df)):
            c = np.corrcoef(pair_rets[i-corr_window:i], btc_rets[i-corr_window:i])[0, 1]
            rolling_corr[i] = c if not np.isnan(c) else 0.0
        df["%-alt_corr_btc"] = rolling_corr
    else:
        for col in ["%-btc_trend", "%-btc_momentum", "%-btc_adx", "%-btc_dom_delta", "%-mkt_vol_index", "%-alt_corr_btc"]:
            df[col] = 0.0

    return df
