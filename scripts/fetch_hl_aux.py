"""Fetch missing 1h candles + funding-rate for HL pairs needed by backtest."""
import time
from pathlib import Path

import ccxt
import pandas as pd

OUT = Path("user_data/data/hyperliquid/futures")

PAIRS = ["LINK/USDC:USDC", "SUI/USDC:USDC", "AVAX/USDC:USDC", "BNB/USDC:USDC", "ADA/USDC:USDC", "XRP/USDC:USDC", "ETH/USDC:USDC", "SOL/USDC:USDC", "BTC/USDC:USDC"]


def fname_ohlcv(sym, tf, kind="futures"):
    return f"{sym.replace('/', '_').replace(':', '_')}-{tf}-{kind}.feather"


def paginate_ohlcv(ex, sym, tf, since_ms, until_ms):
    rows = []
    cursor = since_ms
    while cursor < until_ms:
        try:
            b = ex.fetch_ohlcv(sym, tf, since=cursor, limit=500)
        except ccxt.RateLimitExceeded:
            time.sleep(2.0); continue
        if not b: break
        rows.extend(b)
        last = b[-1][0]
        if last <= cursor: break
        cursor = last + 1
        time.sleep(0.2)
    return rows


def to_df(rows):
    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
    df["date"] = pd.to_datetime(df["date"], unit="ms", utc=True)
    df = df.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
    return df


def paginate_funding(ex, sym, since_ms, until_ms):
    rows = []
    cursor = since_ms
    while cursor < until_ms:
        try:
            batch = ex.fetch_funding_rate_history(sym, since=cursor, limit=500)
        except ccxt.RateLimitExceeded:
            time.sleep(2.0); continue
        except Exception as e:
            print(f"  funding {sym} err: {e}")
            return None
        if not batch: break
        rows.extend(batch)
        last_ts = batch[-1]["timestamp"]
        if last_ts <= cursor: break
        cursor = last_ts + 1
        time.sleep(0.2)
    return rows


def funding_to_df(rows, full_range_start_ms, full_range_end_ms):
    """Convert ccxt funding records to OHLCV-shaped df (rate stored in 'open'),
    aligned to hourly grid."""
    if not rows:
        return None
    df = pd.DataFrame([{"date": r["timestamp"], "open": float(r["fundingRate"])} for r in rows])
    df["date"] = pd.to_datetime(df["date"], unit="ms", utc=True)
    df = df.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
    # Reindex to hourly grid
    full_idx = pd.date_range(
        start=pd.to_datetime(full_range_start_ms, unit="ms", utc=True).floor("1h"),
        end=pd.to_datetime(full_range_end_ms, unit="ms", utc=True).floor("1h"),
        freq="1h",
    )
    df = df.set_index("date").reindex(full_idx).fillna(0.0).reset_index()
    df.columns = ["date", "open"]
    df["high"] = 0.0; df["low"] = 0.0; df["close"] = 0.0; df["volume"] = 0.0
    return df


def main():
    ex = ccxt.hyperliquid({"options": {"defaultType": "swap"}, "enableRateLimit": True})
    ex.load_markets()
    now_ms = int(time.time() * 1000)
    since_ms = now_ms - 60 * 24 * 3600 * 1000  # 60 days

    for sym in PAIRS:
        # 1h candles
        path_1h = OUT / fname_ohlcv(sym, "1h", "futures")
        if not path_1h.exists() or pd.read_feather(path_1h)["date"].iloc[-1] < pd.Timestamp.utcnow() - pd.Timedelta(hours=2):
            print(f"fetching {sym} 1h ...", flush=True)
            rows = paginate_ohlcv(ex, sym, "1h", since_ms, now_ms)
            if rows:
                df = to_df(rows)
                if path_1h.exists():
                    old = pd.read_feather(path_1h)
                    df = pd.concat([old[old["date"] < df["date"].min()], df], ignore_index=True)
                    df = df.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
                df.to_feather(path_1h)
                print(f"  wrote {len(df)} rows  range={df['date'].iloc[0]} -> {df['date'].iloc[-1]}")

        # funding_rate
        path_fr = OUT / fname_ohlcv(sym, "1h", "funding_rate")
        if not path_fr.exists() or pd.read_feather(path_fr)["date"].iloc[-1] < pd.Timestamp.utcnow() - pd.Timedelta(hours=2):
            print(f"fetching {sym} funding ...", flush=True)
            rows = paginate_funding(ex, sym, since_ms, now_ms)
            if rows is None:
                print(f"  skip — funding API failed")
                continue
            df = funding_to_df(rows, since_ms, now_ms)
            if df is not None and not df.empty:
                df.to_feather(path_fr)
                print(f"  wrote {len(df)} rows  range={df['date'].iloc[0]} -> {df['date'].iloc[-1]}")
            else:
                # Write zeros if no funding data at all
                full_idx = pd.date_range(
                    start=pd.to_datetime(since_ms, unit="ms", utc=True).floor("1h"),
                    end=pd.to_datetime(now_ms, unit="ms", utc=True).floor("1h"),
                    freq="1h",
                )
                df = pd.DataFrame({"date": full_idx, "open": 0.0, "high": 0.0, "low": 0.0, "close": 0.0, "volume": 0.0})
                df.to_feather(path_fr)
                print(f"  wrote {len(df)} rows of zeros (no funding data)")


if __name__ == "__main__":
    main()
