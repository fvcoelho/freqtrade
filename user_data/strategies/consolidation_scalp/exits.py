"""Exit logic for Consolidation Scalp.

Priority order:
1. Breakout kill — ATR z-score or momentum spike
2. TP at opposite level — price reaches opposite S/R
3. Trailing stop — activates at threshold, trails behind
4. Time stop — max candles in trade
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def check_exit(
    pair: str,
    trade,
    current_time: datetime,
    current_rate: float,
    current_profit: float,
    cfg: dict,
    dp,
    timeframe: str,
    peak_profit: dict,
) -> Optional[str]:
    """Check exit conditions in priority order. Returns exit reason or None."""
    exit_cfg = cfg["exits"]
    trade_minutes = (current_time - trade.open_date_utc).total_seconds() / 60
    trade_candles = trade_minutes / 5  # 5m timeframe

    # Track peak profit for trailing
    trade_key = f"{pair}_{trade.open_date_utc}"
    if trade_key not in peak_profit:
        peak_profit[trade_key] = current_profit
    peak_profit[trade_key] = max(peak_profit[trade_key], current_profit)
    peak = peak_profit[trade_key]

    # --- 1. BREAKOUT KILL SWITCH ---
    if dp:
        dataframe, _ = dp.get_analyzed_dataframe(pair, timeframe)
        if dataframe is not None and not dataframe.empty:
            last = dataframe.iloc[-1]

            if last.get("is_breakout", False):
                peak_profit.pop(trade_key, None)
                return "breakout_stop"

    # --- 2. TP AT OPPOSITE LEVEL ---
    if dp:
        dataframe, _ = dp.get_analyzed_dataframe(pair, timeframe)
        if dataframe is not None and not dataframe.empty:
            last = dataframe.iloc[-1]
            is_long = trade.is_short is False

            if is_long:
                res = last.get("resistance", None)
                if res and not _isnan(res) and current_rate >= res:
                    peak_profit.pop(trade_key, None)
                    return "tp_level"
            else:
                sup = last.get("support", None)
                if sup and not _isnan(sup) and current_rate <= sup:
                    peak_profit.pop(trade_key, None)
                    return "tp_level"

    # --- 3. TRAILING STOP ---
    trail_activate = exit_cfg["trailing_activate"]
    trail_dist = exit_cfg["trailing_distance"]

    if peak >= trail_activate:
        if current_profit <= peak - trail_dist:
            peak_profit.pop(trade_key, None)
            return "trailing"

    # --- 4. TIME STOP ---
    if trade_candles >= exit_cfg["time_stop_candles"]:
        peak_profit.pop(trade_key, None)
        return "time_stop"

    return None


def _isnan(val) -> bool:
    """Check if value is NaN (works for float and numpy)."""
    try:
        return val != val  # NaN != NaN is True
    except (TypeError, ValueError):
        return False
