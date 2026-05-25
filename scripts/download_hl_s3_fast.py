#!/usr/bin/env python3
"""Fast bulk download of HL fills from S3 → 5m candles.

Strategy: download all lz4 files first via aws s3 cp, then batch-process locally.
Much faster than one-by-one download+parse.

Usage:
    python scripts/download_hl_s3_fast.py --pairs BNB AAVE --start 2025-11-01 --end 2026-05-18
"""
import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

import lz4.frame
import pandas as pd

BUCKET = "hl-mainnet-node-data"
PREFIX = "node_fills_by_block/hourly"
TMP_DIR = Path("/tmp/hl_fills")
OUTPUT_DIR = Path("user_data/data/hyperliquid/futures")


def download_all_days(start: str, end: str):
    """Use aws s3 cp with --recursive to bulk download."""
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    current = start_dt

    # Download day by day using aws s3 cp --recursive (parallel internally)
    while current <= end_dt:
        date_str = current.strftime("%Y%m%d")
        day_dir = TMP_DIR / date_str
        s3_prefix = f"s3://{BUCKET}/{PREFIX}/{date_str}/"

        if day_dir.exists() and len(list(day_dir.glob("*.lz4"))) >= 23:
            print(f"  {date_str}: already downloaded, skipping")
            current += timedelta(days=1)
            continue

        day_dir.mkdir(parents=True, exist_ok=True)
        print(f"  Downloading {date_str}...", end="", flush=True)

        for attempt in range(3):
            try:
                result = subprocess.run(
                    ["aws", "s3", "sync", s3_prefix, str(day_dir) + "/",
                     "--request-payer", "requester", "--quiet", "--only-show-errors"],
                    capture_output=True, text=True, timeout=600,
                )
                break
            except subprocess.TimeoutExpired:
                print(f" timeout(attempt {attempt+1})", end="", flush=True)

        n_files = len(list(day_dir.glob("*.lz4")))
        print(f" {n_files} files")

        current += timedelta(days=1)


def parse_day(date_str: str, target_coins: set) -> list[dict]:
    """Parse all hour files for one day."""
    day_dir = TMP_DIR / date_str
    trades = []

    for lz4_file in sorted(day_dir.glob("*.lz4")):
        try:
            with lz4.frame.open(str(lz4_file), "rb") as f:
                data = f.read().decode("utf-8")

            for line in data.split("\n"):
                if not line:
                    continue
                block = json.loads(line)
                for event in block.get("events", []):
                    if not isinstance(event, list) or len(event) < 2:
                        continue
                    fill = event[1]
                    coin = fill.get("coin", "")
                    if coin in target_coins:
                        trades.append({
                            "coin": coin,
                            "time": int(fill["time"]),
                            "price": float(fill["px"]),
                            "size": float(fill["sz"]),
                        })
        except Exception as e:
            print(f"    Error parsing {lz4_file}: {e}")

    return trades


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", nargs="+", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--interval", type=int, default=5)
    parser.add_argument("--skip-download", action="store_true",
                        help="Skip S3 download, only process existing files")
    args = parser.parse_args()

    target_coins = set(args.pairs)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    start_dt = datetime.strptime(args.start, "%Y-%m-%d")
    end_dt = datetime.strptime(args.end, "%Y-%m-%d")

    # Phase 1: Bulk download
    if not args.skip_download:
        print("=== Phase 1: Downloading from S3 ===")
        download_all_days(args.start, args.end)

    # Phase 2: Parse in parallel
    print("\n=== Phase 2: Parsing fills ===")
    date_strs = []
    current = start_dt
    while current <= end_dt:
        date_strs.append(current.strftime("%Y%m%d"))
        current += timedelta(days=1)

    all_trades: dict[str, list] = {coin: [] for coin in args.pairs}

    with ProcessPoolExecutor(max_workers=os.cpu_count()) as pool:
        futures = {
            pool.submit(parse_day, ds, target_coins): ds
            for ds in date_strs
        }
        done = 0
        total = len(date_strs)
        for fut in as_completed(futures):
            ds = futures[fut]
            done += 1
            try:
                trades = fut.result()
                for t in trades:
                    all_trades[t["coin"]].append(t)
                if done % 10 == 0 or done == total:
                    print(f"  Parsed {done}/{total} days ({sum(len(v) for v in all_trades.values())} total fills)")
            except Exception as e:
                print(f"  Error on {ds}: {e}")

    # Phase 3: Build candles
    print("\n=== Phase 3: Building candles ===")
    for coin in args.pairs:
        trades = all_trades[coin]
        if not trades:
            print(f"  {coin}: no trades found")
            continue

        df = pd.DataFrame(trades)
        df["date"] = pd.to_datetime(df["time"], unit="ms", utc=True)
        df = df.sort_values("date")

        freq = f"{args.interval}min"
        candles = df.resample(freq, on="date").agg(
            open=("price", "first"),
            high=("price", "max"),
            low=("price", "min"),
            close=("price", "last"),
            volume=("size", "sum"),
        ).dropna(subset=["open"]).reset_index()

        # Merge with existing
        out_file = OUTPUT_DIR / f"{coin}_USDC_USDC-{args.interval}m-futures.feather"
        if out_file.exists():
            existing = pd.read_feather(out_file)
            candles = pd.concat([existing, candles]).drop_duplicates(
                subset=["date"]).sort_values("date").reset_index(drop=True)

        candles.to_feather(out_file)
        print(f"  {coin}: {len(candles)} candles → {out_file.name}")

    print("\nDone!")


if __name__ == "__main__":
    main()
