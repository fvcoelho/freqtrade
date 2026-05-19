#!/usr/bin/env python3
"""Download 5m/1h/1d data from Binance futures and save as Hyperliquid USDC format.

For pairs that don't have historical data on HL (listed recently as USDC pairs),
we use Binance USDT futures data which has identical price action.

Usage:
    python scripts/download_binance_to_hl.py --pairs BNB AAVE ENA --start 2025-10-01 --end 2026-05-18
"""
import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd

BINANCE_DIR = Path("user_data/data/binance_tmp")
HL_DIR = Path("user_data/data/hyperliquid/futures")
FREQTRADE = ".venv/bin/freqtrade"


def download_and_convert(pairs: list[str], timeframes: list[str], start: str, end: str):
    BINANCE_DIR.mkdir(parents=True, exist_ok=True)
    HL_DIR.mkdir(parents=True, exist_ok=True)

    timerange = f"{start.replace('-', '')}-{end.replace('-', '')}"

    # Build pair list for Binance (USDT futures)
    binance_pairs = [f"{p}/USDT:USDT" for p in pairs]

    print(f"Downloading from Binance: {pairs}, timeframes={timeframes}, {start} → {end}")
    cmd = [
        FREQTRADE, "download-data",
        "--exchange", "binance",
        "--trading-mode", "futures",
        "--pairs", *binance_pairs,
        "--timeframes", *timeframes,
        "--timerange", timerange,
        "--datadir", str(BINANCE_DIR),
        "--data-format-ohlcv", "feather",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if result.returncode != 0:
        print(f"Download failed: {result.stderr[-500:]}")
        return

    # Convert each pair: rename USDT→USDC, merge with existing HL data
    for pair in pairs:
        for tf in timeframes:
            binance_file = BINANCE_DIR / f"{pair}_USDT_USDT-{tf}-futures.feather"
            hl_file = HL_DIR / f"{pair}_USDC_USDC-{tf}-futures.feather"

            if not binance_file.exists():
                print(f"  {pair} {tf}: no Binance data")
                continue

            df = pd.read_feather(binance_file)
            # Drop mark/funding columns if present, keep only OHLCV
            cols = ["date", "open", "high", "low", "close", "volume"]
            df = df[[c for c in cols if c in df.columns]]

            if hl_file.exists():
                existing = pd.read_feather(hl_file)
                # Binance fills gaps where HL has no data
                df = pd.concat([existing, df]).drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)

            df.to_feather(hl_file)
            print(f"  {pair} {tf}: {len(df)} candles → {hl_file.name}")

    # Cleanup
    import shutil
    shutil.rmtree(BINANCE_DIR, ignore_errors=True)
    print("Done!")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", nargs="+", required=True)
    parser.add_argument("--timeframes", nargs="+", default=["5m", "1h", "1d"])
    parser.add_argument("--start", default="2025-10-01")
    parser.add_argument("--end", default="2026-05-18")
    args = parser.parse_args()
    download_and_convert(args.pairs, args.timeframes, args.start, args.end)


if __name__ == "__main__":
    main()
