"""
Volume Analysis for MA=14 Mean-Reversion Trades
================================================

Analisa o volume relativo (vol_ratio = volume / MA_volume) no momento da entrada.
Compara winners vs losers para encontrar o filtro de volume ideal.
"""
import numpy as np
import pandas as pd
from pathlib import Path

DATA_DIR = Path("user_data/data/hyperliquid/futures")

PAIRS = ["ETH", "SOL", "XRP", "LINK", "SUI", "DOGE", "HYPE", "ONDO", "TON", "ZEC"]
BTC_PAIR = "BTC"
TIMERANGE_START = "2026-01-01"
TIMERANGE_END = "2026-05-19"

# Regime
BTC_MOM_PERIOD = 4
BTC_MOM_THRESHOLD = 2.0
BTC_ATR_PERIOD = 14
BTC_ATR_Z_THRESHOLD = 2.0
BTC_ATR_Z_WINDOW = 144

# Trade params
MA_PERIOD = 14
ENTRY_THRESHOLD = 2.0
EXIT_THRESHOLD = 0.3
MAX_CANDLES = 24
STOPLOSS = -0.07

# Volume MA windows to test
VOL_MA_WINDOWS = [14, 24, 48, 72, 144]


def load_pair(coin):
    f = DATA_DIR / f"{coin}_USDC_USDC-5m-futures.feather"
    if not f.exists():
        return pd.DataFrame()
    df = pd.read_feather(f)
    df = df[(df["date"] >= TIMERANGE_START) & (df["date"] <= TIMERANGE_END)].copy()
    return df.sort_values("date").reset_index(drop=True)


def compute_btc_regime(btc_df):
    mom_lookback = BTC_MOM_PERIOD * 12
    btc_df["btc_mom"] = (btc_df["close"] / btc_df["close"].shift(mom_lookback) - 1) * 100
    high, low = btc_df["high"], btc_df["low"]
    close_prev = btc_df["close"].shift(1)
    tr = pd.concat([high - low, (high - close_prev).abs(), (low - close_prev).abs()], axis=1).max(axis=1)
    atr = tr.rolling(BTC_ATR_PERIOD * 12).mean()
    atr_mean = atr.rolling(BTC_ATR_Z_WINDOW).mean()
    atr_std = atr.rolling(BTC_ATR_Z_WINDOW).std().replace(0, np.nan)
    btc_df["btc_atr_z"] = ((atr - atr_mean) / atr_std).fillna(0)
    btc_df["is_ranging"] = ~((btc_df["btc_mom"].abs() > BTC_MOM_THRESHOLD) | (btc_df["btc_atr_z"] > BTC_ATR_Z_THRESHOLD))
    return btc_df[["date", "is_ranging"]].copy()


def simulate_with_volume(pair_df, regime_df, vol_ma_window):
    df = pair_df.merge(regime_df, on="date", how="left")
    df["is_ranging"] = df["is_ranging"].fillna(False)

    df["ma"] = df["close"].rolling(MA_PERIOD).mean()
    df["ma_std"] = df["close"].rolling(MA_PERIOD).std().replace(0, np.nan)
    df["deviation"] = ((df["close"] - df["ma"]) / df["ma_std"]).fillna(0)

    # Volume ratio
    df["vol_ma"] = df["volume"].rolling(vol_ma_window).mean()
    df["vol_ratio"] = (df["volume"] / df["vol_ma"].replace(0, np.nan)).fillna(1.0)

    trades = []
    in_trade = False

    for i in range(max(MA_PERIOD, vol_ma_window), len(df)):
        if not in_trade:
            if not df["is_ranging"].iloc[i]:
                continue
            dev = df["deviation"].iloc[i]
            if abs(dev) < ENTRY_THRESHOLD:
                continue

            in_trade = True
            entry_price = df["close"].iloc[i]
            entry_idx = i
            is_short = dev > ENTRY_THRESHOLD
            entry_vol_ratio = df["vol_ratio"].iloc[i]
            entry_volume = df["volume"].iloc[i]
            entry_vol_ma = df["vol_ma"].iloc[i]

        else:
            current_price = df["close"].iloc[i]
            dev = df["deviation"].iloc[i]
            candles_held = i - entry_idx

            profit = (entry_price - current_price) / entry_price if is_short else (current_price - entry_price) / entry_price

            exit_reason = None
            if not is_short and dev >= -EXIT_THRESHOLD:
                exit_reason = "revert"
            elif is_short and dev <= EXIT_THRESHOLD:
                exit_reason = "revert"
            if candles_held >= MAX_CANDLES:
                exit_reason = "time_stop"
            if profit <= STOPLOSS:
                exit_reason = "stop_loss"

            if exit_reason:
                trades.append({
                    "profit": profit,
                    "vol_ratio": entry_vol_ratio,
                    "volume": entry_volume,
                    "vol_ma": entry_vol_ma,
                    "win": profit > 0,
                    "candles": candles_held,
                })
                in_trade = False

    return trades


def main():
    print("Loading BTC regime...")
    btc_df = load_pair(BTC_PAIR)
    regime_df = compute_btc_regime(btc_df)

    for vol_window in VOL_MA_WINDOWS:
        print(f"\n{'='*70}")
        print(f"VOLUME MA WINDOW = {vol_window} candles ({vol_window*5} min)")
        print(f"{'='*70}")

        all_trades = []
        for coin in PAIRS:
            pair_df = load_pair(coin)
            if pair_df.empty:
                continue
            trades = simulate_with_volume(pair_df, regime_df, vol_window)
            all_trades.extend(trades)

        if not all_trades:
            print("No trades")
            continue

        df = pd.DataFrame(all_trades)

        # Overall stats
        print(f"\nTotal trades: {len(df)}, Win rate: {df['win'].mean()*100:.1f}%")
        print(f"Vol ratio — mean: {df['vol_ratio'].mean():.2f}, "
              f"median: {df['vol_ratio'].median():.2f}, "
              f"p25: {df['vol_ratio'].quantile(0.25):.2f}, "
              f"p75: {df['vol_ratio'].quantile(0.75):.2f}")

        # Winners vs Losers volume
        winners = df[df["win"]]
        losers = df[~df["win"]]
        print(f"\nWINNERS ({len(winners)}): vol_ratio mean={winners['vol_ratio'].mean():.3f}, median={winners['vol_ratio'].median():.3f}")
        print(f"LOSERS  ({len(losers)}):  vol_ratio mean={losers['vol_ratio'].mean():.3f}, median={losers['vol_ratio'].median():.3f}")

        # Win rate by volume bucket
        print(f"\n{'Vol Ratio Range':>20} | {'Trades':>6} | {'Win%':>6} | {'AvgP%':>7} | {'TotP%':>8}")
        print("-" * 65)

        buckets = [
            (0.0, 0.3, "< 0.3 (very low)"),
            (0.3, 0.5, "0.3 - 0.5 (low)"),
            (0.5, 0.8, "0.5 - 0.8 (below avg)"),
            (0.8, 1.2, "0.8 - 1.2 (normal)"),
            (1.2, 1.5, "1.2 - 1.5 (above avg)"),
            (1.5, 2.0, "1.5 - 2.0 (high)"),
            (2.0, 3.0, "2.0 - 3.0 (very high)"),
            (3.0, 5.0, "3.0 - 5.0 (spike)"),
            (5.0, 100.0, "> 5.0 (extreme)"),
        ]

        for lo, hi, label in buckets:
            mask = (df["vol_ratio"] >= lo) & (df["vol_ratio"] < hi)
            subset = df[mask]
            if len(subset) == 0:
                continue
            wr = subset["win"].mean() * 100
            avg_p = subset["profit"].mean() * 100
            tot_p = subset["profit"].sum() * 100
            print(f"{label:>20} | {len(subset):>6} | {wr:>5.1f}% | {avg_p:>6.3f}% | {tot_p:>7.1f}%")

        # Find optimal vol_ratio threshold (min vol to enter)
        print(f"\n--- Optimal volume filter (min vol_ratio to enter) ---")
        print(f"{'Min Vol':>8} | {'Trades':>6} | {'Win%':>6} | {'AvgP%':>7} | {'TotP%':>8} | {'Profit/Trade':>12}")
        print("-" * 70)

        for min_vol in [0.0, 0.3, 0.5, 0.7, 0.8, 1.0, 1.2, 1.5, 2.0, 2.5, 3.0]:
            subset = df[df["vol_ratio"] >= min_vol]
            if len(subset) < 10:
                continue
            wr = subset["win"].mean() * 100
            avg_p = subset["profit"].mean() * 100
            tot_p = subset["profit"].sum() * 100
            ppt = tot_p / len(subset)
            print(f"{min_vol:>8.1f} | {len(subset):>6} | {wr:>5.1f}% | {avg_p:>6.3f}% | {tot_p:>7.1f}% | {ppt:>11.4f}%")


if __name__ == "__main__":
    main()
