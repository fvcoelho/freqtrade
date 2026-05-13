"""
ZScoreV55Strategy — Dual Independent Group Mean-Reversion Strategy
===================================================================

Two independent groups, each with own spread z-score signal.
Max 2 concurrent trades (1 per group). Per-group cooldown.

Group A: XRP vs (SOL+LINK) — LONG only
Group B: (BTC+SOL) vs ETH — LONG + SHORT
Leverage: Warmup 3→5x (streak-based, gap 12h reset)

Modules:
    lib/btc_trend.py, volume.py, regime.py — shared infrastructure
    zscore_v55/groups.py   — group definitions, per-group state
    zscore_v55/zscore.py   — z-score computation (per-pair + per-group spread)
    zscore_v55/entries.py  — per-group entry signal generation
    zscore_v55/exits.py    — exit logic + per-group cooldown
    zscore_v55/leverage.py — warmup/volume/inverse/exp leverage modes
    zscore_v55/state.py    — persistent state (streaks, trades, equity)
    zscore_v55/risk.py     — pre-trade risk gates
    zscore_v55/dca.py      — DCA on winning positions
"""
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

_STRATEGIES_DIR = str(Path(__file__).resolve().parent.parent)
if _STRATEGIES_DIR not in sys.path:
    sys.path.insert(0, _STRATEGIES_DIR)

from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy

from lib import btc_trend, volume, regime
from zscore_v55 import config as cfg_loader
from zscore_v55 import groups as grp
from zscore_v55.state import StrategyState
from zscore_v55 import zscore, entries, exits, leverage as lev_mod, risk, dca, grid

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "v55_config.json"


class ZScoreV55Strategy(IStrategy):
    """Dual-group orchestrator — runs two independent spread z-score signals."""

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

        # Groups
        self._groups = grp.load_groups(c)
        self.BTC_REF: str = c["groups"]["btc_ref"]

        # Timeframe & stake
        self.timeframe = c.get("timeframe", "5m")
        self.startup_candle_count = c.get("startup_candle_count", 900)

        # Risk (Freqtrade attributes)
        r = c["risk"]
        self.stoploss = r["stoploss"]
        self.minimal_roi = {str(k): v for k, v in r["minimal_roi"].items()}
        self.trailing_stop_positive = r["trailing_stop_positive"]
        self.trailing_stop_positive_offset = r["trailing_stop_positive_offset"]

        ds = r.get("dynamic_stoploss", {})
        self._dynamic_sl_enabled = ds.get("enabled", False)
        if self._dynamic_sl_enabled:
            self.use_custom_stoploss = True

        # Enable custom stoploss for partial stop feature
        ps = c.get("partial_stop", {})
        if ps.get("enabled", False):
            self.use_custom_stoploss = True

        # DCA
        dc = c["dca"]
        self.max_entry_position_adjustment = dc["max_adds"]

        # Fast exit
        fe = c.get("fast_exit", {})
        self._fast_exit_enabled = fe.get("enabled", False)
        self._fast_exit_tf = fe.get("timeframe", "5m")

        # Internal state
        self._pair_zscores: dict[str, DataFrame] = {}
        self._df_cache: dict[str, DataFrame] = {}
        self._df_cache_cycle: int = 0
        self._btc_trend: dict = {}
        self._trade_history: list[dict] = []
        self._pending_features: dict[str, list] = {}
        self._peak_profit: dict[str, float] = {}

        # Persistent state (survives backtest cycles)
        run_id = f"v55_{c.get('timeframe', '5m')}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        self._state = StrategyState(run_id)
        self._state.initial_balance = 100.0
        self._state.balance = 100.0
        self._state.metadata = {
            "strategy": "ZScoreV55Strategy",
            "leverage_mode": c.get("leverage", {}).get("mode", "volume"),
            "groups": {g.name: {"sub1": g.sub1, "sub2": g.sub2} for g in self._groups},
        }

        group_names = [g.name for g in self._groups]
        all_pairs = grp.all_tradable_pairs(self._groups)
        logger.info(f"V55 loaded — groups={group_names} pairs={all_pairs} BTC={self.BTC_REF}")

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
    # INDICATORS — per-pair + per-group spread z-scores
    # =========================================================================

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]

        # Invalidate cache each cycle
        cycle_id = id(dataframe)
        if cycle_id != self._df_cache_cycle:
            self._df_cache.clear()
            self._df_cache_cycle = cycle_id

        # BTC trend (1h timeframe for stable regime classification)
        if not self._btc_trend:
            btc_1h = self._get_pair_df(self.BTC_REF, "1h")
            if btc_1h is not None and len(btc_1h) >= 50:
                self._btc_trend = btc_trend.compute(btc_1h, self._cfg)

        # Map BTC signals to pair timeframe
        dataframe = btc_trend.map_to_timeframe(self._btc_trend, dataframe)

        # Per-pair z-score (once per pair — shared across groups)
        zscore.compute(
            dataframe, pair, self._cfg, self.dp,
            self._pair_zscores, self._df_cache,
            # Use first group's sub1+sub2 for the shared pair z-score
            self._groups[0].sub1, self._groups[0].sub2,
        )

        # Per-group spread z-score
        for g in self._groups:
            col = f"spread_z_{g.name.lower()}"
            dataframe[col] = zscore.compute_group_spread_z(
                dataframe, pair, self._cfg, self.dp,
                self._df_cache, g.sub1, g.sub2,
            )

        # Regime filter (use first group's sub1[0] vs sub2[0] for correlation)
        regime.compute(
            dataframe, pair, self._cfg, self.dp,
            self._df_cache, self.timeframe,
            self._groups[0].sub1, self._groups[0].sub2,
        )

        # Spread volatility filter
        regime.compute_spread_vol(dataframe, self._cfg)

        # Volume filter
        volume.compute(dataframe, self._cfg)

        # Consolidation regime flag (for grid module)
        regime_cfg = self._cfg["regime"]
        is_consolidating = (
            (dataframe["btc_atr_z"] < regime_cfg["consolidation_atr_z"])
            & (dataframe["btc_mom"].abs() < regime_cfg["consolidation_btc_mom_max"])
        )
        # Also check spread is small (using first group's spread)
        if self._groups:
            spread_col = f"spread_z_{self._groups[0].name.lower()}"
            if spread_col in dataframe.columns:
                is_consolidating = is_consolidating & (
                    dataframe[spread_col].abs() < regime_cfg["consolidation_spread_max"]
                )
        dataframe["is_consolidating"] = is_consolidating

        # Grid levels (BTC only)
        if self._cfg.get("grid", {}).get("enabled", False):
            grid.compute_levels(dataframe, pair, self._cfg, self.dp)

        # Export indicators for replay (backtest only)
        if self.dp and self.dp.runmode.value in ("backtest", "hyperopt"):
            export_dir = Path(__file__).parent.parent.parent / "backtest_results" / "indicators"
            export_dir.mkdir(parents=True, exist_ok=True)
            coin = pair.split("/")[0]
            cols = [c for c in dataframe.columns if c in [
                "date", "open", "high", "low", "close", "volume",
                "pair_zscore", "log_return",
                "pair_z_cross_up", "pair_z_cross_down",
                "vol_ratio", "vol_ok",
                "regime_ok", "rolling_corr", "spread_vol_ok",
                "btc_pump", "btc_dump", "btc_high_vol", "btc_vol_ended",
                "btc_mom", "btc_atr_z",
            ] + [f"spread_z_{g.name.lower()}" for g in self._groups]]
            dataframe[cols].to_feather(export_dir / f"{coin}_indicators.feather")

        return dataframe

    # =========================================================================
    # ENTRY — iterate groups, generate per-group signals
    # =========================================================================

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]

        # Initialize columns
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe["enter_tag"] = ""

        grid_enabled = self._cfg.get("grid", {}).get("enabled", False)

        # Grid signals for BTC (before group loop — BTC-specific)
        if grid_enabled:
            grid.generate(dataframe, pair, self._cfg)

        # Ranging → mean-reversion signals per group
        for g in self._groups:
            if pair not in g.all_pairs:
                continue
            col = f"spread_z_{g.name.lower()}"
            entries.generate(
                dataframe, pair, self._cfg, self._btc_trend,
                g.sub1, g.sub2, g.name, col,
            )

        return dataframe

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
            self._cfg, self._pending_features, self._trade_history,
        )
        # Apply cooldown to the group(s) this pair belongs to
        if new_cooldown:
            for g in self._groups:
                if pair in g.unique_pairs:
                    g.cooldown_until = new_cooldown
                    logger.info(f"V55 COOLDOWN: group {g.name} until {new_cooldown}")

        # Record trade in persistent state
        profit = trade.calc_profit_ratio(rate)
        self._state.record_trade(
            pair=pair, profit_ratio=profit, profit_abs=trade.calc_profit_ratio(rate) * trade.stake_amount,
            leverage=trade.leverage, entry_tag=trade.enter_tag or "",
            exit_reason=exit_reason, open_date=trade.open_date_utc,
            close_date=current_time, open_rate=trade.open_rate,
            close_rate=rate, is_short=trade.is_short,
        )
        self._state.save()

        return allow

    # =========================================================================
    # CONFIRM ENTRY — per-group limits
    # =========================================================================

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float,
                            rate: float, time_in_force: str, current_time: datetime,
                            entry_tag: Optional[str], side: str, **kwargs) -> bool:
        open_trades = Trade.get_trades_proxy(is_open=True)

        # Max total trades
        max_total = self._cfg.get("max_total_trades", 2)
        if len(open_trades) >= max_total:
            return False

        # Check per-group: at least one group must allow
        for g in self._groups:
            if pair in g.all_pairs:
                if risk.confirm_entry(pair, self._cfg, current_time, g, self._groups, open_trades):
                    return True
        return False

    # =========================================================================
    # CUSTOM STOPLOSS
    # =========================================================================

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool,
                        **kwargs) -> float | None:
        """Partial Stoploss — tighter stop to reduce max loss per trade.

        Freqtrade requires this method name (IStrategy interface).
        When partial_stop is enabled, replaces the fixed -7% with a
        tighter level (e.g., -4%) to cut losses earlier.
        """
        ps = self._cfg.get("partial_stop", {})
        if ps.get("enabled", False):
            return ps.get("trigger", -0.04)

        # ── Dynamic Stoploss (z-score based) ──
        if not self._dynamic_sl_enabled:
            return None
        features = trade.get_custom_data("v26_features")
        if not features:
            features = self._pending_features.get(pair)
        if not features:
            return None
        entry_z = abs(features[0])
        ds = self._cfg["risk"].get("dynamic_stoploss", {})
        if entry_z >= ds.get("strong_z", 3.0):
            return ds.get("strong_stop", -0.10)
        elif entry_z >= ds.get("medium_z", 2.0):
            return ds.get("medium_stop", -0.05)
        else:
            return ds.get("weak_stop", -0.03)

    # =========================================================================
    # LEVERAGE
    # =========================================================================

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float,
                 entry_tag: Optional[str], side: str, **kwargs) -> float:
        # Grid trades: fixed leverage
        if entry_tag and entry_tag.startswith("grid_"):
            grid_lev = self._cfg.get("grid", {}).get("leverage", 5.0)
            return min(grid_lev, max_leverage)

        # Ranging trades: warmup leverage mode
        self._pending_features["_strategy_state"] = self._state
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
        # Log all calls to debug partial stop
        if current_profit < -0.02:
            logger.warning("ADJUST_POS CALLED: %s profit=%.2f%% stake=$%.2f exits=%d entries=%d",
                         trade.pair, current_profit * 100, trade.stake_amount,
                         trade.nr_of_successful_exits, trade.nr_of_successful_entries)
        return dca.adjust_position(trade, current_profit, self._cfg, min_stake, max_stake)

    # =========================================================================
    # STAKE
    # =========================================================================

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float],
                            max_stake: float, leverage: float, entry_tag: Optional[str],
                            side: str, **kwargs) -> float:
        return lev_mod.stake_amount(self._cfg, max_stake)
