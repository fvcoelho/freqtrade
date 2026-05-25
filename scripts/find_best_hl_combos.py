"""Find best HL pair combos for ZScorePairs strategy.

Steps:
1. Download 5m for candidate set (last ~17d available)
2. Compute log-return correlation matrix
3. Hierarchical clustering -> propose 2-cluster splits
4. Output top combo candidates ranked by intra-cluster cohesion + inter-cluster decorrelation
"""
import time
import json
from pathlib import Path
from itertools import combinations

import ccxt
import numpy as np
import pandas as pd

OUT = Path("user_data/data/hyperliquid/futures")
OUT.mkdir(parents=True, exist_ok=True)

# Top liquid crypto pairs on HL (excludes XYZ-* synthetic perps)
CANDIDATES = [
    "BTC/USDC:USDC", "ETH/USDC:USDC", "HYPE/USDC:USDC", "SOL/USDC:USDC",
    "DOGE/USDC:USDC", "XRP/USDC:USDC", "TAO/USDC:USDC", "ZEC/USDC:USDC",
    "PENDLE/USDC:USDC", "APE/USDC:USDC", "AVAX/USDC:USDC", "LINK/USDC:USDC",
    "BNB/USDC:USDC", "SUI/USDC:USDC", "ARB/USDC:USDC", "ADA/USDC:USDC",
    "NEAR/USDC:USDC", "AAVE/USDC:USDC",
]


def fname(symbol, timeframe="5m"):
    base = symbol.replace("/", "_").replace(":", "_")
    return f"{base}-{timeframe}-futures.feather"


def fetch_paginated(ex, sym, tf, since_ms, until_ms, limit=500, sleep=0.2):
    out = []
    cursor = since_ms
    while cursor < until_ms:
        try:
            batch = ex.fetch_ohlcv(sym, tf, since=cursor, limit=limit)
        except ccxt.RateLimitExceeded:
            time.sleep(2.0)
            continue
        if not batch:
            break
        out.extend(batch)
        last = batch[-1][0]
        if last <= cursor:
            break
        cursor = last + 1
        time.sleep(sleep)
    return out


def download_or_load(ex, sym, days=30):
    path = OUT / fname(sym)
    if path.exists():
        df = pd.read_feather(path)
        last = pd.to_datetime(df["date"].iloc[-1])
        if (pd.Timestamp.utcnow() - last).total_seconds() < 30 * 60:
            return df  # fresh enough
    now_ms = int(time.time() * 1000)
    since_ms = now_ms - days * 24 * 3600 * 1000
    rows = fetch_paginated(ex, sym, "5m", since_ms, now_ms)
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
    df["date"] = pd.to_datetime(df["date"], unit="ms", utc=True)
    df = df.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
    if path.exists():
        old = pd.read_feather(path)
        cutoff = df["date"].min()
        kept = old[old["date"] < cutoff]
        df = pd.concat([kept, df], ignore_index=True)
        df = df.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
    df.to_feather(path)
    return df


def main():
    ex = ccxt.hyperliquid({"options": {"defaultType": "swap"}, "enableRateLimit": True})
    ex.load_markets()

    print(f"Downloading 5m for {len(CANDIDATES)} pairs...", flush=True)
    closes = {}
    for sym in CANDIDATES:
        df = download_or_load(ex, sym, days=30)
        if df is None or len(df) < 1000:
            print(f"  {sym}: insufficient ({0 if df is None else len(df)} bars), skipping")
            continue
        closes[sym] = df.set_index("date")["close"]
        print(f"  {sym}: {len(df)} bars, {df['date'].iloc[0].date()} → {df['date'].iloc[-1].date()}", flush=True)

    print(f"\nAligning on common timestamps...")
    px = pd.DataFrame(closes).dropna()
    print(f"Aligned: {len(px)} bars across {len(px.columns)} pairs")
    print(f"Range: {px.index.min()} → {px.index.max()}")

    # log returns
    ret = np.log(px / px.shift(1)).dropna()

    # correlation matrix
    corr = ret.corr()
    print("\nCorrelation matrix (log 5m returns):")
    short_names = [c.split("/")[0] for c in corr.columns]
    corr_short = corr.copy()
    corr_short.index = short_names
    corr_short.columns = short_names
    print(corr_short.round(2).to_string())

    # Score every 2v2 combination
    syms = list(px.columns)
    n = len(syms)
    print(f"\nScoring {n} pairs as 2v2 combos (intra ↑, inter ↓):")
    scores = []
    for a in combinations(range(n), 2):
        for b in combinations(range(n), 2):
            if set(a) & set(b):
                continue
            if a[0] > b[0]:
                continue  # avoid (A,B)/(C,D) duplicates of (C,D)/(A,B)
            ga = [syms[i] for i in a]
            gb = [syms[i] for i in b]
            intra_a = corr.loc[ga, ga].values
            intra_b = corr.loc[gb, gb].values
            inter = corr.loc[ga, gb].values
            avg_intra = (intra_a[np.triu_indices(2, k=1)].mean()
                         + intra_b[np.triu_indices(2, k=1)].mean()) / 2
            avg_inter = inter.mean()
            score = avg_intra - avg_inter  # higher = tighter clusters, less inter-cluster
            scores.append((score, ga, gb, avg_intra, avg_inter))
    scores.sort(reverse=True)

    print(f"\nTop 15 combos by (intra_corr - inter_corr):")
    print(f"{'rank':>4s} {'score':>6s} {'intra':>6s} {'inter':>6s}  groupA  vs  groupB")
    for i, (s, ga, gb, ai, ainter) in enumerate(scores[:15], 1):
        ga_short = "+".join(p.split("/")[0] for p in ga)
        gb_short = "+".join(p.split("/")[0] for p in gb)
        print(f"  {i:2d}  {s:>+6.3f} {ai:>+6.3f} {ainter:>+6.3f}  {ga_short:18s} vs {gb_short}")

    # Save top 10 to combos json for backtest pipeline
    out_combos = {
        "active_combo": "research_top1",
        "auto_cluster": False,
        "combos": {},
    }
    for i, (s, ga, gb, ai, ainter) in enumerate(scores[:10], 1):
        out_combos["combos"][f"research_top{i}"] = {
            "description": f"intra={ai:.2f} inter={ainter:.2f} score={s:.2f}",
            "group_a": ga,
            "group_b": gb,
        }
    with open("scripts/hl_combo_candidates.json", "w") as f:
        json.dump(out_combos, f, indent=2)
    print(f"\nWrote top 10 to scripts/hl_combo_candidates.json")


if __name__ == "__main__":
    main()
