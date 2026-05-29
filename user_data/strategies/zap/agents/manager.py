"""Manager Agent: handles exits, DCA, trailing, time stops."""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ManagerAgent:
    """Manages open trades: exits, DCA, trailing, time stops."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self._mcfg = cfg.get("manager", {})

    def check_exit(self, pair, trade, current_rate, current_profit, current_prediction, do_predict, candles_open):
        """Check if trade should exit. Returns exit tag string or None."""
        # 1. ML exit: prediction flipped sign
        if do_predict == 1 and current_prediction != 0:
            is_long = trade.is_short is False
            if is_long and current_prediction < -0.002:
                logger.info(f"[ZAP:Manager] ML EXIT {pair}: pred={current_prediction:.4f}")
                return "zap_ml_exit"
            elif not is_long and current_prediction > 0.002:
                logger.info(f"[ZAP:Manager] ML EXIT {pair}: pred={current_prediction:.4f}")
                return "zap_ml_exit"

        # 2. Time stop
        time_stop = self._mcfg.get("time_stop_candles", 48)
        if candles_open >= time_stop:
            logger.info(f"[ZAP:Manager] TIME STOP {pair}: {candles_open} candles, profit={current_profit:.2%}")
            return "zap_time_stop"

        # 3. Profit lock
        trailing_act = self._mcfg.get("trailing_activate", 0.02)
        if current_profit > trailing_act and do_predict == 1:
            if abs(current_prediction) < 0.001:
                logger.info(f"[ZAP:Manager] PROFIT LOCK {pair}: profit={current_profit:.2%}, pred={current_prediction:.4f}")
                return "zap_profit_lock"

        return None

    def get_stoploss(self, pair, current_profit, current_prediction):
        """Dynamic stoploss. Returns negative float."""
        base_sl = self._mcfg.get("stoploss", -0.10)
        trailing_act = self._mcfg.get("trailing_activate", 0.02)
        trailing_off = self._mcfg.get("trailing_offset", 0.005)

        if current_profit > trailing_act:
            return -(current_profit - trailing_off)
        return base_sl

    def check_dca(self, pair, trade, current_profit, current_prediction, do_predict, wallet_balance):
        """Check DCA. Returns stake amount or None."""
        dca_threshold = self._mcfg.get("dca_threshold", -0.03)
        dca_min_pred = self._mcfg.get("dca_min_predicted", 0.008)
        dca_multipliers = self._mcfg.get("dca_multipliers", [1.5, 2.5])

        if current_profit > dca_threshold:
            return None
        if do_predict != 1:
            return None

        is_long = trade.is_short is False
        if is_long and current_prediction < dca_min_pred:
            return None
        if not is_long and current_prediction > -dca_min_pred:
            return None

        dca_count = getattr(trade, "nr_of_successful_entries", 1) - 1
        if dca_count >= len(dca_multipliers):
            return None

        multiplier = dca_multipliers[dca_count]
        base_stake = trade.stake_amount
        dca_stake = base_stake * multiplier
        max_stake = wallet_balance * 0.10
        dca_stake = min(dca_stake, max_stake)

        logger.info(f"[ZAP:Manager] DCA #{dca_count+1} {pair}: ${dca_stake:.2f} (mult={multiplier}x)")
        return dca_stake
