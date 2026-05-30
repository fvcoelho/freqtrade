"""ZAP Strategy — ZScore Agent Pipeline.

Orchestrates 4 agents via freqtrade callbacks:
- Scanner: populate_indicators() — computes features
- Regime: populate_indicators() — determines market state
- Entry: populate_entry_trend() + confirm_trade_entry() — generates signals
- Manager: custom_exit() + custom_stoploss() + adjust_trade_position() — manages trades
"""
from __future__ import annotations

import logging
from functools import reduce
from pathlib import Path

import pandas as pd
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy

from zap.agents.entry import EntryAgent
from zap.agents.manager import ManagerAgent
from zap.agents.regime import RegimeAgent
from zap.agents.scanner import ScannerAgent
from zap.config import load_config
from zap.queues import QueueManager

logger = logging.getLogger(__name__)


class ZAPStrategy(IStrategy):
    """ZScore Agent Pipeline Strategy with FreqAI."""

    INTERFACE_VERSION = 3

    minimal_roi = {"0": 0.15}
    stoploss = -0.05
    trailing_stop = False
    use_exit_signal = True
    use_custom_stoploss = False
    position_adjustment_enable = False
    process_only_new_candles = True
    can_short = False
    startup_candle_count = 300

    timeframe = "5m"

    def __init__(self, config: dict) -> None:
        super().__init__(config)

        zap_cfg_path = Path(config.get("user_data_dir", "user_data")) / "strategies" / "zap_config.json"
        self._cfg = load_config(zap_cfg_path)

        self._qm = QueueManager(self._cfg)
        self._scanner = ScannerAgent(self._cfg, self._qm)
        self._regime = RegimeAgent(self._cfg)
        self._entry = EntryAgent(self._cfg, self._qm)
        self._manager = ManagerAgent(self._cfg)

        self._btc_df: DataFrame | None = None
        self._candle_idx: int = 0

        logger.info("[ZAP] Strategy initialized")

    def informative_pairs(self):
        pairs = [("BTC/USDC:USDC", "5m")]
        # Stock pairs for correlation features (live/dry-run only)
        for stock in self._STOCK_PAIRS:
            pairs.append((stock, "5m"))
        return pairs

    # ========== FreqAI Feature Engineering ==========

    def feature_engineering_expand_all(self, dataframe, period, metadata, **kwargs):
        import talib.abstract as ta
        dataframe["%-rsi-period"] = ta.RSI(dataframe, timeperiod=period)
        dataframe["%-adx-period"] = ta.ADX(dataframe, timeperiod=period)
        dataframe["%-mfi-period"] = ta.MFI(dataframe, timeperiod=period)
        dataframe["%-ema-period"] = ta.EMA(dataframe, timeperiod=period)
        dataframe["%-roc-period"] = ta.ROC(dataframe, timeperiod=period)
        dataframe["%-relative_volume-period"] = (
            dataframe["volume"] / dataframe["volume"].rolling(period).mean()
        )
        return dataframe

    def feature_engineering_expand_basic(self, dataframe, metadata, **kwargs):
        dataframe["%-pct-change"] = dataframe["close"].pct_change()
        dataframe["%-raw_volume"] = dataframe["volume"]
        dataframe["%-raw_price"] = dataframe["close"]
        return dataframe

    # Stock pairs to use as features (HL perps)
    _STOCK_PAIRS = [
        "XYZ-NVDA/USDC:USDC",
        "XYZ-MSTR/USDC:USDC",
        "XYZ-COIN/USDC:USDC",
    ]

    def _add_stock_features(self, dataframe, pair):
        """Add stock price correlation/momentum features for trading pairs.

        Fetches live stock data via dp and computes rolling correlation
        and momentum features. Defaults to 0 when data is unavailable.
        """
        import numpy as np

        pair_ret = dataframe["close"].pct_change()
        window = 144  # 12h rolling window

        for stock in self._STOCK_PAIRS:
            tag = stock.split("/")[0].replace("XYZ-", "").lower()
            try:
                sdf = self.dp.get_pair_dataframe(pair=stock, timeframe="5m")
                if sdf is not None and len(sdf) >= 50:
                    # Align by length
                    stock_ret = sdf["close"].pct_change()
                    n = len(dataframe)
                    if len(stock_ret) >= n:
                        stock_ret = stock_ret.iloc[-n:].reset_index(drop=True)
                    else:
                        pad = pd.Series(0.0, index=range(n - len(stock_ret)))
                        stock_ret = pd.concat([pad, stock_ret.reset_index(drop=True)], ignore_index=True)

                    stock_ret.index = dataframe.index

                    # Rolling correlation with stock
                    dataframe[f"%-stock_corr_{tag}"] = (
                        pair_ret.rolling(window).corr(stock_ret).fillna(0.0)
                    )
                    # Stock momentum (12-candle return)
                    dataframe[f"%-stock_mom_{tag}"] = (
                        stock_ret.rolling(12).sum().fillna(0.0)
                    )
                    continue
            except Exception:
                pass

            # Fallback: no data
            dataframe[f"%-stock_corr_{tag}"] = 0.0
            dataframe[f"%-stock_mom_{tag}"] = 0.0

        return dataframe

    def feature_engineering_standard(self, dataframe, metadata, **kwargs):
        pair = metadata["pair"]
        whitelist = self.dp.current_whitelist() if self.dp else []

        # Only compute custom features for trading pairs, not corr pairs.
        if pair in whitelist:
            all_pairs = whitelist
            btc_df = None
            if self.dp:
                btc_df = self.dp.get_pair_dataframe(pair="BTC/USDC:USDC", timeframe="5m")

            dataframe = self._scanner.update(
                df=dataframe, pair=pair, all_pairs=all_pairs,
                btc_df=btc_df, dp=self.dp,
            )

            # Add stock correlation features (live only, defaults to 0 in backtest)
            if self.dp:
                dataframe = self._add_stock_features(dataframe, pair)

        dates = pd.to_datetime(dataframe["date"], utc=True)
        dataframe["%-day_of_week"] = dates.dt.dayofweek
        dataframe["%-hour_of_day"] = dates.dt.hour
        return dataframe

    def set_freqai_targets(self, dataframe, metadata, **kwargs):
        label_period = self.freqai_info.get(
            "feature_parameters", {}
        ).get("label_period_candles", 12)

        dataframe["&-s_close"] = (
            dataframe["close"]
            .shift(-label_period)
            .rolling(label_period)
            .mean()
            / dataframe["close"]
            - 1
        )
        return dataframe

    # ========== Freqtrade Callbacks ==========

    def populate_indicators(self, dataframe, metadata):
        import talib.abstract as ta

        if self.dp:
            btc_df = self.dp.get_pair_dataframe(pair="BTC/USDC:USDC", timeframe="5m")
            self._regime.update(btc_df)
            self._btc_df = btc_df

            # Compute per-candle regime from BTC data and merge into dataframe
            if btc_df is not None and len(btc_df) > 50:
                btc_regime = btc_df[["date"]].copy()
                btc_adx = ta.ADX(btc_df, timeperiod=14)
                btc_ema21 = ta.EMA(btc_df, timeperiod=21)
                btc_mom = ta.ROC(btc_df, timeperiod=48)
                btc_slope = (btc_ema21 - btc_ema21.shift(3)) / (btc_ema21.shift(3) + 1e-10) * 100

                # Regime: bull if momentum>0 and slope>0, bear if both<0, else ranging
                import numpy as np
                regime_col = np.where(
                    btc_adx < 18, 0,  # ranging
                    np.where(
                        (btc_mom > 0) & (btc_slope > 0), 1,  # bull
                        np.where(
                            (btc_mom < 0) & (btc_slope < 0), -1,  # bear
                            0  # ranging
                        )
                    )
                )
                btc_regime["btc_regime"] = regime_col
                dataframe = dataframe.merge(btc_regime, on="date", how="left")
                dataframe["btc_regime"] = dataframe["btc_regime"].fillna(0).astype(int)
            else:
                dataframe["btc_regime"] = 0

        dataframe = self.freqai.start(dataframe, metadata, self)

        if "&-s_close" in dataframe.columns:
            last = dataframe.iloc[-1]
            pred = float(last.get("&-s_close", 0))
            pair = metadata["pair"]
            side = "long" if pred >= 0 else "short"
            mult = self._regime.state.get_multiplier(side, self._cfg)

            features = {
                col: float(last[col])
                for col in dataframe.columns
                if col.startswith("%-") and last[col] == last[col]
            }

            self._candle_idx = len(dataframe)
            self._qm.update_pair(pair, features, pred, mult, self._candle_idx)
            self._qm.rank_queues(self._candle_idx)

        return dataframe

    def populate_entry_trend(self, dataframe, metadata):
        return self._entry.generate_signals(
            dataframe, metadata["pair"], self._regime.state
        )

    def populate_exit_trend(self, dataframe, metadata):
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        return dataframe

    def confirm_trade_entry(self, pair, order_type, amount, rate, time_in_force, current_time, entry_tag, side, **kwargs):
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df.empty:
            return False

        last = df.iloc[-1]
        pred = float(last.get("&-s_close", 0))
        do_pred = int(last.get("do_predict", 0))

        if do_pred != 1:
            return False

        # Check prediction direction matches side
        min_pred = self._cfg.get("entry", {}).get("min_predicted_return", 0.005)
        if side == "long" and pred < min_pred:
            return False
        if side == "short" and pred > -min_pred:
            return False

        # Regime filter
        btc_regime = int(last.get("btc_regime", 0))
        if side == "long" and btc_regime == -1:  # no longs in bear
            return False
        # Require higher confidence in ranging regime
        if btc_regime == 0:  # ranging
            min_pred_ranging = min_pred * 2
            if side == "long" and pred < min_pred_ranging:
                return False

        # Max trades gate
        open_trades = Trade.get_trades_proxy(is_open=True)
        max_trades = self._cfg.get("max_open_trades", 6)
        if len(open_trades) >= max_trades:
            return False

        return True

    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df.empty:
            return False

        last = df.iloc[-1]
        pred = float(last.get("&-s_close", 0))
        do_pred = int(last.get("do_predict", 0))
        open_date = trade.open_date.replace(tzinfo=current_time.tzinfo) if trade.open_date.tzinfo is None else trade.open_date
        candles_open = (current_time - open_date).total_seconds() / 300

        exit_tag = self._manager.check_exit(
            pair=pair, trade=trade, current_rate=current_rate,
            current_profit=current_profit, current_prediction=pred,
            do_predict=do_pred, candles_open=int(candles_open),
        )

        if exit_tag:
            self._qm.set_cooldown(pair, self._candle_idx)
            return exit_tag
        return False

    def custom_stoploss(self, pair, trade, current_time, current_rate, current_profit, after_fill, **kwargs):
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        pred = 0.0
        if not df.empty:
            pred = float(df.iloc[-1].get("&-s_close", 0))
        return self._manager.get_stoploss(pair, current_profit, pred)

    def leverage(self, pair, current_time, current_rate, proposed_leverage, max_leverage, entry_tag, side, **kwargs):
        lev_cfg = self._cfg.get("leverage", {})
        min_lev = lev_cfg.get("min", 2)
        max_lev = lev_cfg.get("max", 8)

        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df.empty:
            return float(min_lev)

        pred = abs(float(df.iloc[-1].get("&-s_close", 0)))
        scale = min(pred / 0.02, 1.0)
        lev = min_lev + scale * (max_lev - min_lev)

        if self._regime.state.regime == "ranging":
            lev = min(lev, (min_lev + max_lev) / 2)

        lev = min(lev, max_leverage)
        return float(round(lev, 1))

    def adjust_trade_position(self, trade, current_time, current_rate, current_profit, min_stake, max_stake, current_entry_rate, current_exit_rate, current_entry_profit, current_exit_profit, **kwargs):
        df, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
        if df.empty:
            return None

        last = df.iloc[-1]
        pred = float(last.get("&-s_close", 0))
        do_pred = int(last.get("do_predict", 0))
        wallet = self.wallets.get_available_stake_amount() if self.wallets else 0

        return self._manager.check_dca(
            pair=trade.pair, trade=trade, current_profit=current_profit,
            current_prediction=pred, do_predict=do_pred, wallet_balance=wallet,
        )
