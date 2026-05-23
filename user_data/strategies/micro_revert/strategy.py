"""
MicroRevert — Individual Z-Score Mean Reversion Scalp
======================================================

Ultra-short mean reversion on 5m using individual z-score
(price vs its own EMA). Penny entry, 1-candle eval, z-confirmed
scaling, z-reversion exit.

Flow:
    1. Enter with tiered penny ($5-12) when |ind_z| > entry_z
    2. After 1 candle (5 min), classify winner/loser
    3. Losers: close immediately
    4. Winners: scale +$100 when z-delta confirms reversion
    5. Exit on z-reversion to ~0 or time stop (5 candles)
"""
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from pandas import DataFrame

_STRATEGIES_DIR = str(Path(__file__).resolve().parent.parent)
if _STRATEGIES_DIR not in sys.path:
    sys.path.insert(0, _STRATEGIES_DIR)

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy

from micro_revert import btc_trend, volume, zscore, config as cfg_loader

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "micro_revert_config.json"

_trade_state: dict[int, dict] = {}


class MicroRevertStrategy(IStrategy):

    INTERFACE_VERSION = 3
    can_short = True
    process_only_new_candles = True
    timeframe = "5m"
    startup_candle_count = 200
    stoploss = -0.99
    minimal_roi = {"0": 10}
    trailing_stop = False
    use_custom_stoploss = True
    position_adjustment_enable = True
    max_entry_position_adjustment = 5

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        c = cfg_loader.load(CONFIG_PATH)
        self._cfg = c
        self.BTC_REF: str = c["btc_ref"]
        self.timeframe = c.get("timeframe", "5m")
        self.startup_candle_count = c.get("startup_candle_count", 200)
        self.stoploss = c["risk"]["stoploss"]

        self._df_cache: dict[str, DataFrame] = {}
        self._df_cache_cycle: int = 0
        self._btc_trend: dict = {}

        tc = c.get("twin", {})
        self._eval_candles = tc.get("eval_candles", 1)
        self._max_positions = tc.get("max_positions", 8)
        self._winner_exit_z = tc.get("winner_exit_z", 0.1)
        self._max_candles = tc.get("max_candles", 5)
        self._loser_max_candles = tc.get("loser_max_candles", 1)
        self._safety_stop = tc.get("safety_stop", -0.05)
        self._min_winner_profit = tc.get("min_winner_profit", 0.0001)

        self._scale_stake = tc.get("scale_stake", 100.0)
        self._z_revert_min = tc.get("z_revert_min", 0.3)
        self._scale_min_profit = tc.get("scale_min_profit", 0.0003)

        self._entry_z = c["zscore"]["entry_z"]
        self._exit_z = c["zscore"].get("exit_z", 0.1)

        global _trade_state
        _trade_state = {}

        logger.info(
            "MicroRevert — entry_z=%.1f, ema=%d, eval=%dc, max=%dc, "
            "scale=$%.0f, exit_z=%.2f, %d max_pos",
            self._entry_z, c["zscore"]["ema_window"],
            self._eval_candles, self._max_candles,
            self._scale_stake, self._exit_z, self._max_positions,
        )

    # ────────────────────────── Data ──────────────────────────

    def _get_pair_df(self, pair: str, timeframe: str | None = None) -> DataFrame | None:
        tf = timeframe or self.timeframe
        key = f"{pair}__{tf}"
        if key in self._df_cache:
            return self._df_cache[key]
        if not self.dp:
            return None
        df = self.dp.get_pair_dataframe(pair=pair, timeframe=tf)
        if df is not None:
            self._df_cache[key] = df
        return df

    def informative_pairs(self):
        btc_tf = self._cfg.get("btc_trend", {}).get("timeframe", "1h")
        return [(self.BTC_REF, btc_tf)]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]
        cycle_id = id(dataframe)
        if cycle_id != self._df_cache_cycle:
            self._df_cache.clear()
            self._df_cache_cycle = cycle_id
            self._btc_trend = {}

        if not self._btc_trend:
            btc_tf = self._cfg.get("btc_trend", {}).get("timeframe", "1h")
            btc_df = self._get_pair_df(self.BTC_REF, btc_tf)
            if btc_df is not None and len(btc_df) >= 50:
                self._btc_trend = btc_trend.compute(btc_df, self._cfg)
        dataframe = btc_trend.map_to_timeframe(self._btc_trend, dataframe)
        volume.compute(dataframe, self._cfg)
        zscore.compute(dataframe, self._cfg)
        return dataframe

    # ────────────────────────── Entries ──────────────────────────

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe["enter_tag"] = ""

        if dataframe.empty or "ind_z" not in dataframe.columns:
            return dataframe

        vol_ok = dataframe.get("vol_ok", pd.Series(1, index=dataframe.index)) == 1
        no_chaos = ~dataframe.get("btc_high_vol", pd.Series(False, index=dataframe.index)).astype(bool)

        is_below = dataframe["ind_z"] < -self._entry_z
        safe_long = ~dataframe.get("btc_dump", pd.Series(False, index=dataframe.index)).astype(bool)
        mask_long = is_below & safe_long & no_chaos & vol_ok
        dataframe.loc[mask_long, ["enter_long", "enter_tag"]] = (1, "mr_long")

        is_above = dataframe["ind_z"] > self._entry_z
        safe_short = ~dataframe.get("btc_pump", pd.Series(False, index=dataframe.index)).astype(bool)
        mask_short = is_above & safe_short & no_chaos & vol_ok
        dataframe.loc[mask_short, ["enter_short", "enter_tag"]] = (1, "mr_short")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    # ────────────────────────── Helpers ──────────────────────────

    def _get_current_z(self, pair: str, current_time) -> float | None:
        if not self.dp:
            return None
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or df.empty or "ind_z" not in df.columns:
            return None
        ct = pd.Timestamp(current_time)
        if df["date"].dt.tz is not None:
            ct = ct.tz_localize("UTC") if ct.tz is None else ct.tz_convert("UTC")
        mask = df["date"] <= ct
        if not mask.any():
            return None
        return float(df["ind_z"].iloc[mask.sum() - 1])

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float,
                            rate: float, time_in_force: str, current_time: datetime,
                            entry_tag: Optional[str], side: str, **kwargs) -> bool:
        open_trades = Trade.get_trades_proxy(is_open=True)
        if len(open_trades) >= self._max_positions:
            return False
        if pair in {t.pair for t in open_trades}:
            return False
        return True

    # ────────────────────────── Tiered stake ──────────────────────────

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float],
                            max_stake: float, leverage: float, entry_tag: Optional[str],
                            side: str, **kwargs) -> float:
        if not self.dp:
            return min_stake or 5.0

        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or len(df) < 5 or "ind_z" not in df.columns:
            return min_stake or 5.0

        z_abs = abs(float(df["ind_z"].iloc[-1]))

        if z_abs >= 3.0:
            stake = 12.0
        elif z_abs >= 2.5:
            stake = 9.0
        elif z_abs >= 2.0:
            stake = 7.0
        else:
            stake = min_stake or 5.0

        stake = min(stake, max_stake * 0.3)
        if min_stake and stake < min_stake:
            stake = min_stake
        return stake

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float,
                 entry_tag: Optional[str], side: str, **kwargs) -> float:
        initial_lev = self._cfg.get("twin", {}).get("initial_leverage", 3)
        return float(max(1, min(initial_lev, int(max_leverage))))

    # ────────────────────────── Trade state ──────────────────────────

    def _get_ts(self, trade_id: int) -> dict:
        global _trade_state
        if trade_id not in _trade_state:
            _trade_state[trade_id] = {
                "evaluated": False,
                "is_winner": None,
                "scale_count": 0,
                "entry_z": None,
                "last_scale_z": None,
                "peak_profit": 0.0,
            }
        return _trade_state[trade_id]

    # ────────────────────────── Z-confirmed scaling ──────────────────────────

    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: Optional[float], max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs) -> Optional[float]:
        trade_age = (current_time - trade.open_date_utc).total_seconds() / 300
        ts = self._get_ts(trade.id)
        ts["peak_profit"] = max(ts["peak_profit"], current_profit)

        if ts["entry_z"] is None:
            z = self._get_current_z(trade.pair, current_time)
            if z is not None:
                ts["entry_z"] = z

        # Evaluate after eval_candles
        if not ts["evaluated"] and trade_age >= self._eval_candles:
            ts["evaluated"] = True
            ts["is_winner"] = current_profit >= self._min_winner_profit
            label = "W" if ts["is_winner"] else "L"
            logger.info(
                "EVAL %s %s[%s] profit=%.2f%% z_entry=%.3f @%.0fc",
                trade.pair, "S" if trade.is_short else "L", label,
                current_profit * 100, ts["entry_z"] or 0, trade_age,
            )

        # Progressive scaling for winners
        max_scales = self._cfg.get("twin", {}).get("max_scale_times", 2)
        if (ts["is_winner"]
                and ts["scale_count"] < max_scales
                and ts["entry_z"] is not None
                and current_profit >= self._scale_min_profit):

            current_z = self._get_current_z(trade.pair, current_time)
            if current_z is None:
                return None

            entry_z = ts["entry_z"]
            is_long = not trade.is_short

            if is_long:
                z_delta = current_z - entry_z
            else:
                z_delta = entry_z - current_z

            scale_n = ts["scale_count"]
            z_threshold = self._z_revert_min * (1.0 + scale_n * 0.8)

            if ts["last_scale_z"] is not None:
                if is_long:
                    z_since_last = current_z - ts["last_scale_z"]
                else:
                    z_since_last = ts["last_scale_z"] - current_z
                if z_since_last < self._z_revert_min * 0.3:
                    return None

            if z_delta >= z_threshold:
                ts["scale_count"] += 1
                ts["last_scale_z"] = current_z
                add = min(self._scale_stake, max_stake)
                if min_stake and add < min_stake:
                    add = min_stake
                logger.info(
                    "SCALE[%d/%d] %s | z: %.3f -> %.3f (delta=%.3f >= %.2f) | "
                    "profit=%.2f%% | +$%.2f",
                    ts["scale_count"], max_scales, trade.pair,
                    entry_z, current_z, z_delta, z_threshold,
                    current_profit * 100, add,
                )
                return add

        return None

    # ────────────────────────── Stoploss ──────────────────────────

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float,
                        after_fill: bool, **kwargs) -> float | None:
        return self._safety_stop

    # ────────────────────────── Exit ──────────────────────────

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        trade_age = (current_time - trade.open_date_utc).total_seconds() / 300
        ts = self._get_ts(trade.id)

        # Max loss
        if current_profit < self._safety_stop:
            return "mr_max_loss"

        # LOSER: close immediately after eval
        if ts["evaluated"] and not ts["is_winner"]:
            if trade_age >= self._loser_max_candles:
                return "mr_loser_close"

        # WINNER exits
        if ts["is_winner"]:
            z = self._get_current_z(pair, current_time)
            is_long = not trade.is_short

            # Z-reversion exit (primary profit engine)
            if z is not None and current_profit > 0.003:
                if is_long and z > -self._exit_z:
                    return "mr_winner_revert"
                if not is_long and z < self._exit_z:
                    return "mr_winner_revert"

        # Time stop
        if trade_age >= self._max_candles:
            return "mr_time_stop"

        return None

    def confirm_trade_exit(self, pair: str, trade: Trade, order_type: str,
                           amount: float, rate: float, time_in_force: str,
                           exit_reason: str, current_time: datetime, **kwargs) -> bool:
        ts = self._get_ts(trade.id)
        profit = trade.calc_profit_ratio(rate)
        label = "W" if ts.get("is_winner") else ("L" if ts.get("is_winner") is False else "?")
        sc = ts.get("scale_count", 0)
        scaled = f"+S{sc}" if sc > 0 else ""
        logger.info(
            "CLOSE %s %s[%s%s] profit=%.2f%% $%.2f lev=%.0fx | %s",
            pair, "S" if trade.is_short else "L", label, scaled,
            profit * 100, trade.stake_amount, trade.leverage, exit_reason,
        )
        return True
