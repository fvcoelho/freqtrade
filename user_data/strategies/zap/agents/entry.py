"""Entry Agent: reads queues + FreqAI predictions, generates entry signals."""
from __future__ import annotations

import logging

from pandas import DataFrame

from user_data.strategies.zap.agents.regime import RegimeState
from user_data.strategies.zap.queues import QueueManager

logger = logging.getLogger(__name__)


class EntryAgent:
    """Decides entries based on FreqAI predictions and queue ranking."""

    def __init__(self, cfg: dict, queue_manager: QueueManager):
        self.cfg = cfg
        self.qm = queue_manager
        self._ecfg = cfg.get("entry", {})

    def generate_signals(self, df: DataFrame, pair: str, regime: RegimeState) -> DataFrame:
        """Mark entry signals based on FreqAI prediction (&-s_close column)."""
        df["enter_long"] = 0
        df["enter_short"] = 0
        df["enter_tag"] = ""

        min_pred = self._ecfg.get("min_predicted_return", 0.005)
        has_freqai = "&-s_close" in df.columns and "do_predict" in df.columns

        if has_freqai:
            long_mask = (df["do_predict"] == 1) & (df["&-s_close"] > min_pred)
            df.loc[long_mask, "enter_long"] = 1
            df.loc[long_mask, "enter_tag"] = "zap_long"

            short_mask = (df["do_predict"] == 1) & (df["&-s_close"] < -min_pred)
            df.loc[short_mask, "enter_short"] = 1
            df.loc[short_mask, "enter_tag"] = "zap_short"

        return df

    def confirm_entry(
        self,
        pair: str,
        side: str,
        rate: float,
        regime: RegimeState,
        candle_idx: int,
        current_open_trades: int,
        current_prediction: float,
    ) -> bool:
        """Gate entry: only allow if pair is in top-K of its queue."""
        max_trades = self.cfg.get("max_open_trades", 6)
        if current_open_trades >= max_trades:
            logger.info(f"[ZAP:Entry] REJECT {pair} {side}: max trades reached")
            return False

        top_k = self._ecfg.get("top_k", 3)
        min_score = self._ecfg.get("min_predicted_return", 0.005)

        mult = regime.get_multiplier(side, self.cfg)
        self.qm.update_pair(pair, {}, current_prediction, mult, candle_idx)
        self.qm.rank_queues(candle_idx)

        top = self.qm.get_top_k(side, top_k, candle_idx, min_score)
        top_pairs = [e.pair for e in top]

        if pair in top_pairs:
            rank = top_pairs.index(pair)
            score = top[rank].regime_adjusted_score
            logger.info(
                f"[ZAP:Entry] ACCEPT {pair} {side} rank={rank + 1}/{len(top_pairs)}"
                f" score={score:.4f} regime={regime.regime}"
            )
            return True
        else:
            logger.info(
                f"[ZAP:Entry] REJECT {pair} {side}: not in top-{top_k}"
                f" (top: {top_pairs[:3]})"
            )
            return False
