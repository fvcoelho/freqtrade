"""
BetaV59PlusStrategy — V59 + Regime-Aware Improvements
=======================================================

Improvements over BetaV59:
    A. Consolidation/Trending regime detection (ADX, BB squeeze, ATR)
    B. Dynamic entry_z, min_score, exit_z per regime
    C. RSI + z-crossing confirmation in consolidation
    D. Leverage cap in consolidation
    E. Adaptive z-score window (shorter in consol)
    F. Basket dispersion filter (blocks entries when basket is tight)
    G. Faster exits in consolidation (tighter exit_z, shorter time_stop)
"""
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from pandas import DataFrame

_STRATEGIES_DIR = str(Path(__file__).resolve().parent.parent)
if _STRATEGIES_DIR not in sys.path:
    sys.path.insert(0, _STRATEGIES_DIR)

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy

from beta_v59_plus import btc_trend, volume, basket, config as cfg_loader, dca, entry_queue
from beta_v59_plus import leverage as lev_module
from beta_v59_plus.stake import DynamicStake
from beta_v59_plus.state import StrategyState

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "beta_v59_plus_config.json"


class BetaV59PlusStrategy(IStrategy):

    INTERFACE_VERSION = 3
    can_short = True
    process_only_new_candles = True
    timeframe = "5m"
    startup_candle_count = 900
    stoploss = -0.15
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

        run_id = f"v59plus_{self.timeframe}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        self._state = StrategyState(run_id)
        self._state.initial_balance = 100.0
        self._state.balance = 100.0
        self._dynamic_stake = DynamicStake(c)

        if "queue" in self.config:
            c["queue"] = {**c.get("queue", {}), **self.config["queue"]}
        if "leverage" in self.config:
            c["leverage"] = {**c.get("leverage", {}), **self.config["leverage"]}

        entry_queue.reset()
        logger.info(
            "BetaV59Plus loaded — %d pairs, regime-aware, consol_entry_z=%.1f, consol_max_lev=%.0f",
            len(self._basket_pairs),
            c.get("regime_params", {}).get("consolidation", {}).get("entry_z", 2.5),
            c.get("regime_params", {}).get("consolidation", {}).get("max_lev", 4.0),
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

    # ────────────────────────── Indicators ──────────────────────────

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]
        cycle_id = id(dataframe)
        if cycle_id != self._df_cache_cycle:
            self._df_cache.clear()
            self._df_cache_cycle = cycle_id
            self._btc_trend = {}
            self._queue_signals = {}

        # BTC trend + regime
        if not self._btc_trend:
            btc_tf = self._cfg.get("btc_trend", {}).get("timeframe", "1h")
            btc_df = self._get_pair_df(self.BTC_REF, btc_tf)
            if btc_df is not None and len(btc_df) >= 50:
                self._btc_trend = btc_trend.compute(btc_df, self._cfg)
        dataframe = btc_trend.map_to_timeframe(self._btc_trend, dataframe)

        # Volume
        volume.compute(dataframe, self._cfg)

        # Basket z-score (adaptive window, dispersion, RSI)
        basket.compute_basket_zscore(
            dataframe, pair, self._basket_pairs,
            self._cfg["zscore"]["zscore_window"],
            self.timeframe, self.dp, self._df_cache, self._cfg,
        )

        # Queue score (for confirm_trade_entry ranking)
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
            cd_norm = np.ones(len(dataframe))
            score = (weights.get("basket_z", 0.5) * bz_norm +
                     weights.get("vol_ratio", 0.2) * vol_norm +
                     weights.get("spread_velocity", 0.2) * vel_norm +
                     weights.get("cooldown", 0.1) * cd_norm)
            dataframe["queue_score"] = score

        return dataframe

    # ────────────────────────── Entries ──────────────────────────

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe["enter_tag"] = ""

        if pair == self.BTC_REF or dataframe.empty or "basket_z" not in dataframe.columns:
            return dataframe

        basket.generate_basket_entries(dataframe, pair, self._cfg)

        mask_long = dataframe["enter_tag"] == "basket_long"
        mask_short = dataframe["enter_tag"] == "basket_short"
        dataframe.loc[mask_long, "enter_tag"] = "queue_long"
        dataframe.loc[mask_short, "enter_tag"] = "queue_short"

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    # ────────────────────────── Exit ──────────────────────────

    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        tag = trade.enter_tag or ""
        if not tag.startswith("queue_"):
            return None

        orig_tag = trade.enter_tag
        trade.enter_tag = tag.replace("queue_", "basket_")
        result = basket.check_basket_exit(
            pair, trade, current_profit, self._cfg,
            self.dp, self._df_cache, self.timeframe, self._basket_pairs,
        )
        trade.enter_tag = orig_tag

        # Emergency exit: absolute max loss (catches data anomalies too)
        abs_max_loss = self._cfg.get("basket", {}).get("max_loss_per_trade", -0.10)
        if current_profit < abs_max_loss:
            logger.info("EXIT %s | EMERGENCY max_loss profit=%.2f%%", pair, current_profit * 100)
            return "basket_max_loss"

        # Dynamic time_stop per regime
        base_max_candles = self._cfg.get("basket", {}).get("time_stop_candles", 24)
        is_consol = self._is_consolidation(pair)
        if is_consol:
            consol_time = self._cfg.get("regime_params", {}).get("consolidation", {}).get("time_stop", 18)
            max_candles = consol_time
        else:
            max_candles = base_max_candles

        trade_age = (current_time - trade.open_date_utc).total_seconds() / 300

        if result:
            logger.info(
                "EXIT %s | %s profit=%.2f%% age=%.0f/%d | lev=%.0fx consol=%s",
                pair, result, current_profit * 100, trade_age, max_candles,
                trade.leverage, "Y" if is_consol else "N",
            )
            return result

        if trade_age >= max_candles:
            logger.info(
                "EXIT %s | time_stop profit=%.2f%% age=%.0f/%d | consol=%s",
                pair, current_profit * 100, trade_age, max_candles,
                "Y" if is_consol else "N",
            )
            return "basket_time_stop"

        return None

    def _is_consolidation(self, pair: str) -> bool:
        """Check if current candle is in consolidation regime."""
        if not self.dp:
            return False
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or df.empty or "is_consolidation" not in df.columns:
            return False
        return bool(df["is_consolidation"].iloc[-1])

    # ────────────────────────── Confirm entry (queue gate) ──────────────────────────

    def confirm_trade_entry(self, pair, order_type, amount, rate, time_in_force,
                            current_time, entry_tag, side, **kwargs):
        open_trades = Trade.get_trades_proxy(is_open=True)
        max_pos = self._cfg.get("basket", {}).get("max_positions", 4)
        if len(open_trades) >= max_pos:
            return False
        if pair in {t.pair for t in open_trades}:
            return False
        if not self.dp:
            return False

        queue_cfg = self._cfg.get("queue", {})
        regime_params = self._cfg.get("regime_params", {})
        mults = queue_cfg.get("regime_multipliers", {})

        ct = pd.Timestamp(current_time)
        is_long = side == "long"
        open_pairs = {t.pair for t in open_trades}

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

        # Regime
        if btc_mom > 0.0:
            regime = "bull"
        elif btc_mom <= -1.0:
            regime = "bear"
        else:
            regime = "ranging"

        # Check consolidation
        is_consol = bool(df["is_consolidation"].iloc[idx]) if "is_consolidation" in df.columns else False

        # Dynamic min_score per regime
        base_min_score = queue_cfg.get("min_score", 0.45)
        if is_consol:
            min_score = regime_params.get("consolidation", {}).get("min_score", base_min_score + 0.15)
        else:
            min_score = base_min_score

        # Ranging balance
        if regime == "ranging":
            ranging_cfg = queue_cfg.get("ranging_balance", {})
            max_per_side = ranging_cfg.get("max_per_side", 2)
            # In consolidation: tighter per-side limit
            if is_consol:
                max_per_side = min(max_per_side, regime_params.get("consolidation", {}).get("max_per_side", 1))
            open_longs = sum(1 for t in open_trades if not t.is_short)
            open_shorts = sum(1 for t in open_trades if t.is_short)
            if is_long and open_longs >= max_per_side:
                return False
            if not is_long and open_shorts >= max_per_side:
                return False

        side_key = "long" if is_long else "short"
        my_mult = mults.get(f"{regime}_{side_key}", 0.6)
        my_adj_score = my_raw_score * my_mult

        if my_adj_score < min_score:
            logger.info(
                "GATE %s %s | REJECT score=%.3f < min=%.2f | regime=%s consol=%s",
                pair, side, my_adj_score, min_score, regime, "Y" if is_consol else "N",
            )
            return False

        # Queue ranking: must be #1
        beaten_by = None
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
            if is_long and p_bz >= 0:
                continue
            if not is_long and p_bz <= 0:
                continue
            p_adj = p_raw * my_mult
            if p_adj > my_adj_score:
                beaten_by = (p, p_adj)
                break

        if beaten_by:
            return False

        # Re-tag with regime for analysis
        regime_tag = "consol" if is_consol else regime
        if kwargs.get("entry_tag"):
            pass  # can't modify entry_tag in confirm, but log it
        logger.info(
            "GATE %s %s | ACCEPT score=%.3f min=%.2f | regime=%s consol=%s bz=%.3f | tag=%s_%s",
            pair, side, my_adj_score, min_score, regime, "Y" if is_consol else "N", my_bz,
            entry_tag, regime_tag,
        )
        return True

    # ────────────────────────── Confirm exit ──────────────────────────

    def confirm_trade_exit(self, pair, trade, order_type, amount, rate,
                           time_in_force, exit_reason, current_time, **kwargs):
        profit = trade.calc_profit_ratio(rate)
        pnl = profit * trade.stake_amount
        self._state.record_trade(
            pair=pair, profit_ratio=profit, profit_abs=pnl,
            leverage=trade.leverage, entry_tag=trade.enter_tag or "",
            exit_reason=exit_reason, open_date=trade.open_date_utc,
            close_date=current_time, open_rate=trade.open_rate,
            close_rate=rate, is_short=trade.is_short,
        )
        self._state.save()
        logger.info(
            "CLOSE %s | %s profit=%.2f%% pnl=$%.2f | lev=%.0fx | %s",
            pair, "SHORT" if trade.is_short else "LONG",
            profit * 100, pnl, trade.leverage, exit_reason,
        )
        return True

    # ────────────────────────── Stoploss ──────────────────────────

    def custom_stoploss(self, pair, trade, current_time, current_rate,
                        current_profit, after_fill, **kwargs):
        tag = trade.enter_tag or ""
        if not tag.startswith("queue_"):
            r = self._cfg["risk"]
            if current_profit >= r.get("trailing_stop_positive_offset", 0.012):
                return -r.get("trailing_stop_positive", 0.006)
            return r.get("stoploss", -0.07)
        # Queue trades: basket exits handle most. Wide stoploss to avoid
        # trailing interference — basket_max_loss in custom_exit caps actual loss.
        return -0.99

    # ────────────────────────── Leverage (regime-aware) ──────────────────────────

    def leverage(self, pair, current_time, current_rate, proposed_leverage,
                 max_leverage, entry_tag, side, **kwargs):
        is_consol = self._is_consolidation(pair)
        lev, trade_type = lev_module.compute(
            pair, self._cfg, self.dp, self.timeframe,
            entry_tag, side, max_leverage, is_consolidation=is_consol,
        )
        return lev

    # ────────────────────────── DCA ──────────────────────────

    def adjust_trade_position(self, trade, current_time, current_rate, current_profit,
                              min_stake, max_stake, current_entry_rate, current_exit_rate,
                              current_entry_profit, current_exit_profit, **kwargs):
        return dca.adjust_position(trade, current_profit, self._cfg, min_stake, max_stake)

    # ────────────────────────── Stake ──────────────────────────

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                            min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        open_trades = Trade.get_trades_proxy(is_open=True)

        # In consolidation: reduce stake
        is_consol = self._is_consolidation(pair)
        if is_consol:
            consol_stake_mult = self._cfg.get("regime_params", {}).get(
                "consolidation", {}).get("stake_multiplier", 0.7)
        else:
            consol_stake_mult = 1.0

        stake = self._dynamic_stake.compute(
            wallets=self.wallets,
            stake_currency=self.config["stake_currency"],
            open_trade_count=len(open_trades),
            max_stake=max_stake,
            open_trades=open_trades,
        )
        stake *= consol_stake_mult

        if min_stake and stake < min_stake:
            stake = min_stake
        logger.info(
            "STAKE %s %s | $%.2f lev=%.0fx consol=%s | open=%d",
            pair, side, stake, leverage, "Y" if is_consol else "N", len(open_trades),
        )
        return stake
