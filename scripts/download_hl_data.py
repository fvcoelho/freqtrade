#!/usr/bin/env python3
"""
Download dense OHLCV data from 0xArchive for Hyperliquid pairs.

Usage:
    python scripts/download_hl_data.py --pairs XRP ADA SOL LINK ETH BTC \
        --timeframes 5m 15m 1h --start 2026-01-01 --end 2026-05-08
"""

import argparse
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from oxarchive import Client

API_KEY = "0xa_489a0d0e82df687a79e3ceb5108518887a31f80a1a320b3dd5051d8ca5b09931"
OUTPUT_DIR = Path("user_data/data/hyperliquid/futures")


def download_pair(client: Client, coin: str, interval: str,
                  start: str, end: str) -> pd.DataFrame:
    """Download all candles for a coin/interval, handling pagination."""
    all_candles = []
    cursor = None
    page = 0

    while True:
        kwargs = {"interval": interval, "start": start, "end": end}
        if cursor:
            kwargs["cursor"] = cursor

        try:
            resp = client.hyperliquid.candles.history(coin, **kwargs)
        except Exception as e:
            print(f"    Error fetching {coin}: {e}, retrying in 5s...")
            time.sleep(5)
            try:
                resp = client.hyperliquid.candles.history(coin, **kwargs)
            except Exception as e2:
                print(f"    Retry failed: {e2}, stopping pagination for {coin}")
                break

        for c in resp.data:
            all_candles.append({
                "date": pd.to_datetime(c.timestamp, utc=True),
                "open": float(c.open),
                "high": float(c.high),
                "low": float(c.low),
                "close": float(c.close),
                "volume": float(c.volume),
            })

        page += 1
        if not resp.data:
            break

        cursor = getattr(resp, "next_cursor", None)
        if not cursor:
            break

        print(f"    page {page}: {len(all_candles)} candles so far...")
        time.sleep(0.3)

    if not all_candles:
        return pd.DataFrame()

    df = pd.DataFrame(all_candles)
    df = df.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
    return df


def main():
    parser = argparse.ArgumentParser(description="Download Hyperliquid OHLCV from 0xArchive")
    parser.add_argument("--pairs", nargs="+", default=["XRP", "ADA", "SOL", "LINK", "ETH", "BTC"])
    parser.add_argument("--timeframes", nargs="+", default=["5m", "15m", "1h"])
    parser.add_argument("--start", default="2026-01-01")
    parser.add_argument("--end", default="2026-05-08")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    client = Client(api_key=API_KEY)

    for coin in args.pairs:
        for tf in args.timeframes:
            fname = f"{coin}_USDC_USDC-{tf}-futures.feather"
            out_path = OUTPUT_DIR / fname
            print(f"Downloading {coin} {tf}...")

            df = download_pair(client, coin, tf, args.start, args.end)

            if df.empty:
                print(f"  No data for {coin} {tf}")
                continue

            # Merge with existing data if present
            if out_path.exists():
                existing = pd.read_feather(out_path)
                df = pd.concat([existing, df]).drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)

            df.to_feather(out_path)
            print(f"  Saved {len(df)} candles to {out_path}")
            time.sleep(0.5)

    print("Done!")


if __name__ == "__main__":
    main()
