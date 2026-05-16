"""Dynamic stake sizing for ZScore V57.

Queries live wallet balance and calculates optimal stake per position:

    1. Fetch total balance + unrealized PnL from open trades
    2. Reserve margin for DCA adds on existing positions
    3. Scale stake based on available equity / remaining slots
    4. Clamp to [min_stake, stake_cap] and never exceed exchange max

Scaling tiers (equity-proportional):
    < $200   → conservative (35% reserve)
    $200-500 → normal (25% reserve)
    > $500   → aggressive (20% reserve)

Config (v57_config.json -> "stake"):
    mode:           "dynamic" | "fixed"
    reserve_pct:    0.10   — base reserve for margin
    dca_reserve_pct: 0.15  — reserve for DCA adds
    stake_cap:      200    — max stake per position
    min_stake:      10     — min stake per position
    rebalance_secs: 300    — recalculate interval
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
        self._max_dca_adds = cfg.get("dca", {}).get("max_adds", 2)
        self._dca_multipliers = cfg.get("dca", {}).get("multipliers", [0.5, 0.3])

        # Cache
        self._last_calc_time: float = 0.0
        self._cached_stake: float = self._fixed_stake
        self._cached_balance: float = 0.0

    def _get_reserve_pct(self, equity: float, open_trade_count: int) -> float:
        """Adaptive reserve based on equity size and open positions.

        Lower equity → higher reserve (more conservative).
        More open trades → more DCA reserve needed.
        """
        # Base reserve scales with equity size
        if equity < 200:
            base = 0.35
        elif equity < 500:
            base = 0.25
        else:
            base = 0.20

        # Extra DCA reserve per open trade: each open trade may need DCA adds
        # Sum of DCA multipliers = total potential extra stake per trade
        dca_per_trade = sum(self._dca_multipliers[:self._max_dca_adds])
        dca_extra = open_trade_count * dca_per_trade * 0.10  # 10% per unit of DCA exposure

        return min(base + dca_extra, 0.60)  # never reserve more than 60%

    def _get_unrealized_pnl(self, open_trades) -> float:
        """Sum unrealized PnL from open trades."""
        total_pnl = 0.0
        for trade in open_trades:
            try:
                total_pnl += trade.calc_profit() or 0.0
            except Exception:
                pass
        return total_pnl

    def _get_locked_stake(self, open_trades) -> float:
        """Sum of stake locked in open trades."""
        return sum(t.stake_amount for t in open_trades)

    def compute(
        self,
        wallets,
        stake_currency: str,
        open_trade_count: int,
        max_stake: float,
        open_trades: Optional[list] = None,
    ) -> float:
        """Return the optimal stake for the next trade.

        Args:
            wallets: freqtrade Wallets object (self.wallets)
            stake_currency: e.g. "USDC"
            open_trade_count: number of currently open trades
            max_stake: max allowed by freqtrade
            open_trades: list of open Trade objects (for PnL calc)
        """
        if self._mode == "fixed":
            return min(self._fixed_stake, max_stake)

        # Throttle recalculation
        now = time.monotonic()
        if (now - self._last_calc_time) < self._rebalance_secs and self._cached_stake > 0:
            return min(self._cached_stake, max_stake)

        # Query wallet balance
        try:
            total_balance = wallets.get_total(stake_currency)
            free_balance = wallets.get_free(stake_currency)
        except Exception as e:
            logger.warning("DynamicStake: wallet query failed (%s), using cached", e)
            return min(self._cached_stake, max_stake)

        # Calculate equity = free + unrealized PnL + locked stake
        unrealized_pnl = 0.0
        locked_stake = 0.0
        if open_trades:
            unrealized_pnl = self._get_unrealized_pnl(open_trades)
            locked_stake = self._get_locked_stake(open_trades)

        equity = free_balance + locked_stake + unrealized_pnl

        # How many slots remain
        remaining_slots = max(1, self._max_positions - open_trade_count)

        # Adaptive reserve
        reserve_pct = self._get_reserve_pct(equity, open_trade_count)

        # Deployable capital = free balance minus reserve on total equity
        reserve_amount = equity * reserve_pct
        deployable = max(0, free_balance - reserve_amount)

        # Divide among remaining slots
        stake = deployable / remaining_slots

        # Clamp
        stake = max(self._min_stake, min(stake, self._stake_cap, max_stake))

        # If stake is too small, don't trade
        if stake < self._min_stake:
            logger.info(
                "DynamicStake: stake %.2f < min %.2f, skipping",
                stake, self._min_stake,
            )
            stake = 0.0

        # Cache
        self._last_calc_time = now
        self._cached_stake = stake
        self._cached_balance = total_balance

        logger.info(
            "DynamicStake: equity=%.2f free=%.2f locked=%.2f pnl=%.2f "
            "reserve=%.0f%% deployable=%.2f slots=%d -> stake=%.2f",
            equity, free_balance, locked_stake, unrealized_pnl,
            reserve_pct * 100, deployable, remaining_slots, stake,
        )

        return stake

    @property
    def last_balance(self) -> float:
        return self._cached_balance

    @property
    def last_stake(self) -> float:
        return self._cached_stake
