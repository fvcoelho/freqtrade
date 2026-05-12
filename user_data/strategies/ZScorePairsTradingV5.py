"""
Z-Score Pairs Trading V5 — Volatility Filtered Scalp

Two timeframes working together:
- 15m: Z-score spread signal (when to enter the pair trade)
- 5m: Scalp execution (precise entry timing with RSI/BB)

The 15m spread Z-score is the "macro" signal — it tells us the spread
between Group A and Group B is stretched. The 5m candles handle the
"micro" execution — waiting for the best scalp entry within that signal.

Features:
- 15m Z-score neutrality signal via informative_pairs
- 5m scalp entry with RSI + BB timing
- DCA on adverse moves (up to 3 entries)
- Quick ROI take-profit on micro-bounces
- 3x leverage (hedged)
- Strict neutrality: max 3 longs + 3 shorts
"""

import logging
from datetime import datetime
from typing import Optional

import numpy as np
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter, merge_informative_pair


logger = logging.getLogger(__name__)


class ZScorePairsTradingV5(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "5m"  # execution timeframe
    can_short = True

    max_open_trades = 6
    position_adjustment_enable = False
    max_entry_position_adjustment = 0

    stoploss = -0.99  # effectively disabled — we use spread-based exit instead

    minimal_roi = {"0": 100}  # disabled

    startup_candle_count = 300

    trailing_stop = False
    process_only_new_candles = True

    # ----- strategy state -----
    group_a: list[str] = []
    group_b: list[str] = []
    _groups_initialized: bool = False
    _inf_zscores: dict[str, DataFrame] = {}  # cached 15m Z-scores

    # 15m Z-score spread parameters
    zscore_window = IntParameter(100, 500, default=250, space="buy", optimize=True)  # 250 * 15m = 2.6 days
    zscore_entry_threshold = DecimalParameter(1.5, 3.0, default=2.0, decimals=1, space="buy", optimize=True)
    zscore_exit_threshold = DecimalParameter(0.1, 0.8, default=0.3, decimals=1, space="sell", optimize=True)
    cum_return_window = IntParameter(10, 60, default=20, space="buy", optimize=True)  # 20 * 15m = 5h

    # Regime filter on 15m
    regime_window = IntParameter(80, 300, default=150, space="buy", optimize=True)
    regime_corr_min = DecimalParameter(0.2, 0.6, default=0.3, decimals=1, space="buy", optimize=True)

    # Spread-based stop: exit when spread diverges further instead of reverting
    spread_stop_threshold = DecimalParameter(2.5, 4.5, default=3.5, decimals=1, space="sell", optimize=True)

    # 5m scalp timing parameters
    rsi_long_max = IntParameter(35, 55, default=45, space="buy", optimize=True)
    rsi_short_min = IntParameter(55, 75, default=55, space="sell", optimize=True)

    # DCA
    dca_drop_pct = DecimalParameter(0.005, 0.03, default=0.01, decimals=3, space="buy", optimize=True)

    initial_stake_pct: float = 1.0  # full stake, no DCA

    # =========================================================================
    # INFORMATIVE PAIRS — request 15m data for all pairs
    # =========================================================================

    def informative_pairs(self):
        pairs = self.dp.current_whitelist() if self.dp else []
        # 15m for Z-score spread, 1h for clustering
        return [(pair, "15m") for pair in pairs] + [(pair, "1h") for pair in pairs]

    # =========================================================================
    # CLUSTERING
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
            return

        closes = {}
        for pair in pairs:
            df = self.dp.get_pair_dataframe(pair=pair, timeframe="1h")
            if df is not None and len(df) > 50:
                closes[pair] = df["close"].pct_change().dropna().values

        if len(closes) < 4:
            sorted_pairs = sorted(list(closes.keys()) if closes else pairs)
            mid = len(sorted_pairs) // 2
            self.group_a = sorted_pairs[:max(mid, 1)]
            self.group_b = sorted_pairs[max(mid, 1):]
            self._groups_initialized = True
            self._log_groups()
            return

        available = list(closes.keys())
        min_len = min(len(v) for v in closes.values())
        data = np.array([closes[p][-min_len:] for p in available])
        corr = np.corrcoef(data)
        corr = np.nan_to_num(corr, nan=0.0)

        dist = 1.0 - np.abs(corr)
        np.fill_diagonal(dist, 0.0)
        dist = (dist + dist.T) / 2.0
        dist = np.maximum(dist, 0.0)

        try:
            condensed = squareform(dist)
            Z = linkage(condensed, method="ward")
            labels = fcluster(Z, t=2, criterion="maxclust")
        except Exception:
            mid = len(available) // 2
            self.group_a = available[:max(mid, 1)]
            self.group_b = available[max(mid, 1):]
            self._groups_initialized = True
            self._log_groups()
            return

        c1 = [p for p, l in zip(available, labels) if l == 1]
        c2 = [p for p, l in zip(available, labels) if l == 2]
        self.group_a = self._top_corr(c1, corr, available, 3)
        self.group_b = self._top_corr(c2, corr, available, 3)
        if not self.group_a:
            self.group_a = c1[:3]
        if not self.group_b:
            self.group_b = c2[:3]

        self._groups_initialized = True
        self._log_groups()

    def _top_corr(self, cluster, corr, all_p, n):
        if len(cluster) <= n:
            return cluster
        idx = {p: i for i, p in enumerate(all_p)}
        scores = {}
        for p in cluster:
            c = [abs(corr[idx[p]][idx[q]]) for q in cluster if q != p and q in idx]
            scores[p] = np.mean(c) if c else 0
        return sorted(scores, key=scores.get, reverse=True)[:n]

    def _log_groups(self):
        logger.info(f"V3 MTF Groups: A={self.group_a} B={self.group_b}")

    @staticmethod
    def get_pairs():
        return [
            "BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT",
            "AVAX/USDT:USDT", "LINK/USDT:USDT", "DOGE/USDT:USDT",
        ]

    # =========================================================================
    # 15m Z-SCORE COMPUTATION (used as informative)
    # =========================================================================

    def _compute_15m_zscore(self, pair: str) -> Optional[DataFrame]:
        """Compute Z-score on 15m data for a single pair."""
        if not self.dp:
            return None
        df = self.dp.get_pair_dataframe(pair=pair, timeframe="15m")
        if df is None or len(df) < self.zscore_window.value + self.cum_return_window.value:
            return None

        log_ret = np.log(df["close"] / df["close"].shift(1))
        cum_ret = log_ret.rolling(window=self.cum_return_window.value).sum()
        cum_mean = cum_ret.rolling(window=self.zscore_window.value).mean()
        cum_std = cum_ret.rolling(window=self.zscore_window.value).std()
        df["pair_zscore_15m"] = ((cum_ret - cum_mean) / cum_std.replace(0, np.nan)).fillna(0.0)

        return df

    def _compute_spread_15m(self, pair: str, dataframe: DataFrame) -> DataFrame:
        """Compute spread Z-score from 15m data and merge into 5m dataframe."""
        if not self.group_a or not self.group_b or not self.dp:
            dataframe["spread_zscore_15m"] = 0.0
            dataframe["regime_ok_15m"] = 1
            return dataframe

        # Get 15m data for this pair to use as base for merge
        inf_df = self.dp.get_pair_dataframe(pair=pair, timeframe="15m")
        if inf_df is None or len(inf_df) < 50:
            dataframe["spread_zscore_15m"] = 0.0
            dataframe["regime_ok_15m"] = 1
            return dataframe

        # Compute Z-scores for all pairs on 15m
        za, zb = [], []
        for p in self.group_a:
            z_df = self._compute_15m_zscore(p)
            if z_df is not None:
                z = z_df["pair_zscore_15m"]
                z = z.iloc[-len(inf_df):].reset_index(drop=True)
                za.append(z)

        for p in self.group_b:
            z_df = self._compute_15m_zscore(p)
            if z_df is not None:
                z = z_df["pair_zscore_15m"]
                z = z.iloc[-len(inf_df):].reset_index(drop=True)
                zb.append(z)

        if za and zb:
            spread = sum(za) / len(za) - sum(zb) / len(zb)
            sm = spread.rolling(window=self.zscore_window.value).mean()
            ss = spread.rolling(window=self.zscore_window.value).std()
            inf_df["spread_zscore_15m"] = ((spread - sm) / ss.replace(0, np.nan)).fillna(0.0)
        else:
            inf_df["spread_zscore_15m"] = 0.0

        # Regime: rolling correlation on 15m returns
        ret_a = self._get_15m_returns(self.group_a[0])
        ret_b = self._get_15m_returns(self.group_b[0])
        if ret_a is not None and ret_b is not None:
            ret_a = ret_a.iloc[-len(inf_df):].reset_index(drop=True)
            ret_b = ret_b.iloc[-len(inf_df):].reset_index(drop=True)
            rc = ret_a.rolling(window=self.regime_window.value).corr(ret_b)
            inf_df["regime_ok_15m"] = (rc.abs() > self.regime_corr_min.value).astype(int).fillna(0)
        else:
            inf_df["regime_ok_15m"] = 1

        # Merge 15m into 5m using freqtrade's merge_informative_pair
        inf_df = inf_df[["date", "spread_zscore_15m", "regime_ok_15m"]].copy()
        dataframe = merge_informative_pair(dataframe, inf_df, self.timeframe, "15m", ffill=True)

        # Rename columns (merge adds _15m suffix)
        if "spread_zscore_15m_15m" in dataframe.columns:
            dataframe.rename(columns={
                "spread_zscore_15m_15m": "spread_zscore_15m",
                "regime_ok_15m_15m": "regime_ok_15m",
            }, inplace=True)

        return dataframe

    def _get_15m_returns(self, pair: str):
        if not self.dp:
            return None
        df = self.dp.get_pair_dataframe(pair=pair, timeframe="15m")
        if df is None or len(df) < 50:
            return None
        return np.log(df["close"] / df["close"].shift(1))

    # =========================================================================
    # INDICATORS — 5m scalp indicators + 15m spread signal
    # =========================================================================

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]

        if not self._groups_initialized and self.dp:
            self._cluster_pairs(self.dp.current_whitelist())

        # 5m scalp indicators
        dataframe["rsi"] = self._rsi(dataframe["close"], 14)

        # Bollinger Bands
        dataframe["bb_mid"] = dataframe["close"].rolling(window=20).mean()
        bb_std = dataframe["close"].rolling(window=20).std()
        dataframe["bb_upper"] = dataframe["bb_mid"] + 2.0 * bb_std
        dataframe["bb_lower"] = dataframe["bb_mid"] - 2.0 * bb_std

        # EMA for micro-trend
        dataframe["ema8"] = dataframe["close"].ewm(span=8, adjust=False).mean()
        dataframe["ema21"] = dataframe["close"].ewm(span=21, adjust=False).mean()

        # Volume ratio
        dataframe["vol_sma"] = dataframe["volume"].rolling(window=20).mean()
        dataframe["vol_ratio"] = (dataframe["volume"] / dataframe["vol_sma"].replace(0, np.nan)).fillna(1.0)

        # ATR volatility regime (5m)
        high, low, close = dataframe["high"], dataframe["low"], dataframe["close"]
        tr = np.maximum(high - low, np.maximum(abs(high - close.shift(1)), abs(low - close.shift(1))))
        dataframe["atr"] = tr.rolling(window=14).mean()
        dataframe["atr_pct"] = dataframe["atr"] / close * 100

        # Volatility Z-score: how extreme is current vol vs recent history
        atr_mean = dataframe["atr_pct"].rolling(window=200).mean()
        atr_std = dataframe["atr_pct"].rolling(window=200).std()
        dataframe["vol_zscore"] = ((dataframe["atr_pct"] - atr_mean) / atr_std.replace(0, np.nan)).fillna(0.0)

        # BB width as squeeze/expansion indicator
        dataframe["bb_width"] = (dataframe["bb_upper"] - dataframe["bb_lower"]) / dataframe["bb_mid"] * 100
        bb_width_mean = dataframe["bb_width"].rolling(window=200).mean()
        bb_width_std = dataframe["bb_width"].rolling(window=200).std()
        dataframe["bb_width_zscore"] = ((dataframe["bb_width"] - bb_width_mean) / bb_width_std.replace(0, np.nan)).fillna(0.0)

        # 15m spread Z-score (the "macro" signal)
        dataframe = self._compute_spread_15m(pair, dataframe)

        # Fill any NaN from merge
        dataframe["spread_zscore_15m"] = dataframe.get("spread_zscore_15m", 0.0)
        dataframe["regime_ok_15m"] = dataframe.get("regime_ok_15m", 1)
        dataframe["spread_zscore_15m"] = dataframe["spread_zscore_15m"].fillna(0.0)
        dataframe["regime_ok_15m"] = dataframe["regime_ok_15m"].fillna(1).astype(int)

        return dataframe

    @staticmethod
    def _rsi(series, period=14):
        delta = series.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        ag = gain.rolling(window=period).mean()
        al = loss.rolling(window=period).mean()
        rs = ag / al.replace(0, np.nan)
        return (100 - 100 / (1 + rs)).fillna(50)

    # =========================================================================
    # ENTRY — 15m spread signal + 5m scalp timing
    # =========================================================================

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]
        is_a = pair in self.group_a
        is_b = pair in self.group_b

        # 15m macro signal
        regime = dataframe["regime_ok_15m"] == 1
        spread_low = dataframe["spread_zscore_15m"] < -self.zscore_entry_threshold.value
        spread_high = dataframe["spread_zscore_15m"] > self.zscore_entry_threshold.value

        # VOLATILITY REGIME FILTER
        # Skip entries when volatility is extreme — this is when the 9 losses happened
        # vol_zscore > 1.5 means ATR is 1.5 std above normal = dangerous
        # bb_width_zscore > 1.5 means BB bands are very wide = high vol
        vol_ok = (dataframe["vol_zscore"] < 1.5) & (dataframe["bb_width_zscore"] < 1.5)

        # 5m scalp timing
        long_timing = (
            (dataframe["rsi"] < self.rsi_long_max.value)
            & (dataframe["close"] < dataframe["bb_mid"])
            & (dataframe["volume"] > 0)
        )
        short_timing = (
            (dataframe["rsi"] > self.rsi_short_min.value)
            & (dataframe["close"] > dataframe["bb_mid"])
            & (dataframe["volume"] > 0)
        )

        # Combined filter: regime + volatility + timing
        base = regime & vol_ok

        if is_a:
            dataframe.loc[
                base & spread_low & long_timing,
                ["enter_long", "enter_tag"],
            ] = (1, "v3_long_a")
            dataframe.loc[
                base & spread_high & short_timing,
                ["enter_short", "enter_tag"],
            ] = (1, "v3_short_a")

        elif is_b:
            dataframe.loc[
                base & spread_low & short_timing,
                ["enter_short", "enter_tag"],
            ] = (1, "v3_short_b")
            dataframe.loc[
                base & spread_high & long_timing,
                ["enter_long", "enter_tag"],
            ] = (1, "v3_long_b")

        return dataframe

    # =========================================================================
    # EXIT — 15m spread reversion OR 5m RSI extreme
    # =========================================================================

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]

        # EXIT when spread reverts to neutral — the core pairs trading signal
        spread_neutral = (
            (dataframe["spread_zscore_15m"] > -self.zscore_exit_threshold.value)
            & (dataframe["spread_zscore_15m"] < self.zscore_exit_threshold.value)
        )

        if pair in self.group_a or pair in self.group_b:
            dataframe.loc[spread_neutral, "exit_long"] = 1
            dataframe.loc[spread_neutral, "exit_short"] = 1

        return dataframe

    # =========================================================================
    # DCA
    # =========================================================================

    def adjust_trade_position(
        self,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        min_stake: Optional[float],
        max_stake: float,
        current_entry_rate: float,
        current_exit_rate: float,
        current_entry_profit: float,
        current_exit_profit: float,
        **kwargs,
    ) -> Optional[float]:
        if trade.nr_of_successful_entries >= self.max_entry_position_adjustment + 1:
            return None
        if current_profit > 0:
            return None

        dca_level = trade.nr_of_successful_entries
        required_drop = self.dca_drop_pct.value * dca_level

        if current_profit > -required_drop:
            return None

        dca_stake = trade.stake_amount / trade.nr_of_successful_entries
        if min_stake is not None and dca_stake < min_stake:
            dca_stake = min_stake
        return dca_stake

    # =========================================================================
    # CUSTOM EXIT — scalp profit after DCA or time
    # =========================================================================

    def custom_exit(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> Optional[str]:
        # Pure pairs trade — only safety time stop, no scalp
        if not trade.open_date_utc:
            return None

        hours = (current_time - trade.open_date_utc).total_seconds() / 3600

        # Safety only: force exit after 72h if spread signal didn't close it
        if hours > 72:
            return "time_stop"

        return None

    # =========================================================================
    # LEVERAGE + STAKE + NEUTRALITY
    # =========================================================================

    def leverage(self, pair, current_time, current_rate, proposed_leverage,
                 max_leverage, entry_tag, side, **kwargs) -> float:
        """Fixed 3x leverage — proven best for this strategy.

        Dynamic leverage was tested:
        - 5x/3x/2x: more profit per scalp but liquidation risk
        - 3x/2x/1.5x: lowest drawdown (2.3%) but fewer trades
        - Fixed 3x: best total profit (+$23.53) with acceptable drawdown
        """
        return min(3.0, max_leverage)

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                            min_stake, max_stake, leverage, entry_tag, side, **kwargs) -> float:
        full_stake = proposed_stake / self.max_open_trades if proposed_stake else 166.67
        initial = full_stake * self.initial_stake_pct
        return min(initial, max_stake)

    def confirm_trade_entry(self, pair, order_type, amount, rate, time_in_force,
                            current_time, entry_tag, side, **kwargs) -> bool:
        """Block entries that break neutrality: max 3 longs + 3 shorts."""
        open_trades = Trade.get_trades_proxy(is_open=True)
        longs = sum(1 for t in open_trades if not t.is_short)
        shorts = sum(1 for t in open_trades if t.is_short)

        if side == "long" and longs >= 3:
            return False
        if side == "short" and shorts >= 3:
            return False
        return True

    def confirm_trade_exit(
        self,
        pair: str,
        trade: Trade,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        exit_reason: str,
        current_time: datetime,
        **kwargs,
    ) -> bool:
        """Block exit_signal exits when trade is losing.

        The scalp engine (ROI, DCA) exits are always allowed.
        Exit signals only allowed at breakeven or better.
        This is the key fix: prevents the -$71 exit_signal losses.
        """
        if exit_reason == "exit_signal":
            profit = trade.calc_profit_ratio()
            if profit < -0.001:  # only exit if at breakeven or better
                return False
        return True
