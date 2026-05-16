"""ZScoreV57Monitor — V57 Strategy + WebSocket broadcasting for monitor page.

Extends ZScoreV57Strategy with real-time data broadcasting via dp.send_msg().
Each candle cycle, broadcasts pair data + wallet/stake info for the monitor UI.
"""
import json
import logging
from datetime import datetime
from typing import Optional

from pandas import DataFrame
from freqtrade.persistence import Trade

from zscore_v57.strategy import ZScoreV57Strategy

logger = logging.getLogger(__name__)


class ZScoreV57Monitor(ZScoreV57Strategy):

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_indicators(dataframe, metadata)
        pair = metadata["pair"]
        if dataframe.empty or not self.dp:
            return dataframe

        last = dataframe.iloc[-1]

        # Current basket z-score
        basket_z = float(last.get("basket_z", 0.0))
        basket_spread = float(last.get("basket_spread", 0.0))

        # BTC indicators
        btc_mom = float(last.get("btc_mom", 0.0))
        btc_atr_z = float(last.get("btc_atr_z", 0.0))
        btc_pump = bool(last.get("btc_pump", False))
        btc_dump = bool(last.get("btc_dump", False))
        btc_high_vol = bool(last.get("btc_high_vol", False))
        vol_ok = int(last.get("vol_ok", 1))
        vol_ratio = float(last.get("vol_ratio", 1.0))

        # Determine signal
        entry_z = self._cfg.get("basket", {}).get("entry_z", 2.0)
        bear_threshold = self._cfg.get("basket", {}).get("bear_mom_threshold", -1.0)
        bull_threshold = self._cfg.get("basket", {}).get("bull_mom_threshold", 0.0)

        signal = "neutral"
        if btc_mom > bull_threshold and basket_z < -entry_z and not btc_dump and not btc_high_vol and vol_ok:
            signal = "long"
        elif btc_mom < bear_threshold and basket_z > entry_z and not btc_pump and not btc_high_vol and vol_ok:
            signal = "short"

        # Regime
        regime = "BULL" if btc_mom > bull_threshold else "BEAR" if btc_mom < bear_threshold else "RANGING"

        # Open trades
        all_open = Trade.get_trades_proxy(is_open=True)
        pair_trades = [t for t in all_open if t.pair == pair]
        has_trade = len(pair_trades) > 0
        trade_side = ""
        trade_profit = 0.0
        trade_tag = ""
        trade_leverage = 0.0
        trade_stake = 0.0
        trade_duration_min = 0
        trade_adds = 0
        if has_trade:
            t = pair_trades[0]
            trade_side = "short" if t.is_short else "long"
            trade_profit = t.calc_profit_ratio(float(last["close"]))
            trade_tag = t.enter_tag or ""
            trade_leverage = float(t.leverage or 1.0)
            trade_stake = float(t.stake_amount or 0.0)
            trade_duration_min = int((datetime.utcnow() - t.open_date_utc).total_seconds() / 60)
            trade_adds = t.nr_of_successful_entries - 1 if t.nr_of_successful_entries > 1 else 0

        # Wallet / stake info (from dynamic stake)
        wallet_balance = self._dynamic_stake.last_balance
        current_stake = self._dynamic_stake.last_stake

        # Total PnL from open trades
        total_open_pnl = sum(
            t.calc_profit_ratio(float(last["close"])) * t.stake_amount
            for t in all_open
            if t.pair == pair
        )

        msg = json.dumps({
            "monitor": True,
            "version": "v57",
            "pair": pair,
            "timestamp": str(last.get("date", "")),
            "price": round(float(last["close"]), 6),
            "open": round(float(last.get("open", last["close"])), 6),
            "high": round(float(last.get("high", last["close"])), 6),
            "low": round(float(last.get("low", last["close"])), 6),
            # Z-score
            "basket_z": round(basket_z, 4),
            "basket_spread": round(basket_spread, 6),
            "signal": signal,
            # BTC
            "btc_mom": round(btc_mom, 4),
            "btc_atr_z": round(btc_atr_z, 4),
            "btc_pump": btc_pump,
            "btc_dump": btc_dump,
            "btc_high_vol": btc_high_vol,
            "regime": regime,
            # Volume
            "vol_ratio": round(vol_ratio, 2),
            "vol_ok": vol_ok,
            # Trade
            "has_trade": has_trade,
            "trade_side": trade_side,
            "trade_profit_pct": round(trade_profit * 100, 2),
            "trade_tag": trade_tag,
            "trade_leverage": round(trade_leverage, 1),
            "trade_stake": round(trade_stake, 2),
            "trade_duration_min": trade_duration_min,
            "trade_adds": trade_adds,
            # Global
            "total_open_trades": len(all_open),
            "max_positions": self._cfg.get("basket", {}).get("max_positions", 4),
            "wallet_balance": round(wallet_balance, 2),
            "current_stake_size": round(current_stake, 2),
            # Config
            "basket_pairs": [p.split("/")[0] for p in self._basket_pairs],
            "entry_z_threshold": entry_z,
            "timeframe": self.timeframe,
        })
        self.dp.send_msg(msg, always_send=True)
        return dataframe
