"""
Kelly Criterion DCA Mean-Reversion Strategy

Uses Kelly Criterion to dynamically size positions based on historical
win rate and risk/reward ratio. Adjusts stake as performance data accumulates.

Kelly formula: f* = W - (1 - W) / R
  f* = optimal fraction of capital to risk
  W  = win rate (probability of winning)
  R  = win/loss ratio (avg win / avg loss)

We use Half-Kelly (f*/2) for safety — full Kelly is too aggressive
and assumes perfect parameter knowledge.
"""

import logging
from datetime import datetime
from typing import Optional

import talib.abstract as ta
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy

logger = logging.getLogger(__name__)


class KellyDCAMeanReversion(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "5m"
    can_short = True

    position_adjustment_enable = True
    max_entry_position_adjustment = 4

    # Optimized parameters from hyperopt
    minimal_roi = {
        "0": 0.159,
        "20": 0.078,
        "59": 0.03,
        "75": 0,
    }

    stoploss = -0.229

    trailing_stop = True
    trailing_stop_positive = 0.091
    trailing_stop_positive_offset = 0.126
    trailing_only_offset_is_reached = False

    startup_candle_count = 55

    # --- Kelly Criterion parameters ---
    kelly_fraction = 0.5        # Half-Kelly for safety (0.5 = half, 1.0 = full)
    min_trades_for_kelly = 20   # Minimum closed trades before using Kelly
    kelly_lookback = 100        # How many recent trades to consider
    min_stake_pct = 0.02        # Minimum 2% of wallet per trade
    max_stake_pct = 0.15        # Maximum 15% of wallet per trade
    default_stake_pct = 0.05    # Default 5% before enough data

    # DCA settings
    dca_levels = [0.01, 0.02, 0.03, 0.04]
    initial_stake_pct = 0.2     # 20% of calculated stake for first entry

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema20"] = ta.EMA(dataframe, timeperiod=20)

        bb = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe["bb_upper"] = bb["upperband"]
        dataframe["bb_lower"] = bb["lowerband"]
        dataframe["bb_mid"] = bb["middleband"]

        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Long: RSI oversold or near lower BB in uptrend
        dataframe.loc[
            (
                (dataframe["rsi"] < 35)
                | (dataframe["close"] < dataframe["bb_lower"] * 1.005)
            )
            & (dataframe["close"] > dataframe["ema50"])
            & (dataframe["volume"] > 0),
            "enter_long",
        ] = 1

        # Short: RSI overbought or near upper BB in downtrend
        dataframe.loc[
            (
                (dataframe["rsi"] > 65)
                | (dataframe["close"] > dataframe["bb_upper"] * 0.995)
            )
            & (dataframe["close"] < dataframe["ema50"])
            & (dataframe["volume"] > 0),
            "enter_short",
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["rsi"] > 70) & (dataframe["close"] > dataframe["bb_upper"]),
            "exit_long",
        ] = 1

        dataframe.loc[
            (dataframe["rsi"] < 30) & (dataframe["close"] < dataframe["bb_lower"]),
            "exit_short",
        ] = 1

        return dataframe

    def _calculate_kelly(self) -> dict:
        """
        Calculate Kelly Criterion from closed trade history.

        Returns dict with kelly stats:
          - kelly_pct: recommended stake as fraction of wallet
          - win_rate, avg_win, avg_loss, profit_factor
          - trades_used: number of trades in calculation
        """
        closed_trades = Trade.get_trades_proxy(is_open=False)

        # Use only the most recent N trades
        recent = closed_trades[-self.kelly_lookback:]

        if len(recent) < self.min_trades_for_kelly:
            return {
                "kelly_pct": self.default_stake_pct,
                "win_rate": 0,
                "avg_win": 0,
                "avg_loss": 0,
                "profit_factor": 0,
                "trades_used": len(recent),
                "enough_data": False,
            }

        wins = [t for t in recent if t.profit_ratio > 0]
        losses = [t for t in recent if t.profit_ratio <= 0]

        win_count = len(wins)
        loss_count = len(losses)
        total = win_count + loss_count

        if total == 0:
            return {
                "kelly_pct": self.default_stake_pct,
                "win_rate": 0,
                "avg_win": 0,
                "avg_loss": 0,
                "profit_factor": 0,
                "trades_used": 0,
                "enough_data": False,
            }

        win_rate = win_count / total
        avg_win = sum(t.profit_ratio for t in wins) / win_count if wins else 0
        avg_loss = abs(sum(t.profit_ratio for t in losses) / loss_count) if losses else 0.001

        # Win/Loss ratio (R)
        r_ratio = avg_win / avg_loss if avg_loss > 0 else 10

        # Kelly formula: f* = W - (1 - W) / R
        kelly_raw = win_rate - (1 - win_rate) / r_ratio

        # Apply fractional Kelly
        kelly_adjusted = kelly_raw * self.kelly_fraction

        # Clamp to min/max bounds
        kelly_final = max(self.min_stake_pct, min(self.max_stake_pct, kelly_adjusted))

        # If Kelly is negative, use minimum (edge is negative — shouldn't trade,
        # but we allow minimum to keep gathering data)
        if kelly_raw <= 0:
            kelly_final = self.min_stake_pct

        profit_factor = (
            sum(t.profit_ratio for t in wins) / abs(sum(t.profit_ratio for t in losses))
            if losses
            else float("inf")
        )

        return {
            "kelly_pct": kelly_final,
            "kelly_raw": kelly_raw,
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "r_ratio": r_ratio,
            "profit_factor": profit_factor,
            "trades_used": total,
            "enough_data": True,
        }

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
        """
        Use Kelly Criterion to determine position size.
        Initial entry uses 20% of the Kelly-sized stake (rest is for DCA).
        """
        kelly = self._calculate_kelly()

        # Calculate stake based on Kelly % of total wallet
        wallet_balance = self.wallets.get_total_stake_amount() if self.wallets else 1000
        kelly_stake = wallet_balance * kelly["kelly_pct"]

        # Clamp to exchange limits
        if min_stake is not None:
            kelly_stake = max(kelly_stake, min_stake)
        kelly_stake = min(kelly_stake, max_stake)

        # Initial entry: only 20% (DCA fills the rest)
        entry_stake = kelly_stake * self.initial_stake_pct

        if kelly["enough_data"]:
            logger.info(
                f"Kelly sizing for {pair}: "
                f"kelly_raw={kelly['kelly_raw']:.3f} "
                f"kelly_pct={kelly['kelly_pct']:.3f} "
                f"WR={kelly['win_rate']:.1%} "
                f"R={kelly['r_ratio']:.2f} "
                f"PF={kelly['profit_factor']:.2f} "
                f"stake=${kelly_stake:.2f} "
                f"entry=${entry_stake:.2f} "
                f"({kelly['trades_used']} trades)"
            )
        else:
            logger.info(
                f"Kelly sizing for {pair}: "
                f"not enough data ({kelly['trades_used']}/{self.min_trades_for_kelly}), "
                f"using default {self.default_stake_pct:.0%} = ${entry_stake:.2f}"
            )

        return entry_stake

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
        DCA entries with Kelly-adjusted sizing.
        Later DCA entries are larger (scale up into losing positions).
        """
        if trade.nr_of_successful_entries >= len(self.dca_levels) + 1:
            return None

        dca_idx = trade.nr_of_successful_entries - 1
        if dca_idx >= len(self.dca_levels):
            return None

        required_drop = self.dca_levels[dca_idx]

        if current_profit > -required_drop:
            return None

        # Scale DCA entries: each subsequent entry is slightly larger
        # DCA 1: 1.0x, DCA 2: 1.5x, DCA 3: 2.0x, DCA 4: 2.5x
        dca_multiplier = 1.0 + (dca_idx * 0.5)

        base_stake = trade.stake_amount / trade.nr_of_successful_entries
        dca_stake = base_stake * dca_multiplier

        if min_stake is not None and dca_stake < min_stake:
            dca_stake = min_stake

        logger.info(
            f"DCA #{dca_idx + 1} for {trade.pair}: "
            f"profit={current_profit:.2%} "
            f"trigger={-required_drop:.2%} "
            f"multiplier={dca_multiplier:.1f}x "
            f"stake=${dca_stake:.2f}"
        )

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
        # Kelly already sizes the position — use moderate leverage
        if "BTC" in pair or "ETH" in pair:
            return min(3.0, max_leverage)
        return min(2.0, max_leverage)

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
        """
        Skip trades when Kelly is negative (no edge detected).
        """
        kelly = self._calculate_kelly()

        if kelly["enough_data"] and kelly["kelly_raw"] <= 0:
            logger.warning(
                f"SKIPPING {pair} {side}: Kelly is negative "
                f"({kelly['kelly_raw']:.3f}). No edge detected. "
                f"WR={kelly['win_rate']:.1%} R={kelly['r_ratio']:.2f}"
            )
            return False

        return True
