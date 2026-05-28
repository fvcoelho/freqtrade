"""
Lead-Lag Analysis: BTC leads, alts follow
==========================================

1. Cross-correlation BTC vs alts at different lags
2. Simulate: BTC moves X% in N candles → enter alt, exit after M candles
3. Test different BTC move thresholds, lag windows, holding periods
"""
import numpy as np
import pandas as pd
from pathlib import Path

DATA_DIR = Path("user_data/data/hyperliquid/futures")
PAIRS = ["ETH", "SOL", "XRP", "LINK", "SUI", "DOGE", "HYPE", "ONDO", "TON", "ZEC"]
TIMERANGE_START = "2026-01-01"
TIMERANGE_END = "2026-05-19"


def load_pair(coin):
    f = DATA_DIR / f"{coin}_USDC_USDC-5m-futures.feather"
    if not f.exists():
        return pd.DataFrame()
    df = pd.read_feather(f)
    df = df[(df["date"] >= TIMERANGE_START) & (df["date"] <= TIMERANGE_END)].copy()
    df = df.sort_values("date").reset_index(drop=True)
    df["ret"] = df["close"].pct_change()
    return df


def cross_correlation_analysis():
    """Measure how well BTC returns predict alt returns at different lags."""
    btc = load_pair("BTC")
    if btc.empty:
        return

    print("=" * 70)
    print("CROSS-CORRELATION: BTC return(t) vs Alt return(t+lag)")
    print("Positive = alt follows BTC in same direction after lag")
    print("=" * 70)

    print(f"\n{'Pair':>6}", end="")
    for lag in range(0, 11):
        print(f" | lag{lag:>2}", end="")
    print()
    print("-" * 85)

    for coin in PAIRS:
        alt = load_pair(coin)
        if alt.empty or len(alt) < len(btc):
            continue

        # Align by date
        merged = btc[["date", "ret"]].merge(alt[["date", "ret"]], on="date", suffixes=("_btc", "_alt"))
        if len(merged) < 100:
            continue

        print(f"{coin:>6}", end="")
        for lag in range(0, 11):
            if lag == 0:
                corr = merged["ret_btc"].corr(merged["ret_alt"])
            else:
                corr = merged["ret_btc"].iloc[:-lag].reset_index(drop=True).corr(
                    merged["ret_alt"].iloc[lag:].reset_index(drop=True)
                )
            print(f" | {corr:>5.3f}", end="")
        print()


def btc_move_analysis():
    """When BTC moves X% in N candles, what happens to alts in the next M candles?"""
    btc = load_pair("BTC")

    print("\n" + "=" * 70)
    print("BTC MOVE → ALT FOLLOW ANALYSIS")
    print("When BTC moves X% in N candles, what does alt do in next M candles?")
    print("=" * 70)

    # BTC move: % change over lookback window
    lookbacks = [1, 2, 3, 5]
    thresholds = [0.2, 0.3, 0.5, 0.7, 1.0]
    hold_periods = [1, 2, 3, 5, 10]

    for coin in PAIRS:
        alt = load_pair(coin)
        if alt.empty:
            continue

        merged = btc[["date", "close"]].merge(alt[["date", "close"]], on="date", suffixes=("_btc", "_alt"))
        if len(merged) < 200:
            continue

        print(f"\n--- {coin} ---")
        print(f"{'Lookback':>8} | {'BTC_th':>6} | {'Hold':>4} | {'Trades':>6} | {'Win%':>6} | {'AvgP%':>7} | {'TotP%':>7}")
        print("-" * 75)

        best = None
        best_profit = -999

        for lb in lookbacks:
            btc_move = (merged["close_btc"] / merged["close_btc"].shift(lb) - 1) * 100

            for th in thresholds:
                for hold in hold_periods:
                    trades_long = []
                    trades_short = []

                    for i in range(lb, len(merged) - hold):
                        mv = btc_move.iloc[i]
                        if abs(mv) < th:
                            continue

                        entry = merged["close_alt"].iloc[i]
                        exit_price = merged["close_alt"].iloc[i + hold]

                        if mv > th:  # BTC pumped → alt should follow up
                            profit = (exit_price - entry) / entry
                            trades_long.append(profit)
                        elif mv < -th:  # BTC dumped → alt should follow down
                            profit = (entry - exit_price) / entry
                            trades_short.append(profit)

                    all_trades = trades_long + trades_short
                    if len(all_trades) < 20:
                        continue

                    wins = sum(1 for p in all_trades if p > 0)
                    win_pct = wins / len(all_trades) * 100
                    avg_p = np.mean(all_trades) * 100
                    tot_p = np.sum(all_trades) * 100

                    if tot_p > best_profit:
                        best_profit = tot_p
                        best = (lb, th, hold, len(all_trades), win_pct, avg_p, tot_p)

                    # Only print promising ones
                    if avg_p > 0:
                        print(f"{lb:>8} | {th:>5.1f}% | {hold:>4} | {len(all_trades):>6} | "
                              f"{win_pct:>5.1f}% | {avg_p:>6.3f}% | {tot_p:>6.1f}%")

        if best:
            lb, th, hold, n, wr, avg, tot = best
            print(f"  BEST: lookback={lb}, btc>{th}%, hold={hold} → "
                  f"{n} trades, {wr:.1f}% win, avg={avg:.3f}%, total={tot:.1f}%")


def timing_analysis():
    """Measure average delay: when BTC spikes, how many candles until alt follows?"""
    btc = load_pair("BTC")

    print("\n" + "=" * 70)
    print("TIMING: When BTC spikes >0.3%, how fast do alts react?")
    print("peak_lag = candle where alt has max move in same direction")
    print("=" * 70)

    btc_ret = btc["ret"]
    spike_mask = btc_ret.abs() > 0.003  # 0.3% move in 5min

    for coin in PAIRS:
        alt = load_pair(coin)
        if alt.empty:
            continue

        merged = btc[["date", "ret"]].merge(alt[["date", "ret"]], on="date", suffixes=("_btc", "_alt"))

        up_lags = []
        down_lags = []

        for i in range(len(merged) - 10):
            btc_r = merged["ret_btc"].iloc[i]
            if abs(btc_r) < 0.003:
                continue

            # Look at alt returns for next 10 candles
            alt_rets = [merged["ret_alt"].iloc[i + j] if i + j < len(merged) else 0 for j in range(1, 11)]

            if btc_r > 0:
                # BTC up: find when alt moves up most
                cum = np.cumsum(alt_rets)
                peak = np.argmax(cum) + 1
                up_lags.append(peak)
            else:
                # BTC down: find when alt moves down most
                cum = np.cumsum(alt_rets)
                peak = np.argmin(cum) + 1
                down_lags.append(peak)

        if up_lags and down_lags:
            print(f"  {coin:>5}: UP peak_lag={np.mean(up_lags):.1f} candles ({np.mean(up_lags)*5:.0f}min), "
                  f"DOWN peak_lag={np.mean(down_lags):.1f} candles ({np.mean(down_lags)*5:.0f}min), "
                  f"events={len(up_lags)+len(down_lags)}")


if __name__ == "__main__":
    cross_correlation_analysis()
    timing_analysis()
    btc_move_analysis()
