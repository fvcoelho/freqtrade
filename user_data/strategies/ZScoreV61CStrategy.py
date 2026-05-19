"""
ZScoreV61CStrategy — Always-On Queue with Regime Scoring (Vectorized)
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

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent / "v61c_config.json"


class ZScoreV61CStrategy(IStrategy):

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

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """V59: mark all pairs with z!=0 as candidates. Queue filtering in confirm_trade_entry."""
        pair = metadata["pair"]
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe["enter_tag"] = ""

        if pair == self.BTC_REF or dataframe.empty or "basket_z" not in dataframe.columns:
            return dataframe

        # All z<0 → long candidate, z>0 → short candidate
        basket.generate_basket_entries(dataframe, pair, self._cfg)

        # Re-tag
        mask_long = dataframe["enter_tag"] == "basket_long"
        mask_short = dataframe["enter_tag"] == "basket_short"
        dataframe.loc[mask_long, "enter_tag"] = "queue_long"
        dataframe.loc[mask_short, "enter_tag"] = "queue_short"

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        """Consolidation pairs trade exit:
        - Winner: exit on basket revert (z crosses back) or take profit
        - Loser: exit on tight trailing (custom_stoploss handles) or time stop
        - Both: max loss safety net
        """
        tag = trade.enter_tag or ""
        if not tag.startswith("queue_"):
            return None

        trade_age = (current_time - trade.open_date_utc).total_seconds() / 300
        max_candles = self._cfg.get("basket", {}).get("time_stop_candles", 24)
        max_loss = self._cfg.get("basket", {}).get("max_loss_per_trade", -0.05)

        # Max loss safety net
        if current_profit <= max_loss:
            return "consol_max_loss"

        # Time stop
        if trade_age >= max_candles:
            return "consol_time_stop"

        # Check basket revert
        orig_tag = trade.enter_tag
        trade.enter_tag = tag.replace("queue_", "basket_")
        result = basket.check_basket_exit(
            pair, trade, current_profit, self._cfg,
            self.dp, self._df_cache, self.timeframe, self._basket_pairs,
        )
        trade.enter_tag = orig_tag

        if result == "basket_revert_profit":
            return "consol_winner"
        if result == "basket_revert_neutral":
            return "consol_neutral"

        # Winner take profit: lock in at +1%
        if current_profit >= 0.01:
            return "consol_take_profit"

        return None

    def confirm_trade_exit(self, pair: str, trade: Trade, order_type: str,
                           amount: float, rate: float, time_in_force: str,
                           exit_reason: str, current_time: datetime, **kwargs) -> bool:
        profit = trade.calc_profit_ratio(rate)
        self._state.record_trade(
            pair=pair, profit_ratio=profit, profit_abs=profit * trade.stake_amount,
            leverage=trade.leverage, entry_tag=trade.enter_tag or "",
            exit_reason=exit_reason, open_date=trade.open_date_utc,
            close_date=current_time, open_rate=trade.open_rate,
            close_rate=rate, is_short=trade.is_short,
        )
        self._state.save()
        return True

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float,
                            rate: float, time_in_force: str, current_time: datetime,
                            entry_tag: Optional[str], side: str, **kwargs) -> bool:
        """V61B logic + consolidation fallback: when regime is dead zone, enter 1L+1S paired."""
        modes = self._cfg.get("modes", {})
        allow_long = modes.get("allow_long", True)
        allow_short = modes.get("allow_short", True)

        # Per-pair override
        pair_modes = modes.get("pairs", {})
        if pair in pair_modes:
            pm = pair_modes[pair]
            allow_long = pm.get("long", allow_long)
            allow_short = pm.get("short", allow_short)

        if side == "long" and not allow_long:
            return False
        if side == "short" and not allow_short:
            return False

        open_trades = Trade.get_trades_proxy(is_open=True)
        max_pos = self._cfg.get("basket", {}).get("max_positions", 4)
        if len(open_trades) >= max_pos:
            return False
        if pair in {t.pair for t in open_trades}:
            return False

        # Max per side (V61B original)
        max_long = modes.get("max_long", 1)
        max_short = modes.get("max_short", 1)
        open_longs = sum(1 for t in open_trades if not t.is_short)
        open_shorts = sum(1 for t in open_trades if t.is_short)

        # Detect regime from current candle
        import pandas as pd
        btc_mom = 0.0
        if self.dp:
            df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if df is not None and "btc_mom" in df.columns:
                ct = pd.Timestamp(current_time)
                if df["date"].dt.tz is not None:
                    ct = ct.tz_localize("UTC") if ct.tz is None else ct.tz_convert("UTC")
                mask = df["date"] <= ct
                if mask.any():
                    btc_mom = float(df["btc_mom"].iloc[mask.sum() - 1])

        bull_th = self._cfg["basket"].get("bull_mom_threshold", 0.5)
        bear_th = self._cfg["basket"].get("bear_mom_threshold", -0.5)
        is_bull = btc_mom > bull_th
        is_bear = btc_mom < bear_th
        is_consol = not is_bull and not is_bear

        if is_consol:
            # CONSOLIDATION: paired 1L + 1S, relaxed entry
            if side == "long" and open_longs >= 1:
                return False
            if side == "short" and open_shorts >= 1:
                return False
            # In consolidation, skip min_score check — just need #1 in queue
            logger.info("CONSOL ENTRY: %s %s (btc_mom=%.2f)", pair, side, btc_mom)
        else:
            # NORMAL V61B: original max per side
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
        """Consolidation pairs trade stoploss:
        - Winner (profit > 0): loose stop, let it run
        - Loser (profit < 0): tight trailing to cut early
        - Time decay: tighten as trade ages
        """
        cpt = self._cfg.get("queue", {}).get("consol_pairs_trade", {})
        loser_trail = cpt.get("loser_trailing_stop", -0.02)

        open_trades = Trade.get_trades_proxy(is_open=True)
        my_trades = [t for t in open_trades if t.trade_id != trade.trade_id]

        if my_trades:
            other = my_trades[0]
            other_profit = other.calc_profit_ratio(other.close_rate or other.open_rate * (1 + (other.calc_profit_ratio(other.open_rate) or 0)))

            # I'm the LOSER — tight trailing stop
            if current_profit < 0 and (not my_trades or current_profit < 0):
                trade_age_min = (current_time - trade.open_date_utc).total_seconds() / 60
                # Tighten over time: -2% → -1.5% → -1%
                if trade_age_min > 60:
                    return -0.01
                elif trade_age_min > 30:
                    return -0.015
                return loser_trail

        # Winner or solo trade: standard basket stop
        max_loss = self._cfg.get("basket", {}).get("max_loss_per_trade", -0.05)
        if current_profit >= 0.005:
            return -0.003  # lock in profit with tight trail
        return max_loss

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
