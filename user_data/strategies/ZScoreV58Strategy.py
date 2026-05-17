"""
ZScoreV58Strategy — Queue-Based Scoring Entry
===============================================

Replaces V57's per-pair independent entry with centralized scoring.
Each candle, all pairs receive a multi-factor score. Top-K pairs per
side enter a confirmation queue. A pair must stay in top-K for N
consecutive candles before it can trade.

Exits identical to V57 (basket reversion, time stop, max loss).

Modules (self-contained in zscore_v58/):
    entry_queue.py — NEW: scoring, queue ranking, confirmation
    basket.py      — basket z-score computation + exit logic (from V57)
    btc_trend.py   — BTC momentum + volatility from 1h
    volume.py      — volume filter
    dca.py         — DCA on winners
    stake.py       — dynamic stake sizing
    state.py       — persistent state
    config.py      — JSON config loader
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

from zscore_v58 import btc_trend, volume, basket, config as cfg_loader, dca, entry_queue
from zscore_v58.stake import DynamicStake
from zscore_v58.state import StrategyState

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent / "v58_config.json"


class ZScoreV58Strategy(IStrategy):
    """Queue-based scoring entry — pairs compete, best confirmed entries win."""

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
        self._candle_index: int = 0

        run_id = f"v58_{self.timeframe}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        self._state = StrategyState(run_id)
        self._state.initial_balance = 100.0
        self._state.balance = 100.0

        self._dynamic_stake = DynamicStake(c)

        # Reset queue state on init
        entry_queue.reset()

        logger.info(
            "V58 loaded — basket=%d pairs, BTC=%s, queue top_k=%d confirm=%d",
            len(self._basket_pairs), self.BTC_REF,
            c.get("queue", {}).get("top_k", 3),
            c.get("queue", {}).get("confirm_candles", 3),
        )

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

        if pair == self.BTC_REF or dataframe.empty:
            return dataframe

        # Queue logic runs once per candle cycle (first pair triggers it)
        cycle_id = id(dataframe)
        if entry_queue._score_cache.get("cycle") != cycle_id:
            self._candle_index += 1
            self._run_queue_cycle(cycle_id)

        # Check if this pair is in the ready list
        ready_list = entry_queue._score_cache.get("ready", [])
        for ready_pair, side in ready_list:
            if ready_pair == pair:
                if side == "long":
                    dataframe.iloc[-1, dataframe.columns.get_loc("enter_long")] = 1
                    dataframe.iloc[-1, dataframe.columns.get_loc("enter_tag")] = "queue_long"
                else:
                    dataframe.iloc[-1, dataframe.columns.get_loc("enter_short")] = 1
                    dataframe.iloc[-1, dataframe.columns.get_loc("enter_tag")] = "queue_short"
                break

        return dataframe

    def _run_queue_cycle(self, cycle_id: int):
        """Run scoring → queue → confirmation for current candle. Cache results."""
        pair_data: dict[str, dict] = {}
        for p in self._basket_pairs:
            if p == self.BTC_REF:
                continue
            df = self._get_pair_df(p)
            if df is None or df.empty or len(df) < 4:
                continue
            last = df.iloc[-1]
            pair_data[p] = {
                "basket_z": float(last.get("basket_z", 0.0)),
                "basket_z_prev3": float(df["basket_z"].iloc[-4]) if "basket_z" in df.columns and len(df) >= 4 else 0.0,
                "vol_ratio": float(last.get("vol_ratio", 1.0)),
                "vol_ok": bool(last.get("vol_ok", False)),
                "btc_mom": float(last.get("btc_mom", 0.0)),
                "btc_pump": bool(last.get("btc_pump", False)),
                "btc_dump": bool(last.get("btc_dump", False)),
                "btc_high_vol": bool(last.get("btc_high_vol", False)),
            }

        open_trades = Trade.get_trades_proxy(is_open=True)
        open_pairs = {t.pair for t in open_trades}

        scores = entry_queue.compute_scores(pair_data, self._cfg, self._candle_index)
        long_q, short_q = entry_queue.build_queues(scores, pair_data, self._cfg, open_pairs)
        ready = entry_queue.update_confirmation(long_q, short_q, self._cfg)

        # Sort ready by score descending
        ready.sort(key=lambda x: scores.get(x[0], 0), reverse=True)

        entry_queue._score_cache = {"cycle": cycle_id, "scores": scores, "ready": ready}

    # ── Exit ──────────────────────────────────────────────────────

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        tag = trade.enter_tag or ""
        if not tag.startswith("queue_"):
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
        entry_queue.record_exit(pair, self._candle_index)
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
        entry_queue._confirm_long[pair] = 0
        entry_queue._confirm_short[pair] = 0
        return True

    # ── Stoploss ──────────────────────────────────────────────────

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float,
                        after_fill: bool, **kwargs) -> float | None:
        tag = trade.enter_tag or ""
        if tag.startswith("queue_"):
            return -0.99
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
