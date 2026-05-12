"""
Persistent state for V54 strategy — survives backtest cycles.

Stores per-pair warmup streaks, trade history, equity curve, and all
indicators snapshot per trade. Written to JSON file each cycle.

Usage:
    state = StrategyState("v54_backtest_20260401")
    state.record_trade(pair, profit, leverage, indicators...)
    streak = state.get_warmup_streak(pair)
    state.save()
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
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

        # Core state
        self.warmup: dict[str, dict] = {}       # pair → {streak, last_close, last_profit}
        self.trades: list[dict] = []             # All trades with full context
        self.equity_curve: list[dict] = []       # {date, balance, trade_id}
        self.balance: float = 100.0
        self.initial_balance: float = 100.0
        self.cycle_count: int = 0
        self.metadata: dict = {}

        # Load existing state if resuming
        if self._path.exists():
            self._load()

    def _load(self):
        try:
            with open(self._path) as f:
                data = json.load(f)
            self.warmup = data.get("warmup", {})
            self.trades = data.get("trades", [])
            self.equity_curve = data.get("equity_curve", [])
            self.balance = data.get("balance", 100.0)
            self.initial_balance = data.get("initial_balance", 100.0)
            self.cycle_count = data.get("cycle_count", 0)
            self.metadata = data.get("metadata", {})
        except Exception as e:
            logger.warning(f"V54 STATE: failed to load {self._path}: {e}")

    def save(self):
        """Write state to disk."""
        self.cycle_count += 1
        data = {
            "run_id": self.run_id,
            "warmup": self.warmup,
            "trades": self.trades,
            "equity_curve": self.equity_curve,
            "balance": round(self.balance, 4),
            "initial_balance": self.initial_balance,
            "cycle_count": self.cycle_count,
            "metadata": self.metadata,
            "summary": self._compute_summary(),
        }
        try:
            with open(self._path, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.warning(f"V54 STATE: failed to save: {e}")

    def reset(self, initial_balance: float = 100.0):
        """Reset state for a fresh run."""
        self.warmup = {}
        self.trades = []
        self.equity_curve = []
        self.balance = initial_balance
        self.initial_balance = initial_balance
        self.cycle_count = 0
        self.metadata = {}
        # Delete old file
        if self._path.exists():
            self._path.unlink()

    # ── Warmup ──

    def get_warmup_streak(self, pair: str) -> int:
        """Get current win streak for a pair."""
        return self.warmup.get(pair, {}).get("streak", 0)

    def get_warmup_gap_hours(self, pair: str, current_time: datetime) -> float:
        """Get hours since last trade close on this pair."""
        last_close = self.warmup.get(pair, {}).get("last_close")
        if not last_close:
            return 999.0
        try:
            if isinstance(last_close, str):
                last_close = datetime.fromisoformat(last_close.replace("+00:00", "").replace("Z", ""))
            ct = current_time
            if hasattr(ct, 'replace'):
                ct = ct.replace(tzinfo=None)
            if hasattr(last_close, 'replace'):
                last_close = last_close.replace(tzinfo=None)
            return (ct - last_close).total_seconds() / 3600
        except:
            return 999.0

    def compute_warmup_leverage(self, pair: str, current_time: datetime,
                                 vol_leverage: float, cfg_warmup: dict) -> float:
        """Compute leverage with warmup modifier.

        Args:
            pair: Trading pair
            current_time: Current candle time
            vol_leverage: Base leverage from volume calculation
            cfg_warmup: Warmup config section

        Returns:
            Modified leverage value
        """
        streak = self.get_warmup_streak(pair)
        gap = self.get_warmup_gap_hours(pair, current_time)

        gap_reset = cfg_warmup.get("gap_reset_hours", 12)
        levels = cfg_warmup.get("streak_levels", [2.0, 2.5, 3.0, 3.5, 4.0])
        streak_cap = cfg_warmup.get("streak_cap", 4)
        decay_per_excess = cfg_warmup.get("decay_per_excess", 0.5)
        lev_min = cfg_warmup.get("lev_min", 2.0)

        # Reset streak if gap is too long
        if gap > gap_reset:
            streak = 0

        # Warmup cap based on streak
        if streak < len(levels):
            warmup_cap = levels[streak]
        else:
            # Overconfidence decay
            warmup_cap = levels[min(streak_cap, len(levels) - 1)]
            excess = streak - streak_cap
            warmup_cap = max(lev_min, warmup_cap - excess * decay_per_excess)

        return min(vol_leverage, warmup_cap)

    # ── Trade Recording ──

    def record_trade(self, pair: str, profit_ratio: float, profit_abs: float,
                     leverage: float, entry_tag: str, exit_reason: str,
                     open_date, close_date, open_rate: float, close_rate: float,
                     is_short: bool, indicators: Optional[dict] = None):
        """Record a completed trade and update warmup state."""

        # Update warmup
        if pair not in self.warmup:
            self.warmup[pair] = {"streak": 0, "last_close": None, "total_trades": 0,
                                  "total_wins": 0, "total_pnl": 0.0}

        w = self.warmup[pair]
        if profit_ratio > 0:
            w["streak"] = w.get("streak", 0) + 1
            w["total_wins"] = w.get("total_wins", 0) + 1
        else:
            w["streak"] = 0
        w["last_close"] = str(close_date)
        w["last_profit"] = round(profit_ratio * 100, 2)
        w["total_trades"] = w.get("total_trades", 0) + 1
        w["total_pnl"] = round(w.get("total_pnl", 0) + profit_abs, 4)

        # Update balance
        self.balance += profit_abs

        # Record trade
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
            "warmup_streak": w["streak"],
        }
        if indicators:
            trade_record["indicators"] = indicators
        self.trades.append(trade_record)

        # Update equity curve
        self.equity_curve.append({
            "date": str(close_date),
            "balance": round(self.balance, 4),
            "trade_id": trade_record["id"],
            "profit_abs": round(profit_abs, 4),
        })

    # ── Summary ──

    def _compute_summary(self) -> dict:
        if not self.trades:
            return {}
        wins = [t for t in self.trades if t["profit_ratio"] > 0]
        losses = [t for t in self.trades if t["profit_ratio"] <= 0]
        total_profit = sum(t["profit_abs"] for t in self.trades)

        # Max drawdown
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
                "streak": data["streak"],
            } for pair, data in self.warmup.items()},
        }
