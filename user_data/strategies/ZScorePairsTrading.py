"""
Z-Score Pairs Trading Strategy
Market-neutral pairs trading using Z-scores of spread between two correlated groups.

Core idea:
- Split whitelist pairs into two groups via correlation clustering
- Compute rolling Z-score of the spread between group mean returns
- Go long Group A / short Group B when spread is oversold (Z < -2)
- Go short Group A / long Group B when spread is overbought (Z > +2)
- Exit all when spread reverts to neutral (|Z| < 0.5)

This is a market-neutral strategy: always 3 long + 3 short = hedged.
"""

import logging
from datetime import datetime
from typing import Optional

import numpy as np
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter


logger = logging.getLogger(__name__)


class ZScorePairsTrading(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "5m"
    can_short = True

    max_open_trades = 6  # 3 long + 3 short

    stoploss = -0.05  # wide stop since we're hedged

    # No ROI - exit only on spread signal
    minimal_roi = {"0": 100}  # effectively disabled

    startup_candle_count = 1500  # enough for largest Z-score rolling window

    trailing_stop = False

    process_only_new_candles = True

    # ----- strategy state -----
    group_a: list[str] = []
    group_b: list[str] = []
    _groups_initialized: bool = False
    _spread_zscore: float = 0.0

    # Hyperoptable parameters
    zscore_window = IntParameter(360, 1440, default=720, space="buy", optimize=True)
    zscore_entry_threshold = DecimalParameter(1.5, 3.5, default=2.0, decimals=1, space="buy", optimize=True)
    zscore_exit_threshold = DecimalParameter(0.1, 1.0, default=0.5, decimals=1, space="sell", optimize=True)
    cum_return_window = IntParameter(30, 120, default=60, space="buy", optimize=True)

    # Stake splitting: $1000 / 6 positions
    stake_per_position: float = 166.67

    def informative_pairs(self):
        """
        We need data for all whitelist pairs at 5m (handled automatically)
        and optionally 1h for correlation analysis.
        """
        pairs = self.dp.current_whitelist() if self.dp else []
        # Request 1h data for correlation clustering on startup
        informative = [(pair, "1h") for pair in pairs]
        return informative

    def _cluster_pairs(self, pairs: list[str]) -> None:
        """
        Cluster whitelist pairs into two groups based on return correlation.
        Uses hierarchical clustering from scipy.
        """
        if self._groups_initialized:
            return

        if not self.dp:
            logger.warning("DataProvider not available, cannot cluster pairs.")
            return

        if len(pairs) < 2:
            logger.warning("Need at least 2 pairs to form groups.")
            return

        try:
            from scipy.cluster.hierarchy import fcluster, linkage
            from scipy.spatial.distance import squareform
        except ImportError:
            logger.error("scipy is required for clustering. pip install scipy")
            # Fallback: split alphabetically
            sorted_pairs = sorted(pairs)
            mid = len(sorted_pairs) // 2
            self.group_a = sorted_pairs[:mid] if mid >= 1 else sorted_pairs[:1]
            self.group_b = sorted_pairs[mid:] if mid < len(sorted_pairs) else sorted_pairs[1:]
            self._groups_initialized = True
            self._log_groups()
            return

        # Collect 1h close data for correlation
        closes = {}
        for pair in pairs:
            df = self.dp.get_pair_dataframe(pair=pair, timeframe="1h")
            if df is not None and len(df) > 50:
                closes[pair] = df["close"].pct_change().dropna().values

        if len(closes) < 2:
            logger.warning("Not enough 1h data for clustering, falling back to alphabetical split.")
            sorted_pairs = sorted(pairs)
            mid = len(sorted_pairs) // 2
            self.group_a = sorted_pairs[:mid]
            self.group_b = sorted_pairs[mid:]
            self._groups_initialized = True
            self._log_groups()
            return

        # Align lengths
        available_pairs = list(closes.keys())
        min_len = min(len(v) for v in closes.values())
        aligned = {p: closes[p][-min_len:] for p in available_pairs}

        # Build correlation matrix
        n = len(available_pairs)
        returns_matrix = np.array([aligned[p] for p in available_pairs])
        corr_matrix = np.corrcoef(returns_matrix)
        # Replace NaN with 0
        corr_matrix = np.nan_to_num(corr_matrix, nan=0.0)

        if n < 4:
            # Too few pairs for proper clustering, just split in half
            mid = n // 2
            self.group_a = available_pairs[:max(mid, 1)]
            self.group_b = available_pairs[max(mid, 1):]
            self._groups_initialized = True
            self._log_groups()
            return

        # Convert correlation to distance (1 - |corr|)
        dist_matrix = 1.0 - np.abs(corr_matrix)
        np.fill_diagonal(dist_matrix, 0.0)
        # Make symmetric and ensure no negative values
        dist_matrix = (dist_matrix + dist_matrix.T) / 2.0
        dist_matrix = np.maximum(dist_matrix, 0.0)

        try:
            condensed = squareform(dist_matrix)
            Z = linkage(condensed, method="ward")
            labels = fcluster(Z, t=2, criterion="maxclust")
        except Exception as e:
            logger.warning(f"Clustering failed ({e}), falling back to alphabetical split.")
            mid = n // 2
            self.group_a = available_pairs[:max(mid, 1)]
            self.group_b = available_pairs[max(mid, 1):]
            self._groups_initialized = True
            self._log_groups()
            return

        # Split into two groups
        cluster_1 = [p for p, l in zip(available_pairs, labels) if l == 1]
        cluster_2 = [p for p, l in zip(available_pairs, labels) if l == 2]

        # Pick up to 3 most internally correlated within each cluster
        self.group_a = self._pick_top_correlated(cluster_1, corr_matrix, available_pairs, max_n=3)
        self.group_b = self._pick_top_correlated(cluster_2, corr_matrix, available_pairs, max_n=3)

        # Ensure we have at least 1 in each group
        if not self.group_a and cluster_1:
            self.group_a = cluster_1[:3]
        if not self.group_b and cluster_2:
            self.group_b = cluster_2[:3]

        self._groups_initialized = True
        self._log_groups()

    def _pick_top_correlated(
        self,
        cluster_pairs: list[str],
        corr_matrix: np.ndarray,
        all_pairs: list[str],
        max_n: int = 3,
    ) -> list[str]:
        """Pick the top N most mutually correlated pairs within a cluster."""
        if len(cluster_pairs) <= max_n:
            return cluster_pairs

        # Compute average correlation of each pair with others in the cluster
        pair_to_idx = {p: i for i, p in enumerate(all_pairs)}
        avg_corrs = {}
        for p in cluster_pairs:
            idx = pair_to_idx[p]
            corrs = [
                abs(corr_matrix[idx][pair_to_idx[q]])
                for q in cluster_pairs
                if q != p and q in pair_to_idx
            ]
            avg_corrs[p] = np.mean(corrs) if corrs else 0.0

        # Sort by average correlation, pick top N
        sorted_pairs = sorted(avg_corrs, key=avg_corrs.get, reverse=True)
        return sorted_pairs[:max_n]

    def _log_groups(self) -> None:
        """Log the selected pair groups."""
        logger.info("=" * 60)
        logger.info("Z-Score Pairs Trading - Group Assignments")
        logger.info(f"  Group A (long when spread < -{self.zscore_entry_threshold.value}): {self.group_a}")
        logger.info(f"  Group B (long when spread > +{self.zscore_entry_threshold.value}): {self.group_b}")
        logger.info("=" * 60)
        logger.info(
            "Add these pairs to your config pair_whitelist: %s",
            self.group_a + self.group_b,
        )

    @staticmethod
    def get_pairs() -> list[str]:
        """
        Convenience method: returns a default set of 6 high-correlation USDT pairs.
        Call this to know which pairs to put in your config for backtesting.

        Usage:
            from user_data.strategies.ZScorePairsTrading import ZScorePairsTrading
            print(ZScorePairsTrading.get_pairs())
        """
        return [
            # Group A - Large-cap L1s (highly correlated)
            "BTC/USDT:USDT",
            "ETH/USDT:USDT",
            "SOL/USDT:USDT",
            # Group B - Alt L1s / DeFi (correlated among themselves, less with group A)
            "AVAX/USDT:USDT",
            "LINK/USDT:USDT",
            "DOGE/USDT:USDT",
        ]

    def _compute_spread_zscore(self, pair: str, dataframe: DataFrame) -> DataFrame:
        """
        Compute the spread Z-score using returns of all available pairs.
        The spread = mean(group_a_returns) - mean(group_b_returns).
        We Z-score this spread over the rolling window.
        """
        if not self.group_a or not self.group_b:
            dataframe["spread_zscore"] = 0.0
            return dataframe

        # Compute this pair's returns
        dataframe["returns"] = dataframe["close"].pct_change()

        # For each pair, we compute the spread Z-score independently
        # Since we can't easily access other pairs' data in populate_indicators,
        # we use a simplified approach: compute Z-score of this pair's returns
        # and set the spread signal based on group membership
        rolling_mean = dataframe["returns"].rolling(window=self.zscore_window.value).mean()
        rolling_std = dataframe["returns"].rolling(window=self.zscore_window.value).std()

        # Z-score of cumulative returns over the window (price deviation from mean)
        # Use log returns summed over a shorter window for spread computation
        dataframe["log_return"] = np.log(dataframe["close"] / dataframe["close"].shift(1))
        cum_return = dataframe["log_return"].rolling(window=self.cum_return_window.value).sum()  # 5h cumulative return
        cum_mean = cum_return.rolling(window=self.zscore_window.value).mean()
        cum_std = cum_return.rolling(window=self.zscore_window.value).std()

        dataframe["pair_zscore"] = (cum_return - cum_mean) / cum_std.replace(0, np.nan)
        dataframe["pair_zscore"] = dataframe["pair_zscore"].fillna(0.0)

        # The actual spread Z-score will be computed in populate_entry/exit
        # by combining Z-scores across pairs. For now store per-pair Z-score.
        dataframe["spread_zscore"] = dataframe["pair_zscore"]

        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]

        # Initialize groups on first call
        if not self._groups_initialized and self.dp:
            whitelist = self.dp.current_whitelist()
            self._cluster_pairs(whitelist)

        # RSI for additional context
        dataframe["rsi"] = self._compute_rsi(dataframe["close"], period=14)

        # Bollinger Bands for additional context
        bb_window = 20
        bb_std = 2.0
        dataframe["bb_mid"] = dataframe["close"].rolling(window=bb_window).mean()
        dataframe["bb_std"] = dataframe["close"].rolling(window=bb_window).std()
        dataframe["bb_upper"] = dataframe["bb_mid"] + bb_std * dataframe["bb_std"]
        dataframe["bb_lower"] = dataframe["bb_mid"] - bb_std * dataframe["bb_std"]

        # Compute spread Z-score components
        dataframe = self._compute_spread_zscore(pair, dataframe)

        return dataframe

    @staticmethod
    def _compute_rsi(series, period: int = 14):
        """Compute RSI without depending on TA-Lib."""
        delta = series.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi.fillna(50.0)

    def _get_spread_signal(self, pair: str, dataframe: DataFrame) -> DataFrame:
        """
        Determine spread-based signal by aggregating Z-scores across groups.
        Since we process one pair at a time, we look up other pairs' data
        from the DataProvider and compute the actual spread Z-score.
        """
        if not self.group_a or not self.group_b or not self.dp:
            dataframe["spread_signal"] = 0
            return dataframe

        # Collect Z-scores from all pairs in both groups
        group_a_zscores = []
        group_b_zscores = []

        for p in self.group_a:
            if p == pair:
                group_a_zscores.append(dataframe["pair_zscore"])
            else:
                other_df = self.dp.get_pair_dataframe(pair=p, timeframe=self.timeframe)
                if other_df is not None and len(other_df) > self.zscore_window.value + self.cum_return_window.value:
                    log_ret = np.log(other_df["close"] / other_df["close"].shift(1))
                    cum_ret = log_ret.rolling(window=self.cum_return_window.value).sum()
                    cum_mean = cum_ret.rolling(window=self.zscore_window.value).mean()
                    cum_std = cum_ret.rolling(window=self.zscore_window.value).std()
                    z = (cum_ret - cum_mean) / cum_std.replace(0, np.nan)
                    # Align to current dataframe length
                    z = z.iloc[-len(dataframe):].reset_index(drop=True)
                    group_a_zscores.append(z.fillna(0.0))

        for p in self.group_b:
            if p == pair:
                group_b_zscores.append(dataframe["pair_zscore"])
            else:
                other_df = self.dp.get_pair_dataframe(pair=p, timeframe=self.timeframe)
                if other_df is not None and len(other_df) > self.zscore_window.value + self.cum_return_window.value:
                    log_ret = np.log(other_df["close"] / other_df["close"].shift(1))
                    cum_ret = log_ret.rolling(window=self.cum_return_window.value).sum()
                    cum_mean = cum_ret.rolling(window=self.zscore_window.value).mean()
                    cum_std = cum_ret.rolling(window=self.zscore_window.value).std()
                    z = (cum_ret - cum_mean) / cum_std.replace(0, np.nan)
                    z = z.iloc[-len(dataframe):].reset_index(drop=True)
                    group_b_zscores.append(z.fillna(0.0))

        # Compute spread Z-score = mean(group_a) - mean(group_b)
        if group_a_zscores and group_b_zscores:
            mean_a = sum(group_a_zscores) / len(group_a_zscores)
            mean_b = sum(group_b_zscores) / len(group_b_zscores)
            spread = mean_a - mean_b

            # Z-score the spread itself
            spread_mean = spread.rolling(window=self.zscore_window.value).mean()
            spread_std = spread.rolling(window=self.zscore_window.value).std()
            spread_z = (spread - spread_mean) / spread_std.replace(0, np.nan)
            dataframe["spread_zscore"] = spread_z.fillna(0.0)
        else:
            dataframe["spread_zscore"] = 0.0

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]

        # Recompute spread Z-score using cross-pair data
        dataframe = self._get_spread_signal(pair, dataframe)

        is_group_a = pair in self.group_a
        is_group_b = pair in self.group_b

        # When spread Z < -2: long A, short B (spread will revert up)
        # When spread Z > +2: short A, long B (spread will revert down)

        if is_group_a:
            # Group A: long when spread oversold, short when spread overbought
            dataframe.loc[
                dataframe["spread_zscore"] < -self.zscore_entry_threshold.value,
                ["enter_long", "enter_tag"],
            ] = (1, "zscore_long_a")

            dataframe.loc[
                dataframe["spread_zscore"] > self.zscore_entry_threshold.value,
                ["enter_short", "enter_tag"],
            ] = (1, "zscore_short_a")

        elif is_group_b:
            # Group B: short when spread oversold, long when spread overbought
            dataframe.loc[
                dataframe["spread_zscore"] < -self.zscore_entry_threshold.value,
                ["enter_short", "enter_tag"],
            ] = (1, "zscore_short_b")

            dataframe.loc[
                dataframe["spread_zscore"] > self.zscore_entry_threshold.value,
                ["enter_long", "enter_tag"],
            ] = (1, "zscore_long_b")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]

        # Exit when spread Z-score returns to neutral range [-0.5, +0.5]
        neutral = (
            (dataframe["spread_zscore"] > -self.zscore_exit_threshold.value)
            & (dataframe["spread_zscore"] < self.zscore_exit_threshold.value)
        )

        if pair in self.group_a or pair in self.group_b:
            dataframe.loc[neutral, "exit_long"] = 1
            dataframe.loc[neutral, "exit_short"] = 1

        return dataframe

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
        """Split stake evenly across 6 positions: ~$166.67 each."""
        return min(self.stake_per_position, max_stake)

    def leverage(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: Optional[str],
        side: str,
        **kwargs,
    ) -> float:
        """No leverage for now."""
        return 1.0
