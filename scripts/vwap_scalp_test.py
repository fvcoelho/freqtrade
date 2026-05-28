"""
VWAP Scalp Scanner — with REAL fees included
=============================================

VWAP = cumulative(typical_price * volume) / cumulative(volume), reset daily.
Enter when price deviates from VWAP, exit on reversion.

Tests different:
  - VWAP deviation thresholds (0.1% to 1.0%)
  - Hold periods (1-10 candles)
  - With and without BTC regime filter

Includes fees (0.045% * 2 = 0.09% round trip) in profit calculation.
"""
import numpy as np
import pandas as pd
from pathlib import Path

DATA_DIR = Path("user_data/data/hyperliquid/futures")
PAIRS = ["ETH", "SOL", "XRP", "LINK", "SUI", "DOGE", "ONDO", "TON"]
TIMERANGE_START = "2026-01-01"
TIMERANGE_END = "2026-05-19"

FEE = 0.00045  # 0.045% per side, applied on entry + exit = 0.09% total


def load_pair(coin):
    f = DATA_DIR / f"{coin}_USDC_USDC-5m-futures.feather"
    if not f.exists():
        return pd.DataFrame()
    df = pd.read_feather(f)
    df = df[(df["date"] >= TIMERANGE_START) & (df["date"] <= TIMERANGE_END)].copy()
    return df.sort_values("date").reset_index(drop=True)


def compute_vwap(df):
    """Compute intraday VWAP, reset at 00:00 UTC each day."""
    tp = (df["high"] + df["low"] + df["close"]) / 3
    df["tp_vol"] = tp * df["volume"]

    # Group by date for daily reset
    df["day"] = df["date"].dt.date
    df["cum_tp_vol"] = df.groupby("day")["tp_vol"].cumsum()
    df["cum_vol"] = df.groupby("day")["volume"].cumsum()
    df["vwap"] = df["cum_tp_vol"] / df["cum_vol"].replace(0, np.nan)

    # Deviation from VWAP (%)
    df["vwap_dev"] = (df["close"] - df["vwap"]) / df["vwap"] * 100

    # VWAP bands (rolling std of deviation)
    df["vwap_std"] = df["vwap_dev"].rolling(48).std()  # 4h rolling std

    return df


def compute_btc_regime(btc_df, mom_th=0.5):
    """Simple BTC regime filter."""
    btc_df["btc_ret"] = btc_df["close"].pct_change(48) * 100  # 4h momentum
    btc_df["is_ranging"] = btc_df["btc_ret"].abs() < mom_th
    return btc_df[["date", "is_ranging"]].copy()


def simulate_vwap_trades(df, dev_threshold, hold_period, use_regime=False, regime_df=None):
    """Simulate VWAP reversion trades with fees."""
    if use_regime and regime_df is not None:
        df = df.merge(regime_df, on="date", how="left")
        df["is_ranging"] = df["is_ranging"].fillna(False)
    else:
        df["is_ranging"] = True

    trades = []
    in_trade = False

    for i in range(48, len(df) - hold_period):
        if in_trade:
            continue

        if not df["is_ranging"].iloc[i]:
            continue

        dev = df["vwap_dev"].iloc[i]

        # LONG: price far below VWAP
        if dev < -dev_threshold:
            entry = df["close"].iloc[i]
            exit_price = df["close"].iloc[i + hold_period]
            profit = (exit_price - entry) / entry - 2 * FEE
            trades.append({"profit": profit, "side": "long", "dev": dev})
            in_trade = False

        # SHORT: price far above VWAP
        elif dev > dev_threshold:
            entry = df["close"].iloc[i]
            exit_price = df["close"].iloc[i + hold_period]
            profit = (entry - exit_price) / entry - 2 * FEE
            trades.append({"profit": profit, "side": "short", "dev": dev})
            in_trade = False

    return trades


def main():
    # Load BTC for regime
    btc = load_pair("BTC")
    regime_df = compute_btc_regime(btc) if not btc.empty else None

    dev_thresholds = [0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.7, 1.0]
    hold_periods = [1, 2, 3, 5, 10]

    # ===== WITHOUT regime filter =====
    print("=" * 80)
    print("VWAP SCALP — NO regime filter (all candles), FEES INCLUDED (0.09% RT)")
    print("=" * 80)

    all_results = []

    for dev_th in dev_thresholds:
        for hold in hold_periods:
            total_trades = []
            for coin in PAIRS:
                df = load_pair(coin)
                if df.empty:
                    continue
                df = compute_vwap(df)
                trades = simulate_vwap_trades(df, dev_th, hold, use_regime=False)
                total_trades.extend(trades)

            if len(total_trades) < 20:
                continue

            profits = [t["profit"] for t in total_trades]
            wins = sum(1 for p in profits if p > 0)
            wr = wins / len(profits) * 100
            avg_p = np.mean(profits) * 100
            tot_p = np.sum(profits) * 100

            all_results.append({
                "dev": dev_th, "hold": hold, "trades": len(profits),
                "win_pct": wr, "avg_p": avg_p, "tot_p": tot_p, "regime": "none"
            })

    print(f"\n{'Dev%':>5} | {'Hold':>4} | {'Trades':>6} | {'Win%':>6} | {'AvgP%':>8} | {'TotP%':>8}")
    print("-" * 55)
    for r in sorted(all_results, key=lambda x: x["tot_p"], reverse=True)[:20]:
        print(f"{r['dev']:>5.2f} | {r['hold']:>4} | {r['trades']:>6} | {r['win_pct']:>5.1f}% | "
              f"{r['avg_p']:>7.3f}% | {r['tot_p']:>7.1f}%")

    # ===== WITH regime filter =====
    print("\n" + "=" * 80)
    print("VWAP SCALP — WITH regime filter (ranging only), FEES INCLUDED")
    print("=" * 80)

    regime_results = []

    for dev_th in dev_thresholds:
        for hold in hold_periods:
            total_trades = []
            for coin in PAIRS:
                df = load_pair(coin)
                if df.empty:
                    continue
                df = compute_vwap(df)
                trades = simulate_vwap_trades(df, dev_th, hold, use_regime=True, regime_df=regime_df)
                total_trades.extend(trades)

            if len(total_trades) < 20:
                continue

            profits = [t["profit"] for t in total_trades]
            wins = sum(1 for p in profits if p > 0)
            wr = wins / len(profits) * 100
            avg_p = np.mean(profits) * 100
            tot_p = np.sum(profits) * 100

            regime_results.append({
                "dev": dev_th, "hold": hold, "trades": len(profits),
                "win_pct": wr, "avg_p": avg_p, "tot_p": tot_p, "regime": "ranging"
            })

    print(f"\n{'Dev%':>5} | {'Hold':>4} | {'Trades':>6} | {'Win%':>6} | {'AvgP%':>8} | {'TotP%':>8}")
    print("-" * 55)
    for r in sorted(regime_results, key=lambda x: x["tot_p"], reverse=True)[:20]:
        print(f"{r['dev']:>5.2f} | {r['hold']:>4} | {r['trades']:>6} | {r['win_pct']:>5.1f}% | "
              f"{r['avg_p']:>7.3f}% | {r['tot_p']:>7.1f}%")

    # ===== Per-pair breakdown for best config =====
    all_combined = all_results + regime_results
    if all_combined:
        best = max(all_combined, key=lambda x: x["tot_p"])
        print(f"\n{'='*80}")
        print(f"BEST: dev={best['dev']}%, hold={best['hold']}, regime={best['regime']}")
        print(f"      {best['trades']} trades, {best['win_pct']:.1f}% win, avg={best['avg_p']:.3f}%, total={best['tot_p']:.1f}%")
        print(f"{'='*80}")

        print(f"\nPer-pair breakdown:")
        use_regime = best["regime"] == "ranging"
        for coin in PAIRS:
            df = load_pair(coin)
            if df.empty:
                continue
            df = compute_vwap(df)
            trades = simulate_vwap_trades(df, best["dev"], best["hold"],
                                          use_regime=use_regime, regime_df=regime_df)
            if not trades:
                print(f"  {coin:>5}: 0 trades")
                continue
            profits = [t["profit"] for t in trades]
            wins = sum(1 for p in profits if p > 0)
            longs = sum(1 for t in trades if t["side"] == "long")
            shorts = len(trades) - longs
            print(f"  {coin:>5}: {len(trades):>4} trades ({longs}L/{shorts}S), "
                  f"{wins/len(trades)*100:>5.1f}% win, avg={np.mean(profits)*100:>7.3f}%, "
                  f"total={np.sum(profits)*100:>7.1f}%")


if __name__ == "__main__":
    main()
