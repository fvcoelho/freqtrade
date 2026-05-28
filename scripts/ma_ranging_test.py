"""
Mean-Reversion MA Period Scanner for Ranging/Consolidation Regime
=================================================================

Tests MA periods 2-20 for mean-reversion trades during ranging markets.
Ranging = |btc_mom| < threshold AND btc_atr_z < threshold.

For each MA period:
  - Compute price deviation from MA (z-score style)
  - Enter LONG when deviation < -entry_threshold (price below MA)
  - Enter SHORT when deviation > +entry_threshold (price above MA)
  - Exit when deviation reverts to exit_threshold (near MA)
  - Time stop after max_candles
  - Track: win rate, avg profit, total profit, trade count
"""
import sys
import numpy as np
import pandas as pd
from pathlib import Path

DATA_DIR = Path("user_data/data/hyperliquid/futures")

PAIRS = ["ETH", "SOL", "XRP", "LINK", "SUI", "DOGE", "HYPE", "ONDO", "TON", "ZEC"]
BTC_PAIR = "BTC"
TIMEFRAME = "5m"
TIMERANGE_START = "2026-01-01"
TIMERANGE_END = "2026-05-19"

# Regime detection (V54 style)
BTC_MOM_PERIOD = 4  # 1h candles for momentum
BTC_MOM_THRESHOLD = 2.0
BTC_ATR_PERIOD = 14
BTC_ATR_Z_THRESHOLD = 2.0
BTC_ATR_Z_WINDOW = 144

# Trade parameters
ENTRY_THRESHOLD = 2.0  # z-score deviation to enter
EXIT_THRESHOLD = 0.3   # z-score deviation to exit (revert)
MAX_CANDLES = 24        # time stop (2h at 5m)
STOPLOSS = -0.07        # max loss per trade

MA_PERIODS = list(range(2, 21))  # test MA 2 to 20


def load_pair(coin: str) -> pd.DataFrame:
    f = DATA_DIR / f"{coin}_USDC_USDC-5m-futures.feather"
    if not f.exists():
        return pd.DataFrame()
    df = pd.read_feather(f)
    df = df[(df["date"] >= TIMERANGE_START) & (df["date"] <= TIMERANGE_END)].copy()
    df = df.sort_values("date").reset_index(drop=True)
    return df


def compute_btc_regime(btc_df: pd.DataFrame) -> pd.DataFrame:
    """Compute BTC momentum and ATR z-score on 5m data, using 1h equivalent periods."""
    # BTC momentum: % change over mom_period * 12 candles (4h equiv on 5m)
    mom_lookback = BTC_MOM_PERIOD * 12  # 48 candles = 4h on 5m
    btc_df["btc_mom"] = (btc_df["close"] / btc_df["close"].shift(mom_lookback) - 1) * 100

    # ATR
    high = btc_df["high"]
    low = btc_df["low"]
    close_prev = btc_df["close"].shift(1)
    tr = pd.concat([high - low, (high - close_prev).abs(), (low - close_prev).abs()], axis=1).max(axis=1)
    atr = tr.rolling(BTC_ATR_PERIOD * 12).mean()
    atr_mean = atr.rolling(BTC_ATR_Z_WINDOW).mean()
    atr_std = atr.rolling(BTC_ATR_Z_WINDOW).std().replace(0, np.nan)
    btc_df["btc_atr_z"] = ((atr - atr_mean) / atr_std).fillna(0)

    # Regime: ranging = NOT trending
    btc_df["is_trending"] = (btc_df["btc_mom"].abs() > BTC_MOM_THRESHOLD) | (btc_df["btc_atr_z"] > BTC_ATR_Z_THRESHOLD)
    btc_df["is_ranging"] = ~btc_df["is_trending"]

    return btc_df[["date", "btc_mom", "btc_atr_z", "is_ranging"]].copy()


def simulate_trades(pair_df: pd.DataFrame, regime_df: pd.DataFrame, ma_period: int) -> list[dict]:
    """Simulate mean-reversion trades for a given MA period during ranging regime."""
    # Merge regime
    df = pair_df.merge(regime_df, on="date", how="left")
    df["is_ranging"] = df["is_ranging"].fillna(False)

    # Compute MA and deviation z-score
    df["ma"] = df["close"].rolling(ma_period).mean()
    df["ma_std"] = df["close"].rolling(ma_period).std().replace(0, np.nan)
    df["deviation"] = ((df["close"] - df["ma"]) / df["ma_std"]).fillna(0)

    trades = []
    in_trade = False
    entry_price = 0.0
    entry_idx = 0
    is_short = False

    for i in range(ma_period, len(df)):
        if not in_trade:
            if not df["is_ranging"].iloc[i]:
                continue

            dev = df["deviation"].iloc[i]

            # LONG: price far below MA
            if dev < -ENTRY_THRESHOLD:
                in_trade = True
                entry_price = df["close"].iloc[i]
                entry_idx = i
                is_short = False

            # SHORT: price far above MA
            elif dev > ENTRY_THRESHOLD:
                in_trade = True
                entry_price = df["close"].iloc[i]
                entry_idx = i
                is_short = True

        else:
            current_price = df["close"].iloc[i]
            dev = df["deviation"].iloc[i]
            candles_held = i - entry_idx

            if is_short:
                profit = (entry_price - current_price) / entry_price
            else:
                profit = (current_price - entry_price) / entry_price

            exit_reason = None

            # Reversion exit
            if not is_short and dev >= -EXIT_THRESHOLD:
                exit_reason = "revert"
            elif is_short and dev <= EXIT_THRESHOLD:
                exit_reason = "revert"

            # Time stop
            if candles_held >= MAX_CANDLES:
                exit_reason = "time_stop"

            # Stoploss
            if profit <= STOPLOSS:
                exit_reason = "stop_loss"

            if exit_reason:
                trades.append({
                    "entry_date": df["date"].iloc[entry_idx],
                    "exit_date": df["date"].iloc[i],
                    "side": "short" if is_short else "long",
                    "profit": profit,
                    "candles": candles_held,
                    "exit_reason": exit_reason,
                })
                in_trade = False

    return trades


def main():
    print("Loading BTC data for regime detection...")
    btc_df = load_pair(BTC_PAIR)
    if btc_df.empty:
        print("ERROR: No BTC data found")
        return
    regime_df = compute_btc_regime(btc_df)

    ranging_pct = regime_df["is_ranging"].mean() * 100
    print(f"BTC regime: {ranging_pct:.1f}% ranging, {100-ranging_pct:.1f}% trending")
    print(f"Period: {TIMERANGE_START} to {TIMERANGE_END}")
    print(f"Entry threshold: {ENTRY_THRESHOLD}σ, Exit: {EXIT_THRESHOLD}σ, "
          f"Time stop: {MAX_CANDLES} candles, Stoploss: {STOPLOSS*100:.0f}%")
    print()

    # Results per MA period
    results = []

    for ma in MA_PERIODS:
        all_trades = []
        for coin in PAIRS:
            pair_df = load_pair(coin)
            if pair_df.empty:
                continue
            trades = simulate_trades(pair_df, regime_df, ma)
            for t in trades:
                t["pair"] = coin
            all_trades.extend(trades)

        if not all_trades:
            results.append({"ma": ma, "trades": 0, "win_rate": 0, "avg_profit": 0,
                           "total_profit": 0, "avg_candles": 0})
            continue

        profits = [t["profit"] for t in all_trades]
        wins = sum(1 for p in profits if p > 0)
        win_rate = wins / len(profits) * 100
        avg_profit = np.mean(profits) * 100
        total_profit = np.sum(profits) * 100
        avg_candles = np.mean([t["candles"] for t in all_trades])

        # Exit reason breakdown
        reasons = {}
        for t in all_trades:
            r = t["exit_reason"]
            reasons[r] = reasons.get(r, 0) + 1

        results.append({
            "ma": ma, "trades": len(all_trades), "win_rate": win_rate,
            "avg_profit": avg_profit, "total_profit": total_profit,
            "avg_candles": avg_candles, "reasons": reasons,
        })

    # Print results table
    print(f"{'MA':>3} | {'Trades':>6} | {'Win%':>6} | {'AvgP%':>7} | {'TotP%':>8} | {'AvgBars':>7} | Exit Reasons")
    print("-" * 85)
    for r in results:
        reasons_str = ""
        if "reasons" in r:
            reasons_str = ", ".join(f"{k}={v}" for k, v in sorted(r["reasons"].items()))
        print(f"{r['ma']:>3} | {r['trades']:>6} | {r['win_rate']:>5.1f}% | {r['avg_profit']:>6.2f}% | "
              f"{r['total_profit']:>7.1f}% | {r['avg_candles']:>6.1f} | {reasons_str}")

    # Best MA
    if results:
        # Sort by profit/trade (efficiency)
        valid = [r for r in results if r["trades"] >= 10]
        if valid:
            best_wr = max(valid, key=lambda x: x["win_rate"])
            best_tp = max(valid, key=lambda x: x["total_profit"])
            best_avg = max(valid, key=lambda x: x["avg_profit"])

            print()
            print(f"BEST WIN RATE:    MA={best_wr['ma']} ({best_wr['win_rate']:.1f}%, {best_wr['trades']} trades)")
            print(f"BEST TOTAL PROF:  MA={best_tp['ma']} ({best_tp['total_profit']:.1f}%, {best_tp['trades']} trades)")
            print(f"BEST AVG PROFIT:  MA={best_avg['ma']} ({best_avg['avg_profit']:.2f}%, {best_avg['trades']} trades)")

    # Per-pair breakdown for best MA
    if valid:
        best_ma = best_tp["ma"]
        print(f"\n--- Per-pair breakdown for MA={best_ma} ---")
        for coin in PAIRS:
            pair_df = load_pair(coin)
            if pair_df.empty:
                continue
            trades = simulate_trades(pair_df, regime_df, best_ma)
            if not trades:
                print(f"  {coin:>5}: 0 trades")
                continue
            profits = [t["profit"] for t in trades]
            wins = sum(1 for p in profits if p > 0)
            print(f"  {coin:>5}: {len(trades):>4} trades, {wins/len(trades)*100:>5.1f}% win, "
                  f"avg={np.mean(profits)*100:>6.2f}%, total={np.sum(profits)*100:>7.1f}%")


if __name__ == "__main__":
    main()
