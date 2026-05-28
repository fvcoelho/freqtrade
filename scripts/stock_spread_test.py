"""
Stock Pairs Spread Z-Score Test
================================

Test natural stock groups for mean-reversion spread trading.
Groups by sector/correlation:
  - Tech mega: NVDA vs GOOGL, AMZN vs META, MSFT vs AAPL
  - Tech volatile: AMD vs INTC, MU vs SNDK
  - Crypto-corr: COIN vs MSTR
  - Mixed: TSLA vs PLTR, NFLX vs META

Fees included.
"""
import numpy as np
import pandas as pd
from pathlib import Path

DATA = Path("user_data/data/hyperliquid/futures")
START, END = "2026-01-15", "2026-05-19"  # SNDK starts Jan 12
FEE_RT = 0.0009
ZSCORE_WINDOW = 288
TIME_STOP = 24
STOPLOSS = -0.07

# Groups to test: (sub1, sub2, name)
GROUPS = [
    # Tech mega pairs
    (["XYZ-NVDA"], ["XYZ-AMD"], "NVDA_vs_AMD"),
    (["XYZ-NVDA"], ["XYZ-GOOGL"], "NVDA_vs_GOOGL"),
    (["XYZ-AMZN"], ["XYZ-META"], "AMZN_vs_META"),
    (["XYZ-MSFT"], ["XYZ-AAPL"], "MSFT_vs_AAPL"),
    (["XYZ-GOOGL"], ["XYZ-META"], "GOOGL_vs_META"),
    (["XYZ-GOOGL"], ["XYZ-AMZN"], "GOOGL_vs_AMZN"),
    # Semis
    (["XYZ-AMD"], ["XYZ-INTC"], "AMD_vs_INTC"),
    (["XYZ-MU"], ["XYZ-SNDK"], "MU_vs_SNDK"),
    (["XYZ-NVDA"], ["XYZ-MU"], "NVDA_vs_MU"),
    (["XYZ-AMD"], ["XYZ-MU"], "AMD_vs_MU"),
    # Crypto-correlated
    (["XYZ-COIN"], ["XYZ-MSTR"], "COIN_vs_MSTR"),
    # High beta
    (["XYZ-TSLA"], ["XYZ-PLTR"], "TSLA_vs_PLTR"),
    (["XYZ-NFLX"], ["XYZ-META"], "NFLX_vs_META"),
    # Multi-pair groups
    (["XYZ-NVDA"], ["XYZ-AMD", "XYZ-INTC"], "NVDA_vs_AMD+INTC"),
    (["XYZ-GOOGL"], ["XYZ-META", "XYZ-AMZN"], "GOOGL_vs_META+AMZN"),
    (["XYZ-AAPL"], ["XYZ-MSFT", "XYZ-GOOGL"], "AAPL_vs_MSFT+GOOGL"),
]

ENTRY_THRESHOLDS = [1.5, 2.0, 2.5]
EXIT_Z = 0.2


def load(coin):
    for pattern in [f"{coin}_USDC_USDC-5m-futures.feather", f"{coin}_USDC-5m-futures.feather"]:
        f = DATA / pattern
        if f.exists():
            df = pd.read_feather(f)
            return df[(df["date"] >= START) & (df["date"] <= END)].sort_values("date").reset_index(drop=True)
    return pd.DataFrame()


def compute_spread_z(df_sub1, df_sub2_list):
    ret1 = np.log(df_sub1["close"] / df_sub1["close"].shift(1)).cumsum()
    ret2s = []
    for d2 in df_sub2_list:
        ret2s.append(np.log(d2["close"] / d2["close"].shift(1)).cumsum().values)
    ret2_avg = np.mean(ret2s, axis=0)
    spread = ret1.values - ret2_avg
    s = pd.Series(spread)
    mu = s.rolling(ZSCORE_WINDOW).mean()
    sigma = s.rolling(ZSCORE_WINDOW).std().replace(0, np.nan)
    return ((s - mu) / sigma).fillna(0).values


def simulate(spread_z, close_sub1, entry_z):
    n = len(spread_z)
    trades = []
    i = ZSCORE_WINDOW

    while i < n - TIME_STOP:
        sz = spread_z[i]

        if abs(sz) < entry_z:
            i += 1
            continue

        entry_price = close_sub1[i]
        is_short = sz > entry_z  # sub1 expensive → short sub1

        for j in range(i + 1, min(i + TIME_STOP, n)):
            cp = close_sub1[j]
            profit = (entry_price - cp) / entry_price if is_short else (cp - entry_price) / entry_price
            sz_now = spread_z[j]

            exit_r = None
            if not is_short and sz_now >= -EXIT_Z:
                exit_r = "revert"
            elif is_short and sz_now <= EXIT_Z:
                exit_r = "revert"
            elif profit <= STOPLOSS:
                exit_r = "stop"
            elif j - i >= TIME_STOP:
                exit_r = "time"

            if exit_r:
                trades.append({"profit": profit - FEE_RT, "bars": j - i, "exit": exit_r})
                i = j + 1
                break
        else:
            i += 1
            continue
        continue

    return trades


def main():
    print("STOCK SPREAD Z-SCORE TEST — fees included")
    print(f"Period: {START} to {END}, z_window={ZSCORE_WINDOW}, exit={EXIT_Z}")
    print(f"Stoploss={STOPLOSS*100:.0f}%, time_stop={TIME_STOP} candles\n")

    results = []

    for sub1, sub2, name in GROUPS:
        df1 = load(sub1[0])
        df2_list = [load(s) for s in sub2]

        if df1.empty or any(d.empty for d in df2_list):
            continue

        min_len = min(len(df1), *[len(d) for d in df2_list])
        df1 = df1.tail(min_len).reset_index(drop=True)
        df2_list = [d.tail(min_len).reset_index(drop=True) for d in df2_list]

        # Correlation check
        ret1 = np.log(df1["close"] / df1["close"].shift(1)).dropna()
        ret2 = np.log(df2_list[0]["close"] / df2_list[0]["close"].shift(1)).dropna()
        min_r = min(len(ret1), len(ret2))
        corr = ret1.iloc[:min_r].reset_index(drop=True).corr(ret2.iloc[:min_r].reset_index(drop=True))

        spread_z = compute_spread_z(df1, df2_list)

        for entry_z in ENTRY_THRESHOLDS:
            trades = simulate(spread_z, df1["close"].values, entry_z)
            if len(trades) < 5:
                continue
            profits = [t["profit"] for t in trades]
            wins = sum(1 for p in profits if p > 0)
            wr = wins / len(trades) * 100
            avg_p = np.mean(profits) * 100
            tot_p = np.sum(profits) * 100
            avg_bars = np.mean([t["bars"] for t in trades])

            results.append({
                "name": name, "entry_z": entry_z, "trades": len(trades),
                "win_pct": wr, "avg_p": avg_p, "tot_p": tot_p,
                "avg_bars": avg_bars, "corr": corr,
            })

    # Sort by total profit
    results.sort(key=lambda x: x["tot_p"], reverse=True)

    print(f"{'Group':>22} | {'Z':>3} | {'Corr':>5} | {'Trades':>6} | {'Win%':>6} | {'AvgP%':>7} | {'TotP%':>8} | {'Bars':>4}")
    print("-" * 85)
    for r in results:
        print(f"{r['name']:>22} | {r['entry_z']:>3.1f} | {r['corr']:>5.2f} | {r['trades']:>6} | "
              f"{r['win_pct']:>5.1f}% | {r['avg_p']:>6.3f}% | {r['tot_p']:>7.1f}% | {r['avg_bars']:>4.1f}")

    print(f"\nTOP 5 PROFITABLE:")
    for r in results[:5]:
        print(f"  {r['name']}: entry={r['entry_z']}σ, {r['trades']} trades, "
              f"{r['win_pct']:.1f}% win, total={r['tot_p']:.1f}%, corr={r['corr']:.2f}")


if __name__ == "__main__":
    main()
