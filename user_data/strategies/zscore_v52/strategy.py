"""
ZScoreV52Strategy — Modular Z-Score Pairs Trading Strategy
===========================================================

Identical behavior to ZScorePTV51_5m, refactored into modules.
This file is a thin orchestrator (~200 lines) that delegates all logic.

Modules:
    lib/btc_trend.py   — BTC trend signals from 1h candles
    lib/volume.py      — Volume ratio filter
    lib/regime.py      — Correlation regime + spread vol filter
    zscore_v52/config.py   — JSON config loader
    zscore_v52/zscore.py   — Z-score computation + caching
    zscore_v52/entries.py  — Entry signal generation
    zscore_v52/exits.py    — Exit logic + confirm_trade_exit
    zscore_v52/leverage.py — Leverage scaling + stake amount
    zscore_v52/risk.py     — confirm_trade_entry gates
    zscore_v52/dca.py      — Progressive position adds
"""
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Ensure user_data/strategies is on sys.path for lib/ imports
_STRATEGIES_DIR = str(Path(__file__).resolve().parent.parent)
if _STRATEGIES_DIR not in sys.path:
    sys.path.insert(0, _STRATEGIES_DIR)

from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy

from lib import btc_trend, volume, regime
from zscore_v52 import config as cfg_loader
from zscore_v52 import zscore, entries, exits, leverage as lev_mod, risk, dca

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "v52_config.json"


class ZScoreV52Strategy(IStrategy):
    """Thin orchestrator — delegates all logic to modules."""

    INTERFACE_VERSION = 3
    can_short = True
    process_only_new_candles = True
    timeframe = "5m"
    startup_candle_count = 900
    stoploss = -0.07
    minimal_roi = {"0": 0.025, "3": 0.015, "10": 0.01, "20": 0.005}
    trailing_stop = True
    trailing_stop_positive = 0.006
    trailing_stop_positive_offset = 0.012
    trailing_only_offset_is_reached = True
    use_custom_stoploss = False
    position_adjustment_enable = True
    max_entry_position_adjustment = 3

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        c = cfg_loader.load(CONFIG_PATH)
        self._cfg = c

        # --- Pair groups ---
        g = c["groups"]
        self.group_a: list[str] = g["group_a"]
        self.group_b: list[str] = g["group_b"]
        self.BTC_REF: str = g["btc_ref"]

        # --- Timeframe & stake ---
        self.timeframe = c.get("timeframe", "5m")
        self.startup_candle_count = c.get("startup_candle_count", 900)

        # --- Risk (Freqtrade attributes) ---
        r = c["risk"]
        self.stoploss = r["stoploss"]
        self.minimal_roi = {str(k): v for k, v in r["minimal_roi"].items()}
        self.trailing_stop_positive = r["trailing_stop_positive"]
        self.trailing_stop_positive_offset = r["trailing_stop_positive_offset"]

        # Dynamic stoploss
        ds = r.get("dynamic_stoploss", {})
        self._dynamic_sl_enabled = ds.get("enabled", False)
        self._dynamic_sl_strong_z = ds.get("strong_z", 3.0)
        self._dynamic_sl_strong_stop = ds.get("strong_stop", -0.10)
        self._dynamic_sl_medium_z = ds.get("medium_z", 2.0)
        self._dynamic_sl_medium_stop = ds.get("medium_stop", -0.05)
        self._dynamic_sl_weak_stop = ds.get("weak_stop", -0.03)

        # Progressive stop
        ps = r.get("progressive_stop", {})
        self._progressive_stop_enabled = ps.get("enabled", False)
        if self._progressive_stop_enabled:
            self.use_custom_stoploss = True
            self.trailing_stop = False
        if self._dynamic_sl_enabled:
            self.use_custom_stoploss = True

        # --- DCA ---
        dc = c["dca"]
        self.max_entry_position_adjustment = dc["max_adds"]

        # --- Fast exit ---
        fe = c.get("fast_exit", {})
        self._fast_exit_enabled = fe.get("enabled", False)
        self._fast_exit_tf = fe.get("timeframe", "5m")

        # --- Combo config (hot-reload pair groups) ---
        self.COMBO_CONFIG = Path(__file__).parent.parent.parent / "scanner" / "pair_combos.json"
        self._combo_mtime: float = 0
        self._groups_initialized = True
        self._load_combo_config()

        # --- Internal state ---
        self._pair_zscores: dict[str, DataFrame] = {}
        self._df_cache: dict[str, DataFrame] = {}
        self._df_cache_cycle: int = 0
        self._btc_trend: dict = {}
        self._trade_history: list[dict] = []
        self._pending_features: dict[str, list] = {}
        self._loss_cooldown_until: Optional[datetime] = None
        self._peak_profit: dict[str, float] = {}

        self._state_recovered = False

        logger.info(f"V52 loaded — A={self.group_a} B={self.group_b} BTC={self.BTC_REF}")

    # =========================================================================
    # STATE RECOVERY — survive server restarts with open trades
    # =========================================================================

    def _recover_state_from_db(self) -> None:
        """Recover volatile state from SQLite after restart.

        Only runs in live/dry_run mode — backtesting manages its own state.

        Restores:
        1. Loss cooldown: check recent closed trades for catastrophic losses
        2. Pending features: already saved in trade custom_data (v26_features),
           no action needed — custom_exit reads from trade directly.
        """
        try:
            # Recover cooldown from recent closed trades
            closed = Trade.get_trades_proxy(is_open=False)
            if not closed:
                return

            catastrophic_loss = self._cfg["exits"]["catastrophic_loss_threshold"]
            cooldown_hours = self._cfg["consolidation"]["loss_cooldown_hours"]
            now = datetime.utcnow()

            for trade in reversed(closed):  # Most recent first
                if not trade.close_date:
                    continue
                hours_since = (now - trade.close_date_utc).total_seconds() / 3600
                if hours_since > cooldown_hours:
                    break  # No point checking older trades

                profit = trade.close_profit or 0.0
                exit_reason = trade.exit_reason or ""
                if profit < catastrophic_loss or exit_reason in (
                    "stop_loss", "mkt_stop_dump", "mkt_stop_pump"
                ):
                    cooldown_end = trade.close_date_utc + timedelta(hours=cooldown_hours)
                    if cooldown_end > now:
                        self._loss_cooldown_until = cooldown_end
                        logger.info(
                            "V52 RECOVERY: cooldown active until %s (from %s %.1f%%)",
                            cooldown_end, trade.pair, profit * 100,
                        )
                    break
        except Exception as e:
            logger.warning("V52 RECOVERY: could not recover state: %s", e)

    # =========================================================================
    # COMBO CONFIG — hot-reload pair groups
    # =========================================================================

    def _load_combo_config(self) -> bool:
        if not self.COMBO_CONFIG.is_file():
            return False
        mtime = self.COMBO_CONFIG.stat().st_mtime
        if mtime == self._combo_mtime and self._groups_initialized:
            return True
        try:
            with open(self.COMBO_CONFIG) as f:
                config = json.load(f)
        except (json.JSONDecodeError, OSError):
            return False
        if config.get("auto_cluster", False):
            self._combo_mtime = mtime
            return False
        active = config.get("active_combo", "")
        combos = config.get("combos", {})
        if active not in combos:
            return False
        combo = combos[active]
        new_a = combo.get("group_a", [])
        new_b = combo.get("group_b", [])
        if new_a != self.group_a or new_b != self.group_b:
            self.group_a = new_a
            self.group_b = new_b
            self._pair_zscores = {}
            logger.info(f"V52 COMBO: '{active}' A={self.group_a} B={self.group_b}")
        self._combo_mtime = mtime
        return True

    # =========================================================================
    # DATAFRAME CACHE
    # =========================================================================

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

    # =========================================================================
    # INFORMATIVE PAIRS
    # =========================================================================

    def informative_pairs(self):
        pairs = self.dp.current_whitelist() if self.dp else []
        inf = [(pair, "1d") for pair in pairs] + [(self.BTC_REF, "1h")]
        if self._fast_exit_enabled:
            inf += [(pair, self._fast_exit_tf) for pair in pairs]
            inf.append((self.BTC_REF, self._fast_exit_tf))
        return inf

    # =========================================================================
    # INDICATORS
    # =========================================================================

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]
        self._load_combo_config()

        # Recover state once on first run (live/dry_run only)
        if not self._state_recovered:
            self._state_recovered = True
            if self.dp and self.dp.runmode.value in ("live", "dry_run"):
                self._recover_state_from_db()

        # Invalidate cache each cycle
        cycle_id = id(dataframe)
        if cycle_id != self._df_cache_cycle:
            self._df_cache.clear()
            self._df_cache_cycle = cycle_id

        # BTC trend (once per cycle)
        if not self._btc_trend:
            btc_1h = self._get_pair_df(self.BTC_REF, "1h")
            if btc_1h is not None and len(btc_1h) >= 50:
                self._btc_trend = btc_trend.compute(btc_1h, self._cfg)

        # Map BTC signals to pair timeframe
        dataframe = btc_trend.map_to_timeframe(self._btc_trend, dataframe)

        # Z-score computation (pair + spread + cross signals)
        dataframe = zscore.compute(
            dataframe, pair, self._cfg, self.dp,
            self._pair_zscores, self._df_cache,
            self.group_a, self.group_b,
        )

        # Spread volatility filter
        dataframe = regime.compute_spread_vol(dataframe, self._cfg)

        # Regime filter
        dataframe = regime.compute(
            dataframe, pair, self._cfg, self.dp,
            self._df_cache, self.timeframe,
            self.group_a, self.group_b,
        )

        # Volume filter
        dataframe = volume.compute(dataframe, self._cfg)

        # Export full indicator dataframe for replay (backtest only)
        if self.dp and self.dp.runmode.value in ("backtest", "hyperopt"):
            export_dir = Path(__file__).parent.parent.parent / "backtest_results" / "indicators"
            export_dir.mkdir(parents=True, exist_ok=True)
            coin = pair.split("/")[0]
            cols = [c for c in [
                "date", "open", "high", "low", "close", "volume",
                "pair_zscore", "spread_zscore", "log_return",
                "pair_z_cross_up", "pair_z_cross_down",
                "vol_ratio", "vol_ok",
                "regime_ok", "rolling_corr", "spread_vol_ok",
                "btc_pump", "btc_dump", "btc_high_vol", "btc_vol_ended",
                "btc_mom", "btc_atr_z",
            ] if c in dataframe.columns]
            dataframe[cols].to_feather(export_dir / f"{coin}_indicators.feather")

        return dataframe

    # =========================================================================
    # ENTRY
    # =========================================================================

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return entries.generate(
            dataframe, metadata["pair"], self._cfg,
            self._btc_trend, self.group_a, self.group_b,
        )

    # =========================================================================
    # EXIT
    # =========================================================================

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        return exits.check_exit(
            pair, trade, current_time, current_rate, current_profit,
            self._cfg, self.dp, self._btc_trend, self._peak_profit,
            self.timeframe, self._df_cache, self._pending_features,
        )

    def confirm_trade_exit(self, pair: str, trade: Trade, order_type: str,
                           amount: float, rate: float, time_in_force: str,
                           exit_reason: str, current_time: datetime, **kwargs) -> bool:
        allow, new_cooldown = exits.confirm_exit(
            pair, trade, exit_reason, current_time, rate,
            self._cfg, self._pending_features, self._loss_cooldown_until,
            self._trade_history,
        )
        self._loss_cooldown_until = new_cooldown
        return allow

    # =========================================================================
    # CONFIRM ENTRY
    # =========================================================================

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float,
                            rate: float, time_in_force: str, current_time: datetime,
                            entry_tag: Optional[str], side: str, **kwargs) -> bool:
        open_trades = Trade.get_trades_proxy(is_open=True)
        return risk.confirm_entry(
            pair, self._cfg, current_time, self._loss_cooldown_until,
            self.group_a, self.group_b, open_trades,
        )

    # =========================================================================
    # CUSTOM STOPLOSS
    # =========================================================================

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool,
                        **kwargs) -> float | None:
        if not self._dynamic_sl_enabled:
            return None
        features = trade.get_custom_data("v26_features")
        if not features:
            features = self._pending_features.get(pair)
        if not features:
            return None
        entry_z = abs(features[0])
        if entry_z >= self._dynamic_sl_strong_z:
            return self._dynamic_sl_strong_stop
        elif entry_z >= self._dynamic_sl_medium_z:
            return self._dynamic_sl_medium_stop
        else:
            return self._dynamic_sl_weak_stop

    # =========================================================================
    # LEVERAGE
    # =========================================================================

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float,
                 entry_tag: Optional[str], side: str, **kwargs) -> float:
        lev, features = lev_mod.compute(
            pair, self._cfg, self.dp, self.timeframe,
            entry_tag, side, max_leverage, self._pending_features,
        )
        return lev

    # =========================================================================
    # DCA
    # =========================================================================

    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: Optional[float], max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs) -> Optional[float]:
        return dca.adjust_position(trade, current_profit, self._cfg, min_stake, max_stake)

    # =========================================================================
    # STAKE
    # =========================================================================

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float],
                            max_stake: float, leverage: float, entry_tag: Optional[str],
                            side: str, **kwargs) -> float:
        return lev_mod.stake_amount(self._cfg, max_stake)
