"""
KNN Mean Reversion — adapted from TradingView indicator
=========================================================

Features (z-score normalized):
  F1: Distance from EMA20 (%)
  F2: Bollinger Band position
  F3: RSI deviation from 50
  F4: Body/range compression
  F5: Volume fade

Label: did price touch basis MA within rev_window bars?
KNN: find K nearest neighbors, Gaussian-weighted vote → P(reversion)
Signal: P(rev) crosses above threshold AND price extended beyond ATR gate

Includes fees. Tests on real HL 5m data.
"""
import numpy as np
import pandas as pd
from pathlib import Path

DATA_DIR = Path("user_data/data/hyperliquid/futures")
PAIRS = ["ETH", "SOL", "XRP", "LINK", "SUI", "DOGE", "ONDO", "TON"]
START, END = "2026-01-01", "2026-05-19"
FEE_RT = 0.0009

# KNN params (from PineScript defaults)
K = 60
WIN_SIZE = 800
REV_WINDOW = 6
P_DIST = 2.0  # Euclidean
GAUSS_BW = 1.5
PROB_THRESH = 0.65

# Feature params
BASIS_LEN = 20
BB_MULT = 2.0
RSI_LEN = 14
VOL_MA_LEN = 20
GATE_ATR_LEN = 14
GATE_MULT = 1.0


def load(coin):
    f = DATA_DIR / f"{coin}_USDC_USDC-5m-futures.feather"
    if not f.exists(): return pd.DataFrame()
    df = pd.read_feather(f)
    return df[(df["date"] >= START) & (df["date"] <= END)].sort_values("date").reset_index(drop=True)


def compute_rsi(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def zscore(series, window):
    """Z-score using [1] offset to avoid look-ahead."""
    mu = series.shift(1).rolling(window).mean()
    sigma = series.shift(1).rolling(window).std().replace(0, 1e-6)
    return (series - mu) / sigma


def compute_features(df):
    """Compute all 5 features + z-score normalize."""
    close = df["close"]
    high = df["high"]
    low = df["low"]
    opn = df["open"]
    vol = df["volume"]

    # Basis: EMA20
    basis = close.ewm(span=BASIS_LEN, adjust=False).mean()
    df["basis"] = basis

    # BB
    bb_std = close.rolling(BASIS_LEN).std()
    bb_upper = basis + BB_MULT * bb_std

    # RSI
    rsi = compute_rsi(close, RSI_LEN)

    # ATR for gate
    tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.rolling(GATE_ATR_LEN).mean()
    df["atr"] = atr

    # Volume ratio
    vol_ma = vol.shift(1).rolling(VOL_MA_LEN).mean().replace(0, 1)
    vol_ratio = vol / vol_ma

    # Raw features
    f1 = (close - basis) / basis.replace(0, 1e-6) * 100  # dist from MA
    f2 = (close - basis) / (bb_upper - basis).replace(0, 1e-6)  # BB position
    f3 = rsi - 50.0  # RSI deviation
    f4 = (close - opn).abs() / (high - low).replace(0, 1e-6)  # body compression
    f5 = -vol_ratio  # volume fade

    # Z-score normalize
    df["z1"] = zscore(f1, WIN_SIZE)
    df["z2"] = zscore(f2, WIN_SIZE)
    df["z3"] = zscore(f3, WIN_SIZE)
    df["z4"] = zscore(f4, WIN_SIZE)
    df["z5"] = zscore(f5, WIN_SIZE)

    return df


def compute_labels(df):
    """Label: did price touch basis within rev_window bars?"""
    close = df["close"].values
    basis = df["basis"].values
    high = df["high"].values
    low = df["low"].values
    n = len(df)
    labels = np.zeros(n, dtype=int)

    for i in range(n - REV_WINDOW):
        if close[i] > basis[i]:  # above basis
            touched = False
            for j in range(1, REV_WINDOW + 1):
                if i + j < n and low[i + j] <= basis[i + j]:
                    touched = True
                    break
            labels[i] = 1 if touched else 0
        elif close[i] < basis[i]:  # below basis
            touched = False
            for j in range(1, REV_WINDOW + 1):
                if i + j < n and high[i + j] >= basis[i + j]:
                    touched = True
                    break
            labels[i] = -1 if touched else 0

    df["label"] = labels
    return df


def run_knn(df):
    """Run KNN for each bar, compute P(reversion). Optimized with numpy."""
    z = df[["z1", "z2", "z3", "z4", "z5"]].values
    labels = df["label"].values
    close = df["close"].values
    basis = df["basis"].values
    n = len(df)

    p_above = np.zeros(n)
    p_below = np.zeros(n)

    start_idx = WIN_SIZE + REV_WINDOW + 50

    for i in range(start_idx, n):
        # Candidate indices: skip step=REV_WINDOW for speed (like PineScript)
        cand_start = max(0, i - WIN_SIZE - REV_WINDOW)
        cand_end = i - REV_WINDOW
        if cand_end <= cand_start:
            continue

        candidates = np.arange(cand_start, cand_end, REV_WINDOW)
        if len(candidates) < K:
            candidates = np.arange(cand_start, cand_end)
        if len(candidates) < K:
            continue

        # Current feature vector
        curr = z[i]

        # Compute distances (Minkowski with p=2 = Euclidean)
        diffs = np.abs(z[candidates] - curr)
        dists = np.power(np.sum(np.power(diffs, P_DIST), axis=1), 1.0 / P_DIST)

        # Sort, take K nearest
        sorted_idx = np.argsort(dists)[:K]
        k_dists = dists[sorted_idx]
        k_labels = labels[candidates[sorted_idx]]
        k_z1 = z[candidates[sorted_idx], 0]

        # Gaussian kernel weights
        sigma = max(np.median(k_dists), 1e-6)
        weights = np.exp(-np.power(k_dists, GAUSS_BW) / (2 * sigma * sigma))

        # Accumulate by direction
        w_rev_above = np.sum(weights[k_labels == 1])
        w_rev_below = np.sum(weights[k_labels == -1])

        w_total_above = w_rev_above + np.sum(weights[(k_labels == 0) & (k_z1 > 0)])
        w_total_below = w_rev_below + np.sum(weights[(k_labels == 0) & (k_z1 <= 0)])

        p_above[i] = w_rev_above / max(w_total_above, 1e-6)
        p_below[i] = w_rev_below / max(w_total_below, 1e-6)

    df["p_above"] = p_above
    df["p_below"] = p_below
    return df


def simulate_trades(df):
    """Generate signals and simulate trades with fees."""
    close = df["close"].values
    basis = df["basis"].values
    atr = df["atr"].values
    p_above = df["p_above"].values
    p_below = df["p_below"].values
    n = len(df)

    trades = []
    last_dir = 0

    for i in range(1, n):
        # Crossover detection
        cross_short = p_above[i] > PROB_THRESH and p_above[i - 1] <= PROB_THRESH and close[i] > basis[i]
        cross_long = p_below[i] > PROB_THRESH and p_below[i - 1] <= PROB_THRESH and close[i] < basis[i]

        # Extension gate
        ext = GATE_MULT * atr[i] if not np.isnan(atr[i]) else 0
        gate_short = close[i] > basis[i] + ext
        gate_long = close[i] < basis[i] - ext

        # Dedup
        sig_short = cross_short and gate_short and last_dir >= 0
        sig_long = cross_long and gate_long and last_dir <= 0

        if sig_short:
            last_dir = -1
            # Find exit: price crosses back below basis
            for j in range(i + 1, min(i + 50, n)):
                if close[j] <= basis[j]:
                    profit = (close[i] - close[j]) / close[i] - FEE_RT
                    trades.append({"entry": i, "exit": j, "side": "short",
                                   "profit": profit, "bars": j - i, "prob": p_above[i]})
                    break
            else:
                # Time stop at 50 bars
                j = min(i + 50, n - 1)
                profit = (close[i] - close[j]) / close[i] - FEE_RT
                trades.append({"entry": i, "exit": j, "side": "short",
                               "profit": profit, "bars": j - i, "prob": p_above[i]})

        if sig_long:
            last_dir = 1
            for j in range(i + 1, min(i + 50, n)):
                if close[j] >= basis[j]:
                    profit = (close[j] - close[i]) / close[i] - FEE_RT
                    trades.append({"entry": i, "exit": j, "side": "long",
                                   "profit": profit, "bars": j - i, "prob": p_below[i]})
                    break
            else:
                j = min(i + 50, n - 1)
                profit = (close[j] - close[i]) / close[i] - FEE_RT
                trades.append({"entry": i, "exit": j, "side": "long",
                               "profit": profit, "bars": j - i, "prob": p_below[i]})

        # Reset direction
        if close[i] > basis[i] and last_dir == 1:
            last_dir = 0
        if close[i] < basis[i] and last_dir == -1:
            last_dir = 0

    return trades


def main():
    print("KNN Mean Reversion Backtest — fees included (0.09% RT)")
    print(f"K={K}, lookback={WIN_SIZE}, rev_window={REV_WINDOW}, prob_thresh={PROB_THRESH}")
    print(f"Basis=EMA{BASIS_LEN}, BB={BB_MULT}, RSI={RSI_LEN}, gate={GATE_MULT}×ATR{GATE_ATR_LEN}")
    print(f"Period: {START} to {END}\n")

    all_trades = []

    for coin in PAIRS:
        print(f"Processing {coin}...", end=" ", flush=True)
        df = load(coin)
        if df.empty or len(df) < WIN_SIZE + 200:
            print("SKIP (insufficient data)")
            continue

        df = compute_features(df)
        df = compute_labels(df)
        df = run_knn(df)
        trades = simulate_trades(df)

        if not trades:
            print("0 trades")
            continue

        profits = [t["profit"] for t in trades]
        wins = sum(1 for p in profits if p > 0)
        avg_bars = np.mean([t["bars"] for t in trades])
        print(f"{len(trades)} trades, {wins/len(trades)*100:.1f}% win, "
              f"avg={np.mean(profits)*100:.3f}%, total={np.sum(profits)*100:.1f}%, "
              f"avg_bars={avg_bars:.1f}", flush=True)

        for t in trades:
            t["pair"] = coin
        all_trades.extend(trades)

    if not all_trades:
        print("\nNo trades generated!")
        return

    print(f"\n{'='*60}")
    print("AGGREGATE RESULTS")
    print(f"{'='*60}")
    profits = [t["profit"] for t in all_trades]
    wins = sum(1 for p in profits if p > 0)
    print(f"Total trades: {len(all_trades)}")
    print(f"Win rate: {wins/len(all_trades)*100:.1f}%")
    print(f"Avg profit: {np.mean(profits)*100:.3f}%")
    print(f"Total profit: {np.sum(profits)*100:.1f}%")
    print(f"Avg bars held: {np.mean([t['bars'] for t in all_trades]):.1f}")
    print(f"Avg P(rev) at entry: {np.mean([t['prob'] for t in all_trades]):.3f}")

    # By probability bucket
    print(f"\nBy P(rev) bucket:")
    for lo, hi in [(0.65, 0.70), (0.70, 0.75), (0.75, 0.80), (0.80, 0.85), (0.85, 1.0)]:
        subset = [t for t in all_trades if lo <= t["prob"] < hi]
        if len(subset) < 5: continue
        sp = [t["profit"] for t in subset]
        w = sum(1 for p in sp if p > 0)
        print(f"  P={lo:.2f}-{hi:.2f}: {len(subset):>4} trades, "
              f"{w/len(subset)*100:>5.1f}% win, avg={np.mean(sp)*100:>7.3f}%")


if __name__ == "__main__":
    main()
