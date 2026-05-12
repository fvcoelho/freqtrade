"""ZScoreMonitor — V50 Combined + WebSocket broadcasting for monitor page.

Sends a JSON message via dp.send_msg() every cycle with all data
needed for the monitor UI to render.
"""
import json
import logging
from datetime import datetime
from typing import Optional

from pandas import DataFrame

from freqtrade.persistence import Trade
from ZScorePTV50Combined import ZScorePTV50Combined


logger = logging.getLogger(__name__)


class ZScoreMonitor(ZScorePTV50Combined):

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_indicators(dataframe, metadata)
        pair = metadata["pair"]

        if dataframe.empty or not self.dp:
            return dataframe

        last = dataframe.iloc[-1]

        # Determine current signal
        signal = "neutral"
        pair_z = float(last.get("pair_zscore", 0.0))
        spread_z = float(last.get("spread_zscore", 0.0))

        if pair in self.group_a:
            if spread_z < -self._zscore_entry and pair_z < -self._pair_z_entry:
                signal = "long"
        elif pair in self.group_b:
            if spread_z < -self._zscore_entry and pair_z > self._pair_z_entry:
                signal = "short"
            elif spread_z > self._zscore_entry and pair_z < -self._pair_z_entry:
                signal = "long"

        # All open trades (global)
        all_open = Trade.get_trades_proxy(is_open=True)
        total_open = len(all_open)

        # This pair's trade
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

        # Regime detection
        is_consolidation = bool(
            float(last.get("btc_atr_z", 0.0)) < self._consolidation_atr_z
            and abs(spread_z) < self._consolidation_spread_max
            and abs(float(last.get("btc_mom", 0.0))) < self._consolidation_btc_mom_max
        )
        is_trending = bool(
            abs(float(last.get("btc_mom", 0.0))) > self._trending_btc_mom
            or float(last.get("btc_atr_z", 0.0)) > self._trending_atr_z
        )
        regime_label = "TRENDING" if is_trending else ("CONSOLIDATION" if is_consolidation else "RANGING")

        msg = json.dumps({
            "monitor": True,
            "pair": pair,
            "timestamp": str(last.get("date", "")),
            "open": round(float(last.get("open", last["close"])), 4),
            "high": round(float(last.get("high", last["close"])), 4),
            "low": round(float(last.get("low", last["close"])), 4),
            "price": round(float(last["close"]), 4),
            "pair_zscore": round(pair_z, 4),
            "spread_zscore": round(spread_z, 4),
            "signal": signal,
            "regime_ok": int(last.get("regime_ok", 1)),
            "regime_label": regime_label,
            "btc_mom": round(float(last.get("btc_mom", 0.0)), 4),
            "btc_atr_z": round(float(last.get("btc_atr_z", 0.0)), 4),
            "btc_pump": bool(last.get("btc_pump", False)),
            "btc_dump": bool(last.get("btc_dump", False)),
            "btc_high_vol": bool(last.get("btc_high_vol", False)),
            "vol_ratio": round(float(last.get("vol_ratio", 1.0)), 2),
            "rolling_corr": round(float(last.get("rolling_corr", 0.0)), 4),
            # Trade info
            "has_trade": has_trade,
            "trade_side": trade_side,
            "trade_profit_pct": round(trade_profit * 100, 2),
            "trade_tag": trade_tag,
            "trade_leverage": round(trade_leverage, 1),
            "trade_stake": round(trade_stake, 2),
            "trade_duration_min": trade_duration_min,
            "trade_adds": trade_adds,
            # Global
            "total_open_trades": total_open,
            "max_open_trades": self.config.get("max_open_trades", 0),
            "group": "A" if pair in self.group_a else ("B" if pair in self.group_b else "?"),
            "group_a": [p.split("/")[0] for p in self.group_a],
            "group_b": [p.split("/")[0] for p in self.group_b],
            # Strategy config
            "strategy_config": {
                "name": "ZScorePTV50Combined",
                "timeframe": self.timeframe,
                "stoploss": round(self.stoploss, 3),
                "trailing_stop_positive": round(self.trailing_stop_positive, 4),
                "trailing_stop_offset": round(self.trailing_stop_positive_offset, 4),
                "zscore_entry": self._zscore_entry,
                "pair_z_entry": self._pair_z_entry,
                "consol_zscore_entry": self._consol_zscore_entry,
                "regime_corr_min": self._regime_corr_min,
                "minimal_roi": self.minimal_roi,
                "position_adjustment": self.position_adjustment_enable,
                "max_adds": self.max_entry_position_adjustment,
            },
        })

        self.dp.send_msg(msg, always_send=True)

        return dataframe
