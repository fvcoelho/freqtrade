"""DCA (Dollar Cost Average) + Partial Stop for V56.

DCA: adds stake to winning positions progressively.
Partial Stop: sells a portion at a loss threshold to reduce total loss.

Example (Partial Stop at -4%, sell 75%, final stop -7%):
    Without: -7% full → -7% loss
    With:    -4% sell 75% → -2.25%
             -7% stop 25% → -1.75%
             Total: -4.0% (vs -7% without)
"""
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
    """DCA (add) + Partial Stop (reduce) position adjustments.

    Returns:
        Positive float → add stake (DCA)
        Negative float → reduce stake (Partial Stop)
        None → no adjustment
    """
    # Partial Stop: sell portion at loss threshold
    ps = cfg.get("partial_stop", {})
    if ps.get("enabled", False):
        result = _partial_stop(trade, current_profit, ps, min_stake)
        if result is not None:
            return result

    # DCA: add to winners
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
    """Sell a portion of the position when loss reaches trigger.

    Only triggers once per trade (checks nr_of_successful_exits).
    """
    if trade.nr_of_successful_exits > 0:
        return None

    trigger = ps_cfg.get("trigger", -0.04)
    sell_ratio = ps_cfg.get("sell_ratio", 0.75)

    if current_profit <= trigger:
        sell_amount = trade.stake_amount * sell_ratio
        if min_stake and sell_amount < min_stake:
            sell_amount = min_stake
        logger.info(
            "PARTIAL STOP: %s %.1f%% — selling %.0f%%",
            trade.pair, current_profit * 100, sell_ratio * 100,
        )
        return -sell_amount

    return None
