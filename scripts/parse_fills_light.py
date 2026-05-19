#!/usr/bin/env python3
"""Parse downloaded HL fills into 5m candles — one pair at a time (low memory).

Expects fills already downloaded in /tmp/hl_fills/{YYYYMMDD}/{hour}.lz4

Usage:
    python scripts/parse_fills_light.py --pairs BNB AAVE --start 2025-11-01 --end 2026-05-18
"""
import argparse
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import lz4.frame
import pandas as pd

TMP_DIR = Path("/tmp/hl_fills")
OUTPUT_DIR = Path("user_data/data/hyperliquid/futures")


def parse_coin(coin: str, date_strs: list[str]) -> pd.DataFrame:
    """Parse all fills for ONE coin across all dates."""
    trades = []
    for ds in date_strs:
        day_dir = TMP_DIR / ds
        if not day_dir.exists():
            continue
        for lz4_file in sorted(day_dir.glob("*.lz4")):
            try:
                with lz4.frame.open(str(lz4_file), "rb") as f:
                    data = f.read().decode("utf-8")
                for line in data.split("\n"):
                    if not line or coin not in line:
                        continue
                    block = json.loads(line)
                    for event in block.get("events", []):
                        if not isinstance(event, list) or len(event) < 2:
                            continue
                        fill = event[1]
                        if fill.get("coin") == coin:
                            trades.append({
                                "time": int(fill["time"]),
                                "price": float(fill["px"]),
                                "size": float(fill["sz"]),
                            })
            except Exception as e:
                print(f"    Error {lz4_file.name}: {e}")

    if not trades:
        return pd.DataFrame()

    df = pd.DataFrame(trades)
    df["date"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    df = df.sort_values("date")

    candles = df.resample("5min", on="date").agg(
        open=("price", "first"),
        high=("price", "max"),
        low=("price", "min"),
        close=("price", "last"),
        volume=("size", "sum"),
    ).dropna(subset=["open"]).reset_index()

    return candles


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", nargs="+", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    start_dt = datetime.strptime(args.start, "%Y-%m-%d")
    end_dt = datetime.strptime(args.end, "%Y-%m-%d")
    date_strs = []
    cur = start_dt
    while cur <= end_dt:
        date_strs.append(cur.strftime("%Y%m%d"))
        cur += timedelta(days=1)

    print(f"Parsing {len(date_strs)} days for {len(args.pairs)} pairs")

    for coin in args.pairs:
        print(f"  {coin}...", end="", flush=True)
        candles = parse_coin(coin, date_strs)

        if candles.empty:
            print(" no trades")
            continue

        out_file = OUTPUT_DIR / f"{coin}_USDC_USDC-5m-futures.feather"
        if out_file.exists():
            existing = pd.read_feather(out_file)
            candles = pd.concat([existing, candles]).drop_duplicates(
                subset=["date"]).sort_values("date").reset_index(drop=True)

        candles.to_feather(out_file)
        print(f" {len(candles)} candles")

    print("Done!")


if __name__ == "__main__":
    main()
