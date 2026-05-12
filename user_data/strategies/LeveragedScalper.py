"""
Leveraged Scalper Strategy
Fast mean-reversion scalping with leverage on high-probability setups.

Lessons from previous strategies:
- DCAMeanReversion: 77% win rate on 17 days but trailing stops killed it over 3 months
- ZScorePairsTrading: market-neutral hedging works but spread reversion is too slow
- Key insight: take small profits FAST, cut losses FASTER, use leverage on best setups

Core logic:
- 5m timeframe, BTC/ETH/SOL futures
- Enter on RSI extremes + Bollinger Band touch + volume spike
- 3x-5x leverage (hedged by tight stops)
- Take profit at 0.3-0.5% (leveraged = 0.9-2.5% actual)
- Stop loss at 0.5% (leveraged = 1.5-2.5% actual)
- No trailing stop (learned from DCA backtest — they destroy scalpers)
- No DCA (keeps it simple, no amplifying losses)
- Both long and short (captures moves in both directions)
"""

import logging
from datetime import datetime
from typing import Optional

import numpy as np
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter


logger = logging.getLogger(__name__)


class LeveragedScalper(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "5m"
    can_short = True

    max_open_trades = 3

    stoploss = -0.025  # 2.5% hard stop

    minimal_roi = {
        "0": 0.03,    # 3% target (at 3x = 1% move)
        "30": 0.02,   # 2% after 30 min
        "60": 0.015,  # 1.5% after 1h
        "120": 0.008, # 0.8% after 2h — must cover fees
    }

    startup_candle_count = 50

    trailing_stop = False  # NEVER — learned from DCA backtest
    process_only_new_candles = True

    # Hyperoptable parameters — tighter filters for fewer, better trades
    rsi_buy = IntParameter(10, 28, default=20, space="buy", optimize=True)
    rsi_sell = IntParameter(72, 90, default=80, space="sell", optimize=True)
    bb_squeeze = DecimalParameter(0.5, 2.0, default=1.0, decimals=1, space="buy", optimize=True)
    vol_multiplier = DecimalParameter(1.5, 4.0, default=2.0, decimals=1, space="buy", optimize=True)
    ema_fast = IntParameter(5, 15, default=8, space="buy", optimize=True)
    ema_slow = IntParameter(15, 40, default=21, space="buy", optimize=True)

    # Leverage tiers
    leverage_normal = DecimalParameter(2.0, 5.0, default=3.0, decimals=1, space="buy", optimize=True)
    leverage_strong = DecimalParameter(4.0, 8.0, default=5.0, decimals=1, space="buy", optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # RSI
        dataframe["rsi"] = self._rsi(dataframe["close"], 14)

        # Bollinger Bands (20, 2)
        dataframe["bb_mid"] = dataframe["close"].rolling(window=20).mean()
        bb_std = dataframe["close"].rolling(window=20).std()
        dataframe["bb_upper"] = dataframe["bb_mid"] + 2.0 * bb_std
        dataframe["bb_lower"] = dataframe["bb_mid"] - 2.0 * bb_std
        # BB width for squeeze detection
        dataframe["bb_width"] = (dataframe["bb_upper"] - dataframe["bb_lower"]) / dataframe["bb_mid"] * 100

        # EMAs for micro-trend
        dataframe["ema_fast"] = dataframe["close"].ewm(span=self.ema_fast.value, adjust=False).mean()
        dataframe["ema_slow"] = dataframe["close"].ewm(span=self.ema_slow.value, adjust=False).mean()

        # Volume: ratio to rolling average
        dataframe["vol_sma"] = dataframe["volume"].rolling(window=20).mean()
        dataframe["vol_ratio"] = dataframe["volume"] / dataframe["vol_sma"].replace(0, np.nan)
        dataframe["vol_ratio"] = dataframe["vol_ratio"].fillna(1.0)

        # VWAP (volume-weighted average price) — intraday anchor
        typical_price = (dataframe["high"] + dataframe["low"] + dataframe["close"]) / 3
        dataframe["vwap"] = (typical_price * dataframe["volume"]).rolling(window=48).sum() / \
                            dataframe["volume"].rolling(window=48).sum().replace(0, np.nan)
        dataframe["vwap"] = dataframe["vwap"].fillna(dataframe["close"])

        # Price distance from VWAP (mean reversion signal)
        dataframe["vwap_dist"] = (dataframe["close"] - dataframe["vwap"]) / dataframe["vwap"] * 100

        # Momentum: rate of change
        dataframe["roc"] = dataframe["close"].pct_change(periods=6) * 100  # 30min ROC

        # Signal strength (used for leverage decision)
        dataframe["signal_strength"] = 0.0

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        rsi_buy = self.rsi_buy.value
        rsi_sell = self.rsi_sell.value
        vol_min = self.vol_multiplier.value

        # Trend filter: EMA200 determines bias
        # Only long ABOVE ema200, only short BELOW ema200
        ema200 = dataframe["close"].ewm(span=200, adjust=False).mean()
        uptrend = dataframe["close"] > ema200
        downtrend = dataframe["close"] < ema200

        # =====================================================================
        # LONG entries: ONLY in uptrend + oversold bounce
        # =====================================================================

        long_strong = (
            uptrend
            & (dataframe["rsi"] < rsi_buy)
            & (dataframe["close"] < dataframe["bb_lower"])
            & (dataframe["vol_ratio"] > vol_min)
            & (dataframe["vwap_dist"] < -0.2)
            & (dataframe["volume"] > 0)
        )

        long_standard = (
            uptrend
            & (dataframe["rsi"] < rsi_buy + 5)
            & (dataframe["close"] < dataframe["bb_lower"] * 1.002)
            & (dataframe["vol_ratio"] > vol_min * 0.7)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[long_standard, ["enter_long", "enter_tag"]] = (1, "scalp_long")
        dataframe.loc[long_strong, ["enter_long", "enter_tag"]] = (1, "scalp_long_strong")

        # =====================================================================
        # SHORT entries: ONLY in downtrend + overbought rejection
        # =====================================================================

        short_strong = (
            downtrend
            & (dataframe["rsi"] > rsi_sell)
            & (dataframe["close"] > dataframe["bb_upper"])
            & (dataframe["vol_ratio"] > vol_min)
            & (dataframe["vwap_dist"] > 0.2)
            & (dataframe["volume"] > 0)
        )

        short_standard = (
            downtrend
            & (dataframe["rsi"] > rsi_sell - 5)
            & (dataframe["close"] > dataframe["bb_upper"] * 0.998)
            & (dataframe["vol_ratio"] > vol_min * 0.7)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[short_standard, ["enter_short", "enter_tag"]] = (1, "scalp_short")
        dataframe.loc[short_strong, ["enter_short", "enter_tag"]] = (1, "scalp_short_strong")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Long exit: RSI overbought or hit upper BB
        dataframe.loc[
            (dataframe["rsi"] > 70) | (dataframe["close"] > dataframe["bb_upper"] * 0.998),
            "exit_long",
        ] = 1

        # Short exit: RSI oversold or hit lower BB
        dataframe.loc[
            (dataframe["rsi"] < 30) | (dataframe["close"] < dataframe["bb_lower"] * 1.002),
            "exit_short",
        ] = 1

        return dataframe

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
        """Dynamic leverage based on signal strength.

        Strong signals (deep RSI + volume spike) get higher leverage.
        Standard signals get normal leverage.
        """
        if entry_tag and "strong" in entry_tag:
            lev = self.leverage_strong.value
        else:
            lev = self.leverage_normal.value

        return min(lev, max_leverage)

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
        """Equal split across max positions: $1000 / 3 = $333 per trade."""
        stake = proposed_stake / self.max_open_trades if proposed_stake else 333.0
        return min(stake, max_stake)

    @staticmethod
    def _rsi(series, period=14):
        delta = series.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        return (100.0 - (100.0 / (1.0 + rs))).fillna(50.0)
