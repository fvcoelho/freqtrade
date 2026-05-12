"""
Kelly + Polymarket Sentiment Multiplier Strategy (Mode 1)

Polymarket odds adjust Kelly's win probability estimate.
Bullish crowd sentiment increases Kelly for longs, decreases for shorts.
"""

import logging
from datetime import datetime
from typing import Optional

from freqtrade.persistence import Trade

from KellyDCAMeanReversion import KellyDCAMeanReversion
from polymarket_provider import PolymarketDataProvider, PolymarketSignal

logger = logging.getLogger(__name__)


class KellyPolySentiment(KellyDCAMeanReversion):
    poly_sensitivity = 0.3
    poly_neutral_low = 0.45
    poly_neutral_high = 0.55
    poly_weight = 0.5

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._poly_provider = PolymarketDataProvider("user_data/polymarket")

    def _get_coin_from_pair(self, pair: str) -> str:
        return pair.split("/")[0]

    def _get_poly_signal(self, pair: str, current_time: datetime) -> PolymarketSignal:
        self._poly_provider.initialize()
        coin = self._get_coin_from_pair(pair)
        ts = int(current_time.timestamp())
        return self._poly_provider.get_signal(coin, ts)

    def _calculate_kelly_with_sentiment(self, pair: str, side: str, current_time: datetime) -> dict:
        base_kelly = self._calculate_kelly()
        signal = self._get_poly_signal(pair, current_time)

        if signal.num_markets == 0:
            return base_kelly

        if self.poly_neutral_low <= signal.bullish_prob <= self.poly_neutral_high:
            return base_kelly

        sentiment_shift = (signal.bullish_prob - 0.5) * self.poly_sensitivity

        # Use historical win rate if available, otherwise assume 50%
        base_W = base_kelly["win_rate"] if base_kelly["enough_data"] else 0.5
        R = base_kelly["r_ratio"] if base_kelly["enough_data"] else 1.0

        if side == "long":
            adjusted_W = base_W + sentiment_shift
        else:
            adjusted_W = base_W - sentiment_shift

        adjusted_W = max(0.05, min(0.95, adjusted_W))
        kelly_adjusted_raw = adjusted_W - (1 - adjusted_W) / R

        if base_kelly["enough_data"]:
            blended_raw = (
                base_kelly["kelly_raw"] * (1 - self.poly_weight)
                + kelly_adjusted_raw * self.poly_weight
            )
        else:
            # No trade history — use Polymarket-only Kelly
            blended_raw = kelly_adjusted_raw

        kelly_final = blended_raw * self.kelly_fraction
        kelly_final = max(self.min_stake_pct, min(self.max_stake_pct, kelly_final))
        if blended_raw <= 0:
            kelly_final = self.min_stake_pct

        logger.info(
            f"Poly sentiment for {pair} {side}: "
            f"poly_prob={signal.bullish_prob:.2f} shift={sentiment_shift:+.3f} "
            f"base_W={base_W:.3f} adj_W={adjusted_W:.3f} "
            f"base_kelly={base_kelly['kelly_raw']:.3f} adj_kelly={blended_raw:.3f} "
            f"final={kelly_final:.3f} ({signal.num_markets} markets)"
        )

        result = base_kelly.copy()
        result["kelly_pct"] = kelly_final
        result["kelly_raw"] = blended_raw
        result["win_rate"] = adjusted_W
        result["poly_signal"] = signal
        return result

    def custom_stake_amount(
        self, pair: str, current_time: datetime, current_rate: float,
        proposed_stake: float, min_stake: Optional[float], max_stake: float,
        leverage: float, entry_tag: Optional[str], side: str, **kwargs,
    ) -> float:
        kelly = self._calculate_kelly_with_sentiment(pair, side, current_time)
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
        kelly = self._calculate_kelly_with_sentiment(pair, side, current_time)
        if kelly["enough_data"] and kelly["kelly_raw"] <= 0:
            logger.warning(f"SKIPPING {pair} {side}: Sentiment-adjusted Kelly negative ({kelly['kelly_raw']:.3f})")
            return False
        return True
