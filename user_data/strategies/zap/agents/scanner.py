"""Scanner Agent: computes all features for a pair, updates queues."""
from __future__ import annotations

import logging
from typing import Any

from pandas import DataFrame

from user_data.strategies.zap.features import compute_all_features
from user_data.strategies.zap.queues import QueueManager

logger = logging.getLogger(__name__)


class ScannerAgent:
    """Computes features for each pair and updates queues.
    Runs in populate_indicators() for each pair.
    """

    def __init__(self, cfg: dict, queue_manager: QueueManager):
        self.cfg = cfg
        self.qm = queue_manager
        self._df_cache: dict[str, DataFrame] = {}

    def reset_cache(self):
        """Reset df cache at start of new backtest cycle."""
        self._df_cache.clear()
        from user_data.strategies.zap.features.statistical import reset_cache
        reset_cache()

    def update(self, df, pair, all_pairs, btc_df=None, dp=None):
        """Compute all features for a pair.
        Caches pair df, computes features via compute_all_features, returns df with %-columns.
        """
        self._df_cache[f"{pair}__5m"] = df

        df = compute_all_features(
            df=df, pair=pair, cfg=self.cfg,
            dp=dp, all_pairs=all_pairs,
            btc_df=btc_df, df_cache=self._df_cache,
        )

        last = df.iloc[-1]
        features = {
            col: float(last[col])
            for col in df.columns
            if col.startswith("%-") and not (last[col] != last[col])  # skip NaN
        }

        logger.debug(f"[ZAP:Scanner] {pair}: {len(features)} features computed")
        return df
