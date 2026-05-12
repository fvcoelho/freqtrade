"""
Z-Score DCA Hedge Strategy
Combines DCAMeanReversion entries with ZScorePairsTradingBase groups.

Entry: RSI + Bollinger Band mean reversion (from DCA strategy)
Hedge: when a trade is losing, open opposite position on the other group
Exit: ROI scalp + spread-aware hedge exit + time stop

Group A losing long → open Group B short to hedge
Group B losing short → open Group A long to hedge
"""

import logging
from datetime import datetime
from typing import Optional

import numpy as np
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import DecimalParameter, IntParameter
from ZScorePairsTradingBase import ZScorePairsTradingBase


logger = logging.getLogger(__name__)


class ZScoreDCAHedge(ZScorePairsTradingBase):

    timeframe = "15m"
    startup_candle_count = 200

    # DCA disabled — hedge handles losing trades instead
    position_adjustment_enable = False

    # ROI scalp targets
    minimal_roi = {
        "0": 0.012,
        "20": 0.008,
        "60": 0.004,
        "180": 0.002,
    }

    stoploss = -0.10  # safety net
    trailing_stop = False

    # DCA levels: add at 1.5% and 3% drawdown
    dca_levels = [0.015, 0.03]

    initial_stake_pct = 1.0
    stake_per_position: float = 166.67

    # RSI params
    rsi_long = IntParameter(25, 40, default=35, space="buy", optimize=True)
    rsi_short = IntParameter(60, 75, default=65, space="buy", optimize=True)

    _pair_zscores: dict[str, DataFrame] = {}

    # =========================================================================
    # INDICATORS — DCA mean reversion + spread Z-score
    # =========================================================================

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_indicators(dataframe, metadata)
        pair = metadata["pair"]

        # DCA mean reversion indicators
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        bb = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe["bb_upper"] = bb["upperband"]
        dataframe["bb_lower"] = bb["lowerband"]

        # Spread Z-score for hedge awareness
        dataframe["log_return"] = np.log(dataframe["close"] / dataframe["close"].shift(1))
        cum_ret = dataframe["log_return"].rolling(window=8).sum()
        cum_mean = cum_ret.rolling(window=96).mean()
        cum_std = cum_ret.rolling(window=96).std()
        dataframe["pair_zscore"] = ((cum_ret - cum_mean) / cum_std.replace(0, np.nan)).fillna(0.0)

        self._pair_zscores[pair] = dataframe[["pair_zscore"]].copy()
        dataframe["spread_zscore"] = self._compute_spread(pair, dataframe)

        # Volume filter
        dataframe["vol_ok"] = (dataframe["volume"] > dataframe["volume"].rolling(48).mean()).astype(int)

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
        spread_mean = spread.rolling(window=96).mean()
        spread_std = spread.rolling(window=96).std()
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
        if other_df is None or len(other_df) < 104:
            return None
        log_ret = np.log(other_df["close"] / other_df["close"].shift(1))
        cum_ret = log_ret.rolling(window=8).sum()
        cum_mean = cum_ret.rolling(window=96).mean()
        cum_std = cum_ret.rolling(window=96).std()
        z = ((cum_ret - cum_mean) / cum_std.replace(0, np.nan)).fillna(0.0)
        return z.iloc[-len(dataframe):].reset_index(drop=True)

    # =========================================================================
    # ENTRY — DCA mean reversion signals, group-aware
    # =========================================================================

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]
        is_a = pair in self.group_a
        is_b = pair in self.group_b

        vol = dataframe["vol_ok"] == 1

        # Mean reversion: RSI oversold + near lower BB
        oversold = (
            (dataframe["rsi"] < self.rsi_long.value)
            | (dataframe["close"] < dataframe["bb_lower"] * 1.005)
        )
        # Mean reversion: RSI overbought + near upper BB
        overbought = (
            (dataframe["rsi"] > self.rsi_short.value)
            | (dataframe["close"] > dataframe["bb_upper"] * 0.995)
        )

        # Spread confirmation: mild — just needs to lean the right way
        spread_low = dataframe["spread_zscore"] < -0.5
        spread_high = dataframe["spread_zscore"] > 0.5

        if is_a:
            # Long A: oversold + spread says A is cheap
            dataframe.loc[vol & oversold & spread_low, ["enter_long", "enter_tag"]] = (1, "dca_long_a")
            # Short A: overbought + spread says A is expensive
            dataframe.loc[vol & overbought & spread_high, ["enter_short", "enter_tag"]] = (1, "dca_short_a")
        elif is_b:
            # Short B: overbought + spread says A is cheap (B expensive)
            dataframe.loc[vol & overbought & spread_low, ["enter_short", "enter_tag"]] = (1, "dca_short_b")
            # Long B: oversold + spread says A is expensive (B cheap)
            dataframe.loc[vol & oversold & spread_high, ["enter_long", "enter_tag"]] = (1, "dca_long_b")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ROI handles exits
        return dataframe

    # =========================================================================
    # STAKE — initial entry is 50%, DCA fills the rest
    # =========================================================================

    def custom_stake_amount(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_stake: float,
        min_stake: Optional[float],
        max_stake: float,
        leverage: float,
        entry_tag: Optional[str],
        side: str,
        **kwargs,
    ) -> float:
        stake = self.stake_per_position * self.initial_stake_pct
        return min(stake, max_stake)

    # =========================================================================
    # DCA + HEDGE — losing trade? DCA into it, AND open hedge on other group
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
        DCA: add to losing position at defined levels.
        The hedge on the other group happens naturally via entry signals —
        when this pair drops, the other group's pair rises and triggers
        an opposite entry signal.
        """
        if trade.nr_of_successful_entries >= len(self.dca_levels) + 1:
            return None

        dca_idx = trade.nr_of_successful_entries - 1
        if dca_idx >= len(self.dca_levels):
            return None

        required_drop = self.dca_levels[dca_idx]

        if current_profit > -required_drop:
            return None  # not dropped enough

        # DCA stake: same as initial
        dca_stake = trade.stake_amount / trade.nr_of_successful_entries
        if min_stake and dca_stake < min_stake:
            dca_stake = min_stake

        logger.info(
            f"DCA #{dca_idx + 1} on {trade.pair}: profit={current_profit:.2%}, "
            f"adding {dca_stake:.2f} USDT"
        )
        return min(dca_stake, max_stake)

    # =========================================================================
    # CUSTOM EXIT — spread-aware + time stop
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

        # Check if spread has reverted (hedge completed)
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is not None and not dataframe.empty:
            spread_z = dataframe["spread_zscore"].iloc[-1]
            tag = trade.enter_tag or ""

            entered_long = "long" in tag
            entered_short = "short" in tag

            # Spread reverted + small loss → hedge covered it
            spread_neutral = abs(spread_z) < 0.5
            if spread_neutral and current_profit < 0 and current_profit > -0.01 and trade_minutes > 60:
                return "hedge_covered"

        # Time stop: 6h
        if trade_minutes > 360:
            return "time_stop_6h"

        return None

    # =========================================================================
    # BALANCE — keep groups in sync for market neutrality
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
        open_trades = Trade.get_trades_proxy(is_open=True)

        count_a = sum(1 for t in open_trades if t.pair in self.group_a)
        count_b = sum(1 for t in open_trades if t.pair in self.group_b)

        is_a = pair in self.group_a
        is_b = pair in self.group_b

        # Keep groups balanced: max 1 position difference
        if is_a and count_a + 1 - count_b > 1:
            return False
        if is_b and count_b + 1 - count_a > 1:
            return False

        return True

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
