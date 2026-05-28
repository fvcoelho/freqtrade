"""VWAP Scalp — Vectorized fast version with fees."""
import numpy as np
import pandas as pd
from pathlib import Path

DATA_DIR = Path("user_data/data/hyperliquid/futures")
PAIRS = ["ETH", "SOL", "XRP", "LINK", "SUI", "DOGE", "ONDO", "TON"]
START, END = "2026-01-01", "2026-05-19"
FEE_RT = 0.0009  # 0.09% round trip


def load(coin):
    f = DATA_DIR / f"{coin}_USDC_USDC-5m-futures.feather"
    if not f.exists(): return pd.DataFrame()
    df = pd.read_feather(f)
    return df[(df["date"] >= START) & (df["date"] <= END)].sort_values("date").reset_index(drop=True)


def compute_vwap(df):
    tp = (df["high"] + df["low"] + df["close"]) / 3
    df["day"] = df["date"].dt.date
    df["cum_tpv"] = (tp * df["volume"]).groupby(df["day"]).cumsum()
    df["cum_v"] = df["volume"].groupby(df["day"]).cumsum()
    df["vwap"] = df["cum_tpv"] / df["cum_v"].replace(0, np.nan)
    df["vwap_pct"] = (df["close"] - df["vwap"]) / df["vwap"] * 100
    return df


def test_combo(dev, hold):
    """Test one dev/hold combo across all pairs. Vectorized."""
    total_profit = 0
    total_trades = 0
    total_wins = 0

    for coin in PAIRS:
        df = load(coin)
        if df.empty or len(df) < 100:
            continue
        df = compute_vwap(df)

        vd = df["vwap_pct"].values
        close = df["close"].values
        n = len(df)

        for i in range(48, n - hold):
            d = vd[i]
            if abs(d) < dev:
                continue

            entry = close[i]
            exit_p = close[i + hold]

            if d < -dev:  # long
                pnl = (exit_p - entry) / entry - FEE_RT
            else:  # short
                pnl = (entry - exit_p) / entry - FEE_RT

            total_profit += pnl
            total_trades += 1
            if pnl > 0:
                total_wins += 1

    return total_trades, total_wins, total_profit


print("VWAP SCALP SCAN — fees included (0.09% RT)")
print(f"Period: {START} to {END}, Pairs: {len(PAIRS)}")
print(f"\n{'Dev%':>5} | {'Hold':>4} | {'Trades':>7} | {'Win%':>6} | {'AvgP%':>8} | {'TotP%':>8}")
print("-" * 55)

results = []
for dev in [0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.7, 1.0]:
    for hold in [1, 2, 3, 5, 10]:
        trades, wins, profit = test_combo(dev, hold)
        if trades < 20:
            continue
        wr = wins / trades * 100
        avg_p = profit / trades * 100
        tot_p = profit * 100
        results.append((dev, hold, trades, wr, avg_p, tot_p))
        print(f"{dev:>5.2f} | {hold:>4} | {trades:>7} | {wr:>5.1f}% | {avg_p:>7.3f}% | {tot_p:>7.1f}%", flush=True)

print("\n--- TOP 10 ---")
for r in sorted(results, key=lambda x: x[5], reverse=True)[:10]:
    print(f"  dev={r[0]:.2f}%, hold={r[1]}, trades={r[2]}, win={r[3]:.1f}%, avg={r[4]:.3f}%, total={r[5]:.1f}%")

# Best config: per-pair breakdown
if results:
    best = max(results, key=lambda x: x[5])
    dev, hold = best[0], best[1]
    print(f"\nBEST: dev={dev}%, hold={hold}")
    for coin in PAIRS:
        df = load(coin)
        if df.empty: continue
        df = compute_vwap(df)
        vd = df["vwap_pct"].values
        close = df["close"].values
        n = len(df)
        wins = trades = profit = 0
        for i in range(48, n - hold):
            d = vd[i]
            if abs(d) < dev: continue
            entry = close[i]
            exit_p = close[i + hold]
            if d < -dev:
                pnl = (exit_p - entry) / entry - FEE_RT
            else:
                pnl = (entry - exit_p) / entry - FEE_RT
            profit += pnl; trades += 1
            if pnl > 0: wins += 1
        if trades:
            print(f"  {coin:>5}: {trades:>5} trades, {wins/trades*100:>5.1f}% win, total={profit*100:>7.1f}%")
