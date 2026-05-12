"""
Z-Score Pairs Trading V12 — Kelly + Regime + Hedge Recovery
15m scalper with Kelly criterion sizing, regime filter, BTC trend filter,
balanced group entries, and 2x hedge-on-loss recovery.

Phase 1: Scalp entry on spread Z-score deviation (Kelly-sized)
Phase 2: If losing after 1h, hedge opens on other group at 2x size
Phase 3: ROI exits winners, 6h time stop closes the rest
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


class ZScorePairsTradingV12(ZScorePairsTradingBase):

    timeframe = "15m"
    startup_candle_count = 300
    max_open_trades = 6
    position_adjustment_enable = True
    max_entry_position_adjustment = 1  # allow 1 DCA/hedge add per trade

    stoploss = -0.10
    minimal_roi = {
        "0": 0.008,
        "20": 0.005,
        "60": 0.003,
        "180": 0.001,
    }
    trailing_stop = False

    # Z-score params
    zscore_window = IntParameter(48, 192, default=96, space="buy", optimize=True)
    cum_return_window = IntParameter(4, 24, default=8, space="buy", optimize=True)
    zscore_entry = DecimalParameter(1.5, 3.0, default=2.5, decimals=1, space="buy", optimize=True)

    # Regime filter params
    regime_window = IntParameter(48, 192, default=96, space="buy", optimize=True)
    regime_corr_min = DecimalParameter(0.2, 0.7, default=0.4, decimals=1, space="buy", optimize=True)

    # Kelly params
    kelly_fraction = 0.5
    min_trades_for_kelly = 20
    kelly_lookback = 100
    min_stake_pct = 0.10
    max_stake_pct = 0.15
    default_stake_pct = 0.15

    # Hedge params
    hedge_time_minutes = 120
    hedge_loss_threshold = -0.02
    hedge_size_multiplier = 1.5

    _pair_zscores: dict[str, DataFrame] = {}
    _btc_trend: dict = {}

    # =========================================================================
    # INFORMATIVE PAIRS
    # =========================================================================

    def informative_pairs(self):
        pairs = self.dp.current_whitelist() if self.dp else []
        return [(pair, "1d") for pair in pairs] + [("BTC/USDT:USDT", "1h")]

    # =========================================================================
    # BTC TREND — from V9
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
            "high_vol": (atr_z > 1.5).values,
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
    # REGIME FILTER — from V2 (adapted for 15m)
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
    # KELLY CRITERION
    # =========================================================================

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
                "kelly_raw": 0,
                "win_rate": 0,
                "avg_win": 0,
                "avg_loss": 0,
                "r_ratio": 0,
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
                "kelly_raw": 0,
                "win_rate": 0,
                "avg_win": 0,
                "avg_loss": 0,
                "r_ratio": 0,
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

        # Apply fractional Kelly (Half-Kelly)
        kelly_adjusted = kelly_raw * self.kelly_fraction

        # Clamp to min/max bounds
        kelly_final = max(self.min_stake_pct, min(self.max_stake_pct, kelly_adjusted))

        # If Kelly is negative, use minimum
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

    # =========================================================================
    # INDICATORS
    # =========================================================================

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_indicators(dataframe, metadata)
        pair = metadata["pair"]

        # BTC trend
        self._compute_btc_trend()
        dataframe["btc_pump"] = self._get_btc_signal(dataframe, "pump")
        dataframe["btc_dump"] = self._get_btc_signal(dataframe, "dump")
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

        # Regime filter
        dataframe = self._compute_regime(pair, dataframe)

        # Volume filter
        dataframe["vol_ok"] = (dataframe["volume"] > dataframe["volume"].rolling(48).mean()).astype(int)

        return dataframe

    # =========================================================================
    # ENTRY — spread Z-score + regime filter + BTC trend filter
    # =========================================================================

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]
        is_a = pair in self.group_a
        is_b = pair in self.group_b

        # Base filters
        vol = dataframe["vol_ok"] == 1
        regime = dataframe["regime_ok"] == 1

        # BTC trend filter
        no_chaos = ~dataframe["btc_high_vol"]
        safe_long = ~dataframe["btc_dump"] & no_chaos
        safe_short = ~dataframe["btc_pump"] & no_chaos

        # Spread signals
        spread_low = dataframe["spread_zscore"] < -self.zscore_entry.value
        spread_high = dataframe["spread_zscore"] > self.zscore_entry.value

        if is_a:
            dataframe.loc[vol & regime & spread_low & safe_long, ["enter_long", "enter_tag"]] = (1, "v12_long_a")
            dataframe.loc[vol & regime & spread_high & safe_short, ["enter_short", "enter_tag"]] = (1, "v12_short_a")
        elif is_b:
            dataframe.loc[vol & regime & spread_low & safe_short, ["enter_short", "enter_tag"]] = (1, "v12_short_b")
            dataframe.loc[vol & regime & spread_high & safe_long, ["enter_long", "enter_tag"]] = (1, "v12_long_b")

        return dataframe

    # =========================================================================
    # EXIT — ROI handles profits, time stop handles losers
    # =========================================================================

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    # =========================================================================
    # CUSTOM STAKE — Kelly-sized with hedge detection
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
        """
        Use Kelly Criterion to determine position size.
        If this is a hedge entry (other group losing after 1h), apply 2x multiplier.
        """
        kelly = self._calculate_kelly()

        # Kelly stake: use fixed base of $1000 (starting capital) to avoid
        # shrinking wallet issue where available balance drops with open trades
        kelly_stake = 1000 * kelly["kelly_pct"]

        # Detect hedge and apply multiplier
        is_hedge = self._is_hedge_entry(pair, current_time)
        if is_hedge:
            kelly_stake *= self.hedge_size_multiplier
            logger.info(
                f"HEDGE entry for {pair}: applying {self.hedge_size_multiplier}x multiplier "
                f"-> stake=${kelly_stake:.2f}"
            )

        # Clamp to exchange limits
        if min_stake is not None:
            kelly_stake = max(kelly_stake, min_stake)
        kelly_stake = min(kelly_stake, max_stake)

        if kelly["enough_data"]:
            logger.info(
                f"Kelly sizing for {pair}: "
                f"kelly_raw={kelly['kelly_raw']:.3f} "
                f"kelly_pct={kelly['kelly_pct']:.3f} "
                f"WR={kelly['win_rate']:.1%} "
                f"R={kelly['r_ratio']:.2f} "
                f"PF={kelly['profit_factor']:.2f} "
                f"stake=${kelly_stake:.2f} "
                f"hedge={is_hedge} "
                f"({kelly['trades_used']} trades)"
            )
        else:
            logger.info(
                f"Kelly sizing for {pair}: "
                f"not enough data ({kelly['trades_used']}/{self.min_trades_for_kelly}), "
                f"using default {self.default_stake_pct:.0%} = ${kelly_stake:.2f}"
            )

        return kelly_stake

    # =========================================================================
    # HEDGE VIA POSITION ADJUSTMENT — add to losing trades
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
        Hedge: if trade is losing after hedge_time_minutes, add to the position
        with hedge_size_multiplier * original stake. This averages down the entry
        and gives the trade more room to recover via ROI.
        """
        if trade.nr_of_successful_entries >= 2:
            return None  # already hedged once

        trade_minutes = (current_time - trade.open_date_utc).total_seconds() / 60

        if trade_minutes < self.hedge_time_minutes:
            return None

        if current_profit > self.hedge_loss_threshold:
            return None  # not losing enough

        # Add hedge_size_multiplier * original stake
        hedge_stake = trade.stake_amount * self.hedge_size_multiplier
        if min_stake and hedge_stake < min_stake:
            hedge_stake = min_stake

        logger.info(
            f"HEDGE ADD on {trade.pair}: profit={current_profit:.2%} "
            f"after {trade_minutes:.0f}min, adding ${hedge_stake:.2f}"
        )
        return min(hedge_stake, max_stake)

    # =========================================================================
    # HEDGE DETECTION (for custom_stake_amount — kept for non-DCA entries)
    # =========================================================================

    def _is_hedge_entry(self, pair: str, current_time: datetime) -> bool:
        """
        Check if the OTHER group has a trade that's been open longer than
        hedge_time_minutes. If ROI hasn't closed it by then, it's likely losing —
        this entry is a hedge recovery trade.

        We use time-based detection instead of profit-based because in backtesting
        we can't reliably get current unrealized profit for other open trades.
        """
        open_trades = Trade.get_trades_proxy(is_open=True)

        if pair in self.group_a:
            other_group = self.group_b
        elif pair in self.group_b:
            other_group = self.group_a
        else:
            return False

        for trade in open_trades:
            if trade.pair not in other_group:
                continue

            trade_minutes = (current_time - trade.open_date_utc).total_seconds() / 60

            # If a trade survived past hedge_time_minutes without ROI closing it,
            # it's not profitable — treat this as a hedge trigger
            if trade_minutes > self.hedge_time_minutes:
                return True

        return False

    # =========================================================================
    # TIME STOP
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

        if trade_minutes > 360:
            return "time_stop_6h"

        return None

    # =========================================================================
    # CONFIRM ENTRY — Kelly gate + balance check
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
        # Kelly gate: reject if Kelly is negative (no edge detected)
        kelly = self._calculate_kelly()
        if kelly["enough_data"] and kelly["kelly_raw"] <= 0:
            logger.warning(
                f"SKIPPING {pair} {side}: Kelly is negative "
                f"({kelly['kelly_raw']:.3f}). No edge detected. "
                f"WR={kelly['win_rate']:.1%} R={kelly['r_ratio']:.2f}"
            )
            return False

        # Balance check: groups within 1 trade of each other
        open_trades = Trade.get_trades_proxy(is_open=True)
        count_a = sum(1 for t in open_trades if t.pair in self.group_a)
        count_b = sum(1 for t in open_trades if t.pair in self.group_b)

        if pair in self.group_a and count_a + 1 - count_b > 1:
            return False
        if pair in self.group_b and count_b + 1 - count_a > 1:
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
