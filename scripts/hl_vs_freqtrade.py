"""Compare Hyperliquid actual positions vs Freqtrade DB.

Reads wallet/key from config_v59_mainnet.json, queries HL for open positions,
queries v59_mainnet.sqlite for what the bot thinks, prints a side-by-side diff.

Run: .venv/bin/python scripts/hl_vs_freqtrade.py
"""
from __future__ import annotations

import json
import sqlite3
import sys
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


def fetch_hl_positions(wallet: str, secret: str) -> dict[str, dict]:
    ex = ccxt.hyperliquid({
        "walletAddress": wallet,
        "privateKey": secret,
        "options": {"defaultType": "swap"},
    })
    positions = ex.fetch_positions()
    out = {}
    for p in positions:
        if not p.get("contracts"):
            continue
        sym = p["symbol"]
        out[sym] = {
            "side": p.get("side"),
            "leverage": p.get("leverage"),
            "contracts": p.get("contracts"),
            "entry_price": p.get("entryPrice"),
            "mark_price": p.get("markPrice"),
            "liq_price": p.get("liquidationPrice"),
            "unrealized_pnl": p.get("unrealizedPnl"),
            "margin_mode": p.get("marginMode"),
            "initial_margin": p.get("initialMargin"),
        }
    return out


def fetch_db_trades() -> dict[str, dict]:
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(
        "SELECT pair, leverage, amount, open_rate, stake_amount, is_short, enter_tag, id "
        "FROM trades WHERE is_open=1"
    )
    out = {}
    for pair, lev, amount, open_rate, stake, is_short, tag, tid in c.fetchall():
        out[pair] = {
            "trade_id": tid,
            "side": "short" if is_short else "long",
            "leverage": lev,
            "amount": amount,
            "open_rate": open_rate,
            "stake": stake,
            "enter_tag": tag,
        }
    conn.close()
    return out


def main() -> int:
    wallet, secret = load_hl_creds()
    print(f"Wallet: {wallet}\n")

    hl = fetch_hl_positions(wallet, secret)
    db = fetch_db_trades()

    all_pairs = sorted(set(hl) | set(db))
    if not all_pairs:
        print("No open positions on either side.")
        return 0

    print(f"{'PAIR':<22} {'WHERE':<10} {'LEV':>5} {'AMT':>10} {'ENTRY':>10} {'MARK/RATE':>10} {'PNL':>10}")
    print("-" * 90)
    drift = 0
    for pair in all_pairs:
        h = hl.get(pair)
        d = db.get(pair)
        def fmt(x, w=10, prec=None):
            if x is None:
                return f"{'—':>{w}}"
            if prec is not None:
                return f"{float(x):>{w}.{prec}f}"
            return f"{x:>{w}}"

        if h and d:
            print(f"{pair:<22} {'HL':<10} {fmt(h['leverage'],5)} {fmt(h['contracts'])} {fmt(h['entry_price'])} {fmt(h['mark_price'])} {fmt(h['unrealized_pnl'],10,3)}")
            print(f"{pair:<22} {'DB#'+str(d['trade_id']):<10} {fmt(d['leverage'],5)} {fmt(d['amount'])} {fmt(d['open_rate'])} {'—':>10} {'—':>10}")
            diffs = []
            if abs(float(h["leverage"]) - float(d["leverage"])) > 0.01:
                diffs.append(f"leverage HL={h['leverage']} DB={d['leverage']}")
            if abs(float(h["contracts"]) - float(d["amount"])) > 1e-6:
                diffs.append(f"amount HL={h['contracts']} DB={d['amount']}")
            if abs(float(h["entry_price"]) - float(d["open_rate"])) / float(h["entry_price"]) > 0.001:
                diffs.append(f"entry HL={h['entry_price']} DB={d['open_rate']}")
            if diffs:
                drift += 1
                print(f"{'  ⚠ DRIFT:':<22} " + " | ".join(diffs))
        elif h:
            drift += 1
            print(f"{pair:<22} {'HL ONLY ⚠':<10} {fmt(h['leverage'],5)} {fmt(h['contracts'])} {fmt(h['entry_price'])} {fmt(h['mark_price'])} {fmt(h['unrealized_pnl'],10,3)}")
            print(f"  ↑ Position exists on HL but bot has no open trade for it")
        else:
            drift += 1
            print(f"{pair:<22} {'DB ONLY ⚠':<10} {fmt(d['leverage'],5)} {fmt(d['amount'])} {fmt(d['open_rate'])} {'—':>10} {'—':>10}")
            print(f"  ↑ Bot thinks open but no position on HL (likely pending limit order)")
        print()

    print("-" * 90)
    print(f"Total pairs: {len(all_pairs)}  Drift count: {drift}")
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
