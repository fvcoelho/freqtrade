"""Dynamic stake sizing for BetaV59Plus."""
from __future__ import annotations

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class DynamicStake:
    def __init__(self, cfg: dict):
        sc = cfg.get("stake", {})
        self._mode = sc.get("mode", "fixed")
        self._reserve_pct = sc.get("reserve_pct", 0.10)
        self._stake_cap = sc.get("stake_cap", 200.0)
        self._min_stake = sc.get("min_stake", 10.0)
        self._rebalance_secs = sc.get("rebalance_secs", 300)
        self._max_positions = cfg.get("basket", {}).get("max_positions", 4)
        self._fixed_stake = cfg.get("basket", {}).get("stake_per_position", 100.0)
        self._max_dca_adds = cfg.get("dca", {}).get("max_adds", 2)
        self._dca_multipliers = cfg.get("dca", {}).get("multipliers", [0.5, 0.3])
        self._last_calc_time: float = 0.0
        self._cached_stake: float = self._fixed_stake
        self._cached_balance: float = 0.0

    def _get_reserve_pct(self, equity: float, open_trade_count: int) -> float:
        if equity < 150:
            return 0.10
        elif equity < 500:
            base = 0.15
        else:
            base = 0.10
        dca_per_trade = sum(self._dca_multipliers[:self._max_dca_adds])
        dca_extra = open_trade_count * dca_per_trade * 0.05
        return min(base + dca_extra, 0.35)

    def compute(self, wallets, stake_currency: str, open_trade_count: int,
                max_stake: float, open_trades: Optional[list] = None) -> float:
        if self._mode == "fixed":
            return min(self._fixed_stake, max_stake)

        now = time.monotonic()
        if (now - self._last_calc_time) < self._rebalance_secs and self._cached_stake > 0:
            return min(self._cached_stake, max_stake)

        try:
            total_balance = wallets.get_total(stake_currency)
            free_balance = wallets.get_free(stake_currency)
        except Exception as e:
            logger.warning("DynamicStake: wallet query failed (%s)", e)
            return min(self._cached_stake, max_stake)

        unrealized_pnl = 0.0
        locked_stake = 0.0
        if open_trades:
            for t in open_trades:
                try:
                    unrealized_pnl += t.calc_profit() or 0.0
                except Exception:
                    pass
            locked_stake = sum(t.stake_amount for t in open_trades)

        equity = free_balance + locked_stake + unrealized_pnl
        remaining_slots = max(1, self._max_positions - open_trade_count)
        reserve_pct = self._get_reserve_pct(equity, open_trade_count)
        reserve_amount = equity * reserve_pct
        deployable_equity = max(0, equity - reserve_amount)
        stake = deployable_equity / self._max_positions
        stake = min(stake, free_balance * 0.90)
        stake = max(self._min_stake, min(stake, self._stake_cap, max_stake))

        if stake < self._min_stake:
            stake = 0.0

        self._last_calc_time = now
        self._cached_stake = stake
        self._cached_balance = total_balance
        return stake

    @property
    def last_balance(self) -> float:
        return self._cached_balance

    @property
    def last_stake(self) -> float:
        return self._cached_stake
