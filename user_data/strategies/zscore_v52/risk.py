"""Pre-trade risk gates for ZScore V52."""
from __future__ import annotations

from datetime import datetime
from typing import Optional


def confirm_entry(
    pair: str,
    cfg: dict,
    current_time: datetime,
    cooldown_until: Optional[datetime],
    group_a: list[str],
    group_b: list[str],
    open_trades: list,
) -> bool:
    """Final gate before trade opens.

    Checks: cooldown, wait_all_closed, group balance.
    """
    if cooldown_until and current_time < cooldown_until:
        return False

    bal = cfg["balance"]
    wait_all_closed = bal.get("wait_all_closed", False)
    max_group_imbalance = bal.get("max_group_imbalance", 1)

    if wait_all_closed and len(open_trades) > 0:
        return False

    count_a = sum(1 for t in open_trades if t.pair in group_a)
    count_b = sum(1 for t in open_trades if t.pair in group_b)

    if pair in group_a and count_a + 1 - count_b > max_group_imbalance:
        return False
    if pair in group_b and count_b + 1 - count_a > max_group_imbalance:
        return False

    return True
