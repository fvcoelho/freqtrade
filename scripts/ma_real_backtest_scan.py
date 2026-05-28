"""
Scan MA periods 4-20 using REAL freqtrade backtests.
Modifies v66_config.json for each MA, runs backtest, collects results.
"""
import json
import subprocess
import re
from pathlib import Path

CONFIG_PATH = Path("user_data/strategies/v66_config.json")
BT_CONFIG = "user_data/configs/config_v66_backtest.json"
TIMERANGE = "20260101-20260520"

# Test these MA periods
MA_PERIODS = [4, 6, 8, 10, 12, 14, 16, 18, 20]

# Also test entry thresholds
ENTRY_THRESHOLDS = [1.5, 2.0, 2.5, 3.0]

# Fixed regime (tight)
REGIME_MOM = 0.5
REGIME_ATR = 0.5


def run_backtest(ma: int, entry_th: float) -> dict:
    """Modify config and run backtest, return summary."""
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)

    cfg["ma"]["period"] = ma
    cfg["ma"]["entry_threshold"] = entry_th
    cfg["startup_candle_count"] = max(200, ma * 10)
    cfg["regime"]["trending_btc_mom"] = REGIME_MOM
    cfg["regime"]["trending_atr_z"] = REGIME_ATR

    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=4)

    cmd = [
        ".venv/bin/freqtrade", "backtesting",
        "--config", BT_CONFIG,
        "--strategy-path", "user_data/strategies",
        "--timerange", TIMERANGE,
        "--timeframe", "5m",
        "--cache", "none",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    output = result.stdout + result.stderr

    # Parse summary line
    # │ ZScoreV66Strategy │   1490 │        -0.06 │         -19.046 │       -19.05 │      0:42:00 │  833     0   657  55.9 │ 19.076 USDC  19.07% │
    pattern = r"ZScoreV66Strategy\s*│\s*(\d+)\s*│\s*([-\d.]+)\s*│\s*([-\d.]+)\s*│\s*([-\d.]+)\s*│\s*(\S+)\s*│\s*(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)"
    m = re.search(pattern, output)
    if m:
        return {
            "ma": ma,
            "entry_th": entry_th,
            "trades": int(m.group(1)),
            "avg_profit": float(m.group(2)),
            "tot_profit_usdc": float(m.group(3)),
            "tot_profit_pct": float(m.group(4)),
            "duration": m.group(5),
            "wins": int(m.group(6)),
            "draws": int(m.group(7)),
            "losses": int(m.group(8)),
            "win_pct": float(m.group(9)),
        }
    return {"ma": ma, "entry_th": entry_th, "trades": 0, "error": "parse_failed"}


def main():
    results = []
    total = len(MA_PERIODS) * len(ENTRY_THRESHOLDS)
    i = 0

    for entry_th in ENTRY_THRESHOLDS:
        for ma in MA_PERIODS:
            i += 1
            print(f"[{i}/{total}] MA={ma}, entry={entry_th}σ ...", end=" ", flush=True)
            r = run_backtest(ma, entry_th)
            results.append(r)
            if "error" in r:
                print(f"ERROR: {r['error']}")
            else:
                print(f"trades={r['trades']}, win={r['win_pct']:.1f}%, profit={r['tot_profit_pct']:.1f}%")

    # Print summary table
    print(f"\n{'='*90}")
    print(f"{'MA':>3} | {'Entry':>5} | {'Trades':>6} | {'Win%':>6} | {'AvgP%':>7} | {'TotP%':>8} | {'TotUSDC':>8} | {'Duration':>8}")
    print("-" * 90)

    for r in sorted(results, key=lambda x: x.get("tot_profit_pct", -999), reverse=True):
        if "error" in r:
            print(f"{r['ma']:>3} | {r['entry_th']:>5.1f} | ERROR")
            continue
        print(f"{r['ma']:>3} | {r['entry_th']:>5.1f} | {r['trades']:>6} | {r['win_pct']:>5.1f}% | "
              f"{r['avg_profit']:>6.2f}% | {r['tot_profit_pct']:>7.1f}% | {r['tot_profit_usdc']:>7.1f} | {r['duration']:>8}")

    # Best result
    valid = [r for r in results if "error" not in r and r["trades"] >= 10]
    if valid:
        best = max(valid, key=lambda x: x["tot_profit_pct"])
        print(f"\nBEST: MA={best['ma']}, entry={best['entry_th']}σ → "
              f"{best['tot_profit_pct']:.1f}%, {best['win_pct']:.1f}% win, {best['trades']} trades")


if __name__ == "__main__":
    main()
