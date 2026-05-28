"""
ZScoreV64Strategy — Always-On Queue with Regime Scoring (Vectorized)
=====================================================================

All pairs always ranked in LONG/SHORT queues by z-score sign.
Score = raw_score * regime_multiplier. Only #1 enters per candle.

Entry signals computed vectorized in populate_entry_trend (fast backtesting).
Queue ranking done once per candle cycle for all pairs simultaneously.
"""
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from pandas import DataFrame

_STRATEGIES_DIR = str(Path(__file__).resolve().parent)
if _STRATEGIES_DIR not in sys.path:
    sys.path.insert(0, _STRATEGIES_DIR)

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy

from zscore_v59 import btc_trend, volume, basket, config as cfg_loader, dca, entry_queue
from zscore_v59.stake import DynamicStake
from zscore_v59.state import StrategyState
from zscore_v54b import zscore as v54_zscore
from zscore_v54b import exits as v54_exits
from lib import regime as regime_mod

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent / "v64_config.json"


class ZScoreV64Strategy(IStrategy):

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
    max_entry_position_adjustment = 3

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        c = cfg_loader.load(CONFIG_PATH)
        self._cfg = c
        self._basket_pairs: list[str] = c["basket"]["pairs"]
        self.BTC_REF: str = c["basket"]["btc_ref"]
        self.timeframe = c.get("timeframe", "5m")
        self.startup_candle_count = c.get("startup_candle_count", 900)
        self.stoploss = c["risk"]["stoploss"]
        self.max_entry_position_adjustment = c.get("dca", {}).get("max_adds", 3)

        self._df_cache: dict[str, DataFrame] = {}
        self._df_cache_cycle: int = 0
        self._btc_trend: dict = {}
        self._queue_signals: dict[str, tuple] = {}
        self._pair_zscores: dict[str, DataFrame] = {}
        self._peak_profit: dict[str, float] = {}
        self._pending_features: dict[str, list] = {}
        self._trade_history: list[dict] = []
        self._ranging_cooldown: dict[str, datetime] = {}  # per-group cooldown

        # Ranging groups from config
        rg = c.get("v64_regime", {}).get("ranging_groups", {})
        self._ranging_groups: list[dict] = []
        for gname, gsubs in rg.items():
            self._ranging_groups.append({
                "name": gname,
                "sub1": gsubs.get("sub1", []),
                "sub2": gsubs.get("sub2", []),
            })

        run_id = f"v59_{self.timeframe}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        self._state = StrategyState(run_id)
        self._state.initial_balance = 100.0
        self._state.balance = 100.0
        self._dynamic_stake = DynamicStake(c)

        if "queue" in self.config:
            c["queue"] = {**c.get("queue", {}), **self.config["queue"]}
        if "leverage" in self.config:
            c["leverage"] = {**c.get("leverage", {}), **self.config["leverage"]}
        if "risk" in self.config:
            c["risk"] = {**c.get("risk", {}), **self.config["risk"]}
        if "basket" in self.config:
            c["basket"] = {**c.get("basket", {}), **self.config["basket"]}

        entry_queue.reset()
        logger.info("V59 loaded — %d pairs, always-on queue, min_score=%.2f",
                     len(self._basket_pairs), c.get("queue", {}).get("min_score", 0.45))

    def _v54_exit_cfg(self) -> dict:
        """Build V54-compatible config for exits.check_exit."""
        return {
            "fast_exit": {"enabled": False},
            "consolidation": {
                "consol_zscore_entry": 99.0,
                "consol_pair_z_entry": 99.0,
                "consol_time_stop_candles": 12,
                "loss_cooldown_hours": 0,
            },
            "exits": {
                "mkt_stop_loss_threshold": -0.003,
                "mkt_stop_regime_loss": -0.008,
                "catastrophic_loss_threshold": -0.05,
                "dyn_roi_high_z_min": 3.0,
                "dyn_roi_high_z_profit": 0.015,
                "dyn_roi_high_z_minutes": 30,
                "dyn_roi_mid_z_min": 2.7,
                "dyn_roi_mid_z_profit": 0.013,
                "dyn_roi_mid_z_minutes": 20,
                "roi_gate_high_z_minutes": 20,
                "roi_gate_high_z_profit": 0.015,
                "roi_gate_mid_z_minutes": 15,
                "roi_gate_mid_z_profit": 0.013,
            },
            "zscore": {
                "zscore_scalp_min_profit": 0.012,
                "zscore_scalp_exit_threshold": 0.2,
            },
            "no_reversion_exit": {"enabled": False},
            "btc_fast_exit": {"enabled": False},
            "groups": {"btc_ref": self.BTC_REF},
        }

    def _v54_regime_cfg(self) -> dict:
        """Build V54-compatible regime config from v64_regime section."""
        rc = self._cfg.get("v64_regime", {}).get("regime", {})
        return {"regime": {
            "regime_window": rc.get("regime_window", 288),
            "regime_corr_min": rc.get("regime_corr_min", 0.4),
            "use_ewm_corr": rc.get("use_ewm_corr", True),
            "ewm_span": rc.get("ewm_span", 288),
            "spread_vol_filter": rc.get("spread_vol_filter", False),
            "spread_vol_window": rc.get("spread_vol_window", 144),
            "spread_vol_max_z": rc.get("spread_vol_max_z", 2.5),
        }}

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
            self._queue_signals = {}

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

        # Compute per-pair score as dataframe column (used by confirm_trade_entry)
        import numpy as np
        if "basket_z" in dataframe.columns:
            weights = self._cfg.get("queue", {}).get("weights", {})
            bz_abs = np.abs(dataframe["basket_z"].values)
            bz_norm = np.minimum(bz_abs, 4.0) / 4.0

            vr = dataframe["vol_ratio"].values if "vol_ratio" in dataframe.columns else np.ones(len(dataframe))
            vol_norm = np.minimum(vr, 3.0) / 3.0

            bz_vals = dataframe["basket_z"].values
            bz_prev3 = np.roll(bz_vals, 3)
            bz_prev3[:3] = bz_vals[:3]
            vel_norm = np.minimum(np.abs(bz_vals - bz_prev3), 2.0) / 2.0

            cd_norm = np.ones(len(dataframe))  # simplified: no cooldown in vectorized

            score = (weights.get("basket_z", 0.5) * bz_norm +
                     weights.get("vol_ratio", 0.2) * vol_norm +
                     weights.get("spread_velocity", 0.2) * vel_norm +
                     weights.get("cooldown", 0.1) * cd_norm)
            dataframe["queue_score"] = score

        # --- V54 Ranging: curated group spread z-scores + safety filters ---
        regime_cfg = self._cfg.get("v64_regime", {})
        if regime_cfg.get("enable_v54_ranging", False) and self._ranging_groups:
            # Per-pair z-score (needed for pair_z confirmation)
            v54_cfg = self._cfg.copy()
            # Inject V54-compatible zscore config
            if "cum_return_window" not in v54_cfg.get("zscore", {}):
                v54_cfg["zscore"]["cum_return_window"] = 24
            g0 = self._ranging_groups[0]
            v54_zscore.compute(
                dataframe, pair, v54_cfg, self.dp,
                self._pair_zscores, self._df_cache,
                g0["sub1"], g0["sub2"],
            )

            # Per-group spread z-score
            for g in self._ranging_groups:
                col = f"spread_z_{g['name'].lower()}"
                dataframe[col] = v54_zscore.compute_group_spread_z(
                    dataframe, pair, v54_cfg, self.dp,
                    self._df_cache, g["sub1"], g["sub2"],
                )

            # Regime filter (rolling correlation between sub1[0] vs sub2[0])
            regime_mod.compute(
                dataframe, pair, self._v54_regime_cfg(), self.dp,
                self._df_cache, self.timeframe,
                g0["sub1"], g0["sub2"],
            )

            # Spread volatility filter
            regime_mod.compute_spread_vol(dataframe, self._v54_regime_cfg())

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """V59: mark all pairs with z!=0 as candidates. Queue filtering in confirm_trade_entry."""
        pair = metadata["pair"]
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe["enter_tag"] = ""

        if pair == self.BTC_REF or dataframe.empty or "basket_z" not in dataframe.columns:
            return dataframe

        regime_cfg = self._cfg.get("v64_regime", {})
        v61b_on = regime_cfg.get("enable_v61b_trending", True)
        v54_on = regime_cfg.get("enable_v54_ranging", False)

        # V61B: queue entries (bull/bear gated by basket thresholds)
        if v61b_on:
            basket.generate_basket_entries(dataframe, pair, self._cfg)
            mask_long = dataframe["enter_tag"] == "basket_long"
            mask_short = dataframe["enter_tag"] == "basket_short"
            dataframe.loc[mask_long, "enter_tag"] = "queue_long"
            dataframe.loc[mask_short, "enter_tag"] = "queue_short"

        # V54 ranging: curated groups with full V54 safety filters
        if v54_on and "btc_mom" in dataframe.columns:
            ranging_entry_z = regime_cfg.get("ranging_entry_z", 2.1)
            ranging_pair_z = regime_cfg.get("ranging_pair_z", 1.2)
            ranging_mom_max = regime_cfg.get("ranging_mom_max", 2.0)
            entry_modes = regime_cfg.get("ranging_entry_modes", {})
            rg = regime_cfg.get("ranging_groups", {})

            # Regime classification (V54 exact: 3-way split)
            btc_mom = dataframe["btc_mom"]
            btc_atr_z = dataframe["btc_atr_z"] if "btc_atr_z" in dataframe.columns else 0
            trending_btc_mom = regime_cfg.get("trending_btc_mom", 2.0)
            trending_atr_z = regime_cfg.get("trending_atr_z", 2.0)
            is_trending = (btc_mom.abs() > trending_btc_mom) | (btc_atr_z > trending_atr_z)
            is_ranging = ~is_trending

            # Safety filters (V54 complete set)
            vol_ok = (dataframe["vol_ok"] == 1) if "vol_ok" in dataframe.columns else True
            regime_ok = (dataframe["regime_ok"] == 1) if "regime_ok" in dataframe.columns else True
            spread_vol_ok = (dataframe["spread_vol_ok"] == 1) if "spread_vol_ok" in dataframe.columns else True
            no_chaos = ~dataframe["btc_high_vol"] if "btc_high_vol" in dataframe.columns else True
            safe_long = (~dataframe["btc_dump"] if "btc_dump" in dataframe.columns else True) & no_chaos
            safe_short = (~dataframe["btc_pump"] if "btc_pump" in dataframe.columns else True) & no_chaos

            # Per-pair z-score confirmation
            pair_z_long = (dataframe["pair_zscore"] < -ranging_pair_z) if "pair_zscore" in dataframe.columns else True
            pair_z_short = (dataframe["pair_zscore"] > ranging_pair_z) if "pair_zscore" in dataframe.columns else True

            no_long = dataframe["enter_long"] == 0
            no_short = dataframe["enter_short"] == 0

            base = is_ranging & vol_ok & regime_ok & spread_vol_ok

            # Vol bounce: relaxed entry after volatility ends (V54 feature)
            vol_bounce_spread_min = self._cfg.get("btc_trend", {}).get("vol_bounce_spread_min", 1.5)

            for gname, gsubs in rg.items():
                col = f"spread_z_{gname.lower()}"
                if col not in dataframe.columns:
                    continue

                is_sub1 = pair in gsubs.get("sub1", [])
                is_sub2 = pair in gsubs.get("sub2", [])
                if not is_sub1 and not is_sub2:
                    continue

                spread_low = dataframe[col] < -ranging_entry_z
                spread_high = dataframe[col] > ranging_entry_z

                # Vol bounce: enter on relaxed spread after BTC volatility ends
                if "btc_vol_ended" in dataframe.columns:
                    vol_bounce_low = dataframe["btc_vol_ended"] & (dataframe[col] < -vol_bounce_spread_min)
                    vol_bounce_high = dataframe["btc_vol_ended"] & (dataframe[col] > vol_bounce_spread_min)
                    spread_low = spread_low | vol_bounce_low
                    spread_high = spread_high | vol_bounce_high

                gn = gname

                # Sub1 (a): long when spread low, short when spread high
                if is_sub1:
                    if entry_modes.get("sub1_long", True):
                        sig = base & spread_low & safe_long & pair_z_long & no_long
                        dataframe.loc[sig, ["enter_long", "enter_tag"]] = (1, f"mr_long_a_{gn}")
                    if entry_modes.get("sub1_short", False):
                        sig = base & spread_high & safe_short & pair_z_short & no_short
                        dataframe.loc[sig, ["enter_short", "enter_tag"]] = (1, f"mr_short_a_{gn}")

                # Sub2 (b): reverse direction
                elif is_sub2:
                    if entry_modes.get("sub2_short", True):
                        sig = base & spread_low & safe_short & pair_z_short & no_short
                        dataframe.loc[sig, ["enter_short", "enter_tag"]] = (1, f"mr_short_b_{gn}")
                    if entry_modes.get("sub2_long", True):
                        sig = base & spread_high & safe_long & pair_z_long & no_long
                        dataframe.loc[sig, ["enter_long", "enter_tag"]] = (1, f"mr_long_b_{gn}")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        tag = trade.enter_tag or ""

        # V54 ranging exits: ROI + V54 exits module
        if tag.startswith("mr_") or tag.startswith("ranging_"):
            trade_age_min = (current_time - trade.open_date_utc).total_seconds() / 60
            regime_cfg = self._cfg.get("v64_regime", {})

            # ROI escalonado (V54 built-in ROI replicated here)
            roi = regime_cfg.get("ranging_roi", {"0": 0.025, "3": 0.015, "10": 0.01, "20": 0.005})
            for minutes_str in sorted(roi.keys(), key=lambda x: int(x), reverse=True):
                if trade_age_min >= int(minutes_str):
                    if current_profit >= roi[minutes_str]:
                        return "roi"
                    break

            # V54 market-aware exits (mkt_stop_regime, time_stop, z-score scalp)
            v54_cfg = self._v54_exit_cfg()
            result = v54_exits.check_exit(
                pair, trade, current_time, current_rate, current_profit,
                v54_cfg, self.dp, self._btc_trend, self._peak_profit,
                self.timeframe, self._df_cache, self._pending_features,
            )
            return result

        # V61B queue exits: basket revert + time stop
        if tag.startswith("queue_"):
            orig_tag = trade.enter_tag
            trade.enter_tag = tag.replace("queue_", "basket_")
            result = basket.check_basket_exit(
                pair, trade, current_profit, self._cfg,
                self.dp, self._df_cache, self.timeframe, self._basket_pairs,
            )
            trade.enter_tag = orig_tag
            if result:
                return result
            max_candles = self._cfg.get("basket", {}).get("time_stop_candles", 24)
            trade_age = (current_time - trade.open_date_utc).total_seconds() / 300
            if trade_age >= max_candles:
                return "basket_time_stop"
            return None

        return None

    def confirm_trade_exit(self, pair: str, trade: Trade, order_type: str,
                           amount: float, rate: float, time_in_force: str,
                           exit_reason: str, current_time: datetime, **kwargs) -> bool:
        profit = trade.calc_profit_ratio(rate)
        tag = trade.enter_tag or ""

        # Set per-group cooldown on ranging loss exits
        if tag.startswith("mr_") and exit_reason in ("stop_loss", "mkt_stop_dump", "mkt_stop_pump", "mkt_stop_chaos"):
            from datetime import timedelta
            group_suffix = tag.split("_")[-1]
            self._ranging_cooldown[group_suffix] = current_time + timedelta(hours=0)

        self._state.record_trade(
            pair=pair, profit_ratio=profit, profit_abs=profit * trade.stake_amount,
            leverage=trade.leverage, entry_tag=tag,
            exit_reason=exit_reason, open_date=trade.open_date_utc,
            close_date=current_time, open_rate=trade.open_rate,
            close_rate=rate, is_short=trade.is_short,
        )
        self._state.save()
        return True

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float,
                            rate: float, time_in_force: str, current_time: datetime,
                            entry_tag: Optional[str], side: str, **kwargs) -> bool:
        """Queue gate for V61B + simple gate for V54 ranging."""
        tag = entry_tag or ""

        # V54 ranging trades: per-group limit (max 1 per group, max 2 total) + cooldown
        if tag.startswith("mr_"):
            open_trades = Trade.get_trades_proxy(is_open=True)
            regime_cfg = self._cfg.get("v64_regime", {})
            max_rg = regime_cfg.get("ranging_max_trades", 2)

            # Count open ranging trades
            rg_trades = [t for t in open_trades if (t.enter_tag or "").startswith("mr_")]
            if len(rg_trades) >= max_rg:
                return False
            if pair in {t.pair for t in open_trades}:
                return False

            # Per-group limit: max 1 trade per group (V54 behavior)
            group_suffix = tag.split("_")[-1]  # "A" or "B"
            group_open = sum(1 for t in rg_trades
                            if (t.enter_tag or "").endswith(f"_{group_suffix}"))
            if group_open >= 1:
                return False

            # Per-group cooldown (set after loss exits)
            cooldown_until = self._ranging_cooldown.get(group_suffix)
            if cooldown_until and current_time < cooldown_until:
                return False

            return True

        # V61B queue trades: full queue gate below
        modes = self._cfg.get("modes", {})
        pair_modes = modes.get("pairs", {})
        pm = pair_modes.get(pair, {"long": True, "short": True, "regime": "all"})

        # Direction check
        if side == "long" and not pm.get("long", True):
            return False
        if side == "short" and not pm.get("short", True):
            return False

        # Regime check: detect current regime from btc_mom
        pair_regime = pm.get("regime", "all")
        if pair_regime != "all" and pair_regime != "ref" and self.dp:
            import pandas as pd
            df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if df is not None and "btc_mom" in df.columns:
                ct = pd.Timestamp(current_time)
                if df["date"].dt.tz is not None:
                    ct = ct.tz_localize("UTC") if ct.tz is None else ct.tz_convert("UTC")
                mask = df["date"] <= ct
                if mask.any():
                    btc_mom = float(df["btc_mom"].iloc[mask.sum() - 1])
                    regime_cfg = self._cfg.get("v64_regime", {})
                    bull_th = regime_cfg.get("bull_threshold", 0.5)
                    bear_th = regime_cfg.get("bear_threshold", -0.5)

                    if btc_mom > bull_th:
                        current_regime = "bull"
                    elif btc_mom < bear_th:
                        current_regime = "bear"
                    else:
                        current_regime = "ranging"

                    # Check if pair's regime allows current market
                    allowed = pair_regime.split(",")
                    # "all" = wildcard, allows any regime
                    if "all" not in allowed and current_regime not in allowed:
                        return False

        open_trades = Trade.get_trades_proxy(is_open=True)
        max_pos = self._cfg.get("basket", {}).get("max_positions", 4)
        if len(open_trades) >= max_pos:
            return False
        if pair in {t.pair for t in open_trades}:
            return False

        # Max per side
        max_long = modes.get("max_long", 2)
        max_short = modes.get("max_short", 2)
        open_longs = sum(1 for t in open_trades if not t.is_short)
        open_shorts = sum(1 for t in open_trades if t.is_short)
        if side == "long" and open_longs >= max_long:
            return False
        if side == "short" and open_shorts >= max_short:
            return False
        if not self.dp:
            return False

        import pandas as pd
        queue_cfg = self._cfg.get("queue", {})
        min_score = queue_cfg.get("min_score", 0.45)
        mults = queue_cfg.get("regime_multipliers", {})

        ct = pd.Timestamp(current_time)
        is_long = side == "long"
        open_pairs = {t.pair for t in open_trades}

        # Get this pair's score at current candle
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or df.empty or "queue_score" not in df.columns:
            return False

        if df["date"].dt.tz is not None:
            ct = ct.tz_localize("UTC") if ct.tz is None else ct.tz_convert("UTC")
        mask = df["date"] <= ct
        if not mask.any():
            return False
        idx = mask.sum() - 1

        my_raw_score = float(df["queue_score"].iloc[idx])
        my_bz = float(df["basket_z"].iloc[idx])
        btc_mom = float(df["btc_mom"].iloc[idx]) if "btc_mom" in df.columns else 0.0

        # Determine regime
        if btc_mom > 0.0:
            regime = "bull"
        elif btc_mom <= -1.0:
            regime = "bear"
        else:
            regime = "ranging"

        # Ranging: enforce balanced 2L + 2S to reduce directional risk
        if regime == "ranging":
            max_per_side = queue_cfg.get("ranging_balance", {}).get("max_per_side", 2)
            open_longs = sum(1 for t in open_trades if not t.is_short)
            open_shorts = sum(1 for t in open_trades if t.is_short)
            if is_long and open_longs >= max_per_side:
                return False
            if not is_long and open_shorts >= max_per_side:
                return False

        side_key = "long" if is_long else "short"
        my_mult = mults.get(f"{regime}_{side_key}", 0.6)
        my_adj_score = my_raw_score * my_mult

        # Must pass min_score
        if my_adj_score < min_score:
            return False

        # Check if this pair is #1 in its queue (compare against all other pairs)
        for p in self._basket_pairs:
            if p == self.BTC_REF or p == pair or p in open_pairs:
                continue
            p_df, _ = self.dp.get_analyzed_dataframe(p, self.timeframe)
            if p_df is None or p_df.empty or "queue_score" not in p_df.columns:
                continue
            p_mask = p_df["date"] <= ct
            if not p_mask.any():
                continue
            p_idx = p_mask.sum() - 1
            p_raw = float(p_df["queue_score"].iloc[p_idx])
            p_bz = float(p_df["basket_z"].iloc[p_idx])

            # Only compare with pairs in the SAME queue (same side)
            if is_long and p_bz >= 0:
                continue  # this pair is in short queue, skip
            if not is_long and p_bz <= 0:
                continue  # this pair is in long queue, skip

            p_adj = p_raw * my_mult  # same regime multiplier
            if p_adj > my_adj_score:
                return False  # another pair has higher score → I'm not #1

        return True

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float,
                        after_fill: bool, **kwargs) -> float | None:
        """Progressive trailing stoploss — replaces basket_time_stop.

        Trailing: locks in profit when trade is winning.
        Time-decay: tightens stoploss as trade ages (losers exit earlier).

        Config: risk.trailing_stops = [
            {"after_minutes": 0,  "stop": -0.10, "trail_trigger": 0.005, "trail": -0.004},
            {"after_minutes": 30, "stop": -0.05, "trail_trigger": 0.005, "trail": -0.004},
            {"after_minutes": 60, "stop": -0.02, "trail_trigger": 0.005, "trail": -0.004},
            {"after_minutes": 90, "stop": -0.01, "trail_trigger": 0.005, "trail": -0.006},
        ]
        """
        tag = trade.enter_tag or ""

        # Ranging trades: V54-style -7% stoploss + trailing
        if tag.startswith("mr_") or tag.startswith("ranging_"):
            regime_cfg = self._cfg.get("v64_regime", {})
            sl = regime_cfg.get("ranging_stoploss", -0.07)
            trail = regime_cfg.get("ranging_trailing", 0.006)
            trail_offset = regime_cfg.get("ranging_trailing_offset", 0.012)
            if current_profit >= trail_offset:
                return -trail
            return sl

        # Queue trades: basket exits handle everything
        if tag.startswith("queue_"):
            return -0.99

        if not tag.startswith("queue_"):
            r = self._cfg["risk"]
            if current_profit >= r.get("trailing_stop_positive_offset", 0.012):
                return -r.get("trailing_stop_positive", 0.006)
            return r.get("stoploss", -0.07)

        # Queue trades: no trailing — basket exits (revert/time/max_loss) handle everything
        # Trailing interferes with mean-reversion logic and worsens results
        return -0.99

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float,
                 entry_tag: Optional[str], side: str, **kwargs) -> float:
        """Trade-type + Z-based leverage.

        BREAKOUT:       fixed max leverage (high conviction, sudden move)
        TRENDING:       z-based with trending range (moderate conviction)
        MEAN REVERSION: z-based with standard range (varies with z)

        Returned as an integer — Hyperliquid only accepts integer leverage,
        and floors silently otherwise, causing DB/exchange drift.
        """
        tag = entry_tag or ""

        # Ranging trades: fixed conservative leverage (V54 style)
        if tag.startswith("mr_") or tag.startswith("ranging_"):
            ranging_lev = self._cfg.get("v64_regime", {}).get("ranging_leverage", 5)
            return float(max(1, min(int(ranging_lev), int(max_leverage))))

        lev_cfg = self._cfg.get("leverage", {})
        type_cfg = lev_cfg.get("by_type", {})

        def _floor_lev(x: float) -> float:
            return float(max(1, min(int(x), int(max_leverage))))

        if not self.dp:
            return _floor_lev(lev_cfg.get("base_multiplier", 6.0))

        try:
            import pandas as pd
            import numpy as np
            df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if df is None or df.empty or "basket_z" not in df.columns:
                return _floor_lev(lev_cfg.get("base_multiplier", 6.0))

            ct = pd.Timestamp(current_time)
            if df["date"].dt.tz is not None:
                ct = ct.tz_localize("UTC") if ct.tz is None else ct.tz_convert("UTC")
            mask = df["date"] <= ct
            if not mask.any():
                return _floor_lev(lev_cfg.get("base_multiplier", 6.0))
            idx = mask.sum() - 1

            abs_z = abs(float(df["basket_z"].iloc[idx]))
            vol_ratio = float(df["vol_ratio"].iloc[idx]) if "vol_ratio" in df.columns else 1.0
            btc_mom = float(df["btc_mom"].iloc[idx]) if "btc_mom" in df.columns else 0.0
            btc_atr_z = float(df["btc_atr_z"].iloc[idx]) if "btc_atr_z" in df.columns else 0.0

            # Compute spread velocity
            bz_prev = float(df["basket_z"].iloc[idx - 3]) if idx >= 3 else float(df["basket_z"].iloc[idx])
            velocity = abs(float(df["basket_z"].iloc[idx]) - bz_prev)

            # Classify trade type
            if velocity >= 1.0 and vol_ratio >= 2.0:
                trade_type = "breakout"
            elif abs(btc_mom) >= 1.5 and btc_atr_z < 2.0:
                trade_type = "trending"
            else:
                trade_type = "mean_reversion"

            # Get type-specific leverage config
            tc = type_cfg.get(trade_type, {})
            t_min = tc.get("min", lev_cfg.get("min", 2.0))
            t_max = tc.get("max", lev_cfg.get("max", 8.0))
            t_z_min = tc.get("z_min", lev_cfg.get("z_min", 0.3))
            t_z_max = tc.get("z_max", lev_cfg.get("z_max", 2.0))

            # Linear interpolation by |z|
            if abs_z <= t_z_min:
                lev = t_min
            elif abs_z >= t_z_max:
                lev = t_max
            else:
                t = (abs_z - t_z_min) / (t_z_max - t_z_min)
                lev = t_min + t * (t_max - t_min)

            return _floor_lev(lev)
        except Exception:
            return _floor_lev(lev_cfg.get("base_multiplier", 6.0))

    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: Optional[float], max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs) -> Optional[float]:
        return dca.adjust_position(trade, current_profit, self._cfg, min_stake, max_stake)

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float],
                            max_stake: float, leverage: float, entry_tag: Optional[str],
                            side: str, **kwargs) -> float:
        open_trades = Trade.get_trades_proxy(is_open=True)
        stake = self._dynamic_stake.compute(
            wallets=self.wallets,
            stake_currency=self.config["stake_currency"],
            open_trade_count=len(open_trades),
            max_stake=max_stake,
            open_trades=open_trades,
        )
        if min_stake and stake < min_stake:
            stake = min_stake
        return stake
