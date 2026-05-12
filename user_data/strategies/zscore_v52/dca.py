"""DCA (Dollar-Cost Averaging) logic for ZScore V52."""
from __future__ import annotations

from typing import Optional


def adjust_position(
    trade,
    current_profit: float,
    cfg: dict,
    min_stake: Optional[float],
    max_stake: float,
) -> Optional[float]:
    """DCA: add to winning positions progressively.

    Returns positive float stake to add, or None to skip.
    """
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
