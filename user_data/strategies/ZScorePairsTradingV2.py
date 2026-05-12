"""
Z-Score Pairs Trading Strategy V2
Market-neutral pairs trading with regime filter and dynamic leverage.

Improvements over V1:
- 1h timeframe (mean reversion works better on slower timeframes)
- Regime filter: only trade when cross-group correlation is stable
- Dynamic leverage: 2-3x on high-confidence signals, 1x otherwise
- Pre-computed Z-scores in populate_indicators (faster backtest)
"""

import logging
from datetime import datetime
from typing import Optional

import numpy as np
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter


logger = logging.getLogger(__name__)


class ZScorePairsTradingV2(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1h"
    can_short = True

    max_open_trades = 6

    stoploss = -0.04  # tighter stop — 3 stops at -7% was killing us

    minimal_roi = {
        "0": 0.05,    # 5% take profit
        "12": 0.03,   # 3% after 12h
        "24": 0.015,  # 1.5% after 24h
        "48": 0.005,  # 0.5% after 2 days — take anything
    }

    startup_candle_count = 500  # ~21 days of 1h data

    trailing_stop = False
    process_only_new_candles = True

    # ----- strategy state -----
    group_a: list[str] = []
    group_b: list[str] = []
    _groups_initialized: bool = False
    _pair_zscores: dict[str, DataFrame] = {}

    # Hyperoptable parameters (tuned from V1 hyperopt, scaled for 1h)
    zscore_window = IntParameter(72, 360, default=168, space="buy", optimize=True)  # 3-15 days
    zscore_entry_threshold = DecimalParameter(1.5, 3.5, default=2.5, decimals=1, space="buy", optimize=True)
    zscore_exit_threshold = DecimalParameter(0.2, 1.2, default=0.7, decimals=1, space="sell", optimize=True)
    cum_return_window = IntParameter(6, 48, default=12, space="buy", optimize=True)  # 6-48 hours

    # Regime filter: rolling correlation stability window
    regime_window = IntParameter(48, 168, default=72, space="buy", optimize=True)  # 2-7 days
    regime_corr_min = DecimalParameter(0.3, 0.8, default=0.5, decimals=1, space="buy", optimize=True)

    stake_per_position: float = 166.67

    def informative_pairs(self):
        pairs = self.dp.current_whitelist() if self.dp else []
        return [(pair, "1d") for pair in pairs]

    # =========================================================================
    # CLUSTERING (same as V1 but uses 1d data for more stable clusters)
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
            sorted_pairs = sorted(pairs)
            mid = len(sorted_pairs) // 2
            self.group_a = sorted_pairs[:max(mid, 1)]
            self.group_b = sorted_pairs[max(mid, 1):]
            self._groups_initialized = True
            self._log_groups()
            return

        closes = {}
        for pair in pairs:
            df = self.dp.get_pair_dataframe(pair=pair, timeframe="1d")
            if df is not None and len(df) > 20:
                closes[pair] = df["close"].pct_change().dropna().values

        if len(closes) < 2:
            sorted_pairs = sorted(pairs)
            mid = len(sorted_pairs) // 2
            self.group_a = sorted_pairs[:mid]
            self.group_b = sorted_pairs[mid:]
            self._groups_initialized = True
            self._log_groups()
            return

        available_pairs = list(closes.keys())
        min_len = min(len(v) for v in closes.values())
        aligned = {p: closes[p][-min_len:] for p in available_pairs}

        n = len(available_pairs)
        returns_matrix = np.array([aligned[p] for p in available_pairs])
        corr_matrix = np.corrcoef(returns_matrix)
        corr_matrix = np.nan_to_num(corr_matrix, nan=0.0)

        if n < 4:
            mid = n // 2
            self.group_a = available_pairs[:max(mid, 1)]
            self.group_b = available_pairs[max(mid, 1):]
            self._groups_initialized = True
            self._log_groups()
            return

        dist_matrix = 1.0 - np.abs(corr_matrix)
        np.fill_diagonal(dist_matrix, 0.0)
        dist_matrix = (dist_matrix + dist_matrix.T) / 2.0
        dist_matrix = np.maximum(dist_matrix, 0.0)

        try:
            condensed = squareform(dist_matrix)
            Z = linkage(condensed, method="ward")
            labels = fcluster(Z, t=2, criterion="maxclust")
        except Exception:
            mid = n // 2
            self.group_a = available_pairs[:max(mid, 1)]
            self.group_b = available_pairs[max(mid, 1):]
            self._groups_initialized = True
            self._log_groups()
            return

        cluster_1 = [p for p, l in zip(available_pairs, labels) if l == 1]
        cluster_2 = [p for p, l in zip(available_pairs, labels) if l == 2]

        self.group_a = self._pick_top_correlated(cluster_1, corr_matrix, available_pairs, max_n=3)
        self.group_b = self._pick_top_correlated(cluster_2, corr_matrix, available_pairs, max_n=3)

        if not self.group_a and cluster_1:
            self.group_a = cluster_1[:3]
        if not self.group_b and cluster_2:
            self.group_b = cluster_2[:3]

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
        logger.info("Z-Score Pairs V2 - Group Assignments")
        logger.info(f"  Group A: {self.group_a}")
        logger.info(f"  Group B: {self.group_b}")
        logger.info(f"  Entry threshold: +/-{self.zscore_entry_threshold.value}")
        logger.info(f"  Regime filter: corr > {self.regime_corr_min.value}")
        logger.info("=" * 60)

    @staticmethod
    def get_pairs():
        return [
            "BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT",
            "AVAX/USDT:USDT", "LINK/USDT:USDT", "DOGE/USDT:USDT",
        ]

    # =========================================================================
    # INDICATORS — pre-compute everything here (fast backtest)
    # =========================================================================

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]

        if not self._groups_initialized and self.dp:
            self._cluster_pairs(self.dp.current_whitelist())

        # Per-pair Z-score
        dataframe["log_return"] = np.log(dataframe["close"] / dataframe["close"].shift(1))
        cum_ret = dataframe["log_return"].rolling(window=self.cum_return_window.value).sum()
        cum_mean = cum_ret.rolling(window=self.zscore_window.value).mean()
        cum_std = cum_ret.rolling(window=self.zscore_window.value).std()
        dataframe["pair_zscore"] = ((cum_ret - cum_mean) / cum_std.replace(0, np.nan)).fillna(0.0)

        # RSI for regime context
        dataframe["rsi"] = self._compute_rsi(dataframe["close"], period=14)

        # ATR for volatility regime
        high = dataframe["high"]
        low = dataframe["low"]
        close = dataframe["close"]
        tr = np.maximum(high - low, np.maximum(abs(high - close.shift(1)), abs(low - close.shift(1))))
        dataframe["atr"] = tr.rolling(window=14).mean()
        dataframe["atr_pct"] = dataframe["atr"] / close * 100

        # Volatility regime: normalized ATR (high vol = risky for mean reversion)
        atr_mean = dataframe["atr_pct"].rolling(window=self.regime_window.value).mean()
        atr_std = dataframe["atr_pct"].rolling(window=self.regime_window.value).std()
        dataframe["vol_regime"] = ((dataframe["atr_pct"] - atr_mean) / atr_std.replace(0, np.nan)).fillna(0.0)

        # Store this pair's Z-score for cross-pair spread computation
        self._pair_zscores[pair] = dataframe[["pair_zscore"]].copy()

        # Compute spread Z-score using all available pair data
        dataframe = self._compute_spread(pair, dataframe)

        # Regime filter: rolling correlation between groups
        dataframe = self._compute_regime(pair, dataframe)

        return dataframe

    def _compute_spread(self, pair: str, dataframe: DataFrame) -> DataFrame:
        """Compute spread Z-score from pre-cached pair Z-scores."""
        if not self.group_a or not self.group_b or not self.dp:
            dataframe["spread_zscore"] = 0.0
            return dataframe

        group_a_zscores = []
        group_b_zscores = []

        for p in self.group_a:
            z = self._get_pair_zscore(p, pair, dataframe)
            if z is not None:
                group_a_zscores.append(z)

        for p in self.group_b:
            z = self._get_pair_zscore(p, pair, dataframe)
            if z is not None:
                group_b_zscores.append(z)

        if group_a_zscores and group_b_zscores:
            mean_a = sum(group_a_zscores) / len(group_a_zscores)
            mean_b = sum(group_b_zscores) / len(group_b_zscores)
            spread = mean_a - mean_b

            spread_mean = spread.rolling(window=self.zscore_window.value).mean()
            spread_std = spread.rolling(window=self.zscore_window.value).std()
            spread_z = ((spread - spread_mean) / spread_std.replace(0, np.nan)).fillna(0.0)
            dataframe["spread_zscore"] = spread_z
        else:
            dataframe["spread_zscore"] = 0.0

        return dataframe

    def _get_pair_zscore(self, target_pair: str, current_pair: str, dataframe: DataFrame):
        """Get Z-score series for a pair, either from cache or compute fresh."""
        if target_pair == current_pair:
            return dataframe["pair_zscore"]

        # Try cache first
        if target_pair in self._pair_zscores:
            cached = self._pair_zscores[target_pair]["pair_zscore"]
            return cached.iloc[-len(dataframe):].reset_index(drop=True)

        # Compute fresh from DataProvider
        if not self.dp:
            return None
        other_df = self.dp.get_pair_dataframe(pair=target_pair, timeframe=self.timeframe)
        if other_df is None or len(other_df) < self.zscore_window.value + self.cum_return_window.value:
            return None

        log_ret = np.log(other_df["close"] / other_df["close"].shift(1))
        cum_ret = log_ret.rolling(window=self.cum_return_window.value).sum()
        cum_mean = cum_ret.rolling(window=self.zscore_window.value).mean()
        cum_std = cum_ret.rolling(window=self.zscore_window.value).std()
        z = ((cum_ret - cum_mean) / cum_std.replace(0, np.nan)).fillna(0.0)
        return z.iloc[-len(dataframe):].reset_index(drop=True)

    def _compute_regime(self, pair: str, dataframe: DataFrame) -> DataFrame:
        """Compute regime filter: rolling correlation between group A and group B returns.

        When correlation breaks down (drops below threshold), the mean-reversion
        relationship is unstable — skip trades.
        """
        if not self.group_a or not self.group_b or not self.dp:
            dataframe["regime_ok"] = 1
            return dataframe

        # Get returns for one pair from each group
        pair_a = self.group_a[0]
        pair_b = self.group_b[0]

        ret_a = self._get_returns(pair_a, pair, dataframe)
        ret_b = self._get_returns(pair_b, pair, dataframe)

        if ret_a is not None and ret_b is not None:
            # Rolling correlation between the two representative pairs
            rolling_corr = ret_a.rolling(window=self.regime_window.value).corr(ret_b)
            # Regime is OK when correlation is above minimum (pairs are behaving normally)
            # High positive correlation between groups = they move together = good for spread trading
            # We actually want them to be correlated so the spread is mean-reverting
            dataframe["rolling_corr"] = rolling_corr.fillna(0.0)
            dataframe["regime_ok"] = (rolling_corr.abs() > self.regime_corr_min.value).astype(int).fillna(0)
        else:
            dataframe["rolling_corr"] = 0.0
            dataframe["regime_ok"] = 1

        return dataframe

    def _get_returns(self, target_pair: str, current_pair: str, dataframe: DataFrame):
        """Get log returns for a pair."""
        if target_pair == current_pair:
            return dataframe["log_return"]

        if not self.dp:
            return None
        other_df = self.dp.get_pair_dataframe(pair=target_pair, timeframe=self.timeframe)
        if other_df is None or len(other_df) < 50:
            return None

        ret = np.log(other_df["close"] / other_df["close"].shift(1))
        return ret.iloc[-len(dataframe):].reset_index(drop=True)

    @staticmethod
    def _compute_rsi(series, period=14):
        delta = series.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        return (100.0 - (100.0 / (1.0 + rs))).fillna(50.0)

    # =========================================================================
    # ENTRY / EXIT
    # =========================================================================

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]
        is_group_a = pair in self.group_a
        is_group_b = pair in self.group_b

        # Regime filter: only trade when correlation structure is stable
        regime = dataframe["regime_ok"] == 1

        # Volatility filter: don't enter in extreme volatility (vol Z > 1.5)
        vol_ok = dataframe["vol_regime"] < 1.5

        # RSI confirmation: don't long overbought, don't short oversold
        rsi_ok_long = dataframe["rsi"] < 60
        rsi_ok_short = dataframe["rsi"] > 40

        base_filter = regime & vol_ok & (dataframe["volume"] > 0)

        # Spread signals
        spread_oversold = dataframe["spread_zscore"] < -self.zscore_entry_threshold.value
        spread_overbought = dataframe["spread_zscore"] > self.zscore_entry_threshold.value

        # Strong signals (deeper Z-score) — used for leverage decision
        spread_strong_oversold = dataframe["spread_zscore"] < -(self.zscore_entry_threshold.value + 0.5)
        spread_strong_overbought = dataframe["spread_zscore"] > (self.zscore_entry_threshold.value + 0.5)

        if is_group_a:
            # Long A: spread oversold + RSI not overbought
            dataframe.loc[
                base_filter & spread_oversold & rsi_ok_long,
                ["enter_long", "enter_tag"],
            ] = (1, "zscore_long_a")
            dataframe.loc[
                base_filter & spread_strong_oversold & rsi_ok_long,
                ["enter_long", "enter_tag"],
            ] = (1, "zscore_long_a_strong")

            # Short A: spread overbought + RSI not oversold
            dataframe.loc[
                base_filter & spread_overbought & rsi_ok_short,
                ["enter_short", "enter_tag"],
            ] = (1, "zscore_short_a")
            dataframe.loc[
                base_filter & spread_strong_overbought & rsi_ok_short,
                ["enter_short", "enter_tag"],
            ] = (1, "zscore_short_a_strong")

        elif is_group_b:
            # Short B: spread oversold + RSI not oversold
            dataframe.loc[
                base_filter & spread_oversold & rsi_ok_short,
                ["enter_short", "enter_tag"],
            ] = (1, "zscore_short_b")
            dataframe.loc[
                base_filter & spread_strong_oversold & rsi_ok_short,
                ["enter_short", "enter_tag"],
            ] = (1, "zscore_short_b_strong")

            # Long B: spread overbought + RSI not overbought
            dataframe.loc[
                base_filter & spread_overbought & rsi_ok_long,
                ["enter_long", "enter_tag"],
            ] = (1, "zscore_long_b")
            dataframe.loc[
                base_filter & spread_strong_overbought & rsi_ok_long,
                ["enter_long", "enter_tag"],
            ] = (1, "zscore_long_b_strong")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]

        neutral = (
            (dataframe["spread_zscore"] > -self.zscore_exit_threshold.value)
            & (dataframe["spread_zscore"] < self.zscore_exit_threshold.value)
        )

        if pair in self.group_a or pair in self.group_b:
            dataframe.loc[neutral, "exit_long"] = 1
            dataframe.loc[neutral, "exit_short"] = 1

        return dataframe

    # =========================================================================
    # LEVERAGE — dynamic based on signal strength
    # =========================================================================

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
        """Dynamic leverage based on signal strength tag.

        Strong signals (deep Z-score) -> 3x
        Normal signals -> 2x
        """
        if entry_tag and "strong" in entry_tag:
            lev = 3.0
        else:
            lev = 2.0

        return min(lev, max_leverage)

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
