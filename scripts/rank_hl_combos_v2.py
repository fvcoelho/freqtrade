"""Rank HL pair combos for ZScorePairs strategy — properly.

For pairs trading on a spread you need:
1. High intra-group correlation (each group moves cohesively)
2. High inter-group correlation (>0.4 to pass V23 regime filter)
3. Strong mean reversion of the spread (low AR(1) coefficient on the spread)
4. Sufficient spread volatility (otherwise no signals fire)
"""
import json
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("user_data/data/hyperliquid/futures")

CANDIDATES = [
    "BTC/USDC:USDC", "ETH/USDC:USDC", "HYPE/USDC:USDC", "SOL/USDC:USDC",
    "DOGE/USDC:USDC", "XRP/USDC:USDC", "TAO/USDC:USDC", "ZEC/USDC:USDC",
    "PENDLE/USDC:USDC", "APE/USDC:USDC", "AVAX/USDC:USDC", "LINK/USDC:USDC",
    "BNB/USDC:USDC", "SUI/USDC:USDC", "ARB/USDC:USDC", "ADA/USDC:USDC",
    "NEAR/USDC:USDC", "AAVE/USDC:USDC",
]


def fname(symbol):
    return f"{symbol.replace('/', '_').replace(':', '_')}-5m-futures.feather"


def load_closes():
    closes = {}
    for sym in CANDIDATES:
        p = OUT / fname(sym)
        if not p.exists():
            continue
        df = pd.read_feather(p)
        closes[sym] = df.set_index("date")["close"]
    return pd.DataFrame(closes).dropna()


def ar1_coef(series):
    """AR(1) coefficient — closer to 0 = faster mean reversion. Coefficient near 1 = random walk."""
    s = series.dropna()
    if len(s) < 50:
        return np.nan
    s_lag = s.shift(1).dropna()
    s_curr = s.loc[s_lag.index]
    if s_lag.std() == 0:
        return np.nan
    cov = np.cov(s_curr, s_lag)[0, 1]
    return cov / s_lag.var()


def main():
    px = load_closes()
    print(f"Loaded {len(px)} bars × {len(px.columns)} pairs", flush=True)
    print(f"Range: {px.index.min()} → {px.index.max()}", flush=True)

    # log returns
    ret = np.log(px / px.shift(1)).dropna()
    corr = ret.corr()
    syms = list(px.columns)

    # cumulative returns over rolling 8-bar window (matches strategy's cum_return_window=8)
    cum8 = ret.rolling(8).sum()

    print(f"\nScoring 2v2 combos (filter: intra>=0.7 AND inter>=0.5)...", flush=True)
    rows = []
    for a in combinations(range(len(syms)), 2):
        for b in combinations(range(len(syms)), 2):
            if set(a) & set(b):
                continue
            if a > b:
                continue
            ga = [syms[i] for i in a]
            gb = [syms[i] for i in b]

            intra_a = corr.loc[ga[0], ga[1]]
            intra_b = corr.loc[gb[0], gb[1]]
            avg_intra = (intra_a + intra_b) / 2

            inter = corr.loc[ga, gb].values.mean()

            if avg_intra < 0.7 or inter < 0.5:
                continue

            # Spread: avg cum-return of group A minus avg cum-return of group B
            spread = cum8[ga].mean(axis=1) - cum8[gb].mean(axis=1)
            spread = spread.dropna()
            if len(spread) < 500:
                continue

            # Z-score normalize over rolling 96 (matches zscore_window)
            z = (spread - spread.rolling(96).mean()) / spread.rolling(96).std()
            z = z.dropna()
            if len(z) < 500:
                continue

            ar1 = ar1_coef(z)             # closer to 0 = mean reverts fast
            spread_vol = z.std()
            n_signals = ((z > 2.5) | (z < -2.5)).sum()  # how often it crosses ±2.5

            rows.append({
                "groupA": "+".join(s.split("/")[0] for s in ga),
                "groupB": "+".join(s.split("/")[0] for s in gb),
                "intra": round(avg_intra, 3),
                "inter": round(inter, 3),
                "spread_ar1": round(ar1, 3),
                "spread_vol": round(spread_vol, 3),
                "n_signals_2.5": int(n_signals),
                "ga_full": ga,
                "gb_full": gb,
            })

    df = pd.DataFrame(rows)
    if df.empty:
        print("No combos passed filter")
        return

    # Composite rank: high intra + high inter + low ar1 + enough signals
    df["score"] = (df["intra"] * 0.4 + df["inter"] * 0.4
                   - df["spread_ar1"].abs() * 0.5
                   + np.minimum(df["n_signals_2.5"] / 100, 1.0) * 0.2)
    df = df.sort_values("score", ascending=False).reset_index(drop=True)

    print(f"\n{len(df)} combos passed filter. Top 20:")
    cols = ["groupA", "groupB", "intra", "inter", "spread_ar1", "spread_vol", "n_signals_2.5", "score"]
    print(df[cols].head(20).to_string(index=True))

    # Save top 8 for backtest
    out_combos = {
        "active_combo": "research_top1",
        "auto_cluster": False,
        "combos": {},
    }
    for i, row in df.head(8).iterrows():
        name = f"research_top{i+1}"
        out_combos["combos"][name] = {
            "description": f"intra={row['intra']:.2f} inter={row['inter']:.2f} ar1={row['spread_ar1']:.2f} signals={row['n_signals_2.5']}",
            "group_a": row["ga_full"],
            "group_b": row["gb_full"],
        }
    Path("scripts/hl_top_combos.json").write_text(json.dumps(out_combos, indent=2))
    print(f"\nSaved top 8 combos to scripts/hl_top_combos.json")


if __name__ == "__main__":
    main()
