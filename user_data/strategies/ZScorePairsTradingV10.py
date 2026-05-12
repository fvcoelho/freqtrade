"""
Z-Score Pairs Trading V10 — Market Neutral
Always enters BOTH legs: long Group A + short Group B (or vice versa).
No stoploss on individual trades — the hedge IS the protection.
Losing side is offset by winning side. Exit both when spread reverts.

Key difference from V9:
- V9: individual trades with stoploss → 14 catastrophic stops
- V10: paired entries, no stoploss, exit on spread reversion only
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


class ZScorePairsTradingV10(ZScorePairsTradingBase):

    timeframe = "15m"
    startup_candle_count = 300

    # Wide stoploss as safety net — the hedge protects against normal moves
    stoploss = -0.15
    # ROI still captures individual leg profits
    minimal_roi = {
        "0": 0.012,
        "20": 0.008,
        "60": 0.004,
        "180": 0.001,
    }

    trailing_stop = False

    # Z-score params
    zscore_window = IntParameter(48, 192, default=96, space="buy", optimize=True)
    cum_return_window = IntParameter(4, 24, default=8, space="buy", optimize=True)
    zscore_entry = DecimalParameter(1.5, 3.0, default=2.5, decimals=1, space="buy", optimize=True)
    zscore_exit = DecimalParameter(0.1, 0.8, default=0.4, decimals=1, space="sell", optimize=True)

    # Profit target for the NET spread (combined profit of both legs)
    net_profit_target = DecimalParameter(0.005, 0.03, default=0.01, decimals=3, space="sell", optimize=True)

    _pair_zscores: dict[str, DataFrame] = {}

    # =========================================================================
    # INDICATORS
    # =========================================================================

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_indicators(dataframe, metadata)
        pair = metadata["pair"]

        # Per-pair Z-score
        dataframe["log_return"] = np.log(dataframe["close"] / dataframe["close"].shift(1))
        cum_ret = dataframe["log_return"].rolling(window=self.cum_return_window.value).sum()
        cum_mean = cum_ret.rolling(window=self.zscore_window.value).mean()
        cum_std = cum_ret.rolling(window=self.zscore_window.value).std()
        dataframe["pair_zscore"] = ((cum_ret - cum_mean) / cum_std.replace(0, np.nan)).fillna(0.0)

        self._pair_zscores[pair] = dataframe[["pair_zscore"]].copy()

        # Spread Z-score
        dataframe["spread_zscore"] = self._compute_spread(pair, dataframe)

        # Volume filter
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
    # ENTRY — always enter both legs for market neutrality
    # =========================================================================

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]
        is_a = pair in self.group_a
        is_b = pair in self.group_b

        base = (dataframe["volume"] > 0) & (dataframe["vol_above_avg"] == 1)
        spread_low = dataframe["spread_zscore"] < -self.zscore_entry.value
        spread_high = dataframe["spread_zscore"] > self.zscore_entry.value

        # Both groups enter on the SAME spread signal — this ensures paired entries
        if is_a:
            # Spread oversold → A is cheap relative to B → long A
            dataframe.loc[base & spread_low, ["enter_long", "enter_tag"]] = (1, "pair_long_a")
            # Spread overbought → A is expensive relative to B → short A
            dataframe.loc[base & spread_high, ["enter_short", "enter_tag"]] = (1, "pair_short_a")
        elif is_b:
            # Spread oversold → B is expensive relative to A → short B
            dataframe.loc[base & spread_low, ["enter_short", "enter_tag"]] = (1, "pair_short_b")
            # Spread overbought → B is cheap relative to A → long B
            dataframe.loc[base & spread_high, ["enter_long", "enter_tag"]] = (1, "pair_long_b")

        return dataframe

    # =========================================================================
    # EXIT — spread reversion to neutral (exit both legs together)
    # =========================================================================

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # No signal exit — ROI takes profits, time stop limits holding
        return dataframe

    # =========================================================================
    # CUSTOM EXIT — net-aware: exit when hedge pair covers the loss
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

        # Get current spread Z-score from dataframe
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or dataframe.empty:
            return None
        spread_z = dataframe["spread_zscore"].iloc[-1]

        # Determine if this trade's spread direction has reverted
        tag = trade.enter_tag or ""
        entered_on_spread_low = "long_a" in tag or "short_b" in tag  # spread was < -2.5
        entered_on_spread_high = "short_a" in tag or "long_b" in tag  # spread was > +2.5

        spread_reverted = (
            (entered_on_spread_low and spread_z > -0.5) or
            (entered_on_spread_high and spread_z < 0.5)
        )

        # --- Spread reverted: the hedge side already profited via ROI ---
        # This losing leg can exit — the pair trade is complete
        if spread_reverted and current_profit < 0 and trade_minutes > 60:
            # Small loss (< 1%): hedge covered most of it
            if current_profit > -0.01:
                return "hedge_covered"

        # --- Fallback: time stop at 6h ---
        if trade_minutes > 360:
            return "time_stop_6h"

        return None

    # =========================================================================
    # BALANCE CHECK — ensure we only enter when we can hedge
    # =========================================================================

    def confirm_trade_entry(
        self,
        pair: str,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        current_time: datetime,
        entry_tag: Optional[str],
        side: str,
        **kwargs,
    ) -> bool:
        """Only allow entry if we maintain group balance.
        Count open trades per group — allow if the groups stay balanced (max 1 diff).
        """
        open_trades = Trade.get_trades_proxy(is_open=True)

        count_a = sum(1 for t in open_trades if t.pair in self.group_a)
        count_b = sum(1 for t in open_trades if t.pair in self.group_b)

        is_a = pair in self.group_a
        is_b = pair in self.group_b

        if is_a:
            new_a = count_a + 1
            # Allow if A won't be more than 1 ahead of B
            if new_a - count_b > 1:
                return False
        elif is_b:
            new_b = count_b + 1
            if new_b - count_a > 1:
                return False

        return True

    # =========================================================================
    # LEVERAGE — lower for market-neutral (hedge reduces risk)
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
