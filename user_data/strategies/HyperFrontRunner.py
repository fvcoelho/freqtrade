"""
HyperFrontRunner (HFR) v1 — Directional momentum / whale front-running strategy.

Detects whale momentum via volume surges, price breakouts, funding rate spikes,
and BTC alignment. Front-runs the momentum cascade on Hyperliquid.
"""

import json
import logging
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "configs" / "hfr_config.json"


def _load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)


class HyperFrontRunner(IStrategy):
    INTERFACE_VERSION = 3
    can_short = True
    process_only_new_candles = True

    # Defaults overridden by config in __init__
    timeframe = "5m"
    startup_candle_count = 200
    stoploss = -0.06
    minimal_roi = {"0": 100}  # Disabled — exits handled in custom_exit
    trailing_stop = False
    use_custom_stoploss = True

    def __init__(self, config: dict, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        c = _load_config()
        self._cfg = c

        # Pairs
        self.BTC_REF: str = c["pairs"]["btc_ref"]

        # Timeframe
        self.timeframe = c.get("timeframe", "5m")
        self.startup_candle_count = c.get("startup_candle_count", 200)
        self.stake_per_position: float = c.get("stake_per_position", 400.0)
        self.max_open_trades_cfg: int = c.get("max_open_trades", 4)

        # Signal params
        sv = c["signals"]["volume"]
        self._vol_weight: float = sv["weight"]
        self._vol_sma: int = sv["sma_period"]
        self._vol_min_ratio: float = sv["min_ratio"]
        self._vol_max_ratio: float = sv["max_ratio"]
        self._vol_hard_gate: float = sv["hard_gate"]
        self._vol_15m_ratio: float = sv["confirm_15m_ratio"]

        sm = c["signals"]["momentum"]
        self._mom_weight: float = sm["weight"]
        self._mom_breakout: int = sm["breakout_period"]
        self._mom_ema: int = sm["ema_period"]
        self._mom_atr: int = sm["atr_period"]
        self._mom_atr_sma: int = sm["atr_sma_period"]
        self._mom_atr_exp: float = sm["atr_expansion"]
        self._mom_hard_gate: float = sm["hard_gate"]

        sf = c["signals"]["funding"]
        self._fund_weight: float = sf["weight"]
        self._fund_threshold: float = sf["threshold"]
        self._fund_max_scale: float = sf["max_scale"]
        self._fund_data_dir: str = sf["data_dir"]

        sb = c["signals"]["btc"]
        self._btc_weight: float = sb["weight"]
        self._btc_chaos_max: float = sb["chaos_atr_z_max"]
        self._btc_block_atr_z: float = sb["entry_block_atr_z"]
        self._btc_reversal: float = sb["reversal_threshold"]
        self._btc_mom_period: int = sb["mom_period"]
        self._btc_atr_period: int = sb["atr_period"]
        self._btc_atr_z_window: int = sb["atr_z_window"]

        self._entry_threshold: float = c["signals"]["entry_threshold"]

        # Risk params
        r = c["risk"]
        self._sl_atr_mult: float = r["stoploss_atr_mult"]
        self._sl_cap: float = r["stoploss_cap"]
        self._trail_trigger: float = r["trailing_stop_trigger"]
        self._trail_distance: float = r["trailing_stop_distance"]
        self._time_exit_hours: int = r["time_exit_hours"]
        self._decay_threshold: float = r["signal_decay_threshold"]
        self._decay_hours: int = r["signal_decay_hours"]
        self._decay_profit_band: float = r["signal_decay_profit_band"]

        # Take profit params
        tp = c["take_profit"]
        self._tp1_pct: float = tp["tp1_pct"]
        self._tp1_ratio: float = tp["tp1_ratio"]
        self._tp2_pct: float = tp["tp2_pct"]
        self._tp2_ratio: float = tp["tp2_ratio"]

        # Leverage params
        lv = c["leverage"]
        self._lev_min: float = lv["min"]
        self._lev_max: float = lv["max"]

        # Internal state
        self._btc_trend: dict = {}
        self._funding_cache: dict[str, pd.DataFrame] = {}

    def _compute_volume_score(self, dataframe: DataFrame) -> pd.Series:
        """Volume surge score: 0-1 based on current volume vs SMA(volume).

        Uses a 1-bar shifted SMA so the current candle's volume does not
        contaminate its own baseline, giving a clean surge ratio.
        """
        vol_sma = (
            dataframe["volume"]
            .rolling(window=self._vol_sma, min_periods=1)
            .mean()
            .shift(1)
        )
        ratio = dataframe["volume"] / vol_sma.replace(0, np.nan)
        ratio = ratio.fillna(0.0)
        score = (ratio - self._vol_min_ratio) / (self._vol_max_ratio - self._vol_min_ratio)
        return score.clip(0.0, 1.0)

    def _compute_momentum_score(self, dataframe: DataFrame) -> pd.Series:
        """Price momentum score: 0-1 based on breakout + EMA + ATR expansion."""
        close = dataframe["close"]
        high = dataframe["high"]
        low = dataframe["low"]

        # Breakout detection (compare close vs rolling close extremes to catch
        # the moment price breaks above/below the prior window's close range)
        highest = close.rolling(window=self._mom_breakout, min_periods=1).max().shift(1)
        lowest = close.rolling(window=self._mom_breakout, min_periods=1).min().shift(1)
        breakout_up = (close > highest).astype(float)
        breakout_down = (close < lowest).astype(float)

        # EMA alignment
        ema = ta.EMA(dataframe, timeperiod=self._mom_ema)
        ema_long = (close > ema).astype(float)
        ema_short = (close < ema).astype(float)

        # ATR expansion
        atr = ta.ATR(dataframe, timeperiod=self._mom_atr)
        atr_sma = atr.rolling(window=self._mom_atr_sma, min_periods=1).mean()
        atr_expanding = (atr > atr_sma * self._mom_atr_exp).astype(float)

        # Direction: +1 for long, -1 for short, 0 for none
        direction = pd.Series(0, index=dataframe.index, dtype=int)
        direction = direction.where(~((breakout_up == 1) & (ema_long == 1)), 1)
        direction = direction.where(~((breakout_down == 1) & (ema_short == 1)), -1)
        dataframe["momentum_direction"] = direction

        # Score: 0.33 per condition (use direction-aligned conditions)
        score_long = (breakout_up + ema_long + atr_expanding) / 3.0
        score_short = (breakout_down + ema_short + atr_expanding) / 3.0
        score = pd.Series(0.0, index=dataframe.index)
        score = score.where(direction != 1, score_long)
        score = score.where(direction != -1, score_short)

        return score.clip(0.0, 1.0)

    def _compute_funding_score(self, dataframe: DataFrame) -> tuple[pd.Series, pd.Series]:
        """Funding rate score: separate scores for long and short directions.

        Returns (long_score, short_score) each 0-1.
        """
        if "funding_rate" not in dataframe.columns:
            zeros = pd.Series(0.0, index=dataframe.index)
            return zeros, zeros.copy()

        fr = dataframe["funding_rate"].fillna(0.0)
        thr = self._fund_threshold
        max_s = self._fund_max_scale

        # Long score: positive funding above threshold
        long_raw = (fr - thr) / (max_s - thr)
        long_score = long_raw.where(fr > thr, 0.0).clip(0.0, 1.0)

        # Short score: negative funding below -threshold
        short_raw = (-fr - thr) / (max_s - thr)
        short_score = short_raw.where(fr < -thr, 0.0).clip(0.0, 1.0)

        return long_score, short_score

    def _compute_btc_trend(self):
        """Compute BTC momentum and ATR z-score from 1h data. Stores in self._btc_trend."""
        if not self.dp:
            return
        btc_df = self.dp.get_pair_dataframe(self.BTC_REF, "1h")
        if btc_df is None or len(btc_df) < self._btc_atr_z_window:
            return

        close = btc_df["close"]
        mom = close.pct_change(self._btc_mom_period).iloc[-1]
        atr = ta.ATR(btc_df, timeperiod=self._btc_atr_period)
        atr_mean = atr.rolling(window=self._btc_atr_z_window, min_periods=1).mean()
        atr_std = atr.rolling(window=self._btc_atr_z_window, min_periods=1).std()
        atr_z = ((atr - atr_mean) / atr_std.replace(0, np.nan)).fillna(0.0)

        self._btc_trend = {
            "btc_mom": float(mom) if not np.isnan(mom) else 0.0,
            "btc_atr_z": float(atr_z.iloc[-1]),
        }

    def _compute_btc_score(self, direction: int) -> float:
        """BTC alignment score for a given trade direction.

        Args:
            direction: +1 for long, -1 for short

        Returns:
            0.0 (opposed/chaotic), 0.5 (neutral), 1.0 (aligned)
        """
        if not self._btc_trend:
            return 0.0

        mom = self._btc_trend.get("btc_mom", 0.0)
        atr_z = self._btc_trend.get("btc_atr_z", 0.0)

        # Chaotic market
        if atr_z > self._btc_chaos_max:
            return 0.0

        # Check alignment
        mom_direction = 1 if mom > 0.005 else (-1 if mom < -0.005 else 0)

        if mom_direction == direction:
            return 1.0
        elif mom_direction == 0:
            return 0.5
        else:
            return 0.0

    def _load_funding_data(self, pair: str, dataframe: DataFrame) -> DataFrame:
        """Load and merge funding rate CSV data into the dataframe."""
        if pair in self._funding_cache:
            fund_df = self._funding_cache[pair]
        else:
            coin = pair.split("/")[0]
            fund_path = Path(self._fund_data_dir) / f"{coin}_funding.csv"
            if not fund_path.exists():
                dataframe["funding_rate"] = 0.0
                return dataframe
            fund_df = pd.read_csv(fund_path)
            fund_df["timestamp"] = pd.to_datetime(fund_df["timestamp"], format="ISO8601", utc=True)
            fund_df = fund_df.set_index("timestamp").sort_index()
            self._funding_cache[pair] = fund_df

        dates = pd.to_datetime(dataframe["date"], utc=True)
        fund_reindexed = fund_df["funding_rate"].reindex(dates, method="ffill")
        dataframe["funding_rate"] = fund_reindexed.fillna(0.0).values
        return dataframe

    def _get_15m_volume_confirmed(self, pair: str, dataframe: DataFrame) -> pd.Series:
        """Check if 15m volume also shows a surge (confirmation)."""
        if not self.dp:
            return pd.Series(True, index=dataframe.index)
        df_15m = self.dp.get_pair_dataframe(pair, "15m")
        if df_15m is None or df_15m.empty:
            return pd.Series(True, index=dataframe.index)

        vol_sma = df_15m["volume"].rolling(window=self._vol_sma, min_periods=1).mean()
        ratio_15m = df_15m["volume"] / vol_sma.replace(0, np.nan)
        ratio_15m = ratio_15m.fillna(0.0)
        confirmed = (ratio_15m > self._vol_15m_ratio)

        map_df = pd.DataFrame({"date": df_15m["date"], "vol_15m_ok": confirmed}).set_index("date")
        dates_5m = pd.to_datetime(dataframe["date"], utc=True)
        merged = map_df.reindex(dates_5m, method="ffill")
        return merged["vol_15m_ok"].fillna(True).values

    def informative_pairs(self):
        pairs = self.dp.current_whitelist() if self.dp else []
        return (
            [(pair, "15m") for pair in pairs]
            + [(self.BTC_REF, "1h")]
        )

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]

        # BTC trend (computed once, shared across pairs)
        self._compute_btc_trend()

        # Merge funding rate data
        dataframe = self._load_funding_data(pair, dataframe)

        # Signal 1: Volume surge
        dataframe["volume_score"] = self._compute_volume_score(dataframe)
        dataframe["vol_15m_confirmed"] = self._get_15m_volume_confirmed(pair, dataframe)

        # Signal 2: Price momentum (also sets momentum_direction)
        dataframe["momentum_score"] = self._compute_momentum_score(dataframe)

        # Signal 3: Funding rate (directional)
        long_fund, short_fund = self._compute_funding_score(dataframe)
        dataframe["funding_score_long"] = long_fund
        dataframe["funding_score_short"] = short_fund

        # Signal 4: BTC alignment (scalar per candle, applied per direction)
        btc_long = self._compute_btc_score(direction=1)
        btc_short = self._compute_btc_score(direction=-1)

        # Composite signals (separate for long and short)
        dataframe["hfr_signal_long"] = (
            dataframe["volume_score"] * self._vol_weight
            + dataframe["momentum_score"] * self._mom_weight
            + dataframe["funding_score_long"] * self._fund_weight
            + btc_long * self._btc_weight
        )
        dataframe["hfr_signal_short"] = (
            dataframe["volume_score"] * self._vol_weight
            + dataframe["momentum_score"] * self._mom_weight
            + dataframe["funding_score_short"] * self._fund_weight
            + btc_short * self._btc_weight
        )

        # Store ATR for exit logic
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self._mom_atr)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe["enter_tag"] = ""

        btc_atr_z = self._btc_trend.get("btc_atr_z", 0.0) if self._btc_trend else 0.0
        btc_blocked = btc_atr_z > self._btc_block_atr_z

        # Long entries
        long_cond = (
            (dataframe["hfr_signal_long"] >= self._entry_threshold)
            & (dataframe["volume_score"] >= self._vol_hard_gate)
            & (dataframe["momentum_score"] >= self._mom_hard_gate)
            & (dataframe["momentum_direction"] == 1)
            & (dataframe["vol_15m_confirmed"])
        ) if not btc_blocked else pd.Series(False, index=dataframe.index)
        dataframe.loc[long_cond, "enter_long"] = 1
        dataframe.loc[long_cond, "enter_tag"] = "hfr_long"

        # Short entries
        short_cond = (
            (dataframe["hfr_signal_short"] >= self._entry_threshold)
            & (dataframe["volume_score"] >= self._vol_hard_gate)
            & (dataframe["momentum_score"] >= self._mom_hard_gate)
            & (dataframe["momentum_direction"] == -1)
            & (dataframe["vol_15m_confirmed"])
        ) if not btc_blocked else pd.Series(False, index=dataframe.index)
        dataframe.loc[short_cond, "enter_short"] = 1
        dataframe.loc[short_cond, "enter_tag"] = "hfr_short"

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        """
        Exit priority:
        1. Time exit (> max hours)
        2. BTC reversal (BTC flips while in profit)
        3. Signal decay (signal fizzled, trade flat)
        """
        # 1. Time exit
        trade_duration = (current_time - trade.open_date_utc).total_seconds() / 3600
        if trade_duration >= self._time_exit_hours:
            return "time_exit"

        # 2. BTC reversal exit
        if self._btc_trend and current_profit > 0.005:
            btc_mom = self._btc_trend.get("btc_mom", 0.0)
            if not trade.is_short and btc_mom < -self._btc_reversal:
                return "btc_reversal"
            if trade.is_short and btc_mom > self._btc_reversal:
                return "btc_reversal"

        # 3. Signal decay exit
        if trade_duration >= self._decay_hours and abs(current_profit) < self._decay_profit_band:
            if self.dp:
                analyzed_df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
                if analyzed_df is not None and not analyzed_df.empty:
                    last = analyzed_df.iloc[-1]
                    signal_col = "hfr_signal_short" if trade.is_short else "hfr_signal_long"
                    if signal_col in last and last[signal_col] < self._decay_threshold:
                        return "signal_decay"

        return None

    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: Optional[float], max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs) -> Optional[float]:
        """Partial take profits via negative stake returns.

        TP1: sell 40% at +2.5%
        TP2: sell 30% at +5.0%
        Remaining 30% rides with trailing stop.
        """
        exits_done = trade.nr_of_successful_exits

        if exits_done == 0 and current_profit >= self._tp1_pct:
            return -(trade.stake_amount * self._tp1_ratio)

        if exits_done == 1 and current_profit >= self._tp2_pct:
            return -(trade.stake_amount * self._tp2_ratio)

        return None

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float,
                 entry_tag: Optional[str], side: str, **kwargs) -> float:
        """Linear leverage scaling: 5x at signal 0.55, 12x at signal 1.0."""
        signal = self._entry_threshold  # Default minimum
        if self.dp:
            analyzed_df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if analyzed_df is not None and not analyzed_df.empty:
                last = analyzed_df.iloc[-1]
                signal_col = "hfr_signal_short" if side == "short" else "hfr_signal_long"
                if signal_col in last:
                    signal = float(last[signal_col])

        lev = self._lev_min + (signal - self._entry_threshold) * (
            (self._lev_max - self._lev_min) / (1.0 - self._entry_threshold)
        )
        lev = max(self._lev_min, min(lev, self._lev_max, max_leverage))
        return int(lev)  # Hyperliquid requires integer leverage

    def custom_stake_amount(self, pair: str, current_time: datetime,
                            current_rate: float, proposed_stake: float,
                            min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str],
                            side: str, **kwargs) -> float:
        return min(self.stake_per_position, max_stake)

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float,
                            rate: float, time_in_force: str, current_time: datetime,
                            entry_tag: Optional[str], side: str, **kwargs) -> bool:
        open_trades = Trade.get_trades_proxy(is_open=True)
        if len(open_trades) >= self.max_open_trades_cfg:
            return False
        return True

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float,
                        after_fill: bool, **kwargs) -> float:
        """ATR-based stop below trailing trigger, trailing stop above it."""
        # Above trailing trigger → tight trailing stop
        if current_profit >= self._trail_trigger:
            return -self._trail_distance

        # Below trailing trigger → ATR-based stop
        if self.dp:
            analyzed_df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if analyzed_df is not None and not analyzed_df.empty:
                atr = float(analyzed_df["atr"].iloc[-1])
                atr_stop = -(atr * self._sl_atr_mult) / trade.open_rate
                return max(atr_stop, self._sl_cap)

        return self._sl_cap
