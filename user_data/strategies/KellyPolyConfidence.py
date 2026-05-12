"""
Kelly + Polymarket Confidence Scaler Strategy (Mode 2)

Uses Polymarket conviction strength and volume to scale Kelly fraction.
High conviction + high volume = full Kelly. Low conviction = quarter Kelly.
"""

import logging
from datetime import datetime
from typing import Optional

from KellyDCAMeanReversion import KellyDCAMeanReversion
from polymarket_provider import PolymarketDataProvider

logger = logging.getLogger(__name__)


class KellyPolyConfidence(KellyDCAMeanReversion):
    min_kelly_mult = 0.25
    volume_threshold = 100000.0
    conviction_weight = 0.7
    volume_weight = 0.3

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._poly_provider = PolymarketDataProvider("user_data/polymarket")

    def _get_coin_from_pair(self, pair: str) -> str:
        return pair.split("/")[0]

    def _calculate_kelly_with_confidence(self, pair: str, current_time: datetime) -> dict:
        base_kelly = self._calculate_kelly()
        self._poly_provider.initialize()
        coin = self._get_coin_from_pair(pair)
        signal = self._poly_provider.get_signal(coin, int(current_time.timestamp()))

        if signal.num_markets == 0:
            return base_kelly

        conviction = signal.conviction
        volume_score = min(1.0, signal.total_volume / self.volume_threshold)
        confidence = conviction * self.conviction_weight + volume_score * self.volume_weight
        kelly_multiplier = self.min_kelly_mult + confidence * (1.0 - self.min_kelly_mult)

        # Use base kelly_pct, or default if not enough trade data yet
        base_pct = base_kelly["kelly_pct"] if base_kelly["enough_data"] else self.default_stake_pct
        adjusted_pct = base_pct * kelly_multiplier
        adjusted_pct = max(self.min_stake_pct, min(self.max_stake_pct, adjusted_pct))

        logger.info(
            f"Poly confidence for {pair}: "
            f"conviction={conviction:.2f} vol_score={volume_score:.2f} "
            f"confidence={confidence:.2f} multiplier={kelly_multiplier:.2f} "
            f"base_kelly={base_kelly['kelly_pct']:.3f} adjusted={adjusted_pct:.3f} "
            f"({signal.num_markets} markets)"
        )

        result = base_kelly.copy()
        result["kelly_pct"] = adjusted_pct
        result["poly_signal"] = signal
        return result

    def custom_stake_amount(
        self, pair: str, current_time: datetime, current_rate: float,
        proposed_stake: float, min_stake: Optional[float], max_stake: float,
        leverage: float, entry_tag: Optional[str], side: str, **kwargs,
    ) -> float:
        kelly = self._calculate_kelly_with_confidence(pair, current_time)
        wallet_balance = self.wallets.get_total_stake_amount() if self.wallets else 1000
        kelly_stake = wallet_balance * kelly["kelly_pct"]
        if min_stake is not None:
            kelly_stake = max(kelly_stake, min_stake)
        kelly_stake = min(kelly_stake, max_stake)
        return kelly_stake * self.initial_stake_pct
