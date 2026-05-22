"""
TwinPennies AllIn — All-In Before Z-Reversion Exit
=====================================================

Based on TwinPennies V4. Adds a 3rd scaling stage: ALL-IN.

Key insight: twin_winner_revert is 100% win rate across all periods.
When z-score is approaching the exit threshold (close to 0), the
reversion is almost certain. This is the moment to go ALL-IN with
maximum capital for 1-2 candles before exit.

Scaling stages:
    1. Penny entry ($5-12) — probe the trade
    2. Scale 1 (+$100) at z_revert >= 0.4 — z confirms direction
    3. Scale 2 (+$100) at z_revert >= 0.72 — deeper confirmation
    4. ALL-IN (+$200, 2x lev) when z is within allin_z_range of exit
       AND profit > 0 AND already scaled — maximum conviction

The all-in fires ~1-2 candles before exit, capturing the last leg
of reversion with the largest position.
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

from twin_pennies_allin import btc_trend, volume, basket, config as cfg_loader

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "twin_pennies_allin_config.json"

_trade_state: dict[int, dict] = {}


class TwinPenniesAllInStrategy(IStrategy):

    INTERFACE_VERSION = 3
    can_short = True
    process_only_new_candles = True
    timeframe = "5m"
    startup_candle_count = 900
    stoploss = -0.99
    minimal_roi = {"0": 10}
    trailing_stop = False
    use_custom_stoploss = True
    position_adjustment_enable = True
    max_entry_position_adjustment = 8

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        c = cfg_loader.load(CONFIG_PATH)
        self._cfg = c
        self._basket_pairs: list[str] = c["basket"]["pairs"]
        self.BTC_REF: str = c["basket"]["btc_ref"]
        self.timeframe = c.get("timeframe", "5m")
        self.startup_candle_count = c.get("startup_candle_count", 900)
        self.stoploss = c["risk"]["stoploss"]

        self._df_cache: dict[str, DataFrame] = {}
        self._df_cache_cycle: int = 0
        self._btc_trend: dict = {}

        tc = c.get("twin", {})
        self._eval_candles = tc.get("eval_candles", 2)
        self._max_positions = tc.get("max_positions", 4)
        self._winner_exit_z = tc.get("winner_exit_z", 0.15)
        self._max_candles = tc.get("max_candles", 24)
        self._loser_max_candles = tc.get("loser_max_candles", 3)
        self._safety_stop = tc.get("safety_stop", -0.05)
        self._min_winner_profit = tc.get("min_winner_profit", 0.001)

        self._scale_stake = tc.get("scale_stake", 100.0)
        self._z_revert_min = tc.get("z_revert_min", 0.4)
        self._scale_min_profit = tc.get("scale_min_profit", 0.0005)

        # All-in config
        ai = tc.get("allin", {})
        self._allin_stake = ai.get("stake", 200.0)
        self._allin_z_range = ai.get("z_range", 0.5)
        self._allin_min_profit = ai.get("min_profit", 0.003)
        self._allin_min_scales = ai.get("min_scales", 1)

        global _trade_state
        _trade_state = {}

        logger.info(
            "TwinPennies AllIn — %d pairs, scale=$%.0f, allin=$%.0f "
            "(z_range=%.2f, min_profit=%.1f%%), exit_z=%.2f",
            len(self._basket_pairs), self._scale_stake, self._allin_stake,
            self._allin_z_range, self._allin_min_profit * 100,
            self._winner_exit_z,
        )

    # ────────────────────────── Data ──────────────────────────

    def _get_pair_df(self, pair, timeframe=None):
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
        pairs = self.dp.current_whitelist() if self.dp else []
        btc_tf = self._cfg.get("btc_trend", {}).get("timeframe", "1h")
        return [(pair, "1d") for pair in pairs] + [(self.BTC_REF, btc_tf)]

    def populate_indicators(self, dataframe, metadata):
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
        basket.compute_basket_zscore(
            dataframe, pair, self._basket_pairs,
            self._cfg["zscore"]["zscore_window"],
            self.timeframe, self.dp, self._df_cache, self._cfg,
        )
        return dataframe

    # ────────────────────────── Entries ──────────────────────────

    def populate_entry_trend(self, dataframe, metadata):
        pair = metadata["pair"]
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe["enter_tag"] = ""
        if pair == self.BTC_REF or dataframe.empty or "basket_z" not in dataframe.columns:
            return dataframe

        entry_z = self._cfg["basket"]["entry_z"]
        vol_ok = dataframe.get("vol_ok", pd.Series(1, index=dataframe.index)) == 1
        no_chaos = ~dataframe.get("btc_high_vol", pd.Series(False, index=dataframe.index)).astype(bool)

        is_lagging = dataframe["basket_z"] < -entry_z
        safe_long = ~dataframe.get("btc_dump", pd.Series(False, index=dataframe.index)).astype(bool)
        dataframe.loc[is_lagging & safe_long & no_chaos & vol_ok, ["enter_long", "enter_tag"]] = (1, "twin_long")

        is_leading = dataframe["basket_z"] > entry_z
        safe_short = ~dataframe.get("btc_pump", pd.Series(False, index=dataframe.index)).astype(bool)
        dataframe.loc[is_leading & safe_short & no_chaos & vol_ok, ["enter_short", "enter_tag"]] = (1, "twin_short")
        return dataframe

    def populate_exit_trend(self, dataframe, metadata):
        return dataframe

    # ────────────────────────── Helpers ──────────────────────────

    def _get_current_z(self, pair, current_time):
        if not self.dp:
            return None
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or df.empty or "basket_z" not in df.columns:
            return None
        ct = pd.Timestamp(current_time)
        if df["date"].dt.tz is not None:
            ct = ct.tz_localize("UTC") if ct.tz is None else ct.tz_convert("UTC")
        mask = df["date"] <= ct
        if not mask.any():
            return None
        return float(df["basket_z"].iloc[mask.sum() - 1])

    def _get_btc_mom(self, pair, current_time):
        if not self.dp:
            return 0.0
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or df.empty or "btc_mom" not in df.columns:
            return 0.0
        ct = pd.Timestamp(current_time)
        if df["date"].dt.tz is not None:
            ct = ct.tz_localize("UTC") if ct.tz is None else ct.tz_convert("UTC")
        mask = df["date"] <= ct
        if not mask.any():
            return 0.0
        return float(df["btc_mom"].iloc[mask.sum() - 1])

    def confirm_trade_entry(self, pair, order_type, amount, rate, time_in_force,
                            current_time, entry_tag, side, **kwargs):
        open_trades = Trade.get_trades_proxy(is_open=True)
        if len(open_trades) >= self._max_positions:
            return False
        if pair in {t.pair for t in open_trades}:
            return False
        entry_z = self._cfg["basket"]["entry_z"]
        open_pairs = {t.pair for t in open_trades}
        for p in self._basket_pairs:
            if p == self.BTC_REF or p == pair or p in open_pairs:
                continue
            z = self._get_current_z(p, current_time)
            if z is None:
                continue
            if side == "long" and z > entry_z:
                return True
            if side == "short" and z < -entry_z:
                return True
        return False

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                            min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        if not self.dp:
            return min_stake or 5.0
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or len(df) < 5 or "basket_z" not in df.columns:
            return min_stake or 5.0
        z_abs = abs(float(df["basket_z"].iloc[-1]))
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

    def leverage(self, pair, current_time, current_rate, proposed_leverage,
                 max_leverage, entry_tag, side, **kwargs):
        initial_lev = self._cfg.get("twin", {}).get("initial_leverage", 3)
        return float(max(1, min(initial_lev, int(max_leverage))))

    # ────────────────────────── Trade state ──────────────────────────

    def _get_ts(self, trade_id):
        global _trade_state
        if trade_id not in _trade_state:
            _trade_state[trade_id] = {
                "evaluated": False,
                "is_winner": None,
                "scale_count": 0,
                "entry_z": None,
                "last_scale_z": None,
                "peak_profit": 0.0,
                "allin_done": False,
            }
        return _trade_state[trade_id]

    # ────────────────────────── Scaling + All-In ──────────────────────────

    def adjust_trade_position(self, trade, current_time, current_rate, current_profit,
                              min_stake, max_stake, current_entry_rate, current_exit_rate,
                              current_entry_profit, current_exit_profit, **kwargs):
        trade_age = (current_time - trade.open_date_utc).total_seconds() / 300
        ts = self._get_ts(trade.id)
        ts["peak_profit"] = max(ts["peak_profit"], current_profit)

        if ts["entry_z"] is None:
            z = self._get_current_z(trade.pair, current_time)
            if z is not None:
                ts["entry_z"] = z

        # Evaluate winner/loser
        if not ts["evaluated"] and trade_age >= self._eval_candles:
            ts["evaluated"] = True
            ts["is_winner"] = current_profit >= self._min_winner_profit
            label = "W" if ts["is_winner"] else "L"
            logger.info(
                "EVAL %s %s[%s] profit=%.2f%% z_entry=%.3f @%.0fc",
                trade.pair, "S" if trade.is_short else "L", label,
                current_profit * 100, ts["entry_z"] or 0, trade_age,
            )

        if not ts["is_winner"] or ts["entry_z"] is None:
            return None

        current_z = self._get_current_z(trade.pair, current_time)
        if current_z is None:
            return None

        entry_z = ts["entry_z"]
        is_long = not trade.is_short
        z_delta = (current_z - entry_z) if is_long else (entry_z - current_z)

        # ── Stage 1-2: Progressive scaling ──
        max_scales = self._cfg.get("twin", {}).get("max_scale_times", 2)
        if ts["scale_count"] < max_scales and current_profit >= self._scale_min_profit:
            scale_n = ts["scale_count"]
            z_threshold = self._z_revert_min * (1.0 + scale_n * 0.8)

            if ts["last_scale_z"] is not None:
                z_since = (current_z - ts["last_scale_z"]) if is_long else (ts["last_scale_z"] - current_z)
                if z_since < self._z_revert_min * 0.3:
                    # Check all-in even if regular scale blocked
                    return self._check_allin(ts, trade, current_z, current_profit, min_stake, max_stake)

            if z_delta >= z_threshold:
                ts["scale_count"] += 1
                ts["last_scale_z"] = current_z
                add = min(self._scale_stake, max_stake)
                if min_stake and add < min_stake:
                    add = min_stake
                logger.info(
                    "SCALE[%d/%d] %s | z: %.3f -> %.3f (delta=%.3f) | profit=%.2f%% | +$%.2f",
                    ts["scale_count"], max_scales, trade.pair,
                    entry_z, current_z, z_delta, current_profit * 100, add,
                )
                return add

        # ── Stage 3: ALL-IN ──
        return self._check_allin(ts, trade, current_z, current_profit, min_stake, max_stake)

    def _check_allin(self, ts, trade, current_z, current_profit, min_stake, max_stake):
        """All-in when z is close to exit threshold — the last push."""
        if ts["allin_done"]:
            return None
        if ts["scale_count"] < self._allin_min_scales:
            return None
        if current_profit < self._allin_min_profit:
            return None

        is_long = not trade.is_short

        # How close is z to exit?
        # LONG exit when z > -winner_exit_z → z is close when z > -(winner_exit_z + allin_z_range)
        # SHORT exit when z < winner_exit_z → z is close when z < (winner_exit_z + allin_z_range)
        if is_long:
            z_near_exit = current_z > -(self._winner_exit_z + self._allin_z_range)
        else:
            z_near_exit = current_z < (self._winner_exit_z + self._allin_z_range)

        if not z_near_exit:
            return None

        ts["allin_done"] = True
        add = min(self._allin_stake, max_stake)
        if min_stake and add < min_stake:
            add = min_stake
        logger.info(
            "ALL-IN %s | z=%.3f (near exit=%.2f) | profit=%.2f%% | +$%.2f | stake_total=$%.2f",
            trade.pair, current_z, self._winner_exit_z,
            current_profit * 100, add, trade.stake_amount + add,
        )
        return add

    # ────────────────────────── Stoploss ──────────────────────────

    def custom_stoploss(self, pair, trade, current_time, current_rate,
                        current_profit, after_fill, **kwargs):
        ts = self._get_ts(trade.id)
        if not ts["evaluated"]:
            return self._safety_stop

        # All stages: safety stop only. No trailing.
        # Z-reversion exit handles winners. Proven best in V4.
        return self._safety_stop

    # ────────────────────────── Exit ──────────────────────────

    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        trade_age = (current_time - trade.open_date_utc).total_seconds() / 300
        ts = self._get_ts(trade.id)

        if current_profit < self._safety_stop:
            return "twin_max_loss"

        if ts["evaluated"] and not ts["is_winner"]:
            if trade_age >= self._loser_max_candles:
                return "twin_loser_close"

        if ts["is_winner"]:
            z = self._get_current_z(pair, current_time)
            is_long = not trade.is_short

            if z is not None and current_profit > 0.003:
                if is_long and z > -self._winner_exit_z:
                    return "twin_winner_revert"
                if not is_long and z < self._winner_exit_z:
                    return "twin_winner_revert"

            if ts["scale_count"] > 0 and current_profit > 0.018 and trade_age > 8:
                btc_mom = self._get_btc_mom(pair, current_time)
                if is_long and btc_mom < -3.5:
                    return "twin_mom_reverse"
                if not is_long and btc_mom > 3.5:
                    return "twin_mom_reverse"

        if trade_age >= self._max_candles:
            return "twin_time_stop"

        return None

    def confirm_trade_exit(self, pair, trade, order_type, amount, rate,
                           time_in_force, exit_reason, current_time, **kwargs):
        ts = self._get_ts(trade.id)
        profit = trade.calc_profit_ratio(rate)
        label = "W" if ts.get("is_winner") else ("L" if ts.get("is_winner") is False else "?")
        sc = ts.get("scale_count", 0)
        ai = "+AI" if ts.get("allin_done") else ""
        scaled = f"+S{sc}{ai}" if sc > 0 or ai else ""
        logger.info(
            "CLOSE %s %s[%s%s] profit=%.2f%% $%.2f lev=%.0fx | %s",
            pair, "S" if trade.is_short else "L", label, scaled,
            profit * 100, trade.stake_amount, trade.leverage, exit_reason,
        )
        return True
