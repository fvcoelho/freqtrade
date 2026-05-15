"""Dynamic stake sizing for ZScore V57.

Periodically queries wallet balance and divides stake optimally:
    available = total_balance - locked_in_trades
    reserve   = available * reserve_pct        (safety buffer for margin/DCA)
    deployable = available - reserve
    stake     = deployable / remaining_slots

Clamps to [min_stake, max_stake] and never exceeds stake_cap from config.

Config (v57_config.json → "stake"):
    mode:           "dynamic" | "fixed"  (default: "fixed" for backward compat)
    reserve_pct:    0.10   — 10% reserve for margin calls / DCA
    dca_reserve_pct: 0.15  — extra 15% for DCA adds (total 25% reserved)
    stake_cap:      200    — max stake per position (safety)
    min_stake:      10     — min stake per position
    rebalance_secs: 300    — how often to recalculate (5 min)
"""
from __future__ import annotations

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class DynamicStake:
    """Calculates optimal stake per position based on live wallet balance."""

    def __init__(self, cfg: dict):
        sc = cfg.get("stake", {})
        self._mode = sc.get("mode", "fixed")
        self._reserve_pct = sc.get("reserve_pct", 0.10)
        self._dca_reserve_pct = sc.get("dca_reserve_pct", 0.15)
        self._stake_cap = sc.get("stake_cap", 200.0)
        self._min_stake = sc.get("min_stake", 10.0)
        self._rebalance_secs = sc.get("rebalance_secs", 300)
        self._max_positions = cfg.get("basket", {}).get("max_positions", 4)
        self._fixed_stake = cfg.get("basket", {}).get("stake_per_position", 100.0)

        # Cache
        self._last_calc_time: float = 0.0
        self._cached_stake: float = self._fixed_stake
        self._cached_balance: float = 0.0

    def compute(
        self,
        wallets,
        stake_currency: str,
        open_trade_count: int,
        max_stake: float,
    ) -> float:
        """Return the optimal stake for the next trade.

        Args:
            wallets: freqtrade Wallets object (self.wallets)
            stake_currency: e.g. "USDC"
            open_trade_count: number of currently open trades
            max_stake: max allowed by freqtrade
        """
        if self._mode == "fixed":
            return min(self._fixed_stake, max_stake)

        # Throttle recalculation
        now = time.monotonic()
        if (now - self._last_calc_time) < self._rebalance_secs and self._cached_stake > 0:
            return min(self._cached_stake, max_stake)

        # Query wallet
        try:
            total_balance = wallets.get_total(stake_currency)
            free_balance = wallets.get_free(stake_currency)
        except Exception as e:
            logger.warning("DynamicStake: wallet query failed (%s), using cached", e)
            return min(self._cached_stake, max_stake)

        # How many slots are still available
        remaining_slots = max(1, self._max_positions - open_trade_count)

        # Reserve for margin + DCA
        total_reserve_pct = self._reserve_pct + self._dca_reserve_pct
        deployable = free_balance * (1.0 - total_reserve_pct)

        # Divide equally among remaining slots
        stake = deployable / remaining_slots

        # Clamp
        stake = max(self._min_stake, min(stake, self._stake_cap, max_stake))

        # Cache
        self._last_calc_time = now
        self._cached_stake = stake
        self._cached_balance = total_balance

        logger.info(
            "DynamicStake: total=%.2f free=%.2f deployable=%.2f "
            "slots=%d → stake=%.2f",
            total_balance, free_balance, deployable,
            remaining_slots, stake,
        )

        return stake

    @property
    def last_balance(self) -> float:
        return self._cached_balance

    @property
    def last_stake(self) -> float:
        return self._cached_stake
