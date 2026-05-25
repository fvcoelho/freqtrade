"""Fetch HL mainnet OHLCV history via ccxt and write to freqtrade feather format."""
import sys
import time
from pathlib import Path

import ccxt
import pandas as pd

OUT = Path("user_data/data/hyperliquid/futures")
OUT.mkdir(parents=True, exist_ok=True)


def fetch_range(ex, symbol, timeframe, since_ms, until_ms, page_limit=500):
    out = []
    cursor = since_ms
    while cursor < until_ms:
        batch = ex.fetch_ohlcv(symbol, timeframe, since=cursor, limit=page_limit)
        if not batch:
            break
        out.extend(batch)
        last = batch[-1][0]
        if last <= cursor:
            break
        cursor = last + 1
        time.sleep(0.15)  # rate limit
    return out


def to_df(rows):
    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
    df["date"] = pd.to_datetime(df["date"], unit="ms", utc=True)
    df = df.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
    return df


def merge_existing(path, df):
    if path.exists():
        old = pd.read_feather(path)
        # Keep only old rows older than the new range start, then concat
        cutoff = df["date"].min()
        kept = old[old["date"] < cutoff]
        df = pd.concat([kept, df], ignore_index=True)
        df = df.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
    return df


def fname(symbol, timeframe):
    base = symbol.replace("/", "_").replace(":", "_")
    return f"{base}-{timeframe}-futures.feather"


def main():
    pairs_5m = ["DOGE/USDC:USDC", "ADA/USDC:USDC", "ETH/USDC:USDC", "SOL/USDC:USDC"]
    pair_1h = "BTC/USDC:USDC"

    # Last ~50 days for 5m (covers 1mo backtest + warmup), 90 days for BTC 1h
    now_ms = int(time.time() * 1000)
    since_5m = now_ms - 50 * 24 * 3600 * 1000
    since_1h = now_ms - 90 * 24 * 3600 * 1000

    ex = ccxt.hyperliquid({"options": {"defaultType": "swap"}, "enableRateLimit": True})
    ex.load_markets()

    for sym in pairs_5m:
        print(f"fetching {sym} 5m ...", flush=True)
        rows = fetch_range(ex, sym, "5m", since_5m, now_ms)
        df = to_df(rows)
        out_path = OUT / fname(sym, "5m")
        merged = merge_existing(out_path, df)
        merged.to_feather(out_path)
        print(f"  wrote {len(merged)} rows  range={merged['date'].iloc[0]} -> {merged['date'].iloc[-1]}", flush=True)

    print(f"fetching {pair_1h} 1h ...", flush=True)
    rows = fetch_range(ex, pair_1h, "1h", since_1h, now_ms, page_limit=500)
    df = to_df(rows)
    out_path = OUT / fname(pair_1h, "1h")
    merged = merge_existing(out_path, df)
    merged.to_feather(out_path)
    print(f"  wrote {len(merged)} rows  range={merged['date'].iloc[0]} -> {merged['date'].iloc[-1]}", flush=True)


if __name__ == "__main__":
    main()
