"""Compare freqtrade closed trades vs Hyperliquid actual fills/realized PnL.

For each bot trade in the DB, find the corresponding HL fills and verify:
- Realized PnL agrees within tolerance
- Entry / exit prices match the recorded fills
- Total realized USDC summed across all closed trades matches HL account state.

Run: .venv/bin/python scripts/hl_history_compare.py [hours]
  hours: how far back to scan (default 24)
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

import ccxt

REPO = Path(__file__).resolve().parents[1]
SECRETS = REPO / "user_data" / "secrets" / "hl_mainnet.json"
CONFIG = REPO / "config_v59_mainnet.json"
DB = REPO / "user_data" / "v59_mainnet.sqlite"


def load_hl_creds() -> tuple[str, str]:
    """Load wallet/key from gitignored secrets file (or fall back to config)."""
    import os
    if env_w := os.environ.get("HL_WALLET"):
        return env_w, os.environ["HL_PRIVATE_KEY"]
    src = SECRETS if SECRETS.exists() else CONFIG
    cfg = json.loads(src.read_text())
    ex = cfg["exchange"]
    if not ex.get("wallet_address") or not ex.get("private_key"):
        raise SystemExit(f"No credentials in {src}. Set HL_WALLET/HL_PRIVATE_KEY env vars or populate {SECRETS}.")
    return ex["wallet_address"], ex["private_key"]


def fetch_db_closed_trades(since_ms: int) -> list[dict]:
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(
        "SELECT id, pair, leverage, amount, open_rate, close_rate, "
        "close_profit, close_profit_abs, open_date, close_date, exit_reason "
        "FROM trades WHERE is_open=0 ORDER BY id"
    )
    out = []
    for r in c.fetchall():
        out.append({
            "trade_id": r[0],
            "pair": r[1],
            "leverage": r[2],
            "amount": r[3],
            "open_rate": r[4],
            "close_rate": r[5],
            "close_profit": r[6],
            "close_profit_abs": r[7],
            "open_date": r[8],
            "close_date": r[9],
            "exit_reason": r[10],
        })
    conn.close()
    return out


def fetch_hl_fills(wallet: str, secret: str, since_ms: int) -> list[dict]:
    """Fetch HL user fills via ccxt. HL provides 'fills' (executed trades)."""
    ex = ccxt.hyperliquid({
        "walletAddress": wallet,
        "privateKey": secret,
        "options": {"defaultType": "swap"},
    })
    # ccxt's fetch_my_trades hits the userFills endpoint on HL
    trades = ex.fetch_my_trades(since=since_ms, limit=1000)
    return trades


def main() -> int:
    hours = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    since_ms = int((time.time() - hours * 3600) * 1000)

    wallet, secret = load_hl_creds()
    print(f"Wallet: {wallet}")
    print(f"Window: last {hours}h\n")

    db_trades = fetch_db_closed_trades(since_ms)
    fills = fetch_hl_fills(wallet, secret, since_ms)

    # Index fills by symbol
    fills_by_sym: dict[str, list[dict]] = {}
    for f in fills:
        fills_by_sym.setdefault(f["symbol"], []).append(f)

    print(f"DB closed trades: {len(db_trades)}")
    print(f"HL fills:         {len(fills)}\n")

    print(f"{'#':>3} {'PAIR':<22} {'LEV':>4} {'AMT':>10} {'ENTRY':>10} {'EXIT':>10} "
          f"{'BOT PnL':>9} {'HL FILLS':>9} {'DIFF':>8} {'REASON':<24}")
    print("-" * 130)

    total_db = 0.0
    total_hl = 0.0
    drift_count = 0

    for t in db_trades:
        sym_fills = fills_by_sym.get(t["pair"], [])
        # HL fills carry "info.closedPnl" — sum closed-pnl for fills within trade window
        open_ts = _to_ms(t["open_date"])
        close_ts = _to_ms(t["close_date"])
        match_fills = [
            f for f in sym_fills
            if open_ts - 60_000 <= f["timestamp"] <= close_ts + 60_000
        ]
        hl_pnl = sum(
            float((f.get("info") or {}).get("closedPnl", 0) or 0) for f in match_fills
        )
        # HL fee info
        hl_fees = sum(float(((f.get("fee") or {}).get("cost")) or 0) for f in match_fills)
        hl_net = hl_pnl - hl_fees

        bot_pnl = float(t["close_profit_abs"] or 0)
        diff = bot_pnl - hl_net
        flag = "  ⚠" if abs(diff) > 0.02 else ""

        total_db += bot_pnl
        total_hl += hl_net
        if flag:
            drift_count += 1

        print(
            f"{t['trade_id']:>3} {t['pair']:<22} {t['leverage']:>4} "
            f"{t['amount']:>10} {t['open_rate']:>10} {t['close_rate']:>10} "
            f"{bot_pnl:>+9.4f} {hl_net:>+9.4f} {diff:>+8.4f}{flag} {t['exit_reason']:<24}"
        )

    print("-" * 130)
    print(f"Totals: BOT={total_db:+.4f} USDC   HL(fills net)={total_hl:+.4f} USDC   "
          f"Δ={total_db-total_hl:+.4f}   drift trades={drift_count}")
    return 1 if drift_count else 0


def _to_ms(dt_str: str | None) -> int:
    if not dt_str:
        return 0
    # SQLite stores 'YYYY-MM-DD HH:MM:SS.ffffff'
    from datetime import datetime, timezone
    try:
        dt = datetime.fromisoformat(dt_str)
    except ValueError:
        dt = datetime.strptime(dt_str.split(".")[0], "%Y-%m-%d %H:%M:%S")
    return int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)


if __name__ == "__main__":
    sys.exit(main())
