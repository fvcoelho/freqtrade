"""DCA (Dollar Cost Average) + Partial Stop."""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def adjust_position(
    trade,
    current_profit: float,
    cfg: dict,
    min_stake: Optional[float],
    max_stake: float,
) -> Optional[float]:
    ps = cfg.get("partial_stop", {})
    if ps.get("enabled", False):
        result = _partial_stop(trade, current_profit, ps, min_stake)
        if result is not None:
            return result

    dca = cfg["dca"]
    thresholds = dca["thresholds"]
    multipliers = dca["multipliers"]

    adds = trade.nr_of_successful_entries - 1
    if adds >= len(thresholds):
        return None
    if current_profit <= 0:
        return None
    if current_profit >= thresholds[adds]:
        add_stake = trade.stake_amount * multipliers[adds]
        if min_stake and add_stake < min_stake:
            add_stake = min_stake
        return min(add_stake, max_stake)
    return None


def _partial_stop(trade, current_profit, ps_cfg, min_stake):
    if trade.nr_of_successful_exits > 0:
        return None
    trigger = ps_cfg.get("trigger", -0.04)
    sell_ratio = ps_cfg.get("sell_ratio", 0.75)
    if current_profit <= trigger:
        sell_amount = trade.stake_amount * sell_ratio
        if min_stake and sell_amount < min_stake:
            sell_amount = min_stake
        logger.info("PARTIAL STOP: %s %.1f%%", trade.pair, current_profit * 100)
        return -sell_amount
    return None
