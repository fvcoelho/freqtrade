"""Hyperliquid trade report — fetches fills directly from HL via ccxt.

Source of truth: this script pulls from the Hyperliquid API (NOT the local
freqtrade SQLite DB), so partial fills, restarts, and DB drift don't affect
the numbers. PnL = HL's reported `closedPnl` per fill. Fees = `fee.cost` per fill.

SETUP
-----
1. Run from the freqtrade project root (`/root/freqtrade`).
2. Use the project's venv: `.venv/bin/python3` (already has `ccxt` installed).
3. Credentials file (JSON):
       user_data/secrets/hl_mainnet.json
   Must contain:
       { "exchange": { "wallet_address": "0x...", "private_key": "0x..." } }
   Use `--secrets <path>` to point at a different file (e.g. testnet).

USAGE
-----
    # Today (00:00 UTC up to now) — default
    .venv/bin/python3 scripts/hl_trade_report.py

    # Full UTC day before today
    .venv/bin/python3 scripts/hl_trade_report.py --yesterday

    # Rolling last N days (ends now)
    .venv/bin/python3 scripts/hl_trade_report.py --days 7

    # Explicit UTC range (until is exclusive; defaults to now)
    .venv/bin/python3 scripts/hl_trade_report.py --since 2026-05-01 --until 2026-05-18

    # Hide the per-close detail table (only totals + per-pair)
    .venv/bin/python3 scripts/hl_trade_report.py --no-detail

    # Dump raw rows for further analysis
    .venv/bin/python3 scripts/hl_trade_report.py --days 7 --json report.json
    .venv/bin/python3 scripts/hl_trade_report.py --days 7 --csv fills.csv

    # Different account (e.g. testnet)
    .venv/bin/python3 scripts/hl_trade_report.py --secrets user_data/secrets/hl_testnet.json

OUTPUT
------
1. Header — window, fill count (opens/closes), volume, gross PnL, fees,
   NET, fee/PnL ratio (<10% healthy, >25% means fees are eating the edge).
2. Per-pair table — opens, closes, volume, fees, PnL, NET; sorted by NET.
3. Close events table — every realized PnL event with timestamp, notional,
   fee, and PnL (skip with --no-detail).

NOTES
-----
- All times are UTC. The argparse date format is `YYYY-MM-DD`.
- HL's `fetch_my_trades` is paginated by timestamp; this script handles that.
- Opens have `closedPnl == 0` — only closes contribute to gross PnL.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from collections import defaultdict
from pathlib import Path

import ccxt


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Fetch HL trade fills and print a per-pair / per-close report.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    g = p.add_mutually_exclusive_group()
    g.add_argument("--today", action="store_true", help="From 00:00 UTC today (default).")
    g.add_argument("--yesterday", action="store_true", help="Full UTC day before today.")
    g.add_argument("--days", type=int, metavar="N",
                   help="Last N days (rolling, ends now).")
    g.add_argument("--since", metavar="YYYY-MM-DD",
                   help="Start date (UTC 00:00). Pairs with --until or defaults to now.")
    p.add_argument("--until", metavar="YYYY-MM-DD",
                   help="End date (UTC 00:00, exclusive). Defaults to now.")
    p.add_argument("--secrets", default="user_data/secrets/hl_mainnet.json",
                   help="Path to JSON with exchange.wallet_address / private_key.")
    p.add_argument("--limit", type=int, default=2000,
                   help="Max fills to fetch per request batch (paginated).")
    p.add_argument("--json", metavar="PATH",
                   help="Also dump full per-fill data as JSON to PATH.")
    p.add_argument("--csv", metavar="PATH",
                   help="Also dump per-fill rows as CSV to PATH.")
    p.add_argument("--no-detail", action="store_true",
                   help="Skip the per-close detail table (only show totals + per-pair).")
    return p.parse_args()


def resolve_window(args: argparse.Namespace) -> tuple[dt.datetime, dt.datetime]:
    now = dt.datetime.now(dt.timezone.utc)
    today_utc = dt.datetime(now.year, now.month, now.day, tzinfo=dt.timezone.utc)

    if args.yesterday:
        start = today_utc - dt.timedelta(days=1)
        end = today_utc
    elif args.days is not None:
        if args.days < 1:
            sys.exit("--days must be >= 1")
        start = now - dt.timedelta(days=args.days)
        end = now
    elif args.since:
        start = dt.datetime.fromisoformat(args.since).replace(tzinfo=dt.timezone.utc)
        end = (dt.datetime.fromisoformat(args.until).replace(tzinfo=dt.timezone.utc)
               if args.until else now)
    else:
        # default: today
        start = today_utc
        end = now

    if end <= start:
        sys.exit(f"End ({end.isoformat()}) must be after start ({start.isoformat()})")
    return start, end


def load_exchange(secrets_path: Path) -> ccxt.hyperliquid:
    if not secrets_path.exists():
        sys.exit(f"Secrets file not found: {secrets_path}")
    creds = json.loads(secrets_path.read_text()).get("exchange", {})
    addr = creds.get("wallet_address")
    pk = creds.get("private_key")
    if not addr or not pk:
        sys.exit(f"{secrets_path} must contain exchange.wallet_address and exchange.private_key")
    return ccxt.hyperliquid({"walletAddress": addr, "privateKey": pk})


def fetch_fills(ex: ccxt.hyperliquid, start: dt.datetime, end: dt.datetime,
                page_limit: int) -> list[dict]:
    """Paginate through fetch_my_trades until end is reached or HL stops returning rows."""
    out: list[dict] = []
    since_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    seen_ids: set[str] = set()
    cursor = since_ms

    while cursor < end_ms:
        batch = ex.fetch_my_trades(since=cursor, limit=page_limit)
        if not batch:
            break
        added = 0
        for f in batch:
            fid = str(f.get("id") or f.get("info", {}).get("tid") or f["timestamp"])
            if fid in seen_ids:
                continue
            if f["timestamp"] > end_ms:
                continue
            if f["timestamp"] < since_ms:
                continue
            seen_ids.add(fid)
            out.append(f)
            added += 1

        last_ts = max(b["timestamp"] for b in batch)
        if added == 0 or last_ts <= cursor:
            break
        cursor = last_ts + 1

    out.sort(key=lambda f: f["timestamp"])
    return out


def aggregate(fills: list[dict]) -> tuple[dict, list, list]:
    per_pair: dict = defaultdict(lambda: {
        "opens": 0, "closes": 0, "fees": 0.0, "pnl": 0.0, "volume": 0.0
    })
    opens: list = []
    closes: list = []

    for f in fills:
        sym = f["symbol"].replace("/USDC:USDC", "")
        info = f.get("info", {}) or {}
        direction = info.get("dir", "") or ""
        fee_cost = float((f.get("fee") or {}).get("cost", 0) or 0)
        closed_pnl = float(info.get("closedPnl", 0) or 0)
        notional = float(f.get("cost", 0) or 0)

        a = per_pair[sym]
        a["fees"] += fee_cost
        a["pnl"] += closed_pnl
        a["volume"] += notional

        row = {
            "datetime": f.get("datetime", ""),
            "symbol": sym,
            "dir": direction,
            "side": f.get("side"),
            "price": float(f.get("price", 0) or 0),
            "amount": float(f.get("amount", 0) or 0),
            "notional": notional,
            "fee": fee_cost,
            "pnl": closed_pnl,
        }
        if direction.startswith("Open"):
            a["opens"] += 1
            opens.append(row)
        elif direction.startswith("Close"):
            a["closes"] += 1
            closes.append(row)

    return per_pair, opens, closes


def print_report(start: dt.datetime, end: dt.datetime, fills: list[dict],
                 per_pair: dict, opens: list, closes: list, show_detail: bool) -> None:
    total_pnl = sum(a["pnl"] for a in per_pair.values())
    total_fees = sum(a["fees"] for a in per_pair.values())
    total_vol = sum(a["volume"] for a in per_pair.values())
    net = total_pnl - total_fees

    bar = "=" * 78
    print(bar)
    print(f"HL TRADE REPORT — {start.isoformat()} → {end.isoformat()}")
    print(bar)
    print(f"Total fills:   {len(fills)}  ({sum(a['opens'] for a in per_pair.values())} opens, "
          f"{sum(a['closes'] for a in per_pair.values())} closes)")
    print(f"Volume:        {total_vol:,.2f} USDC")
    print(f"Gross PnL:     {total_pnl:+.4f} USDC")
    print(f"Fees:          {total_fees:.4f} USDC")
    print(f"NET PnL:       {net:+.4f} USDC")
    if total_pnl > 0:
        print(f"Fee/PnL ratio: {total_fees / total_pnl * 100:.1f}%  (<10% = healthy)")

    print("\n" + "-" * 78)
    print(f"{'PAIR':<10}{'OPENS':>7}{'CLOSES':>8}{'VOLUME':>14}{'FEES':>10}{'PNL':>11}{'NET':>11}")
    print("-" * 78)
    for sym in sorted(per_pair.keys(), key=lambda k: -(per_pair[k]["pnl"] - per_pair[k]["fees"])):
        a = per_pair[sym]
        net_p = a["pnl"] - a["fees"]
        print(f"{sym:<10}{a['opens']:>7}{a['closes']:>8}"
              f"{a['volume']:>14,.2f}{a['fees']:>10.3f}"
              f"{a['pnl']:>+11.3f}{net_p:>+11.3f}")

    if not show_detail or not closes:
        return

    print("\n" + "-" * 78)
    print("CLOSE EVENTS (realized PnL):")
    print("-" * 78)
    print(f"{'TIME (UTC)':<21}{'PAIR':<10}{'DIR':<14}{'NOTIONAL':>12}{'FEE':>8}{'PNL':>10}")
    for r in closes:
        print(f"{r['datetime'][:19]:<21}{r['symbol']:<10}{r['dir']:<14}"
              f"{r['notional']:>12.2f}{r['fee']:>8.3f}{r['pnl']:>+10.3f}")


def write_json(path: Path, start, end, fills, per_pair, opens, closes) -> None:
    path.write_text(json.dumps({
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "summary": {
            "fills": len(fills),
            "opens": sum(a["opens"] for a in per_pair.values()),
            "closes": sum(a["closes"] for a in per_pair.values()),
            "volume": sum(a["volume"] for a in per_pair.values()),
            "gross_pnl": sum(a["pnl"] for a in per_pair.values()),
            "fees": sum(a["fees"] for a in per_pair.values()),
        },
        "per_pair": {k: dict(v) for k, v in per_pair.items()},
        "opens": opens,
        "closes": closes,
    }, indent=2, default=str))
    print(f"\nWrote JSON: {path}")


def write_csv(path: Path, opens: list, closes: list) -> None:
    rows = opens + closes
    rows.sort(key=lambda r: r["datetime"])
    if not rows:
        print(f"\nNo fills to write to CSV.")
        return
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote CSV:  {path}  ({len(rows)} rows)")


def main() -> None:
    args = parse_args()
    start, end = resolve_window(args)
    ex = load_exchange(Path(args.secrets))

    fills = fetch_fills(ex, start, end, args.limit)
    per_pair, opens, closes = aggregate(fills)
    print_report(start, end, fills, per_pair, opens, closes, show_detail=not args.no_detail)

    if args.json:
        write_json(Path(args.json), start, end, fills, per_pair, opens, closes)
    if args.csv:
        write_csv(Path(args.csv), opens, closes)


if __name__ == "__main__":
    main()
