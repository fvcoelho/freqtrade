"""Group management for V54 dual independent groups."""
from __future__ import annotations
from datetime import datetime
from typing import Optional


class GroupState:
    """Per-group mutable state."""
    def __init__(self, name: str, sub1: list[str], sub2: list[str]):
        self.name = name
        self.sub1 = sub1
        self.sub2 = sub2
        self.all_pairs = sub1 + sub2
        self.cooldown_until: Optional[datetime] = None
        self.pair_zscores: dict = {}

    @property
    def unique_pairs(self) -> set[str]:
        return set(self.all_pairs)


def load_groups(cfg: dict) -> list[GroupState]:
    groups = []
    for key in ("group_a", "group_b"):
        g = cfg["groups"].get(key)
        if not g:
            continue
        groups.append(GroupState(name=g["name"], sub1=g["sub1"], sub2=g["sub2"]))
    return groups


def all_tradable_pairs(groups: list[GroupState]) -> list[str]:
    pairs = set()
    for g in groups:
        pairs.update(g.all_pairs)
    return sorted(pairs)


def count_open_trades_in_group(group: GroupState, open_trades: list) -> int:
    return sum(1 for t in open_trades if t.pair in group.unique_pairs)


def can_open_trade(group: GroupState, pair: str, cfg: dict,
                   current_time: datetime, open_trades: list,
                   all_groups: list[GroupState]) -> bool:
    if group.cooldown_until and current_time < group.cooldown_until:
        return False
    max_per_group = cfg.get("max_trades_per_group", 1)
    if count_open_trades_in_group(group, open_trades) >= max_per_group:
        return False
    max_total = cfg.get("max_total_trades", 2)
    if len(open_trades) >= max_total:
        return False
    return True
