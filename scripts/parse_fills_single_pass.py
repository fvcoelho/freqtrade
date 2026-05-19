#!/usr/bin/env python3
"""Parse HL fills into 5m candles — single pass, all pairs at once.

Reads each lz4 file once and extracts all target coins simultaneously.
Processes one day at a time to limit memory usage, writes candles incrementally.

Usage:
    python scripts/parse_fills_single_pass.py --pairs BNB AAVE --start 2025-11-01 --end 2026-05-18
"""
import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

import lz4.frame
import pandas as pd

TMP_DIR = Path("/tmp/hl_fills")
OUTPUT_DIR = Path("user_data/data/hyperliquid/futures")


def parse_day(day_dir: Path, target_coins: set) -> dict[str, list]:
    """Parse one day, return trades grouped by coin."""
    trades: dict[str, list] = {c: [] for c in target_coins}

    for lz4_file in sorted(day_dir.glob("*.lz4")):
        try:
            with lz4.frame.open(str(lz4_file), "rb") as f:
                data = f.read().decode("utf-8")

            for line in data.split("\n"):
                if not line:
                    continue
                # Quick string check before JSON parse
                has_coin = False
                for c in target_coins:
                    if c in line:
                        has_coin = True
                        break
                if not has_coin:
                    continue

                block = json.loads(line)
                for event in block.get("events", []):
                    if not isinstance(event, list) or len(event) < 2:
                        continue
                    fill = event[1]
                    coin = fill.get("coin", "")
                    if coin in target_coins:
                        trades[coin].append({
                            "time": int(fill["time"]),
                            "price": float(fill["px"]),
                            "size": float(fill["sz"]),
                        })
        except Exception as e:
            print(f"    Error {lz4_file.name}: {e}")

    return trades


def trades_to_candles(trades: list[dict]) -> pd.DataFrame:
    if not trades:
        return pd.DataFrame()
    df = pd.DataFrame(trades)
    df["date"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    df = df.sort_values("date")
    return df.resample("5min", on="date").agg(
        open=("price", "first"),
        high=("price", "max"),
        low=("price", "min"),
        close=("price", "last"),
        volume=("size", "sum"),
    ).dropna(subset=["open"]).reset_index()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", nargs="+", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    target_coins = set(args.pairs)

    start_dt = datetime.strptime(args.start, "%Y-%m-%d")
    end_dt = datetime.strptime(args.end, "%Y-%m-%d")

    # Collect all candles per coin
    all_candles: dict[str, list[pd.DataFrame]] = {c: [] for c in args.pairs}

    cur = start_dt
    day_num = 0
    total_days = (end_dt - start_dt).days + 1

    while cur <= end_dt:
        ds = cur.strftime("%Y%m%d")
        day_dir = TMP_DIR / ds
        day_num += 1

        if not day_dir.exists():
            cur += timedelta(days=1)
            continue

        print(f"  [{day_num}/{total_days}] {ds}", end="", flush=True)
        day_trades = parse_day(day_dir, target_coins)

        fills = sum(len(v) for v in day_trades.values())
        print(f" → {fills} fills", flush=True)

        for coin, trades in day_trades.items():
            if trades:
                candles = trades_to_candles(trades)
                if not candles.empty:
                    all_candles[coin].append(candles)

        cur += timedelta(days=1)

    # Save per coin
    print("\n=== Saving candles ===")
    for coin in args.pairs:
        parts = all_candles[coin]
        if not parts:
            print(f"  {coin}: no trades")
            continue

        candles = pd.concat(parts, ignore_index=True).drop_duplicates(
            subset=["date"]).sort_values("date").reset_index(drop=True)

        out_file = OUTPUT_DIR / f"{coin}_USDC_USDC-5m-futures.feather"
        if out_file.exists():
            existing = pd.read_feather(out_file)
            candles = pd.concat([existing, candles]).drop_duplicates(
                subset=["date"]).sort_values("date").reset_index(drop=True)

        candles.to_feather(out_file)
        print(f"  {coin}: {len(candles)} candles")

    print("Done!")


if __name__ == "__main__":
    main()
