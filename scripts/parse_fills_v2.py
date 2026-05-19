#!/usr/bin/env python3
"""Parse HL fills → 5m candles. Single pass, Python lz4, string pre-filter.

Usage:
    python scripts/parse_fills_v2.py --pairs BNB AAVE --start 2025-11-01 --end 2026-05-18
"""
import argparse
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

import lz4.frame
import pandas as pd

TMP_DIR = Path("/tmp/hl_fills")
OUTPUT_DIR = Path("user_data/data/hyperliquid/futures")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", nargs="+", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    target_coins = set(args.pairs)
    # Pre-compile regex for fast string matching
    coin_pattern = re.compile("|".join(args.pairs))

    start_dt = datetime.strptime(args.start, "%Y-%m-%d")
    end_dt = datetime.strptime(args.end, "%Y-%m-%d")
    total_days = (end_dt - start_dt).days + 1

    all_trades: dict[str, list] = {c: [] for c in args.pairs}
    cur = start_dt
    day_num = 0

    while cur <= end_dt:
        ds = cur.strftime("%Y%m%d")
        day_dir = TMP_DIR / ds
        day_num += 1
        cur += timedelta(days=1)

        if not day_dir.exists():
            continue

        day_fills = 0
        for lz4_file in sorted(day_dir.glob("*.lz4")):
            try:
                with lz4.frame.open(str(lz4_file), "rb") as f:
                    data = f.read().decode("utf-8")

                for line in data.split("\n"):
                    if not line or not coin_pattern.search(line):
                        continue
                    block = json.loads(line)
                    for event in block.get("events", []):
                        if not isinstance(event, list) or len(event) < 2:
                            continue
                        fill = event[1]
                        coin = fill.get("coin", "")
                        if coin in target_coins:
                            all_trades[coin].append((
                                int(fill["time"]),
                                float(fill["px"]),
                                float(fill["sz"]),
                            ))
                            day_fills += 1
            except Exception as e:
                print(f"    Err {lz4_file.name}: {e}")

        if day_num % 10 == 0 or day_num == total_days:
            total_fills = sum(len(v) for v in all_trades.values())
            print(f"  [{day_num}/{total_days}] {ds} → day:{day_fills} total:{total_fills}", flush=True)

    # Build candles
    print("\n=== Building candles ===")
    for coin in args.pairs:
        trades = all_trades[coin]
        if not trades:
            print(f"  {coin}: no trades")
            continue

        df = pd.DataFrame(trades, columns=["time", "price", "size"])
        df["date"] = pd.to_datetime(df["time"], unit="ms", utc=True)
        df = df.sort_values("date")

        candles = df.resample("5min", on="date").agg(
            open=("price", "first"),
            high=("price", "max"),
            low=("price", "min"),
            close=("price", "last"),
            volume=("size", "sum"),
        ).dropna(subset=["open"]).reset_index()

        out_file = OUTPUT_DIR / f"{coin}_USDC_USDC-5m-futures.feather"
        if out_file.exists():
            existing = pd.read_feather(out_file)
            candles = pd.concat([existing, candles]).drop_duplicates(
                subset=["date"]).sort_values("date").reset_index(drop=True)

        candles.to_feather(out_file)
        print(f"  {coin}: {len(candles)} candles ({df['date'].min().date()} → {df['date'].max().date()})")

    print("\nDone!")


if __name__ == "__main__":
    main()
