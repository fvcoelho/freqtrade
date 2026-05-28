"""
V54 Hedge Twin Test
====================

Lógica original V54: LONG XRP quando spread_z < -2.1 (XRP barato vs SOL+LINK)
Hedge Twin: se após 15min (3 candles) o trade está negativo,
            abrir o oposto (LONG SOL ou LINK — o lado "caro" que está a ganhar)

Simula ambos os cenários:
  A) V54 normal (sem hedge)
  B) V54 + hedge twin após 15min se perdendo

Inclui fees.
"""
import numpy as np
import pandas as pd
from pathlib import Path

DATA_DIR = Path("user_data/data/hyperliquid/futures")
START, END = "2026-01-01", "2026-05-19"
FEE_RT = 0.0009

# V54 params
ZSCORE_WINDOW = 288
ENTRY_Z = 2.1
EXIT_Z = 0.2
STOPLOSS = -0.07
TIME_STOP = 24  # candles
HEDGE_AFTER = 3  # candles (15min)
HEDGE_LOSS_THRESHOLD = 0.0  # hedge if profit <= this (0 = any loss)


def load(coin):
    f = DATA_DIR / f"{coin}_USDC_USDC-5m-futures.feather"
    if not f.exists(): return pd.DataFrame()
    df = pd.read_feather(f)
    return df[(df["date"] >= START) & (df["date"] <= END)].sort_values("date").reset_index(drop=True)


def compute_spread_z(df_sub1, df_sub2_list):
    """Compute cumulative return spread z-score between sub1 and avg(sub2)."""
    ret1 = np.log(df_sub1["close"] / df_sub1["close"].shift(1)).cumsum()

    ret2_list = []
    for df2 in df_sub2_list:
        r = np.log(df2["close"] / df2["close"].shift(1)).cumsum()
        ret2_list.append(r.values)

    ret2_avg = np.mean(ret2_list, axis=0)
    spread = ret1.values - ret2_avg

    spread_series = pd.Series(spread)
    spread_mean = spread_series.rolling(ZSCORE_WINDOW).mean()
    spread_std = spread_series.rolling(ZSCORE_WINDOW).std().replace(0, np.nan)
    spread_z = ((spread_series - spread_mean) / spread_std).fillna(0)

    return spread_z.values


def simulate_group(sub1_coin, sub2_coins, group_name, allow_long=True, allow_short=True):
    """Simulate V54 trades for one group, with and without hedge twin."""
    df_sub1 = load(sub1_coin)
    df_sub2 = [load(c) for c in sub2_coins]

    if df_sub1.empty or any(d.empty for d in df_sub2):
        return [], []

    # Align lengths
    min_len = min(len(df_sub1), *[len(d) for d in df_sub2])
    df_sub1 = df_sub1.tail(min_len).reset_index(drop=True)
    df_sub2 = [d.tail(min_len).reset_index(drop=True) for d in df_sub2]

    spread_z = compute_spread_z(df_sub1, df_sub2)
    close_sub1 = df_sub1["close"].values
    # Use first sub2 as hedge target
    close_sub2 = df_sub2[0]["close"].values
    n = len(df_sub1)

    trades_normal = []
    trades_hedge = []

    i = ZSCORE_WINDOW
    while i < n - TIME_STOP:
        sz = spread_z[i]

        # Entry: spread_z < -ENTRY_Z → LONG sub1 (sub1 cheap)
        if sz < -ENTRY_Z and allow_long:
            entry_price = close_sub1[i]
            entry_idx = i
            side = "long"
            hedge_opened = False
            hedge_entry_price = 0
            hedge_entry_idx = 0

            # Walk forward
            for j in range(i + 1, min(i + TIME_STOP, n)):
                current_price = close_sub1[j]
                profit = (current_price - entry_price) / entry_price
                bars = j - entry_idx
                sz_now = spread_z[j]

                # --- HEDGE TWIN CHECK ---
                if bars == HEDGE_AFTER and profit <= HEDGE_LOSS_THRESHOLD and not hedge_opened:
                    hedge_opened = True
                    hedge_entry_price = close_sub2[j]
                    hedge_entry_idx = j

                # Exit conditions for primary
                exit_reason = None
                if sz_now >= -EXIT_Z:
                    exit_reason = "revert"
                elif profit <= STOPLOSS:
                    exit_reason = "stop_loss"
                elif bars >= TIME_STOP:
                    exit_reason = "time_stop"

                if exit_reason:
                    final_profit = profit - FEE_RT
                    trades_normal.append({
                        "pair": sub1_coin, "side": side, "profit": final_profit,
                        "bars": bars, "exit": exit_reason, "group": group_name
                    })

                    # Also close hedge if open
                    if hedge_opened:
                        # Hedge is LONG sub2 (opposite side of spread)
                        hedge_profit = (close_sub2[j] - hedge_entry_price) / hedge_entry_price - FEE_RT
                        trades_hedge.append({
                            "pair": sub2_coins[0], "side": "long_hedge",
                            "profit": hedge_profit, "bars": j - hedge_entry_idx,
                            "exit": "with_primary", "group": group_name,
                            "primary_profit": final_profit,
                        })

                    i = j + 1
                    break
            else:
                i += 1
            continue

        # Entry: spread_z > ENTRY_Z → SHORT sub1 (sub1 expensive)
        elif sz > ENTRY_Z and allow_short:
            entry_price = close_sub1[i]
            entry_idx = i
            side = "short"
            hedge_opened = False
            hedge_entry_price = 0
            hedge_entry_idx = 0

            for j in range(i + 1, min(i + TIME_STOP, n)):
                current_price = close_sub1[j]
                profit = (entry_price - current_price) / entry_price
                bars = j - entry_idx
                sz_now = spread_z[j]

                if bars == HEDGE_AFTER and profit <= HEDGE_LOSS_THRESHOLD and not hedge_opened:
                    hedge_opened = True
                    hedge_entry_price = close_sub2[j]
                    hedge_entry_idx = j

                exit_reason = None
                if sz_now <= EXIT_Z:
                    exit_reason = "revert"
                elif profit <= STOPLOSS:
                    exit_reason = "stop_loss"
                elif bars >= TIME_STOP:
                    exit_reason = "time_stop"

                if exit_reason:
                    final_profit = profit - FEE_RT
                    trades_normal.append({
                        "pair": sub1_coin, "side": side, "profit": final_profit,
                        "bars": bars, "exit": exit_reason, "group": group_name
                    })

                    if hedge_opened:
                        # Hedge is SHORT sub2
                        hedge_profit = (hedge_entry_price - close_sub2[j]) / hedge_entry_price - FEE_RT
                        trades_hedge.append({
                            "pair": sub2_coins[0], "side": "short_hedge",
                            "profit": hedge_profit, "bars": j - hedge_entry_idx,
                            "exit": "with_primary", "group": group_name,
                            "primary_profit": final_profit,
                        })

                    i = j + 1
                    break
            else:
                i += 1
            continue

        i += 1

    return trades_normal, trades_hedge


def print_stats(label, trades):
    if not trades:
        print(f"  {label}: 0 trades")
        return
    profits = [t["profit"] for t in trades]
    wins = sum(1 for p in profits if p > 0)
    print(f"  {label}: {len(trades)} trades, {wins/len(trades)*100:.1f}% win, "
          f"avg={np.mean(profits)*100:.3f}%, total={np.sum(profits)*100:.1f}%")


def main():
    print("V54 Hedge Twin Test — fees included")
    print(f"Hedge after {HEDGE_AFTER} candles ({HEDGE_AFTER*5}min) if losing")
    print(f"Entry: spread_z > {ENTRY_Z}, Exit: revert to {EXIT_Z}")
    print(f"Period: {START} to {END}\n")

    # Group A: XRP vs (SOL+LINK) — LONG only
    print("=== GROUP A: XRP vs (SOL+LINK) — LONG only ===")
    normal_a, hedge_a = simulate_group("XRP", ["SOL", "LINK"], "A", allow_long=True, allow_short=False)
    print_stats("Normal", normal_a)
    print_stats("Hedge twins", hedge_a)

    # Group B: BTC+SOL vs ETH — LONG+SHORT (simplified: use BTC as sub1)
    print("\n=== GROUP B: BTC vs ETH — LONG+SHORT ===")
    normal_b, hedge_b = simulate_group("BTC", ["ETH"], "B", allow_long=True, allow_short=True)
    print_stats("Normal", normal_b)
    print_stats("Hedge twins", hedge_b)

    # Group B alt: SOL vs ETH
    print("\n=== GROUP B alt: SOL vs ETH — LONG+SHORT ===")
    normal_b2, hedge_b2 = simulate_group("SOL", ["ETH"], "B2", allow_long=True, allow_short=True)
    print_stats("Normal", normal_b2)
    print_stats("Hedge twins", hedge_b2)

    # Combined
    all_normal = normal_a + normal_b + normal_b2
    all_hedge = hedge_a + hedge_b + hedge_b2

    print(f"\n{'='*60}")
    print("COMBINED RESULTS")
    print(f"{'='*60}")

    print("\nA) V54 NORMAL (sem hedge):")
    print_stats("All trades", all_normal)

    print("\nB) V54 + HEDGE TWINS:")
    combined = all_normal + all_hedge
    print_stats("All trades (primary + hedge)", combined)

    print("\nC) HEDGE TWINS ONLY:")
    print_stats("Only hedge trades", all_hedge)

    # Analyse: when hedge helps vs hurts
    if all_hedge:
        hedge_helped = [h for h in all_hedge if h["primary_profit"] < 0 and h["profit"] > abs(h["primary_profit"])]
        hedge_partial = [h for h in all_hedge if h["primary_profit"] < 0 and h["profit"] > 0]
        hedge_hurt = [h for h in all_hedge if h["profit"] < 0]
        print(f"\n  Hedge fully compensated loss: {len(hedge_helped)} trades")
        print(f"  Hedge partially helped (positive): {len(hedge_partial)} trades")
        print(f"  Hedge also lost: {len(hedge_hurt)} trades")

    # Test different hedge timings
    print(f"\n{'='*60}")
    print("HEDGE TIMING SCAN (candles after entry to open hedge)")
    print(f"{'='*60}")
    import sys
    mod = sys.modules[__name__]
    for delay in [1, 2, 3, 5, 8, 12]:
        mod.HEDGE_AFTER = delay
        n_a, h_a = simulate_group("XRP", ["SOL", "LINK"], "A", True, False)
        n_b, h_b = simulate_group("BTC", ["ETH"], "B", True, True)
        n_b2, h_b2 = simulate_group("SOL", ["ETH"], "B2", True, True)

        all_n = n_a + n_b + n_b2
        all_h = h_a + h_b + h_b2
        combined = all_n + all_h

        if combined:
            p = [t["profit"] for t in combined]
            w = sum(1 for x in p if x > 0)
            hp = [t["profit"] for t in all_h]
            print(f"  delay={delay:>2} ({delay*5:>3}min): "
                  f"primary={len(all_n)}, hedges={len(all_h)}, "
                  f"combined_total={np.sum(p)*100:>7.1f}%, "
                  f"hedge_avg={np.mean(hp)*100:>7.3f}%" if hp else "no hedges")


if __name__ == "__main__":
    main()
