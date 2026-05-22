"""
Twin state tracking for TwinPennies strategy.

Tracks twin pairs (long+short entered together), determines winner/loser,
and records trade results for equity curve.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

STATE_DIR = Path(__file__).parent.parent.parent / "backtest_results" / "state"


class TwinState:
    """Tracks twin pairs and trade results."""

    def __init__(self, run_id: str = "default"):
        self.run_id = run_id
        self._path = STATE_DIR / f"{run_id}.json"
        STATE_DIR.mkdir(parents=True, exist_ok=True)

        self.trades: list[dict] = []
        self.balance: float = 100.0
        self.initial_balance: float = 100.0

        # Twin tracking: twin_id -> twin info
        # twin_id is the candle date string when the pair entered
        self.twins: dict[str, dict] = {}
        # trade_id -> twin_id mapping
        self.trade_twin_map: dict[int, str] = {}

    def register_twin_trade(self, trade_id: int, twin_id: str, pair: str, side: str):
        """Register a trade as part of a twin pair."""
        if twin_id not in self.twins:
            self.twins[twin_id] = {
                "long_pair": None,
                "short_pair": None,
                "long_trade_id": None,
                "short_trade_id": None,
                "evaluated": False,
                "winner_side": None,
                "winner_scaled": False,
            }

        twin = self.twins[twin_id]
        if side == "long":
            twin["long_pair"] = pair
            twin["long_trade_id"] = trade_id
        else:
            twin["short_pair"] = pair
            twin["short_trade_id"] = trade_id

        self.trade_twin_map[trade_id] = twin_id

    def is_twin_complete(self, twin_id: str) -> bool:
        """Check if both sides of a twin are registered."""
        twin = self.twins.get(twin_id)
        if not twin:
            return False
        return twin["long_pair"] is not None and twin["short_pair"] is not None

    def get_twin_info(self, trade_id: int) -> dict | None:
        """Get twin info for a trade."""
        twin_id = self.trade_twin_map.get(trade_id)
        if not twin_id:
            return None
        return self.twins.get(twin_id)

    def get_twin_id(self, trade_id: int) -> str | None:
        return self.trade_twin_map.get(trade_id)

    def mark_evaluated(self, twin_id: str, winner_side: str):
        """Mark a twin as evaluated (winner determined)."""
        twin = self.twins.get(twin_id)
        if twin:
            twin["evaluated"] = True
            twin["winner_side"] = winner_side

    def mark_scaled(self, twin_id: str):
        twin = self.twins.get(twin_id)
        if twin:
            twin["winner_scaled"] = True

    def is_winner(self, trade_id: int) -> bool | None:
        """Check if this trade is the winner of its twin. None if not yet evaluated."""
        twin = self.get_twin_info(trade_id)
        if not twin or not twin["evaluated"]:
            return None
        winner_side = twin["winner_side"]
        if winner_side == "long":
            return twin["long_trade_id"] == trade_id
        else:
            return twin["short_trade_id"] == trade_id

    def active_twin_count(self) -> int:
        """Count active (not fully closed) twin pairs."""
        return sum(1 for t in self.twins.values()
                   if t["long_pair"] is not None or t["short_pair"] is not None)

    def pending_twin_ids(self) -> list[str]:
        """Twin IDs that have one side but not both."""
        return [tid for tid, t in self.twins.items()
                if (t["long_pair"] is None) != (t["short_pair"] is None)]

    def record_trade(self, pair: str, profit_ratio: float, profit_abs: float,
                     leverage: float, entry_tag: str, exit_reason: str,
                     open_date, close_date, open_rate: float, close_rate: float,
                     is_short: bool):
        self.balance += profit_abs

        trade_record = {
            "id": len(self.trades) + 1,
            "pair": pair,
            "is_short": is_short,
            "entry_tag": entry_tag,
            "exit_reason": exit_reason,
            "open_date": str(open_date),
            "close_date": str(close_date),
            "open_rate": round(open_rate, 6),
            "close_rate": round(close_rate, 6),
            "profit_ratio": round(profit_ratio, 6),
            "profit_abs": round(profit_abs, 4),
            "leverage": leverage,
            "balance_after": round(self.balance, 4),
        }
        self.trades.append(trade_record)

    def save(self):
        data = {
            "run_id": self.run_id,
            "trades": self.trades,
            "balance": round(self.balance, 4),
            "initial_balance": self.initial_balance,
            "summary": self._compute_summary(),
        }
        try:
            with open(self._path, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.warning("TwinPennies STATE: failed to save: %s", e)

    def _compute_summary(self) -> dict:
        if not self.trades:
            return {}
        wins = [t for t in self.trades if t["profit_ratio"] > 0]
        total_profit = sum(t["profit_abs"] for t in self.trades)

        peak = self.initial_balance
        max_dd = 0
        balance = self.initial_balance
        for t in self.trades:
            balance += t["profit_abs"]
            peak = max(peak, balance)
            dd = (peak - balance) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)

        return {
            "total_trades": len(self.trades),
            "wins": len(wins),
            "win_pct": round(len(wins) / len(self.trades) * 100, 1),
            "total_profit_abs": round(total_profit, 2),
            "profit_pct": round(total_profit / self.initial_balance * 100, 2),
            "max_drawdown_pct": round(max_dd * 100, 2),
            "final_balance": round(self.balance, 2),
        }
