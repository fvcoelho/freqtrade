"""Pre-trade risk gates for ZScore V53 -- per-group cooldown."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from zscore_v53.groups import GroupState, can_open_trade


def confirm_entry(
    pair: str,
    cfg: dict,
    current_time: datetime,
    group: GroupState,
    all_groups: list["GroupState"],
    open_trades: list,
) -> bool:
    """Return True if the trade is allowed to open.

    Delegates to groups.can_open_trade which checks per-group cooldown,
    per-group trade count, and total trade count.
    """
    return can_open_trade(group, pair, cfg, current_time, open_trades, all_groups)
