"""
Z-Score Pairs Trading V18 — V16 + Optimized ROI
All V16 features (scoring, adaptive leverage, graduated time stop, DCA)
with higher ROI targets to let winners run longer.

From V16: scoring engine, adaptive leverage, graduated time stop, DCA
Changed: ROI targets raised — 1.2% immediate, scaling to 0.3% at 3h.
Lets mean-reversion play out more fully before taking profit.
"""

import logging
from datetime import datetime
from typing import Optional

import numpy as np
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import DecimalParameter, IntParameter
from ZScorePairsTradingBase import ZScorePairsTradingBase


logger = logging.getLogger(__name__)


class ZScorePairsTradingV18(ZScorePairsTradingBase):

    timeframe = "15m"
    startup_candle_count = 300

    stoploss = -0.10
    minimal_roi = {
        "0": 0.012,
        "30": 0.008,
        "90": 0.005,
        "180": 0.003,
    }
    trailing_stop = False

    # DCA config
    position_adjustment_enable = True
    max_entry_position_adjustment = 1  # 1 DCA add per trade

    # DCA params
    dca_trigger_minutes = 60      # DCA after 1h
    dca_loss_threshold = -0.015   # DCA when down > 1.5%

    # Graduated time stop: (minutes, max_loss)
    # Exit if trade exceeds age AND is losing more than threshold
    graduated_stops = [
        (120, -0.025),   # after 2h: exit only if down > 2.5% (near-wreck)
        (180, -0.012),   # after 3h: exit if still down > 1.2%
        (300, 0.0),      # after 5h: exit anything not profitable
    ]

    # Z-score params
    zscore_window = IntParameter(48, 192, default=96, space="buy", optimize=True)
    cum_return_window = IntParameter(4, 24, default=8, space="buy", optimize=True)
    zscore_entry = DecimalParameter(1.5, 3.0, default=2.5, decimals=1, space="buy", optimize=True)

    # Regime filter params
    regime_window = IntParameter(48, 192, default=96, space="buy", optimize=True)
    regime_corr_min = DecimalParameter(0.2, 0.7, default=0.4, decimals=1, space="buy", optimize=True)

    _min_history_for_scoring = 20

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Per-instance mutable state (avoid class-level sharing)
        self._pair_zscores: dict[str, DataFrame] = {}
        self._btc_trend: dict = {}
        self._trade_history: list[dict] = []
        self._pending_features: dict[str, list] = {}

    def informative_pairs(self):
        pairs = self.dp.current_whitelist() if self.dp else []
        return [(pair, "1d") for pair in pairs] + [("BTC/USDT:USDT", "1h")]

    # =========================================================================
    # BTC TREND — from V9
    # =========================================================================

    def _compute_btc_trend(self) -> None:
        if self._btc_trend or not self.dp:
            return

        btc_1h = self.dp.get_pair_dataframe(pair="BTC/USDT:USDT", timeframe="1h")
        if btc_1h is None or len(btc_1h) < 50:
            return

        ema_fast = btc_1h["close"].ewm(span=8).mean()
        ema_slow = btc_1h["close"].ewm(span=21).mean()
        mom_4h = btc_1h["close"].pct_change(4) * 100

        tr = np.maximum(
            btc_1h["high"] - btc_1h["low"],
            np.maximum(
                abs(btc_1h["high"] - btc_1h["close"].shift(1)),
                abs(btc_1h["low"] - btc_1h["close"].shift(1)),
            ),
        )
        atr = tr.rolling(14).mean()
        atr_pct = atr / btc_1h["close"] * 100
        atr_z = ((atr_pct - atr_pct.rolling(48).mean()) / atr_pct.rolling(48).std().replace(0, np.nan)).fillna(0)

        self._btc_trend = {
            "dates": btc_1h["date"].values,
            "pump": (mom_4h > 1.5).values,
            "dump": (mom_4h < -1.5).values,
            "high_vol": (atr_z > 2.0).values,
            "vol_just_ended": ((atr_z.shift(1) > 1.5) & (atr_z <= 1.5)).values,
            "btc_mom": mom_4h.fillna(0.0).values,
            "btc_atr_z": atr_z.fillna(0.0).values,
        }

    def _get_btc_signal(self, dataframe: DataFrame, signal: str, numeric: bool = False):
        import pandas as pd
        if not self._btc_trend:
            return pd.Series(0.0 if numeric else False, index=dataframe.index)

        btc_df = pd.DataFrame({
            "date": pd.to_datetime(self._btc_trend["dates"], utc=True),
            signal: self._btc_trend[signal],
        }).set_index("date")

        pair_dates = pd.to_datetime(dataframe["date"], utc=True)
        merged = btc_df.reindex(pair_dates, method="ffill")
        return merged[signal].fillna(0.0 if numeric else False).values

    # =========================================================================
    # REGIME FILTER — from V2 (adapted for 15m)
    # =========================================================================

    def _compute_regime(self, pair: str, dataframe: DataFrame) -> DataFrame:
        if not self.group_a or not self.group_b or not self.dp:
            dataframe["regime_ok"] = 1
            return dataframe

        pair_a = self.group_a[0]
        pair_b = self.group_b[0]

        ret_a = self._get_returns(pair_a, pair, dataframe)
        ret_b = self._get_returns(pair_b, pair, dataframe)

        if ret_a is not None and ret_b is not None:
            rolling_corr = ret_a.rolling(window=self.regime_window.value).corr(ret_b)
            dataframe["rolling_corr"] = rolling_corr.fillna(0.0)
            dataframe["regime_ok"] = (rolling_corr.abs() > self.regime_corr_min.value).astype(int).fillna(0)
        else:
            dataframe["rolling_corr"] = 0.0
            dataframe["regime_ok"] = 1

        return dataframe

    def _get_returns(self, target_pair: str, current_pair: str, dataframe: DataFrame):
        if target_pair == current_pair:
            return dataframe["log_return"]
        if not self.dp:
            return None
        other_df = self.dp.get_pair_dataframe(pair=target_pair, timeframe=self.timeframe)
        if other_df is None or len(other_df) < 50:
            return None
        ret = np.log(other_df["close"] / other_df["close"].shift(1))
        return ret.iloc[-len(dataframe):].reset_index(drop=True)

    # =========================================================================
    # INDICATORS
    # =========================================================================

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_indicators(dataframe, metadata)
        pair = metadata["pair"]

        # BTC trend
        self._compute_btc_trend()
        dataframe["btc_pump"] = self._get_btc_signal(dataframe, "pump")
        dataframe["btc_dump"] = self._get_btc_signal(dataframe, "dump")
        dataframe["btc_high_vol"] = self._get_btc_signal(dataframe, "high_vol")
        dataframe["btc_vol_ended"] = self._get_btc_signal(dataframe, "vol_just_ended")
        dataframe["btc_mom"] = self._get_btc_signal(dataframe, "btc_mom", numeric=True)
        dataframe["btc_atr_z"] = self._get_btc_signal(dataframe, "btc_atr_z", numeric=True)

        # Per-pair Z-score
        dataframe["log_return"] = np.log(dataframe["close"] / dataframe["close"].shift(1))
        cum_ret = dataframe["log_return"].rolling(window=self.cum_return_window.value).sum()
        cum_mean = cum_ret.rolling(window=self.zscore_window.value).mean()
        cum_std = cum_ret.rolling(window=self.zscore_window.value).std()
        dataframe["pair_zscore"] = ((cum_ret - cum_mean) / cum_std.replace(0, np.nan)).fillna(0.0)

        self._pair_zscores[pair] = dataframe[["pair_zscore"]].copy()

        # Spread Z-score
        dataframe["spread_zscore"] = self._compute_spread(pair, dataframe)

        # Regime filter
        dataframe = self._compute_regime(pair, dataframe)

        # Volume filter
        vol_ma = dataframe["volume"].rolling(48).mean()
        dataframe["vol_ratio"] = (dataframe["volume"] / vol_ma.replace(0, np.nan)).fillna(1.0)
        dataframe["vol_ok"] = (dataframe["vol_ratio"] > 1.0).astype(int)

        return dataframe

    def _compute_spread(self, pair: str, dataframe: DataFrame):
        if not self.group_a or not self.group_b or not self.dp:
            return 0.0

        group_a_z, group_b_z = [], []
        for p in self.group_a:
            z = self._get_zscore(p, pair, dataframe)
            if z is not None:
                group_a_z.append(z)
        for p in self.group_b:
            z = self._get_zscore(p, pair, dataframe)
            if z is not None:
                group_b_z.append(z)

        if not group_a_z or not group_b_z:
            return 0.0

        spread = sum(group_a_z) / len(group_a_z) - sum(group_b_z) / len(group_b_z)
        spread_mean = spread.rolling(window=self.zscore_window.value).mean()
        spread_std = spread.rolling(window=self.zscore_window.value).std()
        return ((spread - spread_mean) / spread_std.replace(0, np.nan)).fillna(0.0)

    def _get_zscore(self, target_pair: str, current_pair: str, dataframe: DataFrame):
        if target_pair == current_pair:
            return dataframe["pair_zscore"]
        if target_pair in self._pair_zscores:
            cached = self._pair_zscores[target_pair]["pair_zscore"]
            return cached.iloc[-len(dataframe):].reset_index(drop=True)
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

    # =========================================================================
    # ENTRY — spread Z-score + regime filter + BTC trend filter
    # =========================================================================

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]
        is_a = pair in self.group_a
        is_b = pair in self.group_b

        # Base filters
        vol = dataframe["vol_ok"] == 1
        regime = dataframe["regime_ok"] == 1

        # BTC trend filter
        no_chaos = ~dataframe["btc_high_vol"]
        safe_long = ~dataframe["btc_dump"] & no_chaos
        safe_short = ~dataframe["btc_pump"] & no_chaos

        # Spread signals
        spread_low = dataframe["spread_zscore"] < -self.zscore_entry.value
        spread_high = dataframe["spread_zscore"] > self.zscore_entry.value

        # Post-volatility re-entry: lower threshold when vol just ended
        vol_bounce_low = dataframe["btc_vol_ended"] & (dataframe["spread_zscore"] < -1.5)
        vol_bounce_high = dataframe["btc_vol_ended"] & (dataframe["spread_zscore"] > 1.5)
        spread_low = spread_low | vol_bounce_low
        spread_high = spread_high | vol_bounce_high

        if is_a:
            dataframe.loc[vol & regime & spread_low & safe_long, ["enter_long", "enter_tag"]] = (1, "v18_long_a")
            dataframe.loc[vol & regime & spread_high & safe_short, ["enter_short", "enter_tag"]] = (1, "v18_short_a")
        elif is_b:
            dataframe.loc[vol & regime & spread_low & safe_short, ["enter_short", "enter_tag"]] = (1, "v18_short_b")
            dataframe.loc[vol & regime & spread_high & safe_long, ["enter_long", "enter_tag"]] = (1, "v18_long_b")

        return dataframe

    # =========================================================================
    # DCA — average down on losing trades (from V13)
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
        """
        DCA: if trade is losing > dca_loss_threshold after dca_trigger_minutes,
        add equal stake to average down. Skip if BTC is in chaos.
        """
        if trade.nr_of_successful_entries >= 2:
            return None  # already DCA'd once

        trade_minutes = (current_time - trade.open_date_utc).total_seconds() / 60
        if trade_minutes < self.dca_trigger_minutes:
            return None

        if current_profit > self.dca_loss_threshold:
            return None  # not losing enough

        # BTC chaos guard: don't DCA during pumps/dumps/high vol
        dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
        if dataframe is not None and not dataframe.empty:
            last = dataframe.iloc[-1]
            if last.get("btc_pump", False) or last.get("btc_dump", False) or last.get("btc_high_vol", False):
                return None  # skip DCA during BTC chaos

        # Add equal stake
        dca_stake = self.stake_per_position
        if min_stake and dca_stake < min_stake:
            dca_stake = min_stake

        return min(dca_stake, max_stake)

    # =========================================================================
    # BALANCE CHECK — from V10
    # =========================================================================

    def confirm_trade_entry(
        self,
        pair: str,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        current_time: datetime,
        entry_tag: Optional[str],
        side: str,
        **kwargs,
    ) -> bool:
        open_trades = Trade.get_trades_proxy(is_open=True)
        count_a = sum(1 for t in open_trades if t.pair in self.group_a)
        count_b = sum(1 for t in open_trades if t.pair in self.group_b)

        if pair in self.group_a and count_a + 1 - count_b > 1:
            return False
        if pair in self.group_b and count_b + 1 - count_a > 1:
            return False

        return True

    # =========================================================================
    # TRADE SIMILARITY SCORING (NEW in V16)
    # =========================================================================

    def _snapshot_features(self, last) -> list[float]:
        """Extract 5-element feature vector from a dataframe row."""
        return [
            abs(float(last.get("spread_zscore", 0.0))),
            float(last.get("rolling_corr", 0.0)),
            float(last.get("vol_ratio", 1.0)),
            float(last.get("btc_mom", 0.0)),
            float(last.get("btc_atr_z", 0.0)),
        ]

    def _compute_trade_score(self, vector: list[float]) -> float:
        """
        Compute confidence score for a new trade by cosine similarity
        to historical trades. Returns -1.0 to +1.0.
        """
        if len(self._trade_history) < self._min_history_for_scoring:
            return 0.0

        # Compute running feature stds for normalization
        all_vectors = np.array([t["vector"] for t in self._trade_history])
        stds = all_vectors.std(axis=0)
        stds[stds == 0] = 1.0

        # Normalize current vector
        c = np.array(vector) / stds
        c_norm = np.linalg.norm(c)
        if c_norm == 0:
            return 0.0

        total_score = 0.0
        for trade in self._trade_history:
            h = np.array(trade["vector"]) / stds
            h_norm = np.linalg.norm(h)
            if h_norm == 0:
                continue
            similarity = np.dot(c, h) / (c_norm * h_norm)
            total_score += similarity * trade["outcome"]

        return total_score / len(self._trade_history)

    def _record_trade_outcome(self, trade: Trade, features: list[float], profit: float) -> None:
        """Store a closed trade's features and outcome in history."""
        self._trade_history.append({
            "vector": features,
            "outcome": 1 if profit > 0 else -1,
            "profit_pct": profit,
            "pair": trade.pair,
            "side": "long" if trade.is_short is False else "short",
        })

    # =========================================================================
    # EXIT — graduated time stop + feature persistence (V16)
    # =========================================================================

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def custom_exit(
        self,
        pair: str,
        trade: 'Trade',
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> Optional[str]:
        # Persist pending features to trade on first call
        if trade.get_custom_data("v18_features") is None and pair in self._pending_features:
            trade.set_custom_data("v18_features", self._pending_features.pop(pair))

        trade_minutes = (current_time - trade.open_date_utc).total_seconds() / 60

        for stop_minutes, max_loss in self.graduated_stops:
            if trade_minutes > stop_minutes and current_profit < max_loss:
                return f"grad_stop_{stop_minutes // 60}h"

        return None

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
        """Record trade outcome for scoring on every exit."""
        features = trade.get_custom_data("v18_features")
        if features is None:
            features = self._pending_features.pop(pair, None)
        if features is not None:
            self._record_trade_outcome(trade, features, trade.calc_profit_ratio(rate))
        return True

    # =========================================================================
    # SCORE-BASED ADAPTIVE LEVERAGE (NEW in V16)
    # =========================================================================

    # Score → leverage mapping (3x is the optimal ceiling — tested 4x and 6x,
    # both degrade due to amplified loser impact)
    score_leverage_tiers = [
        (0.4, 3.0),   # score >= 0.4 → 3x (strong match with winners)
        (0.0, 2.0),   # score >= 0   → 2x (neutral)
        (-999, 2.0),  # score < 0    → 2x (resembles losers, stay safe)
    ]

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
        # Get latest indicators
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or dataframe.empty:
            return min(2.0, max_leverage)

        last = dataframe.iloc[-1]

        # Step 1: snapshot features and store for this trade
        features = self._snapshot_features(last)
        self._pending_features[pair] = features

        # Step 2: compute trade score from history
        score = self._compute_trade_score(features)

        # Step 3: map score to leverage
        lev = 2.0
        for score_threshold, tier_lev in self.score_leverage_tiers:
            if score >= score_threshold:
                lev = tier_lev
                break

        reason = f"score={score:.2f} → base {lev:.0f}x (history={len(self._trade_history)})"

        # Step 4: V15 safety guards still apply
        if last.get("btc_high_vol", False):
            lev = min(lev, 2.0)
            reason += " | capped@2x:high_vol"
        elif last.get("btc_pump", False) or last.get("btc_dump", False):
            lev = round(lev * 0.6, 1)
            reason += " | *0.6:pump_dump"

        if last.get("regime_ok", 1) == 0:
            lev = min(lev, 2.0)
            reason += " | capped@2x:regime"

        if last.get("btc_vol_ended", False):
            lev = min(lev, 2.0)
            reason += " | capped@2x:vol_ended"

        # Floor at 2x, cap at max_leverage
        lev = max(2.0, min(lev, max_leverage))

        logger.debug(f"V18 leverage {pair}: {reason} → final {lev:.1f}x")

        return lev
