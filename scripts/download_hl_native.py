#!/usr/bin/env python3
"""Download OHLCV data directly from Hyperliquid's public API.

Usage:
    python scripts/download_hl_native.py --pairs BNB AAVE ENA --timeframes 15m 1h 1d \
        --start 2025-01-01 --end 2026-05-18
"""
import argparse
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

API_URL = "https://api.hyperliquid.xyz/info"
OUTPUT_DIR = Path("user_data/data/hyperliquid/futures")
CHUNK_MS = {
    "5m": 86400000 * 7,    # 7 days per chunk
    "15m": 86400000 * 14,  # 14 days per chunk
    "1h": 86400000 * 30,   # 30 days per chunk
    "1d": 86400000 * 365,  # 1 year per chunk
}


def ts(datestr: str) -> int:
    return int(datetime.strptime(datestr, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)


def download_pair(coin: str, interval: str, start_ms: int, end_ms: int) -> pd.DataFrame:
    chunk = CHUNK_MS.get(interval, 86400000 * 14)
    all_candles = []
    cursor = start_ms

    while cursor < end_ms:
        chunk_end = min(cursor + chunk, end_ms)
        payload = {
            "type": "candleSnapshot",
            "req": {
                "coin": coin,
                "interval": interval,
                "startTime": cursor,
                "endTime": chunk_end,
            },
        }
        for attempt in range(3):
            try:
                r = requests.post(API_URL, json=payload, timeout=30)
                r.raise_for_status()
                data = r.json()
                break
            except Exception as e:
                print(f"    Attempt {attempt+1} failed: {e}")
                time.sleep(2)
                data = []

        if isinstance(data, list):
            for c in data:
                all_candles.append({
                    "date": pd.to_datetime(int(c["t"]), unit="ms", utc=True),
                    "open": float(c["o"]),
                    "high": float(c["h"]),
                    "low": float(c["l"]),
                    "close": float(c["c"]),
                    "volume": float(c["v"]),
                })

        cursor = chunk_end
        time.sleep(0.3)

    if not all_candles:
        return pd.DataFrame()

    df = pd.DataFrame(all_candles)
    df = df.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
    return df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", nargs="+", required=True)
    parser.add_argument("--timeframes", nargs="+", default=["15m", "1h", "1d"])
    parser.add_argument("--start", default="2025-01-01")
    parser.add_argument("--end", default="2026-05-18")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    start_ms = ts(args.start)
    end_ms = ts(args.end)

    for coin in args.pairs:
        for tf in args.timeframes:
            fname = f"{coin}_USDC_USDC-{tf}-futures.feather"
            out_path = OUTPUT_DIR / fname
            print(f"Downloading {coin} {tf}...", end=" ", flush=True)

            df = download_pair(coin, tf, start_ms, end_ms)

            if df.empty:
                print("no data")
                continue

            if out_path.exists():
                existing = pd.read_feather(out_path)
                df = pd.concat([existing, df]).drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)

            df.to_feather(out_path)
            print(f"{len(df)} candles saved")
            time.sleep(0.5)

    print("Done!")


if __name__ == "__main__":
    main()
