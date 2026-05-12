"""
Z-Score Pairs Trading Base Strategy
Skeleton: clustering into 2 groups of 3 pairs, opens and closes positions.
Baseline for building on top of.
"""

import logging
from datetime import datetime
from typing import Optional

import numpy as np
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy


logger = logging.getLogger(__name__)


class ZScorePairsTradingBase(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1h"
    can_short = True

    max_open_trades = 6

    stoploss = -0.99  # effectively disabled
    minimal_roi = {"0": 999}  # effectively disabled

    startup_candle_count = 100
    trailing_stop = False
    process_only_new_candles = True

    stake_per_position: float = 166.67

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Per-instance mutable state (avoid class-level sharing in strategy-list)
        self.group_a: list[str] = []
        self.group_b: list[str] = []
        self._groups_initialized: bool = False

    @staticmethod
    def get_pairs():
        return [
            "BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT",
            "AVAX/USDT:USDT", "LINK/USDT:USDT", "DOGE/USDT:USDT",
        ]

    def informative_pairs(self):
        pairs = self.dp.current_whitelist() if self.dp else []
        return [(pair, "1d") for pair in pairs]

    # =========================================================================
    # CLUSTERING — split 6 pairs into 2 groups of 3
    # =========================================================================

    def _cluster_pairs(self, pairs: list[str]) -> None:
        if self._groups_initialized:
            return

        if not self.dp or len(pairs) < 2:
            return

        try:
            from scipy.cluster.hierarchy import fcluster, linkage
            from scipy.spatial.distance import squareform
        except ImportError:
            self._fallback_split(pairs)
            return

        closes = {}
        for pair in pairs:
            df = self.dp.get_pair_dataframe(pair=pair, timeframe="1d")
            if df is not None and len(df) > 20:
                closes[pair] = df["close"].pct_change().dropna().values

        if len(closes) < 4:
            self._fallback_split(list(closes.keys()) or pairs)
            return

        available_pairs = list(closes.keys())
        min_len = min(len(v) for v in closes.values())
        aligned = {p: closes[p][-min_len:] for p in available_pairs}

        returns_matrix = np.array([aligned[p] for p in available_pairs])
        corr_matrix = np.corrcoef(returns_matrix)
        corr_matrix = np.nan_to_num(corr_matrix, nan=0.0)

        dist_matrix = 1.0 - np.abs(corr_matrix)
        np.fill_diagonal(dist_matrix, 0.0)
        dist_matrix = (dist_matrix + dist_matrix.T) / 2.0
        dist_matrix = np.maximum(dist_matrix, 0.0)

        try:
            condensed = squareform(dist_matrix)
            Z = linkage(condensed, method="ward")
            labels = fcluster(Z, t=2, criterion="maxclust")
        except Exception:
            self._fallback_split(available_pairs)
            return

        cluster_1 = [p for p, l in zip(available_pairs, labels) if l == 1]
        cluster_2 = [p for p, l in zip(available_pairs, labels) if l == 2]

        # Ensure balanced groups: if clustering is too lopsided, rebalance
        if len(cluster_1) < 2 or len(cluster_2) < 2:
            # Clustering failed to produce balanced groups — use fallback
            self._fallback_split(available_pairs)
            return

        # Pick top correlated pairs from each cluster (max 3 per group)
        self.group_a = self._pick_top_correlated(cluster_1, corr_matrix, available_pairs, max_n=3)
        self.group_b = self._pick_top_correlated(cluster_2, corr_matrix, available_pairs, max_n=3)

        if not self.group_a and cluster_1:
            self.group_a = cluster_1[:3]
        if not self.group_b and cluster_2:
            self.group_b = cluster_2[:3]

        # Final safety: must have at least 2 in each group
        if len(self.group_a) < 2 or len(self.group_b) < 2:
            self._fallback_split(available_pairs)
            return

        self._groups_initialized = True
        self._log_groups()

    def _fallback_split(self, pairs: list[str]) -> None:
        sorted_pairs = sorted(pairs)
        mid = max(len(sorted_pairs) // 2, 1)
        self.group_a = sorted_pairs[:mid][:3]
        self.group_b = sorted_pairs[mid:][:3]
        self._groups_initialized = True
        self._log_groups()

    def _pick_top_correlated(self, cluster_pairs, corr_matrix, all_pairs, max_n=3):
        if len(cluster_pairs) <= max_n:
            return cluster_pairs
        pair_to_idx = {p: i for i, p in enumerate(all_pairs)}
        avg_corrs = {}
        for p in cluster_pairs:
            idx = pair_to_idx[p]
            corrs = [abs(corr_matrix[idx][pair_to_idx[q]]) for q in cluster_pairs if q != p and q in pair_to_idx]
            avg_corrs[p] = np.mean(corrs) if corrs else 0.0
        return sorted(avg_corrs, key=avg_corrs.get, reverse=True)[:max_n]

    def _log_groups(self):
        logger.info("=" * 60)
        logger.info("Z-Score Pairs Base - Group Assignments")
        logger.info(f"  Group A (3): {self.group_a}")
        logger.info(f"  Group B (3): {self.group_b}")
        logger.info("=" * 60)

    # =========================================================================
    # INDICATORS — minimal, just initialize groups
    # =========================================================================

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if not self._groups_initialized and self.dp:
            self._cluster_pairs(self.dp.current_whitelist())
        return dataframe

    # =========================================================================
    # ENTRY / EXIT — no signals (skeleton)
    # =========================================================================

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]

        if pair in self.group_a:
            # Group A: long — signal every candle, freqtrade opens once per pair
            dataframe.loc[:, "enter_long"] = 1
            dataframe.loc[:, "enter_tag"] = "group_a"
        elif pair in self.group_b:
            # Group B: short — signal every candle, freqtrade opens once per pair
            dataframe.loc[:, "enter_short"] = 1
            dataframe.loc[:, "enter_tag"] = "group_b"

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    # =========================================================================
    # STAKE — fixed per position
    # =========================================================================

    def custom_stake_amount(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_stake: float,
        min_stake: Optional[float],
        max_stake: float,
        leverage: float,
        entry_tag: Optional[str],
        side: str,
        **kwargs,
    ) -> float:
        return min(self.stake_per_position, max_stake)
