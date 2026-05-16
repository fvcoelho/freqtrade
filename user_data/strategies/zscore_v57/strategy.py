"""
ZScoreV57Strategy — Dynamic Basket Mean-Reversion
===================================================

All pairs in a single basket. Each candle, z-score is recalculated
for every pair relative to the basket average. Pairs dynamically
enter and exit based on their z-score ranking.

How it works:
    basket_avg = mean(normalized log prices of ALL pairs)
    pair_z = z-score(pair - basket_avg)

    pair_z < -2.0 → pair lagging behind basket → LONG
    pair_z reverts to 0 → pair caught up → EXIT

No fixed groups, no fixed sub1/sub2. The basket self-organizes.
Pairs that underperform get bought, pairs that catch up get sold.

Modules (self-contained in zscore_v57/):
    basket.py     — basket z-score + entry/exit signals (NEW)
    btc_trend.py  — BTC momentum + volatility from 1h
    volume.py     — volume filter
    dca.py        — DCA on winners
    leverage.py   — leverage modes
    state.py      — persistent state
    config.py     — JSON config loader
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

from zscore_v57 import btc_trend, volume, basket, config as cfg_loader, dca
from zscore_v57.stake import DynamicStake
from zscore_v57.state import StrategyState

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "v57_config.json"


class ZScoreV57Strategy(IStrategy):
    """Dynamic basket mean-reversion — all pairs compete, z-score decides."""

    INTERFACE_VERSION = 3
    can_short = True  # short in bear market, long in bull/ranging
    process_only_new_candles = True
    timeframe = "5m"
    startup_candle_count = 900
    stoploss = -0.99  # basket exits via custom_exit, not stoploss
    minimal_roi = {"0": 10}  # disabled — basket exit handles it
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
        self._trade_history: list[dict] = []

        run_id = f"v57_{self.timeframe}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        self._state = StrategyState(run_id)
        self._state.initial_balance = 100.0
        self._state.balance = 100.0
        self._state.metadata = {"strategy": "ZScoreV57Strategy", "basket_pairs": self._basket_pairs}

        self._dynamic_stake = DynamicStake(c)

        logger.info("V57 loaded — basket=%d pairs, BTC=%s, stake_mode=%s", len(self._basket_pairs), self.BTC_REF, c.get('stake', {}).get('mode', 'fixed'))

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

    # ── Indicators ────────────────────────────────────────────────

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]
        cycle_id = id(dataframe)
        if cycle_id != self._df_cache_cycle:
            self._df_cache.clear()
            self._df_cache_cycle = cycle_id

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
            self.timeframe, self.dp, self._df_cache,
            self._cfg,
        )
        return dataframe

    # ── Entry ─────────────────────────────────────────────────────

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe["enter_tag"] = ""
        if pair != self.BTC_REF:
            basket.generate_basket_entries(dataframe, pair, self._cfg)
        return dataframe

    # ── Exit ──────────────────────────────────────────────────────

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        tag = trade.enter_tag or ""
        if not tag.startswith("basket_"):
            return None

        result = basket.check_basket_exit(
            pair, trade, current_profit, self._cfg,
            self.dp, self._df_cache, self.timeframe, self._basket_pairs,
        )
        if result:
            return result

        max_candles = self._cfg.get("basket", {}).get("time_stop_candles", 72)
        trade_age = (current_time - trade.open_date_utc).total_seconds() / 300
        if trade_age >= max_candles:
            return "basket_time_stop"

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

    # ── Confirm entry ─────────────────────────────────────────────

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float,
                            rate: float, time_in_force: str, current_time: datetime,
                            entry_tag: Optional[str], side: str, **kwargs) -> bool:
        open_trades = Trade.get_trades_proxy(is_open=True)
        max_pos = self._cfg.get("basket", {}).get("max_positions", 4)
        if len(open_trades) >= max_pos:
            return False
        if pair in {t.pair for t in open_trades}:
            return False
        return True

    # ── Stoploss ──────────────────────────────────────────────────

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float,
                        after_fill: bool, **kwargs) -> float | None:
        # Basket trades: no individual stop — exits via custom_exit only
        # Return -0.99 to effectively disable (None would use class stoploss)
        tag = trade.enter_tag or ""
        if tag.startswith("basket_"):
            return -0.99
        # Non-basket: trailing stop
        r = self._cfg["risk"]
        if current_profit >= r.get("trailing_stop_positive_offset", 0.012):
            return -r.get("trailing_stop_positive", 0.006)
        return r.get("stoploss", -0.07)

    # ── Leverage ──────────────────────────────────────────────────

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float,
                 entry_tag: Optional[str], side: str, **kwargs) -> float:
        return min(self._cfg.get("leverage", {}).get("base_multiplier", 3.0), max_leverage)

    # ── DCA ───────────────────────────────────────────────────────

    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: Optional[float], max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs) -> Optional[float]:
        return dca.adjust_position(trade, current_profit, self._cfg, min_stake, max_stake)

    # ── Stake ─────────────────────────────────────────────────────

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
