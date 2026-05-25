"""
TwinPennies V4 — Aggressive Z-Confirmed Scaling
==================================================

V4 changes from V3:
    - Tiered entry stake based on z-score strength (not flat penny)
    - Smarter trailing: proportional to profit for scaled winners
    - Momentum-aware exit: BTC reversal protection
    - Larger scale ($75), more room (36 candles), lower z threshold (0.35)

Flow:
    1. Enter with tiered stake ($5-12) when |z| > entry_z
    2. After eval_candles, classify winner/loser by profit
    3. Losers: close fast (loser_max_candles)
    4. Winners: WAIT for z-score reversion >= z_revert_min
    5. Scale 1: +$75 at z_delta >= 0.35
    6. Scale 2: +$75 at z_delta >= 0.63 (deeper confirmation)
    7. Exit on z-reversion to ~0 or momentum reversal
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

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "twin_pennies_config.json"

_trade_state: dict[int, dict] = {}
_winner_cooldowns: dict[tuple[str, str], datetime] = {}


class TwinPenniesStrategy(IStrategy):

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
        self._cycle_zscores: dict[str, float] = {}

        tc = c.get("twin", {})
        self._eval_candles = tc.get("eval_candles", 2)
        self._max_positions = tc.get("max_positions", 4)
        self._winner_exit_z = tc.get("winner_exit_z", 0.08)
        self._max_candles = tc.get("max_candles", 36)
        self._loser_max_candles = tc.get("loser_max_candles", 4)
        self._safety_stop = tc.get("safety_stop", -0.045)
        self._min_winner_profit = tc.get("min_winner_profit", 0.0005)

        self._scale_stake = tc.get("scale_stake", 75.0)
        self._z_revert_min = tc.get("z_revert_min", 0.35)
        self._scale_min_profit = tc.get("scale_min_profit", 0.0003)

        self._cooldown_minutes = float(tc.get("cooldown_after_winner_minutes", 0))
        self._min_entry_notional = float(tc.get("min_entry_notional", 0))

        global _trade_state, _winner_cooldowns
        _trade_state = {}
        _winner_cooldowns = {}

        logger.info(
            "TwinPennies V4 — %d pairs, z_revert=%.2f, scale=$%.0f, "
            "exit_z=%.2f, max=%d candles",
            len(self._basket_pairs), self._z_revert_min,
            self._scale_stake, self._winner_exit_z, self._max_candles,
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
        return [(pair, "1d") for pair in pairs] + [(self.BTC_REF, btc_tf)]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]
        cycle_id = id(dataframe)
        if cycle_id != self._df_cache_cycle:
            self._df_cache.clear()
            self._df_cache_cycle = cycle_id
            self._btc_trend = {}
            self._cycle_zscores = {}

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

        # Log cycle summary on last pair processed
        if not dataframe.empty and "basket_z" in dataframe.columns:
            last = dataframe.iloc[-1]
            z = float(last.get("basket_z", 0))
            vol_ok = int(last.get("vol_ok", 0))
            self._cycle_zscores[pair] = z

            # Log full dashboard when all pairs are processed
            if len(self._cycle_zscores) >= len(self._basket_pairs) - 1:
                btc_mom = float(last.get("btc_mom", 0))
                btc_atr_z = float(last.get("btc_atr_z", 0))
                pump = bool(last.get("btc_pump", False))
                dump = bool(last.get("btc_dump", False))
                chaos = bool(last.get("btc_high_vol", False))

                z_parts = " | ".join(
                    f"{p.split('/')[0]}={v:+.2f}"
                    for p, v in sorted(self._cycle_zscores.items())
                    if p != self.BTC_REF
                )

                open_trades = Trade.get_trades_proxy(is_open=True)
                trades_str = ""
                if open_trades:
                    parts = []
                    for t in open_trades:
                        ts = self._get_ts(t.id)
                        lbl = "W" if ts.get("is_winner") else ("L" if ts.get("is_winner") is False else "?")
                        sc = ts.get("scale_count", 0)
                        age = (datetime.now(timezone.utc) - t.open_date_utc).total_seconds() / 300
                        parts.append(
                            f"{t.pair.split('/')[0]}({'S' if t.is_short else 'L'})[{lbl}+S{sc}] "
                            f"p={t.calc_profit_ratio(t.close_rate or t.open_rate) * 100:+.2f}% "
                            f"@{age:.0f}c"
                        )
                    trades_str = " | ".join(parts)

                entry_z = self._cfg["basket"]["entry_z"]
                signals = [
                    p.split('/')[0] for p, v in self._cycle_zscores.items()
                    if p != self.BTC_REF and abs(v) > entry_z
                ]

                logger.info(
                    "TICK z=[%s] | BTC mom=%.2f atr_z=%.2f pump=%s dump=%s chaos=%s | "
                    "signals=%s | open=%d/%d [%s]",
                    z_parts, btc_mom, btc_atr_z, pump, dump, chaos,
                    ",".join(signals) or "none",
                    len(open_trades), self._max_positions,
                    trades_str or "none",
                )
                self._cycle_zscores = {}

        return dataframe

    # ────────────────────────── Entries ──────────────────────────

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
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
        mask_long = is_lagging & safe_long & no_chaos & vol_ok
        dataframe.loc[mask_long, ["enter_long", "enter_tag"]] = (1, "twin_long")

        is_leading = dataframe["basket_z"] > entry_z
        safe_short = ~dataframe.get("btc_pump", pd.Series(False, index=dataframe.index)).astype(bool)
        mask_short = is_leading & safe_short & no_chaos & vol_ok
        dataframe.loc[mask_short, ["enter_short", "enter_tag"]] = (1, "twin_short")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    # ────────────────────────── Helpers ──────────────────────────

    def _get_current_z(self, pair: str, current_time) -> float | None:
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

    def _get_btc_mom(self, pair: str, current_time) -> float:
        """Get current BTC momentum from the pair's analyzed dataframe."""
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
                        "ENTRY REJECT %s %s — cooldown %.0f/%.0fmin since winner",
                        pair, side, elapsed_min, self._cooldown_minutes,
                    )
                    return False

        if self._min_entry_notional > 0:
            notional = amount * rate
            if notional < self._min_entry_notional:
                logger.info(
                    "ENTRY REJECT %s %s — notional $%.2f < min $%.2f",
                    pair, side, notional, self._min_entry_notional,
                )
                return False

        my_z = self._get_current_z(pair, current_time)
        entry_z = self._cfg["basket"]["entry_z"]
        open_pairs = {t.pair for t in open_trades}
        twin_match = None
        for p in self._basket_pairs:
            if p == self.BTC_REF or p == pair or p in open_pairs:
                continue
            z = self._get_current_z(p, current_time)
            if z is None:
                continue
            if side == "long" and z > entry_z:
                twin_match = (p, z)
                break
            if side == "short" and z < -entry_z:
                twin_match = (p, z)
                break

        if twin_match:
            logger.info(
                "ENTRY CONFIRM %s %s z=%.3f | twin=%s z=%.3f | rate=%.4f $%.2f lev=%s",
                pair, side, my_z or 0, twin_match[0], twin_match[1],
                rate, amount * rate, self._cfg.get("twin", {}).get("initial_leverage", 3),
            )
            return True

        logger.info(
            "ENTRY REJECT %s %s z=%.3f — no twin opposite (need |z|>%.1f)",
            pair, side, my_z or 0, entry_z,
        )
        return False

    # ────────────────────────── Tiered stake ──────────────────────────

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float],
                            max_stake: float, leverage: float, entry_tag: Optional[str],
                            side: str, **kwargs) -> float:
        """Tiered stake based on z-score strength. Stronger signal = larger penny."""
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

        # Evaluate
        if not ts["evaluated"] and trade_age >= self._eval_candles:
            ts["evaluated"] = True
            ts["is_winner"] = current_profit >= self._min_winner_profit
            label = "W" if ts["is_winner"] else "L"
            logger.info(
                "EVAL %s %s[%s] profit=%.2f%% z_entry=%.3f @%.0fc",
                trade.pair, "S" if trade.is_short else "L", label,
                current_profit * 100, ts["entry_z"] or 0, trade_age,
            )

        # Progressive scaling
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

            # Check z moved since last scale
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
        ts = self._get_ts(trade.id)

        if not ts["evaluated"]:
            return self._safety_stop

        # ALL: safety stop only — no trailing
        # Winners exit via z-reversion or momentum. Losers via loser_close.
        # This was proven best in V3 testing.
        return self._safety_stop

    # ────────────────────────── Exit ──────────────────────────

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        trade_age = (current_time - trade.open_date_utc).total_seconds() / 300
        ts = self._get_ts(trade.id)
        z = self._get_current_z(pair, current_time)
        is_long = not trade.is_short
        side = "L" if is_long else "S"
        label = "W" if ts.get("is_winner") else ("L" if ts.get("is_winner") is False else "?")
        sc = ts.get("scale_count", 0)

        # Max loss
        if current_profit < self._safety_stop:
            return "twin_max_loss"

        # LOSER: close fast
        if ts["evaluated"] and not ts["is_winner"]:
            if trade_age >= self._loser_max_candles:
                return "twin_loser_close"

        # WINNER exits
        if ts["is_winner"]:
            # Z-reversion exit (primary)
            if z is not None and current_profit > 0.003:
                if is_long and z > -self._winner_exit_z:
                    return "twin_winner_revert"
                if not is_long and z < self._winner_exit_z:
                    return "twin_winner_revert"

            # Momentum reversal protection (scaled winners only)
            if sc > 0 and current_profit > 0.018 and trade_age > 8:
                btc_mom = self._get_btc_mom(pair, current_time)
                if is_long and btc_mom < -3.5:
                    return "twin_mom_reverse"
                if not is_long and btc_mom > 3.5:
                    return "twin_mom_reverse"

        # Time stop
        if trade_age >= self._max_candles:
            return "twin_time_stop"

        # Log trade status every candle (no exit triggered)
        if trade_age > 0 and trade_age % 1 < 0.2:
            z_entry = ts.get("entry_z", 0) or 0
            z_delta = 0.0
            if z is not None and z_entry:
                z_delta = (z - z_entry) if is_long else (z_entry - z)
            btc_mom = self._get_btc_mom(pair, current_time)
            logger.info(
                "HOLD %s %s[%s+S%d] @%.0fc | z=%.3f entry_z=%.3f delta=%.3f | "
                "profit=%.2f%% peak=%.2f%% $%.2f | btc_mom=%.2f | "
                "time_left=%.0fc exit_z=%.2f",
                pair, side, label, sc, trade_age,
                z or 0, z_entry, z_delta,
                current_profit * 100, ts.get("peak_profit", 0) * 100,
                trade.stake_amount, btc_mom,
                self._max_candles - trade_age, self._winner_exit_z,
            )

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

        if self._cooldown_minutes > 0 and exit_reason == "twin_winner_revert":
            side = "short" if trade.is_short else "long"
            _winner_cooldowns[(pair, side)] = current_time

        return True
