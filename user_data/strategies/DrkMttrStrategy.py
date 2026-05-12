"""
DrkMttr Strategy — Inspired by Hyperliquid vault 0xc179e...
Hybrid approach: conviction longs on altcoins + BTC short hedge.

Key patterns from the vault:
- Long altcoins with 3-4x leverage, hold for days
- Exit via limit orders 10-30% above entry (patient)
- BTC short as portfolio hedge
- DCA on dips
- 89% win rate over last month on $5.6M AUM

Adapted for Freqtrade backtest:
- 1h timeframe (longer holds than our 15m scalper)
- EMA crossover + RSI for trend entry
- BTC trend alignment filter
- Wide ROI targets (3-8% vs our 1.2%)
- BTC hedge via short entries when portfolio is long
"""

import logging
from datetime import datetime
from typing import Optional

import numpy as np
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy


logger = logging.getLogger(__name__)


class DrkMttrStrategy(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = "1h"
    can_short = True
    startup_candle_count = 100

    stoploss = -0.08
    minimal_roi = {
        "0": 0.08,       # 8% immediate exit
        "24": 0.05,      # 5% after 1 day
        "72": 0.03,      # 3% after 3 days
        "168": 0.01,     # 1% after 1 week
    }
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = True

    # DCA
    position_adjustment_enable = True
    max_entry_position_adjustment = 2  # 2 DCA adds

    max_open_trades = 6

    process_only_new_candles = True

    def informative_pairs(self):
        return [("BTC/USDT:USDT", "1h"), ("BTC/USDT:USDT", "1d")]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]

        # EMAs for trend
        dataframe["ema_8"] = dataframe["close"].ewm(span=8).mean()
        dataframe["ema_21"] = dataframe["close"].ewm(span=21).mean()
        dataframe["ema_55"] = dataframe["close"].ewm(span=55).mean()

        # RSI
        delta = dataframe["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        dataframe["rsi"] = 100 - (100 / (1 + rs))

        # Volume trend
        dataframe["vol_sma"] = dataframe["volume"].rolling(24).mean()
        dataframe["vol_ratio"] = dataframe["volume"] / dataframe["vol_sma"].replace(0, np.nan)

        # Momentum (24h return)
        dataframe["mom_24h"] = dataframe["close"].pct_change(24) * 100

        # ATR for volatility
        tr = np.maximum(
            dataframe["high"] - dataframe["low"],
            np.maximum(
                abs(dataframe["high"] - dataframe["close"].shift(1)),
                abs(dataframe["low"] - dataframe["close"].shift(1)),
            ),
        )
        dataframe["atr"] = tr.rolling(14).mean()
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"] * 100

        # BTC trend (for hedge and alignment)
        if self.dp:
            btc_1h = self.dp.get_pair_dataframe(pair="BTC/USDT:USDT", timeframe="1h")
            if btc_1h is not None and len(btc_1h) > 50:
                btc_ema_fast = btc_1h["close"].ewm(span=8).mean()
                btc_ema_slow = btc_1h["close"].ewm(span=21).mean()
                btc_mom = btc_1h["close"].pct_change(24) * 100

                import pandas as pd
                btc_df = pd.DataFrame({
                    "date": pd.to_datetime(btc_1h["date"], utc=True),
                    "btc_trend_up": (btc_ema_fast > btc_ema_slow).astype(int),
                    "btc_mom": btc_mom.fillna(0),
                }).set_index("date")

                pair_dates = pd.to_datetime(dataframe["date"], utc=True)
                merged = btc_df.reindex(pair_dates, method="ffill")
                dataframe["btc_trend_up"] = merged["btc_trend_up"].fillna(0).values
                dataframe["btc_mom"] = merged["btc_mom"].fillna(0).values
            else:
                dataframe["btc_trend_up"] = 1
                dataframe["btc_mom"] = 0
        else:
            dataframe["btc_trend_up"] = 1
            dataframe["btc_mom"] = 0

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]
        is_btc = "BTC" in pair

        if is_btc:
            # BTC: SHORT when momentum turns negative (hedge)
            dataframe.loc[
                (dataframe["ema_8"] < dataframe["ema_21"])
                & (dataframe["rsi"] < 45)
                & (dataframe["mom_24h"] < -2),
                ["enter_short", "enter_tag"],
            ] = (1, "btc_hedge")
        else:
            # Altcoins: LONG on trend + momentum + volume confirmation
            dataframe.loc[
                (dataframe["ema_8"] > dataframe["ema_21"])
                & (dataframe["ema_21"] > dataframe["ema_55"])
                & (dataframe["rsi"] > 50)
                & (dataframe["rsi"] < 75)
                & (dataframe["vol_ratio"] > 0.8)
                & (dataframe["mom_24h"] > 1)
                & (dataframe["btc_trend_up"] == 1),
                ["enter_long", "enter_tag"],
            ] = (1, "conviction_long")

            # Also SHORT altcoins when trend is clearly down (not just hedge)
            dataframe.loc[
                (dataframe["ema_8"] < dataframe["ema_21"])
                & (dataframe["ema_21"] < dataframe["ema_55"])
                & (dataframe["rsi"] < 40)
                & (dataframe["mom_24h"] < -3)
                & (dataframe["btc_trend_up"] == 0),
                ["enter_short", "enter_tag"],
            ] = (1, "trend_short")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def custom_exit(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> Optional[str]:
        trade_hours = (current_time - trade.open_date_utc).total_seconds() / 3600

        # Exit conviction longs if trend reverses after 24h+
        if not trade.is_short and trade_hours > 24:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if dataframe is not None and not dataframe.empty:
                last = dataframe.iloc[-1]
                # EMA death cross — trend over
                if last["ema_8"] < last["ema_21"] and current_profit > 0:
                    return "trend_reversal_exit"

        # Exit BTC hedge if BTC turns bullish
        if trade.is_short and "BTC" in pair:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if dataframe is not None and not dataframe.empty:
                last = dataframe.iloc[-1]
                if last["ema_8"] > last["ema_21"] and last["mom_24h"] > 2:
                    return "hedge_close"

        # Time stop: exit anything not profitable after 2 weeks
        if trade_hours > 336 and current_profit < 0:
            return "time_stop_2w"

        return None

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
        """DCA: add on dips for conviction longs."""
        if trade.is_short:
            return None  # no DCA on shorts

        if trade.nr_of_successful_entries >= 3:
            return None  # max 2 DCA adds

        trade_hours = (current_time - trade.open_date_utc).total_seconds() / 3600

        # DCA after 12h if down > 3%
        if trade_hours > 12 and current_profit < -0.03:
            stake = trade.stake_amount * 0.5  # half-size DCA
            if min_stake and stake < min_stake:
                stake = min_stake
            return min(stake, max_stake)

        return None

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
        # BTC hedge: 4x
        if "BTC" in pair:
            return min(4.0, max_leverage)
        # Altcoin conviction: 3x
        return min(3.0, max_leverage)
