"""
Z-Score Pairs Trading V9 — Scalp
15m scalper on top of Base. Trades the spread Z-score between groups
with tight ROI targets. Relies on ROI for profit, spread reversion for exit.

Group A: long when spread oversold, short when overbought
Group B: opposite direction (market-neutral)
"""

import logging
from datetime import datetime
from typing import Optional

import numpy as np
from pandas import DataFrame

from freqtrade.strategy import DecimalParameter, IntParameter
from ZScorePairsTradingBase import ZScorePairsTradingBase


logger = logging.getLogger(__name__)


class ZScorePairsTradingV9(ZScorePairsTradingBase):

    timeframe = "15m"
    startup_candle_count = 300

    stoploss = -0.10   # safety net only — custom_exit handles time-based cuts
    minimal_roi = {
        "0": 0.012,   # 1.2% immediate
        "20": 0.008,  # 0.8% after 20 min
        "60": 0.004,  # 0.4% after 1h
        "180": 0.001, # 0.1% after 3h
    }
    trailing_stop = False

    # Z-score params for 15m
    zscore_window = IntParameter(48, 192, default=96, space="buy", optimize=True)  # 12h-48h
    cum_return_window = IntParameter(4, 24, default=8, space="buy", optimize=True)  # 1-6h
    zscore_entry = DecimalParameter(1.5, 3.0, default=2.5, decimals=1, space="buy", optimize=True)
    zscore_exit = DecimalParameter(0.1, 0.8, default=0.4, decimals=1, space="sell", optimize=True)

    _pair_zscores: dict[str, DataFrame] = {}
    _btc_trend: dict = {}  # cached BTC trend data

    def informative_pairs(self):
        pairs = self.dp.current_whitelist() if self.dp else []
        return [(pair, "1d") for pair in pairs] + [("BTC/USDT:USDT", "1h")]

    # =========================================================================
    # INDICATORS
    # =========================================================================

    def _compute_btc_trend(self) -> None:
        """Compute BTC 1h EMA trend and 4h momentum — cached once for all pairs."""
        if self._btc_trend or not self.dp:
            return

        btc_1h = self.dp.get_pair_dataframe(pair="BTC/USDT:USDT", timeframe="1h")
        if btc_1h is None or len(btc_1h) < 50:
            return

        ema_fast = btc_1h["close"].ewm(span=8).mean()
        ema_slow = btc_1h["close"].ewm(span=21).mean()

        # 4h momentum: % change over last 4 candles (4h on 1h data)
        mom_4h = btc_1h["close"].pct_change(4) * 100

        # ATR volatility: high ATR = choppy/dangerous market
        tr = np.maximum(
            btc_1h["high"] - btc_1h["low"],
            np.maximum(
                abs(btc_1h["high"] - btc_1h["close"].shift(1)),
                abs(btc_1h["low"] - btc_1h["close"].shift(1)),
            ),
        )
        atr = tr.rolling(14).mean()
        atr_pct = atr / btc_1h["close"] * 100
        atr_z = ((atr_pct - atr_pct.rolling(48).mean()) / atr_pct.rolling(48).std().replace(0, np.nan)).fillna(0)

        self._btc_trend = {
            "dates": btc_1h["date"].values,
            "uptrend": (ema_fast > ema_slow).values,
            "downtrend": (ema_fast < ema_slow).values,
            "pump": (mom_4h > 1.5).values,                 # BTC up >1.5% in 4h
            "dump": (mom_4h < -1.5).values,                # BTC down >1.5% in 4h
            "high_vol": (atr_z > 1.5).values,              # ATR 1.5 std above mean
        }

    def _get_btc_signal(self, dataframe: DataFrame, signal: str) -> DataFrame:
        """Map BTC 1h signal onto the 15m dataframe using forward-fill."""
        import pandas as pd
        if not self._btc_trend:
            return pd.Series(False, index=dataframe.index)

        btc_df = pd.DataFrame({
            "date": pd.to_datetime(self._btc_trend["dates"], utc=True),
            signal: self._btc_trend[signal],
        }).set_index("date")

        pair_dates = pd.to_datetime(dataframe["date"], utc=True)
        # Reindex BTC 1h signal to 15m using forward-fill
        merged = btc_df.reindex(pair_dates, method="ffill")
        return merged[signal].fillna(False).values

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_indicators(dataframe, metadata)
        pair = metadata["pair"]

        # BTC trend (computed once, cached)
        self._compute_btc_trend()
        dataframe["btc_pump"] = self._get_btc_signal(dataframe, "pump")
        dataframe["btc_dump"] = self._get_btc_signal(dataframe, "dump")
        dataframe["btc_uptrend"] = self._get_btc_signal(dataframe, "uptrend")
        dataframe["btc_downtrend"] = self._get_btc_signal(dataframe, "downtrend")
        dataframe["btc_high_vol"] = self._get_btc_signal(dataframe, "high_vol")

        # Per-pair Z-score
        dataframe["log_return"] = np.log(dataframe["close"] / dataframe["close"].shift(1))
        cum_ret = dataframe["log_return"].rolling(window=self.cum_return_window.value).sum()
        cum_mean = cum_ret.rolling(window=self.zscore_window.value).mean()
        cum_std = cum_ret.rolling(window=self.zscore_window.value).std()
        dataframe["pair_zscore"] = ((cum_ret - cum_mean) / cum_std.replace(0, np.nan)).fillna(0.0)

        self._pair_zscores[pair] = dataframe[["pair_zscore"]].copy()

        # Spread Z-score
        dataframe["spread_zscore"] = self._compute_spread(pair, dataframe)

        # Volume filter: above average
        dataframe["vol_above_avg"] = (
            dataframe["volume"] > dataframe["volume"].rolling(48).mean()
        ).astype(int)

        return dataframe

    def _compute_spread(self, pair: str, dataframe: DataFrame):
        if not self.group_a or not self.group_b or not self.dp:
            return 0.0

        group_a_z, group_b_z = [], []

        for p in self.group_a:
            z = self._get_zscore(p, pair, dataframe)
            if z is not None:
                group_a_z.append(z)
        for p in self.group_b:
            z = self._get_zscore(p, pair, dataframe)
            if z is not None:
                group_b_z.append(z)

        if not group_a_z or not group_b_z:
            return 0.0

        spread = sum(group_a_z) / len(group_a_z) - sum(group_b_z) / len(group_b_z)
        spread_mean = spread.rolling(window=self.zscore_window.value).mean()
        spread_std = spread.rolling(window=self.zscore_window.value).std()
        return ((spread - spread_mean) / spread_std.replace(0, np.nan)).fillna(0.0)

    def _get_zscore(self, target_pair: str, current_pair: str, dataframe: DataFrame):
        if target_pair == current_pair:
            return dataframe["pair_zscore"]

        if target_pair in self._pair_zscores:
            cached = self._pair_zscores[target_pair]["pair_zscore"]
            return cached.iloc[-len(dataframe):].reset_index(drop=True)

        if not self.dp:
            return None
        other_df = self.dp.get_pair_dataframe(pair=target_pair, timeframe=self.timeframe)
        if other_df is None or len(other_df) < self.zscore_window.value + self.cum_return_window.value:
            return None

        log_ret = np.log(other_df["close"] / other_df["close"].shift(1))
        cum_ret = log_ret.rolling(window=self.cum_return_window.value).sum()
        cum_mean = cum_ret.rolling(window=self.zscore_window.value).mean()
        cum_std = cum_ret.rolling(window=self.zscore_window.value).std()
        z = ((cum_ret - cum_mean) / cum_std.replace(0, np.nan)).fillna(0.0)
        return z.iloc[-len(dataframe):].reset_index(drop=True)

    # =========================================================================
    # ENTRY — scalp on deep spread deviation + volume confirmation
    # =========================================================================

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]
        is_a = pair in self.group_a
        is_b = pair in self.group_b

        base = (dataframe["volume"] > 0) & (dataframe["vol_above_avg"] == 1)
        spread_low = dataframe["spread_zscore"] < -self.zscore_entry.value
        spread_high = dataframe["spread_zscore"] > self.zscore_entry.value

        # Trend filter: block during BTC momentum or high volatility regime
        no_chaos = ~dataframe["btc_high_vol"]
        safe_long = ~dataframe["btc_dump"] & no_chaos
        safe_short = ~dataframe["btc_pump"] & no_chaos

        if is_a:
            dataframe.loc[base & spread_low & safe_long, ["enter_long", "enter_tag"]] = (1, "scalp_long_a")
            dataframe.loc[base & spread_high & safe_short, ["enter_short", "enter_tag"]] = (1, "scalp_short_a")
        elif is_b:
            dataframe.loc[base & spread_low & safe_short, ["enter_short", "enter_tag"]] = (1, "scalp_short_b")
            dataframe.loc[base & spread_high & safe_long, ["enter_long", "enter_tag"]] = (1, "scalp_long_b")

        return dataframe

    # =========================================================================
    # EXIT — spread reversion to neutral
    # =========================================================================

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Let ROI handle all exits — no signal-based exit
        return dataframe

    # =========================================================================
    # CUSTOM STOPLOSS — time-decay: wide early, tightens over time
    # =========================================================================

    def custom_exit(
        self,
        pair: str,
        trade: 'Trade',
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> Optional[str]:
        trade_minutes = (current_time - trade.open_date_utc).total_seconds() / 60

        # After 6h: force exit everything — if spread hasn't reverted by now, give up
        if trade_minutes > 360:
            return "time_stop_6h"

        return None

    # =========================================================================
    # LEVERAGE
    # =========================================================================

    def leverage(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: Optional[str],
        side: str,
        **kwargs,
    ) -> float:
        return min(2.0, max_leverage)
