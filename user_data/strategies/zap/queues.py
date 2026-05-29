"""Passive LONG/SHORT queues with feature storage and ranking."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PairEntry:
    """Single pair entry in a queue."""
    pair: str
    features: dict[str, float] = field(default_factory=dict)
    predicted_return: float = 0.0
    regime_adjusted_score: float = 0.0
    rank: int = 0
    last_updated: int = 0
    cooldown_until: int = 0


class QueueManager:
    """Manages LONG and SHORT queues for all pairs."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.long_queue: dict[str, PairEntry] = {}
        self.short_queue: dict[str, PairEntry] = {}
        self._cooldown_candles = cfg.get("entry", {}).get("cooldown_candles", 36)

    def reset(self):
        self.long_queue.clear()
        self.short_queue.clear()

    def update_pair(self, pair, features, predicted_return, regime_multiplier, candle_idx):
        """Update pair in appropriate queue (positive=LONG, negative=SHORT)."""
        entry = PairEntry(
            pair=pair, features=features, predicted_return=predicted_return,
            regime_adjusted_score=predicted_return * regime_multiplier,
            last_updated=candle_idx,
        )
        # Preserve cooldown from previous queue position
        old = self.long_queue.get(pair) or self.short_queue.get(pair)
        if old and old.cooldown_until > candle_idx:
            entry.cooldown_until = old.cooldown_until

        if predicted_return >= 0:
            self.long_queue[pair] = entry
            self.short_queue.pop(pair, None)
        else:
            self.short_queue[pair] = entry
            self.long_queue.pop(pair, None)

    def set_cooldown(self, pair, candle_idx):
        until = candle_idx + self._cooldown_candles
        if pair in self.long_queue:
            self.long_queue[pair].cooldown_until = until
        if pair in self.short_queue:
            self.short_queue[pair].cooldown_until = until

    def rank_queues(self, candle_idx):
        for queue in [self.long_queue, self.short_queue]:
            eligible = [(p, e) for p, e in queue.items() if e.cooldown_until <= candle_idx]
            eligible.sort(key=lambda x: abs(x[1].regime_adjusted_score), reverse=True)
            for rank, (pair, _) in enumerate(eligible):
                queue[pair].rank = rank

    def get_top_k(self, side, k, candle_idx, min_score=0.0):
        queue = self.long_queue if side == "long" else self.short_queue
        eligible = [
            e for e in queue.values()
            if e.cooldown_until <= candle_idx and abs(e.regime_adjusted_score) >= min_score
        ]
        eligible.sort(key=lambda x: abs(x.regime_adjusted_score), reverse=True)
        return eligible[:k]

    def get_pair_features(self, pair):
        entry = self.long_queue.get(pair) or self.short_queue.get(pair)
        return entry.features if entry else {}

    def log_state(self, candle_idx, top_n=5):
        long_top = sorted(
            self.long_queue.values(),
            key=lambda x: abs(x.regime_adjusted_score),
            reverse=True,
        )[:top_n]
        short_top = sorted(
            self.short_queue.values(),
            key=lambda x: abs(x.regime_adjusted_score),
            reverse=True,
        )[:top_n]
        logger.info(
            f"[ZAP] Candle {candle_idx} | LONG Q ({len(self.long_queue)}): "
            + ", ".join(f"{e.pair}={e.regime_adjusted_score:.4f}" for e in long_top)
            + f" | SHORT Q ({len(self.short_queue)}): "
            + ", ".join(f"{e.pair}={e.regime_adjusted_score:.4f}" for e in short_top)
        )
