"""Macro features: BTC trend, momentum, dominance, alt correlation."""
from __future__ import annotations

import numpy as np
import talib.abstract as ta
from pandas import DataFrame


def compute(df: DataFrame, btc_df: DataFrame | None, cfg: dict) -> DataFrame:
    """Add macro features. All prefixed with %-."""
    rcfg = cfg.get("regime", {})
    mom_window = rcfg.get("btc_momentum_window", 48)

    if btc_df is not None and len(btc_df) >= 50:
        n = min(len(btc_df), len(df))
        btc_close = btc_df["close"].values[-n:]
        btc_series = DataFrame({
            "open": btc_df["open"].values[-n:],
            "high": btc_df["high"].values[-n:],
            "low": btc_df["low"].values[-n:],
            "close": btc_close,
            "volume": btc_df["volume"].values[-n:],
        })

        # Helper: pad array to len(df) with zeros at front
        def _pad(arr):
            if len(arr) < len(df):
                return np.concatenate([np.zeros(len(df) - len(arr)), arr])
            return arr

        # 1. BTC trend direction (EMA21 slope sign)
        btc_ema = ta.EMA(btc_series, timeperiod=21)
        btc_slope = btc_ema.pct_change(3)
        df["%-btc_trend"] = _pad(np.sign(btc_slope.fillna(0)).values)

        # 2. BTC momentum (ROC)
        df["%-btc_momentum"] = _pad(ta.ROC(btc_series, timeperiod=mom_window).fillna(0).values)

        # 3. BTC ADX
        df["%-btc_adx"] = _pad(ta.ADX(btc_series, timeperiod=14).fillna(0).values)

        # 4. BTC dominance delta (BTC strength vs pair)
        btc_ret = np.diff(np.log(btc_close + 1e-10), prepend=0)
        pair_close = df["close"].values[-n:]
        pair_ret = np.diff(np.log(pair_close + 1e-10), prepend=0)
        dom_delta = btc_ret - pair_ret
        dom_roll = DataFrame({"d": dom_delta})["d"].rolling(mom_window, min_periods=5).mean().fillna(0).values
        df["%-btc_dom_delta"] = _pad(dom_roll)

        # 5. Market volatility index (BTC ATR normalized)
        btc_atr = ta.ATR(btc_series, timeperiod=14)
        mvi = (btc_atr / (btc_series["close"] + 1e-10) * 100).fillna(0).values
        df["%-mkt_vol_index"] = _pad(mvi)

        # 6. Alt-BTC rolling correlation
        pair_rets = df["close"].pct_change().fillna(0).values
        btc_rets_full = np.zeros(len(df))
        btc_r = np.diff(btc_close, prepend=btc_close[0]) / (btc_close + 1e-10)
        btc_rets_full[-n:] = btc_r
        corr_window = mom_window
        rolling_corr = np.full(len(df), 0.0)
        for i in range(corr_window, len(df)):
            c = np.corrcoef(pair_rets[i-corr_window:i], btc_rets_full[i-corr_window:i])[0, 1]
            rolling_corr[i] = c if not np.isnan(c) else 0.0
        df["%-alt_corr_btc"] = rolling_corr
    else:
        for col in ["%-btc_trend", "%-btc_momentum", "%-btc_adx", "%-btc_dom_delta", "%-mkt_vol_index", "%-alt_corr_btc"]:
            df[col] = 0.0

    return df
