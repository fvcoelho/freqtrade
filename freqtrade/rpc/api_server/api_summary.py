"""
Public (no-auth) summary endpoint for Hermes integration.
Returns a plain-text overview of bot status, open trades, and recent history.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from freqtrade.rpc.api_server.deps import get_rpc, get_rpc_optional

router_summary = APIRouter()


@router_summary.get("/summary", response_class=PlainTextResponse, tags=["Summary"])
def bot_summary(rpc=Depends(get_rpc_optional)):
    if rpc is None:
        return "Bot is not running."

    lines = []
    now = datetime.now(timezone.utc)

    # ── Config ──
    try:
        cfg = rpc._rpc_show_config()
        strategy = cfg.get("strategy", "?")
        state = cfg.get("state", "?")
        timeframe = cfg.get("timeframe", "?")
        lines.append(f"Strategy: {strategy} | TF: {timeframe} | State: {state}")
    except Exception:
        lines.append("Strategy: unknown")

    lines.append("")

    # ── Balance ──
    try:
        bal = rpc._rpc_balance(
            cfg.get("stake_currency", "USDC"),
            cfg.get("fiat_display_currency", ""),
        )
        total = bal.get("total", 0)
        starting = bal.get("starting_capital", total)
        pnl = total - starting
        pnl_pct = (pnl / starting * 100) if starting else 0
        lines.append(f"Balance: ${total:.2f} (start ${starting:.2f}, P&L {pnl_pct:+.1f}%)")
    except Exception:
        lines.append("Balance: unavailable")

    lines.append("")

    # ── Open Trades ──
    try:
        trades = rpc._rpc_trade_status()
        if not trades:
            lines.append("Open Trades: none")
        else:
            lines.append(f"Open Trades: {len(trades)}")
            for t in trades:
                pair = t.get("pair", "?").split("/")[0]
                side = "SHORT" if t.get("is_short") else "LONG"
                pnl = (t.get("profit_ratio", 0)) * 100
                tag = t.get("enter_tag", "")
                lev = t.get("leverage", 1)
                open_date = t.get("open_date", "")
                dur = ""
                if open_date:
                    try:
                        od = datetime.fromisoformat(open_date.replace("Z", "+00:00"))
                        if od.tzinfo is None:
                            od = od.replace(tzinfo=timezone.utc)
                        mins = int((now - od).total_seconds() / 60)
                        dur = f"{mins // 60}h{mins % 60}m" if mins >= 60 else f"{mins}m"
                    except Exception:
                        dur = ""
                lines.append(
                    f"  {pair} {side} {lev}x | {pnl:+.2f}% | {dur} | {tag}"
                )
    except Exception:
        lines.append("Open Trades: error reading")

    lines.append("")

    # ── Recent Closed Trades (last 10) ──
    try:
        result = rpc._rpc_trade_history(limit=10)
        closed = result.get("trades", [])
        if not closed:
            lines.append("Recent Trades: none")
        else:
            wins = sum(1 for t in closed if (t.get("profit_ratio", 0)) >= 0)
            losses = len(closed) - wins
            lines.append(f"Recent Trades: {len(closed)} (W:{wins} L:{losses})")
            for t in closed:
                pair = t.get("pair", "?").split("/")[0]
                side = "SHORT" if t.get("is_short") else "LONG"
                pnl = (t.get("profit_ratio", 0)) * 100
                pnl_abs = t.get("profit_abs", 0)
                reason = t.get("exit_reason", "")
                close_date = t.get("close_date", "")
                date_str = ""
                if close_date:
                    try:
                        cd = datetime.fromisoformat(close_date.replace("Z", "+00:00"))
                        date_str = cd.strftime("%m/%d %H:%M")
                    except Exception:
                        date_str = close_date[:16]
                lines.append(
                    f"  {pair} {side} {pnl:+.2f}% (${pnl_abs:+.2f}) | {reason} | {date_str}"
                )
    except Exception:
        lines.append("Recent Trades: error reading")

    lines.append("")

    # ── Profit Summary ──
    try:
        profit = rpc._rpc_trade_statistics(
            cfg.get("stake_currency", "USDC"),
            cfg.get("fiat_display_currency", ""),
        )
        total_trades = profit.get("trade_count", 0)
        win_trades = profit.get("winning_trades", 0)
        loss_trades = profit.get("losing_trades", 0)
        win_pct = (win_trades / total_trades * 100) if total_trades else 0
        total_profit = profit.get("profit_all_coin", 0)
        total_profit_pct = profit.get("profit_all_percent", 0)
        lines.append(f"All Time: {total_trades} trades | Win: {win_pct:.0f}% ({win_trades}W/{loss_trades}L)")
        lines.append(f"Total P&L: ${total_profit:.2f} ({total_profit_pct:+.1f}%)")
    except Exception:
        lines.append("Profit: unavailable")

    # ── What to expect ──
    lines.append("")
    try:
        trades_open = rpc._rpc_trade_status()
        if trades_open:
            lines.append("Watching: exit conditions on open positions")
        else:
            lines.append("Watching: waiting for entry signals (spread_z crossing ±2.1)")
    except Exception:
        pass

    return "\n".join(lines)
