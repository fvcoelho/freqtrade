"""
Z-Score Pairs Trading V13e — V13d + Improved DCA + Hyperoptable params
V13d with three improvements:
1. DCA params now hyperoptable (dca_trigger_minutes, dca_loss_threshold)
2. DCA safety: skip if already near stoploss (< -7%)
3. DCA allows entry when vol_just_ended (chaos ending = bounce opportunity)
4. Safer confirm_trade_entry with getattr fallback
"""

import logging
from datetime import datetime
from typing import Optional

import numpy as np
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import DecimalParameter, IntParameter
from ZScorePairsTradingBase import ZScorePairsTradingBase

logger = logging.getLogger(__name__)


class ZScorePairsTradingV13e(ZScorePairsTradingBase):

    timeframe = "15m"
    startup_candle_count = 300

    stoploss = -0.10
    minimal_roi = {
        "0": 0.008,
        "20": 0.005,
        "60": 0.003,
        "180": 0.001,
    }
    trailing_stop = False

    # DCA config
    position_adjustment_enable = True
    max_entry_position_adjustment = 1

    # DCA params — now hyperoptable
    dca_trigger_minutes = IntParameter(45, 90, default=60, space="buy", optimize=True)
    dca_loss_threshold = DecimalParameter(-0.025, -0.008, default=-0.015, decimals=3, space="buy", optimize=True)

    # Time stop
    time_stop_total_minutes = 300

    # Z-score params
    zscore_window = IntParameter(48, 192, default=96, space="buy", optimize=True)
    cum_return_window = IntParameter(4, 24, default=8, space="buy", optimize=True)
    zscore_entry = DecimalParameter(1.5, 3.0, default=2.5, decimals=1, space="buy", optimize=True)

    # Regime filter params
    regime_window = IntParameter(48, 192, default=96, space="buy", optimize=True)
    regime_corr_min = DecimalParameter(0.2, 0.7, default=0.4, decimals=1, space="buy", optimize=True)

    _pair_zscores: dict[str, DataFrame] = {}
    _btc_trend: dict = {}

    def informative_pairs(self):
        pairs = self.dp.current_whitelist() if self.dp else []
        return [(pair, "1d") for pair in pairs] + [("BTC/USDT:USDT", "1h")]

    # =========================================================================
    # BTC TREND
    # =========================================================================

    def _compute_btc_trend(self) -> None:
        if self._btc_trend or not self.dp:
            return
        btc_1h = self.dp.get_pair_dataframe(pair="BTC/USDT:USDT", timeframe="1h")
        if btc_1h is None or len(btc_1h) < 50:
            return
        ema_fast = btc_1h["close"].ewm(span=8).mean()
        ema_slow = btc_1h["close"].ewm(span=21).mean()
        mom_4h = btc_1h["close"].pct_change(4) * 100
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
            "pump": (mom_4h > 1.5).values,
            "dump": (mom_4h < -1.5).values,
            "high_vol": (atr_z > 2.0).values,
            "vol_just_ended": ((atr_z.shift(1) > 1.5) & (atr_z <= 1.5)).values,
        }

    def _get_btc_signal(self, dataframe: DataFrame, signal: str):
        import pandas as pd
        if not self._btc_trend:
            return pd.Series(False, index=dataframe.index)
        btc_df = pd.DataFrame({
            "date": pd.to_datetime(self._btc_trend["dates"], utc=True),
            signal: self._btc_trend[signal],
        }).set_index("date")
        pair_dates = pd.to_datetime(dataframe["date"], utc=True)
        merged = btc_df.reindex(pair_dates, method="ffill")
        return merged[signal].fillna(False).values

    # =========================================================================
    # REGIME FILTER
    # =========================================================================

    def _compute_regime(self, pair: str, dataframe: DataFrame) -> DataFrame:
        if not self.group_a or not self.group_b or not self.dp:
            dataframe["regime_ok"] = 1
            return dataframe
        pair_a = self.group_a[0]
        pair_b = self.group_b[0]
        ret_a = self._get_returns(pair_a, pair, dataframe)
        ret_b = self._get_returns(pair_b, pair, dataframe)
        if ret_a is not None and ret_b is not None:
            rolling_corr = ret_a.rolling(window=self.regime_window.value).corr(ret_b)
            dataframe["rolling_corr"] = rolling_corr.fillna(0.0)
            dataframe["regime_ok"] = (rolling_corr.abs() > self.regime_corr_min.value).astype(int).fillna(0)
        else:
            dataframe["rolling_corr"] = 0.0
            dataframe["regime_ok"] = 1
        return dataframe

    def _get_returns(self, target_pair: str, current_pair: str, dataframe: DataFrame):
        if target_pair == current_pair:
            return dataframe["log_return"]
        if not self.dp:
            return None
        other_df = self.dp.get_pair_dataframe(pair=target_pair, timeframe=self.timeframe)
        if other_df is None or len(other_df) < 50:
            return None
        ret = np.log(other_df["close"] / other_df["close"].shift(1))
        return ret.iloc[-len(dataframe):].reset_index(drop=True)

    # =========================================================================
    # INDICATORS
    # =========================================================================

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_indicators(dataframe, metadata)
        pair = metadata["pair"]
        self._compute_btc_trend()
        dataframe["btc_pump"] = self._get_btc_signal(dataframe, "pump")
        dataframe["btc_dump"] = self._get_btc_signal(dataframe, "dump")
        dataframe["btc_high_vol"] = self._get_btc_signal(dataframe, "high_vol")
        dataframe["btc_vol_ended"] = self._get_btc_signal(dataframe, "vol_just_ended")
        dataframe["log_return"] = np.log(dataframe["close"] / dataframe["close"].shift(1))
        cum_ret = dataframe["log_return"].rolling(window=self.cum_return_window.value).sum()
        cum_mean = cum_ret.rolling(window=self.zscore_window.value).mean()
        cum_std = cum_ret.rolling(window=self.zscore_window.value).std()
        dataframe["pair_zscore"] = ((cum_ret - cum_mean) / cum_std.replace(0, np.nan)).fillna(0.0)
        self._pair_zscores[pair] = dataframe[["pair_zscore"]].copy()
        dataframe["spread_zscore"] = self._compute_spread(pair, dataframe)
        dataframe = self._compute_regime(pair, dataframe)
        dataframe["vol_ok"] = (dataframe["volume"] > dataframe["volume"].rolling(48).mean()).astype(int)
        return dataframe

    # =========================================================================
    # SPREAD Z-SCORE
    # =========================================================================

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
    # ENTRY
    # =========================================================================

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]
        is_a = pair in self.group_a
        is_b = pair in self.group_b
        vol = dataframe["vol_ok"] == 1
        regime = dataframe["regime_ok"] == 1
        no_chaos = ~dataframe["btc_high_vol"]
        safe_long = ~dataframe["btc_dump"] & no_chaos
        safe_short = ~dataframe["btc_pump"] & no_chaos
        spread_low = dataframe["spread_zscore"] < -self.zscore_entry.value
        spread_high = dataframe["spread_zscore"] > self.zscore_entry.value
        vol_bounce_low = dataframe["btc_vol_ended"] & (dataframe["spread_zscore"] < -1.5)
        vol_bounce_high = dataframe["btc_vol_ended"] & (dataframe["spread_zscore"] > 1.5)
        spread_low = spread_low | vol_bounce_low
        spread_high = spread_high | vol_bounce_high
        if is_a:
            dataframe.loc[vol & regime & spread_low & safe_long, ["enter_long", "enter_tag"]] = (1, "v13e_long_a")
            dataframe.loc[vol & regime & spread_high & safe_short, ["enter_short", "enter_tag"]] = (1, "v13e_short_a")
        elif is_b:
            dataframe.loc[vol & regime & spread_low & safe_short, ["enter_short", "enter_tag"]] = (1, "v13e_short_b")
            dataframe.loc[vol & regime & spread_high & safe_long, ["enter_long", "enter_tag"]] = (1, "v13e_long_b")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    # =========================================================================
    # EXIT
    # =========================================================================

    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        trade_minutes = (current_time - trade.open_date_utc).total_seconds() / 60
        if trade_minutes > self.time_stop_total_minutes:
            return "time_stop_5h"
        return None

    # =========================================================================
    # DCA — improved from V13d
    # =========================================================================

    def adjust_trade_position(
        self,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        min_stake: Optional[float],
        max_stake: float,
        current_entry_rate: float,
        current_exit_rate: float,
        current_entry_profit: float,
        current_exit_profit: float,
        **kwargs,
    ) -> Optional[float]:
        """
        Improved DCA over V13d:
        1. Hyperoptable trigger time and loss threshold
        2. Skip DCA if already near stoploss (< -7%) — don't throw money at a wreck
        3. Allow DCA when vol_just_ended — chaos is ending, bounce is likely
        """
        if trade.nr_of_successful_entries >= 2:
            return None

        trade_minutes = (current_time - trade.open_date_utc).total_seconds() / 60
        if trade_minutes < self.dca_trigger_minutes.value:
            return None

        if current_profit > self.dca_loss_threshold.value:
            return None

        # NEW: don't DCA if already deep in loss (near stoploss territory)
        if current_profit < -0.07:
            return None

        dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
        if dataframe is None or dataframe.empty:
            return None

        last = dataframe.iloc[-1]

        # Improved BTC chaos guard: block during chaos UNLESS vol just ended
        in_chaos = last.get("btc_pump", False) or last.get("btc_dump", False) or last.get("btc_high_vol", False)
        vol_just_ended = last.get("btc_vol_ended", False)

        if in_chaos and not vol_just_ended:
            return None

        # Equal stake DCA using trade's current stake
        dca_stake = trade.stake_amount
        if min_stake and dca_stake < min_stake:
            dca_stake = min_stake

        return min(dca_stake, max_stake)

    # =========================================================================
    # BALANCE CHECK — with getattr safety
    # =========================================================================

    def confirm_trade_entry(self, pair, order_type, amount, rate, time_in_force,
                            current_time, entry_tag, side, **kwargs):
        open_trades = Trade.get_trades_proxy(is_open=True)
        group_a = getattr(self, "group_a", [])
        group_b = getattr(self, "group_b", [])
        count_a = sum(1 for t in open_trades if t.pair in group_a)
        count_b = sum(1 for t in open_trades if t.pair in group_b)
        if pair in group_a and count_a + 1 - count_b > 1:
            return False
        if pair in group_b and count_b + 1 - count_a > 1:
            return False
        return True

    # =========================================================================
    # LEVERAGE
    # =========================================================================

    def leverage(self, pair, current_time, current_rate, proposed_leverage,
                 max_leverage, entry_tag, side, **kwargs):
        return min(2.0, max_leverage)
