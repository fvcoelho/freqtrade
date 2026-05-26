"""
TwinPennies Hybrid V5 — Asymmetric Long Breakout + Short Mean-Reversion
======================================================================

Rationale: TwinPennies V4 trades both sides with the same mean-reversion
basket z-score. Backtests show shorts (z > entry_z reverting to mean) work,
but symmetric longs against the basket bleed in trending markets. This
hybrid splits the directions:

    SHORT — mean reversion against basket z-score (V4 logic)
        - Pair is leading basket: basket_z > entry_z
        - Exit when z reverts to ~0 (winner_exit_z) OR time stop
        - BTC pump blocks new shorts (don't fade strong trend)

    LONG — Donchian breakout (NEW)
        - Close breaks above prior N-candle high
        - Confirmed by BTC momentum > min_btc_mom (trend alignment)
        - Volume filter, no chaos, no BTC dump
        - Exit via chandelier (peak - atr_mult * ATR), breakout invalidation
          (close back inside the box), or time stop. NOT z-score based.

NO twin requirement — longs and shorts are independent signals. Each side
has its own position-management track (winner/loser eval for shorts,
trailing for longs).

Lookahead safety: Donchian high uses `.rolling(N).max().shift(1)` so the
current close is compared against the prior N highs, never including the
current bar.
"""
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
from pandas import DataFrame

_STRATEGIES_DIR = str(Path(__file__).resolve().parent.parent)
if _STRATEGIES_DIR not in sys.path:
    sys.path.insert(0, _STRATEGIES_DIR)

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy

from twin_pennies import btc_trend, volume, basket, config as cfg_loader
from twin_pennies_hybrid import breakout

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "twin_pennies_hybrid_config.json"

_trade_state: dict[int, dict] = {}
_winner_cooldowns: dict[tuple[str, str], datetime] = {}
_loss_streaks: dict[tuple[str, str], int] = {}
_pair_cooldowns: dict[tuple[str, str], datetime] = {}


class TwinPenniesHybridStrategy(IStrategy):

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
    max_entry_position_adjustment = 5

    CONFIG_PATH = DEFAULT_CONFIG_PATH

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        c = cfg_loader.load(self.CONFIG_PATH)
        self._cfg = c
        self._basket_pairs: list[str] = c["basket"]["pairs"]
        self.BTC_REF: str = c["basket"]["btc_ref"]
        self.timeframe = c.get("timeframe", "5m")
        self.startup_candle_count = c.get("startup_candle_count", 900)
        self.stoploss = c["risk"]["stoploss"]

        self._df_cache: dict[str, DataFrame] = {}
        self._df_cache_cycle: int = 0
        self._btc_trend: dict = {}
        self._cycle_state: dict[str, dict] = {}

        # Short (mean-rev) params
        tc = c.get("twin", {})
        self._eval_candles = tc.get("eval_candles", 2)
        self._max_positions = tc.get("max_positions", 4)
        self._winner_exit_z = tc.get("winner_exit_z", 0.08)
        self._max_candles_short = tc.get("max_candles", 30)
        self._loser_max_candles = tc.get("loser_max_candles", 3)
        self._safety_stop = tc.get("safety_stop", -0.1167)
        self._min_winner_profit = tc.get("min_winner_profit", 0.0023)
        self._scale_stake = tc.get("scale_stake", 250.0)
        self._z_revert_min = tc.get("z_revert_min", 0.35)
        self._scale_min_profit = tc.get("scale_min_profit", 0.00117)
        self._cooldown_minutes = float(tc.get("cooldown_after_winner_minutes", 0))
        self._min_entry_notional = float(tc.get("min_entry_notional", 0))
        self._require_twin_for_short = bool(tc.get("require_twin_for_short", False))

        # V8 — short improvements (0/None = disabled)
        self._stale_exit_after = int(tc.get("stale_exit_after_candles", 0))
        self._stale_z_threshold = float(tc.get("stale_z_threshold", 0.0))
        self._z_worsen_mult = float(tc.get("z_worsen_mult", 0.0))
        self._cooldown_after_n_losses = int(tc.get("cooldown_after_n_losses", 0))
        self._cooldown_pair_minutes = float(tc.get("cooldown_pair_minutes", 0))

        # Long (breakout) params
        bk = c.get("breakout", {})
        self._bk_disable_long = bool(bk.get("disable_long", False))
        self._bk_min_btc_mom = float(bk.get("min_btc_mom", 0.3))
        self._bk_min_atr_z = float(bk.get("min_atr_z", 0.0))
        self._bk_max_candles = int(bk.get("max_candles", 48))
        self._bk_safety_stop = float(bk.get("safety_stop", -0.10))
        self._bk_chandelier_atr_mult = float(bk.get("chandelier_atr_mult", 2.5))
        self._bk_chandelier_min_profit = float(bk.get("chandelier_min_profit", 0.005))
        self._bk_invalidation_buffer = float(bk.get("invalidation_atr_buffer", 0.5))
        self._bk_min_profit_for_invalidation = float(bk.get("min_profit_for_invalidation", -0.005))
        self._bk_initial_stake = float(bk.get("initial_stake", 12.0))
        self._bk_scale_stake = float(bk.get("scale_stake", 250.0))
        self._bk_max_scale_times = int(bk.get("max_scale_times", 1))
        self._bk_scale_at_profit = float(bk.get("scale_at_profit", 0.01))
        self._bk_scale_breakout_required = bool(bk.get("scale_requires_new_high", True))

        global _trade_state, _winner_cooldowns, _loss_streaks, _pair_cooldowns
        _trade_state = {}
        _winner_cooldowns = {}
        _loss_streaks = {}
        _pair_cooldowns = {}

        logger.info(
            "TwinPenniesHybrid V5 — %d pairs | SHORT mean-rev (entry_z=%.2f, exit_z=%.2f) | "
            "LONG breakout (lookback=%d, min_btc_mom=%.2f, chandelier=%.1fxATR)",
            len(self._basket_pairs),
            c["basket"]["entry_z"], self._winner_exit_z,
            bk.get("lookback", 24), self._bk_min_btc_mom, self._bk_chandelier_atr_mult,
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
        pairs = self.dp.current_whitelist() if self.dp else []
        btc_tf = self._cfg.get("btc_trend", {}).get("timeframe", "1h")
        return [(self.BTC_REF, btc_tf)]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]
        cycle_id = id(dataframe)
        if cycle_id != self._df_cache_cycle:
            self._df_cache.clear()
            self._df_cache_cycle = cycle_id
            self._btc_trend = {}
            self._cycle_state = {}

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
        breakout.compute(dataframe, self._cfg)

        if not dataframe.empty:
            last = dataframe.iloc[-1]
            self._cycle_state[pair] = {
                "z": float(last.get("basket_z", 0)),
                "breakout": int(last.get("breakout_long", 0)),
                "donchian_high": float(last.get("donchian_high", 0) or 0),
                "close": float(last.get("close", 0)),
            }

            if len(self._cycle_state) >= len(self._basket_pairs) - 1:
                btc_mom = float(last.get("btc_mom", 0))
                pump = bool(last.get("btc_pump", False))
                dump = bool(last.get("btc_dump", False))
                chaos = bool(last.get("btc_high_vol", False))

                z_parts = " | ".join(
                    f"{p.split('/')[0]}={s['z']:+.2f}{'^' if s['breakout'] else ''}"
                    for p, s in sorted(self._cycle_state.items())
                    if p != self.BTC_REF
                )

                entry_z = self._cfg["basket"]["entry_z"]
                short_signals = [
                    p.split('/')[0] for p, s in self._cycle_state.items()
                    if p != self.BTC_REF and s["z"] > entry_z
                ]
                long_signals = [
                    p.split('/')[0] for p, s in self._cycle_state.items()
                    if p != self.BTC_REF and s["breakout"]
                ]

                open_trades = Trade.get_trades_proxy(is_open=True)
                trades_str = ""
                if open_trades:
                    parts = []
                    for t in open_trades:
                        ts = self._get_ts(t.id)
                        kind = "BK" if ts.get("kind") == "breakout" else "MR"
                        sc = ts.get("scale_count", 0)
                        age = (datetime.now(timezone.utc) - t.open_date_utc).total_seconds() / 300
                        parts.append(
                            f"{t.pair.split('/')[0]}({'S' if t.is_short else 'L'}-{kind})[S{sc}] "
                            f"p={t.calc_profit_ratio(t.close_rate or t.open_rate) * 100:+.2f}% "
                            f"@{age:.0f}c"
                        )
                    trades_str = " | ".join(parts)

                logger.info(
                    "TICK z=[%s] | BTC mom=%.2f pump=%s dump=%s chaos=%s | "
                    "short=%s | long=%s | open=%d/%d [%s]",
                    z_parts, btc_mom, pump, dump, chaos,
                    ",".join(short_signals) or "none",
                    ",".join(long_signals) or "none",
                    len(open_trades), self._max_positions,
                    trades_str or "none",
                )
                self._cycle_state = {}

        return dataframe

    # ────────────────────────── Entries ──────────────────────────

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe["enter_tag"] = ""

        if pair == self.BTC_REF or dataframe.empty:
            return dataframe

        vol_ok = dataframe.get("vol_ok", pd.Series(1, index=dataframe.index)) == 1
        no_chaos = ~dataframe.get("btc_high_vol", pd.Series(False, index=dataframe.index)).astype(bool)
        btc_pump = dataframe.get("btc_pump", pd.Series(False, index=dataframe.index)).astype(bool)
        btc_dump = dataframe.get("btc_dump", pd.Series(False, index=dataframe.index)).astype(bool)
        btc_mom = dataframe.get("btc_mom", pd.Series(0.0, index=dataframe.index))

        # SHORT — mean reversion
        if "basket_z" in dataframe.columns:
            entry_z = self._cfg["basket"]["entry_z"]
            is_leading = dataframe["basket_z"] > entry_z
            mask_short = is_leading & ~btc_pump & no_chaos & vol_ok
            dataframe.loc[mask_short, ["enter_short", "enter_tag"]] = (1, "hybrid_short_mr")

        # LONG — breakout
        if not self._bk_disable_long and "breakout_strong" in dataframe.columns:
            is_breakout = dataframe["breakout_strong"] == 1
            trend_up = dataframe.get("trend_up", pd.Series(1, index=dataframe.index)) == 1
            mom_ok = btc_mom > self._bk_min_btc_mom
            atr_z = dataframe.get("atr_z", pd.Series(0.0, index=dataframe.index))
            atr_z_ok = atr_z >= self._bk_min_atr_z
            mask_long = is_breakout & mom_ok & trend_up & atr_z_ok & ~btc_dump & no_chaos & vol_ok
            dataframe.loc[mask_long, ["enter_long", "enter_tag"]] = (1, "hybrid_long_bk")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    # ────────────────────────── Helpers ──────────────────────────

    def _get_indicator_at(self, pair: str, current_time, column: str, default: float = 0.0) -> float:
        if not self.dp:
            return default
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or df.empty or column not in df.columns:
            return default
        ct = pd.Timestamp(current_time)
        if df["date"].dt.tz is not None:
            ct = ct.tz_localize("UTC") if ct.tz is None else ct.tz_convert("UTC")
        mask = df["date"] <= ct
        if not mask.any():
            return default
        val = df[column].iloc[mask.sum() - 1]
        try:
            return float(val)
        except (TypeError, ValueError):
            return default

    def _get_current_z(self, pair: str, current_time) -> float | None:
        v = self._get_indicator_at(pair, current_time, "basket_z", default=float("nan"))
        return None if v != v else v

    def _get_btc_mom(self, pair: str, current_time) -> float:
        return self._get_indicator_at(pair, current_time, "btc_mom", 0.0)

    def _get_atr(self, pair: str, current_time) -> float:
        return self._get_indicator_at(pair, current_time, "atr", 0.0)

    def _get_donchian_high(self, pair: str, current_time) -> float:
        return self._get_indicator_at(pair, current_time, "donchian_high", 0.0)

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float,
                            rate: float, time_in_force: str, current_time: datetime,
                            entry_tag: Optional[str], side: str, **kwargs) -> bool:
        open_trades = Trade.get_trades_proxy(is_open=True)
        if len(open_trades) >= self._max_positions:
            logger.info(
                "ENTRY REJECT %s %s — max positions %d/%d",
                pair, side, len(open_trades), self._max_positions,
            )
            return False
        if pair in {t.pair for t in open_trades}:
            logger.info("ENTRY REJECT %s %s — already open", pair, side)
            return False

        if self._cooldown_minutes > 0:
            last_exit = _winner_cooldowns.get((pair, side))
            if last_exit is not None:
                elapsed_min = (current_time - last_exit).total_seconds() / 60.0
                if elapsed_min < self._cooldown_minutes:
                    logger.info(
                        "ENTRY REJECT %s %s — cooldown %.0f/%.0fmin",
                        pair, side, elapsed_min, self._cooldown_minutes,
                    )
                    return False

        # Pair-cooldown after N consecutive losses
        if self._cooldown_pair_minutes > 0:
            pair_lock = _pair_cooldowns.get((pair, side))
            if pair_lock is not None:
                elapsed_min = (current_time - pair_lock).total_seconds() / 60.0
                if elapsed_min < self._cooldown_pair_minutes:
                    streak = _loss_streaks.get((pair, side), 0)
                    logger.info(
                        "ENTRY REJECT %s %s — pair locked %.0f/%.0fmin (%d consecutive losses)",
                        pair, side, elapsed_min, self._cooldown_pair_minutes, streak,
                    )
                    return False

        if self._min_entry_notional > 0 and amount * rate < self._min_entry_notional:
            return False

        # Twin filter (mean-rev shorts only): require another pair at the
        # opposite z-extreme to confirm the basket is genuinely dispersed
        # (not a single-pair anomaly).
        if side == "short" and self._require_twin_for_short:
            entry_z = self._cfg["basket"]["entry_z"]
            open_pairs = {t.pair for t in open_trades}
            twin_match = None
            for p in self._basket_pairs:
                if p == self.BTC_REF or p == pair or p in open_pairs:
                    continue
                z = self._get_current_z(p, current_time)
                if z is None:
                    continue
                if z < -entry_z:
                    twin_match = (p, z)
                    break
            if not twin_match:
                my_z = self._get_current_z(pair, current_time)
                logger.info(
                    "ENTRY REJECT %s short z=%.3f — no twin opposite (need z<%.2f)",
                    pair, my_z or 0, -entry_z,
                )
                return False

        kind = "breakout" if side == "long" else "mean_rev"
        logger.info(
            "ENTRY CONFIRM %s %s (%s) tag=%s | rate=%.5f $%.2f",
            pair, side, kind, entry_tag or "?", rate, amount * rate,
        )
        return True

    # ────────────────────────── Stake ──────────────────────────

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float],
                            max_stake: float, leverage: float, entry_tag: Optional[str],
                            side: str, **kwargs) -> float:
        if side == "long":
            stake = self._bk_initial_stake
            if min_stake and stake < min_stake:
                stake = min_stake
            return min(stake, max_stake * 0.3)

        # short: tiered by z-strength (V4 logic)
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

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float,
                 entry_tag: Optional[str], side: str, **kwargs) -> float:
        tc = self._cfg.get("twin", {})
        default_lev = tc.get("initial_leverage", 3)
        if side == "short":
            lev = tc.get("short_leverage", default_lev)
        else:
            lev = tc.get("long_leverage", default_lev)
        return float(max(1, min(int(lev), int(max_leverage))))

    # ────────────────────────── Trade state ──────────────────────────

    def _get_ts(self, trade_id: int, kind: str | None = None) -> dict:
        global _trade_state
        if trade_id not in _trade_state:
            _trade_state[trade_id] = {
                "kind": kind,
                "evaluated": False,
                "is_winner": None,
                "scale_count": 0,
                "entry_z": None,
                "last_scale_z": None,
                "peak_profit": 0.0,
                "peak_price": None,
            }
        elif kind and _trade_state[trade_id].get("kind") is None:
            _trade_state[trade_id]["kind"] = kind
        return _trade_state[trade_id]

    def _kind_for(self, trade: Trade) -> str:
        tag = (trade.enter_tag or "").lower()
        if "long_bk" in tag or "breakout" in tag:
            return "breakout"
        if "short_mr" in tag or "mean" in tag:
            return "mean_rev"
        return "breakout" if not trade.is_short else "mean_rev"

    # ────────────────────────── Position scaling ──────────────────────────

    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: Optional[float], max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs) -> Optional[float]:
        kind = self._kind_for(trade)
        ts = self._get_ts(trade.id, kind=kind)
        ts["peak_profit"] = max(ts["peak_profit"], current_profit)

        if kind == "breakout":
            return self._adjust_breakout(trade, current_time, current_rate,
                                         current_profit, min_stake, max_stake, ts)
        return self._adjust_mean_rev(trade, current_time, current_rate,
                                     current_profit, min_stake, max_stake, ts)

    def _adjust_breakout(self, trade: Trade, current_time, current_rate, current_profit,
                         min_stake, max_stake, ts) -> Optional[float]:
        if not (not trade.is_short):
            return None
        if ts["scale_count"] >= self._bk_max_scale_times:
            return None
        if current_profit < self._bk_scale_at_profit:
            return None

        donchian = self._get_donchian_high(trade.pair, current_time)
        if self._bk_scale_breakout_required and donchian > 0:
            # only scale if price made a new high since entry
            if current_rate <= donchian:
                return None

        add = min(self._bk_scale_stake, max_stake)
        if min_stake and add < min_stake:
            add = min_stake
        ts["scale_count"] += 1
        logger.info(
            "BK-SCALE[%d/%d] %s | rate=%.5f profit=%.2f%% | +$%.2f",
            ts["scale_count"], self._bk_max_scale_times, trade.pair,
            current_rate, current_profit * 100, add,
        )
        return add

    def _adjust_mean_rev(self, trade: Trade, current_time, current_rate, current_profit,
                         min_stake, max_stake, ts) -> Optional[float]:
        trade_age = (current_time - trade.open_date_utc).total_seconds() / 300

        if ts["entry_z"] is None:
            z = self._get_current_z(trade.pair, current_time)
            if z is not None:
                ts["entry_z"] = z

        if not ts["evaluated"] and trade_age >= self._eval_candles:
            ts["evaluated"] = True
            ts["is_winner"] = current_profit >= self._min_winner_profit
            logger.info(
                "MR-EVAL %s %s[%s] profit=%.2f%% z_entry=%.3f @%.0fc",
                trade.pair, "S" if trade.is_short else "L",
                "W" if ts["is_winner"] else "L",
                current_profit * 100, ts["entry_z"] or 0, trade_age,
            )

        max_scales = self._cfg.get("twin", {}).get("max_scale_times", 1)
        if (ts["is_winner"]
                and ts["scale_count"] < max_scales
                and ts["entry_z"] is not None
                and current_profit >= self._scale_min_profit):

            current_z = self._get_current_z(trade.pair, current_time)
            if current_z is None:
                return None

            entry_z = ts["entry_z"]
            # short: z_delta = entry_z - current_z (z dropping from positive toward 0)
            z_delta = entry_z - current_z if trade.is_short else current_z - entry_z
            scale_n = ts["scale_count"]
            z_threshold = self._z_revert_min * (1.0 + scale_n * 0.8)

            if ts["last_scale_z"] is not None:
                z_since = (ts["last_scale_z"] - current_z) if trade.is_short else (current_z - ts["last_scale_z"])
                if z_since < self._z_revert_min * 0.3:
                    return None

            if z_delta >= z_threshold:
                ts["scale_count"] += 1
                ts["last_scale_z"] = current_z
                add = min(self._scale_stake, max_stake)
                if min_stake and add < min_stake:
                    add = min_stake
                logger.info(
                    "MR-SCALE[%d/%d] %s | z: %.3f -> %.3f (delta=%.3f >= %.2f) | "
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
        kind = self._kind_for(trade)
        ts = self._get_ts(trade.id, kind=kind)
        if kind == "breakout":
            return self._bk_safety_stop
        if not ts["evaluated"]:
            return self._safety_stop
        return self._safety_stop

    # ────────────────────────── Exit ──────────────────────────

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        kind = self._kind_for(trade)
        ts = self._get_ts(trade.id, kind=kind)
        ts["peak_profit"] = max(ts["peak_profit"], current_profit)

        if kind == "breakout":
            return self._exit_breakout(pair, trade, current_time, current_rate,
                                       current_profit, ts)
        return self._exit_mean_rev(pair, trade, current_time, current_rate,
                                   current_profit, ts)

    def _exit_breakout(self, pair, trade, current_time, current_rate,
                       current_profit, ts) -> Optional[str]:
        trade_age = (current_time - trade.open_date_utc).total_seconds() / 300

        if current_profit < self._bk_safety_stop:
            return "bk_max_loss"

        # track peak price (for chandelier)
        peak = ts.get("peak_price") or trade.open_rate
        if current_rate > peak:
            peak = current_rate
            ts["peak_price"] = peak

        atr = self._get_atr(pair, current_time)

        # Chandelier exit: peak - atr_mult * ATR (only after some profit)
        if (current_profit >= self._bk_chandelier_min_profit
                and atr > 0):
            chandelier = peak - atr * self._bk_chandelier_atr_mult
            if current_rate < chandelier:
                return "bk_chandelier"

        # Invalidation: price falls back inside the box (close < donchian_high - buffer*ATR)
        if current_profit > self._bk_min_profit_for_invalidation:
            donchian = self._get_donchian_high(pair, current_time)
            if donchian > 0 and atr > 0:
                invalidation = donchian - atr * self._bk_invalidation_buffer
                if current_rate < invalidation:
                    return "bk_invalidation"

        # Time stop
        if trade_age >= self._bk_max_candles:
            return "bk_time_stop"

        # Heartbeat log
        if trade_age > 0 and trade_age % 6 < 0.2:
            atr_pct = (atr / current_rate * 100) if current_rate > 0 else 0
            btc_mom = self._get_btc_mom(pair, current_time)
            logger.info(
                "BK-HOLD %s L[BK+S%d] @%.0fc | rate=%.5f peak=%.5f atr%%=%.2f | "
                "profit=%.2f%% peak=%.2f%% | btc_mom=%.2f | time_left=%.0fc",
                pair, ts.get("scale_count", 0), trade_age,
                current_rate, peak, atr_pct,
                current_profit * 100, ts.get("peak_profit", 0) * 100, btc_mom,
                self._bk_max_candles - trade_age,
            )
        return None

    def _exit_mean_rev(self, pair, trade, current_time, current_rate,
                       current_profit, ts) -> Optional[str]:
        trade_age = (current_time - trade.open_date_utc).total_seconds() / 300
        z = self._get_current_z(pair, current_time)
        is_long = not trade.is_short
        side = "L" if is_long else "S"
        label = "W" if ts.get("is_winner") else ("L" if ts.get("is_winner") is False else "?")
        sc = ts.get("scale_count", 0)

        if current_profit < self._safety_stop:
            return "mr_max_loss"

        # V8: z worsening — z moved further away from reversion (got more extreme)
        if (self._z_worsen_mult > 0 and ts.get("entry_z") is not None
                and z is not None):
            entry_z = ts["entry_z"]
            # For short (entry_z > 0): bad if z keeps going up past entry_z * mult
            # For long  (entry_z < 0): bad if z keeps going down past entry_z * mult
            if not is_long and entry_z > 0 and z > entry_z * self._z_worsen_mult:
                return "mr_z_worsening"
            if is_long and entry_z < 0 and z < entry_z * self._z_worsen_mult:
                return "mr_z_worsening"

        if ts["evaluated"] and not ts["is_winner"]:
            if trade_age >= self._loser_max_candles:
                return "mr_loser_close"

        # V8: stale short — trade aged enough but z still hasn't reverted enough
        if (self._stale_exit_after > 0 and trade_age >= self._stale_exit_after
                and ts.get("entry_z") is not None and z is not None):
            entry_z = ts["entry_z"]
            # short: stale if z still above stale_z_threshold (hasn't reverted close to 0)
            # long:  stale if z still below -stale_z_threshold
            if not is_long and entry_z > 0 and z > self._stale_z_threshold:
                return "mr_stale"
            if is_long and entry_z < 0 and z < -self._stale_z_threshold:
                return "mr_stale"

        if ts["is_winner"]:
            if z is not None and current_profit > 0.003:
                if is_long and z > -self._winner_exit_z:
                    return "mr_winner_revert"
                if not is_long and z < self._winner_exit_z:
                    return "mr_winner_revert"
            if sc > 0 and current_profit > 0.018 and trade_age > 8:
                btc_mom = self._get_btc_mom(pair, current_time)
                if is_long and btc_mom < -3.5:
                    return "mr_mom_reverse"
                if not is_long and btc_mom > 3.5:
                    return "mr_mom_reverse"

        if trade_age >= self._max_candles_short:
            return "mr_time_stop"

        if trade_age > 0 and trade_age % 1 < 0.2:
            z_entry = ts.get("entry_z", 0) or 0
            z_delta = 0.0
            if z is not None and z_entry:
                z_delta = (z - z_entry) if is_long else (z_entry - z)
            btc_mom = self._get_btc_mom(pair, current_time)
            logger.info(
                "MR-HOLD %s %s[%s+S%d] @%.0fc | z=%.3f entry_z=%.3f delta=%.3f | "
                "profit=%.2f%% peak=%.2f%% $%.2f | btc_mom=%.2f | time_left=%.0fc",
                pair, side, label, sc, trade_age,
                z or 0, z_entry, z_delta,
                current_profit * 100, ts.get("peak_profit", 0) * 100,
                trade.stake_amount, btc_mom,
                self._max_candles_short - trade_age,
            )
        return None

    def confirm_trade_exit(self, pair: str, trade: Trade, order_type: str,
                           amount: float, rate: float, time_in_force: str,
                           exit_reason: str, current_time: datetime, **kwargs) -> bool:
        kind = self._kind_for(trade)
        ts = self._get_ts(trade.id, kind=kind)
        profit = trade.calc_profit_ratio(rate)
        sc = ts.get("scale_count", 0)
        scaled = f"+S{sc}" if sc > 0 else ""
        kind_tag = "BK" if kind == "breakout" else "MR"
        logger.info(
            "CLOSE %s %s-%s[%s%s] profit=%.2f%% $%.2f lev=%.0fx | %s",
            pair, "S" if trade.is_short else "L", kind_tag,
            "W" if ts.get("is_winner") else ("L" if ts.get("is_winner") is False else "?"),
            scaled, profit * 100, trade.stake_amount, trade.leverage, exit_reason,
        )
        side = "short" if trade.is_short else "long"
        if self._cooldown_minutes > 0 and exit_reason in ("mr_winner_revert", "bk_chandelier"):
            _winner_cooldowns[(pair, side)] = current_time

        # V8: loss-streak tracking + pair cooldown
        if self._cooldown_after_n_losses > 0:
            key = (pair, side)
            if profit < 0:
                _loss_streaks[key] = _loss_streaks.get(key, 0) + 1
                if _loss_streaks[key] >= self._cooldown_after_n_losses:
                    _pair_cooldowns[key] = current_time
                    logger.info(
                        "PAIR LOCK %s %s — %d consecutive losses, locked for %.0fmin",
                        pair, side, _loss_streaks[key], self._cooldown_pair_minutes,
                    )
                    _loss_streaks[key] = 0  # reset after locking
            else:
                # winning trade resets the streak
                _loss_streaks[key] = 0
        return True
