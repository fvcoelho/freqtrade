"""
Persistent state for BetaV59 strategy — trade log and equity curve.

Written to JSON file after each trade close.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

STATE_DIR = Path(__file__).parent.parent.parent / "backtest_results" / "state"


class StrategyState:
    """Persistent strategy state — one JSON file per run."""

    def __init__(self, run_id: str = "default"):
        self.run_id = run_id
        self._path = STATE_DIR / f"{run_id}.json"
        STATE_DIR.mkdir(parents=True, exist_ok=True)

        self.per_pair: dict[str, dict] = {}
        self.trades: list[dict] = []
        self.equity_curve: list[dict] = []
        self.balance: float = 100.0
        self.initial_balance: float = 100.0
        self.cycle_count: int = 0

        if self._path.exists():
            self._load()

    def _load(self):
        try:
            with open(self._path) as f:
                data = json.load(f)
            self.per_pair = data.get("per_pair", {})
            self.trades = data.get("trades", [])
            self.equity_curve = data.get("equity_curve", [])
            self.balance = data.get("balance", 100.0)
            self.initial_balance = data.get("initial_balance", 100.0)
            self.cycle_count = data.get("cycle_count", 0)
        except Exception as e:
            logger.warning("BetaV59 STATE: failed to load %s: %s", self._path, e)

    def save(self):
        """Write state to disk."""
        self.cycle_count += 1
        data = {
            "run_id": self.run_id,
            "per_pair": self.per_pair,
            "trades": self.trades,
            "equity_curve": self.equity_curve,
            "balance": round(self.balance, 4),
            "initial_balance": self.initial_balance,
            "cycle_count": self.cycle_count,
            "summary": self._compute_summary(),
        }
        try:
            with open(self._path, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.warning("BetaV59 STATE: failed to save: %s", e)

    def reset(self, initial_balance: float = 100.0):
        """Reset state for a fresh run."""
        self.per_pair = {}
        self.trades = []
        self.equity_curve = []
        self.balance = initial_balance
        self.initial_balance = initial_balance
        self.cycle_count = 0
        if self._path.exists():
            self._path.unlink()

    def record_trade(self, pair: str, profit_ratio: float, profit_abs: float,
                     leverage: float, entry_tag: str, exit_reason: str,
                     open_date, close_date, open_rate: float, close_rate: float,
                     is_short: bool, indicators: Optional[dict] = None):
        """Record a completed trade."""

        if pair not in self.per_pair:
            self.per_pair[pair] = {"total_trades": 0, "total_wins": 0, "total_pnl": 0.0}

        p = self.per_pair[pair]
        p["total_trades"] += 1
        if profit_ratio > 0:
            p["total_wins"] += 1
        p["total_pnl"] = round(p["total_pnl"] + profit_abs, 4)

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
        if indicators:
            trade_record["indicators"] = indicators
        self.trades.append(trade_record)

        self.equity_curve.append({
            "date": str(close_date),
            "balance": round(self.balance, 4),
            "trade_id": trade_record["id"],
            "profit_abs": round(profit_abs, 4),
        })

    def _compute_summary(self) -> dict:
        if not self.trades:
            return {}
        wins = [t for t in self.trades if t["profit_ratio"] > 0]
        losses = [t for t in self.trades if t["profit_ratio"] <= 0]
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
            "losses": len(losses),
            "win_pct": round(len(wins) / len(self.trades) * 100, 1) if self.trades else 0,
            "total_profit_abs": round(total_profit, 2),
            "profit_pct": round(total_profit / self.initial_balance * 100, 2),
            "max_drawdown_pct": round(max_dd * 100, 2),
            "final_balance": round(self.balance, 2),
            "per_pair": {pair: {
                "trades": data["total_trades"],
                "wins": data["total_wins"],
                "pnl": round(data["total_pnl"], 2),
            } for pair, data in self.per_pair.items()},
        }
