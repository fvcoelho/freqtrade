"""
Kelly + Polymarket Regime Detector Strategy (Mode 3)

Uses aggregated Polymarket odds to classify market regime
(BULLISH / BEARISH / UNCERTAIN), then filters trade direction
and adjusts Kelly accordingly.
"""

import logging
from datetime import datetime
from typing import Optional

from pandas import DataFrame

from KellyDCAMeanReversion import KellyDCAMeanReversion
from polymarket_provider import PolymarketDataProvider

logger = logging.getLogger(__name__)


class KellyPolyRegime(KellyDCAMeanReversion):
    bullish_threshold = 0.60
    bearish_threshold = 0.40
    uncertain_kelly_mult = 0.5

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._poly_provider = PolymarketDataProvider("user_data/polymarket")

    def _get_coin_from_pair(self, pair: str) -> str:
        return pair.split("/")[0]

    def _get_regime(self, pair: str, current_time: datetime) -> tuple[str, float]:
        self._poly_provider.initialize()
        coin = self._get_coin_from_pair(pair)
        signal = self._poly_provider.get_signal(coin, int(current_time.timestamp()))

        if signal.num_markets == 0:
            return "UNCERTAIN", 0.5

        bp = signal.bullish_prob
        if bp > self.bullish_threshold:
            regime = "BULLISH"
        elif bp < self.bearish_threshold:
            regime = "BEARISH"
        else:
            regime = "UNCERTAIN"

        logger.info(f"Poly regime for {pair}: {regime} (prob={bp:.2f}, {signal.num_markets} markets)")
        return regime, bp

    def custom_stake_amount(
        self, pair: str, current_time: datetime, current_rate: float,
        proposed_stake: float, min_stake: Optional[float], max_stake: float,
        leverage: float, entry_tag: Optional[str], side: str, **kwargs,
    ) -> float:
        kelly = self._calculate_kelly()
        regime, _ = self._get_regime(pair, current_time)

        base_pct = kelly["kelly_pct"] if kelly["enough_data"] else self.default_stake_pct
        if regime == "UNCERTAIN":
            kelly["kelly_pct"] = base_pct * self.uncertain_kelly_mult
        else:
            kelly["kelly_pct"] = base_pct
        kelly["kelly_pct"] = max(self.min_stake_pct, kelly["kelly_pct"])

        wallet_balance = self.wallets.get_total_stake_amount() if self.wallets else 1000
        kelly_stake = wallet_balance * kelly["kelly_pct"]
        if min_stake is not None:
            kelly_stake = max(kelly_stake, min_stake)
        kelly_stake = min(kelly_stake, max_stake)
        return kelly_stake * self.initial_stake_pct

    def confirm_trade_entry(
        self, pair: str, order_type: str, amount: float, rate: float,
        time_in_force: str, current_time: datetime, entry_tag: Optional[str],
        side: str, **kwargs,
    ) -> bool:
        kelly = self._calculate_kelly()
        if kelly["enough_data"] and kelly["kelly_raw"] <= 0:
            return False

        regime, _ = self._get_regime(pair, current_time)

        if regime == "BULLISH" and side == "sell":
            logger.info(f"SKIPPING {pair} SHORT: BULLISH regime, longs only")
            return False
        if regime == "BEARISH" and side == "buy":
            logger.info(f"SKIPPING {pair} LONG: BEARISH regime, shorts only")
            return False

        return True
