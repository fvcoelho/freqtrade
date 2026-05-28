"""
SV67 Group Scanner — test each group individually with real backtest.
"""
import json
import subprocess
import re
from pathlib import Path

CONFIG_PATH = Path("user_data/strategies/sv67_config.json")
BT_CONFIG = "user_data/configs/config_sv67_backtest.json"
TIMERANGE = "20260115-20260520"

# All candidate groups
GROUPS = {
    # Original 3
    "AMD_MU":       (["XYZ-AMD/USDC:USDC"], ["XYZ-MU/USDC:USDC"]),
    "COIN_MSTR":    (["XYZ-COIN/USDC:USDC"], ["XYZ-MSTR/USDC:USDC"]),
    "MSFT_AAPL":    (["XYZ-MSFT/USDC:USDC"], ["XYZ-AAPL/USDC:USDC"]),
    # Extra candidates
    "MU_SNDK":      (["XYZ-MU/USDC:USDC"], ["XYZ-SNDK/USDC:USDC"]),
    "NVDA_GOOGL":   (["XYZ-NVDA/USDC:USDC"], ["XYZ-GOOGL/USDC:USDC"]),
    "GOOGL_META":   (["XYZ-GOOGL/USDC:USDC"], ["XYZ-META/USDC:USDC"]),
    "AMZN_META":    (["XYZ-AMZN/USDC:USDC"], ["XYZ-META/USDC:USDC"]),
    "TSLA_PLTR":    (["XYZ-TSLA/USDC:USDC"], ["XYZ-PLTR/USDC:USDC"]),
    "AMD_INTC":     (["XYZ-AMD/USDC:USDC"], ["XYZ-INTC/USDC:USDC"]),
    "NFLX_META":    (["XYZ-NFLX/USDC:USDC"], ["XYZ-META/USDC:USDC"]),
    "NVDA_AMD":     (["XYZ-NVDA/USDC:USDC"], ["XYZ-AMD/USDC:USDC"]),
    "GOOGL_AMZN":   (["XYZ-GOOGL/USDC:USDC"], ["XYZ-AMZN/USDC:USDC"]),
    # Multi-pair
    "NVDA_AMD+INTC": (["XYZ-NVDA/USDC:USDC"], ["XYZ-AMD/USDC:USDC", "XYZ-INTC/USDC:USDC"]),
    "GOOGL_META+AMZN": (["XYZ-GOOGL/USDC:USDC"], ["XYZ-META/USDC:USDC", "XYZ-AMZN/USDC:USDC"]),
    "AAPL_MSFT+GOOGL": (["XYZ-AAPL/USDC:USDC"], ["XYZ-MSFT/USDC:USDC", "XYZ-GOOGL/USDC:USDC"]),
}


def run_single_group(name, sub1, sub2):
    # Build config with only this group
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)

    cfg["groups"] = {"A": {"sub1": sub1, "sub2": sub2}}
    cfg["entry_modes"] = {"A": {"sub1_long": True, "sub1_short": True, "sub2_long": True, "sub2_short": True}}
    cfg["risk"]["max_open_trades"] = 1
    cfg["risk"]["leverage"] = 1

    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=4)

    # Update whitelist
    all_pairs = list(set(sub1 + sub2))
    with open(BT_CONFIG) as f:
        bt = json.load(f)
    bt["exchange"]["pair_whitelist"] = all_pairs
    bt["max_open_trades"] = 1
    with open(BT_CONFIG, "w") as f:
        json.dump(bt, f)

    cmd = [
        ".venv/bin/freqtrade", "backtesting",
        "--config", BT_CONFIG,
        "--strategy-path", "user_data/strategies",
        "--timerange", TIMERANGE,
        "--timeframe", "5m",
        "--cache", "none",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    output = result.stdout + result.stderr

    pattern = r"ZScoreSV67Strategy\s*│\s*(\d+)\s*│\s*([-\d.]+)\s*│\s*([-\d.]+)\s*│\s*([-\d.]+)\s*│\s*(\S+)\s*│\s*(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)"
    m = re.search(pattern, output)
    if m:
        return {
            "name": name, "trades": int(m.group(1)),
            "avg_p": float(m.group(2)), "tot_usdc": float(m.group(3)),
            "tot_pct": float(m.group(4)), "duration": m.group(5),
            "wins": int(m.group(6)), "losses": int(m.group(8)),
            "win_pct": float(m.group(9)),
        }
    # Check for errors
    if "No pair in whitelist" in output:
        return {"name": name, "error": "no_pairs"}
    if "No data found" in output:
        return {"name": name, "error": "no_data"}
    return {"name": name, "error": "parse_fail"}


def main():
    print(f"SV67 Group Scanner — testing {len(GROUPS)} groups individually")
    print(f"Period: {TIMERANGE}, 1x leverage, reversion exit only\n")

    results = []
    for i, (name, (sub1, sub2)) in enumerate(GROUPS.items(), 1):
        print(f"[{i}/{len(GROUPS)}] {name}...", end=" ", flush=True)
        r = run_single_group(name, sub1, sub2)
        results.append(r)
        if "error" in r:
            print(f"ERROR: {r['error']}")
        else:
            print(f"{r['trades']} trades, {r['win_pct']:.1f}% win, {r['tot_pct']:+.1f}%")

    print(f"\n{'Group':>18} | {'Trades':>6} | {'Win%':>6} | {'AvgP%':>7} | {'TotP%':>8} | {'Duration':>8}")
    print("-" * 70)
    for r in sorted(results, key=lambda x: x.get("tot_pct", -999), reverse=True):
        if "error" in r:
            print(f"{r['name']:>18} | ERROR: {r['error']}")
            continue
        print(f"{r['name']:>18} | {r['trades']:>6} | {r['win_pct']:>5.1f}% | "
              f"{r['avg_p']:>6.2f}% | {r['tot_pct']:>+7.1f}% | {r['duration']:>8}")


if __name__ == "__main__":
    main()
