"""
DCA Mean-Reversion Scalper Strategy
Reverse-engineered from Hyperliquid trader 0x61ceef21...

Core logic:
- Enter long on RSI oversold, short on RSI overbought
- DCA into positions at defined price drops (up to 4 additional entries)
- Take profit at ~1% from average entry
- EMA trend filter: only long above EMA50, short below
- Designed for 5m timeframe on BTC, ETH, SOL futures
"""

from datetime import datetime
from typing import Optional

import talib.abstract as ta
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, stoploss_from_open


class DCAMeanReversion(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "5m"
    can_short = True

    # Allow up to 4 additional DCA entries per trade
    position_adjustment_enable = True
    max_entry_position_adjustment = 4

    # Exit at small profit quickly (matches ~30min median hold)
    minimal_roi = {
        "0": 0.01,      # 1% immediate target
        "30": 0.008,     # 0.8% after 30min
        "60": 0.005,     # 0.5% after 1h
        "120": 0.003,    # 0.3% after 2h
    }

    stoploss = -0.05  # -5% wide stop (DCA reduces avg cost)

    # Trailing stop: lock in gains after 0.8% profit
    trailing_stop = True
    trailing_stop_positive = 0.005     # 0.5% trailing
    trailing_stop_positive_offset = 0.008  # activate after 0.8%
    trailing_only_offset_is_reached = True

    # Need 50 candles for EMA50
    startup_candle_count = 55

    # Strategy parameters
    rsi_period = 14
    rsi_long_entry = 30
    rsi_short_entry = 70
    ema_trend_period = 50

    # DCA settings: price drop % triggers for each additional entry
    dca_levels = [0.01, 0.02, 0.03, 0.04]  # 1%, 2%, 3%, 4% drops

    # Initial entry uses 20% of stake, DCA fills the rest
    initial_stake_pct = 0.2

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.rsi_period)
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=self.ema_trend_period)
        dataframe["ema20"] = ta.EMA(dataframe, timeperiod=20)

        # Bollinger Bands for additional mean-reversion confirmation
        bb = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe["bb_upper"] = bb["upperband"]
        dataframe["bb_lower"] = bb["lowerband"]
        dataframe["bb_mid"] = bb["middleband"]

        # ATR for volatility awareness
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Long: RSI oversold OR price near lower BB in uptrend
        dataframe.loc[
            (
                (dataframe["rsi"] < 35)  # RSI oversold
                | (dataframe["close"] < dataframe["bb_lower"] * 1.005)  # near lower BB
            )
            & (dataframe["close"] > dataframe["ema50"])  # uptrend filter
            & (dataframe["volume"] > 0),
            "enter_long",
        ] = 1

        # Short: RSI overbought OR price near upper BB in downtrend
        dataframe.loc[
            (
                (dataframe["rsi"] > 65)  # RSI overbought
                | (dataframe["close"] > dataframe["bb_upper"] * 0.995)  # near upper BB
            )
            & (dataframe["close"] < dataframe["ema50"])  # downtrend filter
            & (dataframe["volume"] > 0),
            "enter_short",
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Long exit: RSI overbought or price hits upper BB
        dataframe.loc[
            (dataframe["rsi"] > 70) & (dataframe["close"] > dataframe["bb_upper"]),
            "exit_long",
        ] = 1

        # Short exit: RSI oversold or price hits lower BB
        dataframe.loc[
            (dataframe["rsi"] < 30) & (dataframe["close"] < dataframe["bb_lower"]),
            "exit_short",
        ] = 1

        return dataframe

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
        # Initial entry: only use 20% of the full stake
        # DCA entries will add the remaining 80%
        return proposed_stake * self.initial_stake_pct

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
        DCA: add to the position when price drops by defined levels.
        Each DCA entry uses the same size as the initial entry.
        """
        if trade.nr_of_successful_entries >= len(self.dca_levels) + 1:
            return None  # max DCA entries reached

        # Get the DCA level for this entry
        dca_idx = trade.nr_of_successful_entries - 1  # 0-indexed
        if dca_idx >= len(self.dca_levels):
            return None

        required_drop = self.dca_levels[dca_idx]

        # For longs: price must drop by required_drop from entry
        # For shorts: price must rise by required_drop from entry
        if not trade.is_short:
            if current_profit > -required_drop:
                return None  # not dropped enough yet
        else:
            if current_profit > -required_drop:
                return None  # not risen enough yet

        # Add the same stake as the initial entry
        dca_stake = trade.stake_amount / trade.nr_of_successful_entries
        if min_stake is not None and dca_stake < min_stake:
            dca_stake = min_stake

        return dca_stake

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
        # Conservative leverage: 3x for BTC/ETH, 2x for SOL
        if "BTC" in pair or "ETH" in pair:
            return min(3.0, max_leverage)
        return min(2.0, max_leverage)
