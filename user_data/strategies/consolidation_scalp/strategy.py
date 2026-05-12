"""
ConsolidationScalpStrategy — BTC Mean-Reversion Scalper
========================================================

Trades BTC/USDT bounces off S/R levels during consolidation.
3 swappable S/R engines: order_blocks, pivot_fractal, rolling_minmax.

Modules:
    consolidation_scalp/config.py         — JSON config loader
    consolidation_scalp/consolidation.py  — regime filter
    consolidation_scalp/levels.py         — S/R detection (3 engines)
    consolidation_scalp/entries.py        — entry signals
    consolidation_scalp/exits.py          — exit logic
    consolidation_scalp/leverage.py       — dynamic leverage
"""
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

_STRATEGIES_DIR = str(Path(__file__).resolve().parent.parent)
if _STRATEGIES_DIR not in sys.path:
    sys.path.insert(0, _STRATEGIES_DIR)

from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy

from consolidation_scalp import config as cfg_loader
from consolidation_scalp import consolidation, levels, entries, exits
from consolidation_scalp import leverage as lev_mod
from consolidation_scalp import btc_trend

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "consolidation_scalp_config.json"


class ConsolidationScalpStrategy(IStrategy):
    """BTC consolidation scalper — mean-reversion off S/R levels."""

    INTERFACE_VERSION = 3
    can_short = False
    process_only_new_candles = True
    timeframe = "5m"
    startup_candle_count = 200
    stoploss = -0.05
    minimal_roi = {}
    trailing_stop = False
    use_custom_stoploss = False
    position_adjustment_enable = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        c = cfg_loader.load(CONFIG_PATH)
        self._cfg = c

        self.timeframe = c.get("timeframe", "5m")
        self.startup_candle_count = c.get("startup_candle_count", 200)

        # BTC reference pair for regime filter
        self._btc_ref = c.get("btc_ref", "BTC/USDC:USDC")
        self._btc_trend: dict = {}

        # Exit tracking
        self._peak_profit: dict[str, float] = {}
        self._df_cache: dict = {}
        self._df_cache_cycle: int = 0

        engine = c["level_engine"]
        logger.info(
            "ConsolidationScalp loaded — engine=%s pair=%s tf=%s",
            engine, c["pair"], self.timeframe,
        )

    # =========================================================================
    # INFORMATIVE PAIRS
    # =========================================================================

    def informative_pairs(self):
        return [(self._btc_ref, "1h")]

    # =========================================================================
    # INDICATORS
    # =========================================================================

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Cache invalidation per cycle
        cycle_id = id(dataframe)
        if cycle_id != self._df_cache_cycle:
            self._df_cache.clear()
            self._df_cache_cycle = cycle_id
            self._btc_trend = {}

        # 0. BTC regime filter (1h data)
        if not self._btc_trend and self.dp:
            btc_1h = self.dp.get_pair_dataframe(pair=self._btc_ref, timeframe="1h")
            if btc_1h is not None and len(btc_1h) >= 50:
                self._btc_trend = btc_trend.compute(btc_1h, self._cfg)
        dataframe = btc_trend.map_to_timeframe(self._btc_trend, dataframe)

        # 1. Consolidation filter (ATR, range, momentum, volume)
        dataframe = consolidation.compute(dataframe, self._cfg)

        # 2. S/R levels from selected engine
        dataframe = levels.compute(dataframe, self._cfg)

        return dataframe

    # =========================================================================
    # ENTRIES
    # =========================================================================

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = entries.generate(dataframe, self._cfg)
        return dataframe

    # =========================================================================
    # EXITS
    # =========================================================================

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        return exits.check_exit(
            pair, trade, current_time, current_rate, current_profit,
            self._cfg, self.dp, self.timeframe, self._peak_profit,
        )

    # Stoploss handled by IStrategy.stoploss (-2%) — no custom_stoploss needed

    # =========================================================================
    # LEVERAGE
    # =========================================================================

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float,
                 entry_tag: Optional[str], side: str, **kwargs) -> float:
        return lev_mod.compute(
            self._cfg, self.dp, pair, self.timeframe, max_leverage,
        )

    # =========================================================================
    # STAKE
    # =========================================================================

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float],
                            max_stake: float, leverage: float, entry_tag: Optional[str],
                            side: str, **kwargs) -> float:
        return lev_mod.stake_amount(self._cfg, max_stake)
