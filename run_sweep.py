"""Run a strategy x combo sweep and collect summary metrics."""
import json
import os
import subprocess
import sys
import zipfile
import glob
from pathlib import Path

ROOT = Path("/root/freqtrade")
COMBOS_PATH = ROOT / "user_data/scanner/pair_combos.json"
CFG_TPL = ROOT / "user_data/configs/config_binance_research_bt.json"
CFG_OUT = ROOT / f"user_data/configs/config_sweep_{os.environ.get('SWEEP_TF','20m')}.json"
RESULTS_DIR = ROOT / "user_data/backtest_results"

STRATS_15M = ["ZScorePairsTradingV24", "ZScorePTV25", "ZScorePTV26", "ZScorePTV27", "ZScorePTNeutral1"]
COMBOS = ["C1_AVAXETH_SUISOL", "C2_BTCETH_SOLLINK", "C3_DOGEXRP_SUIAVAX", "C4_ETHXRP_LINKSOL", "C5_AVAXSUI_LINKADA"]
TIMEFRAME = os.environ.get("SWEEP_TF", "20m")
TIMERANGE = "20250502-20260502"
OUT_NAME = f"sweep_results_{TIMEFRAME}_y1.json"


def set_active(combo_name):
    with open(COMBOS_PATH) as f:
        d = json.load(f)
    d["active_combo"] = combo_name
    with open(COMBOS_PATH, "w") as f:
        json.dump(d, f, indent=4)
    return d["combos"][combo_name]


def write_config(combo_data, strategy):
    with open(CFG_TPL) as f:
        c = json.load(f)
    c["strategy"] = strategy
    c["exchange"]["pair_whitelist"] = combo_data["group_a"] + combo_data["group_b"]
    c["max_open_trades"] = 4
    with open(CFG_OUT, "w") as f:
        json.dump(c, f, indent=2)


def latest_result():
    files = sorted(glob.glob(str(RESULTS_DIR / "*.zip")))
    return files[-1] if files else None


def parse_result(zp):
    base = os.path.basename(zp).replace(".zip", "")
    try:
        with zipfile.ZipFile(zp) as z:
            with z.open(base + ".json") as f:
                d = json.load(f)
    except Exception as e:
        return None
    s = list(d.get("strategy", {}).values())
    if not s:
        return None
    s = s[0]
    return {
        "trades": s.get("total_trades", 0),
        "profit_pct": s.get("profit_total", 0) * 100,
        "profit_abs": s.get("profit_total_abs", 0),
        "cagr": s.get("cagr", 0),
        "sharpe": s.get("sharpe", 0),
        "sortino": s.get("sortino", 0),
        "calmar": s.get("calmar", 0),
        "max_dd": (s.get("max_drawdown_account") or 0) * 100,
        "winrate": (s.get("winrate") or 0) * 100,
        "profit_factor": s.get("profit_factor", 0),
        "long_trades": s.get("trade_count_long", 0),
        "short_trades": s.get("trade_count_short", 0),
    }


def run_one(strategy, combo_name):
    combo_data = set_active(combo_name)
    write_config(combo_data, strategy)
    cmd = [
        ".venv/bin/freqtrade",
        "backtesting",
        "-c", str(CFG_OUT),
        "-s", strategy,
        "--timerange", TIMERANGE,
        "--timeframe", TIMEFRAME,
        "--cache", "none",
    ]
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        return {"error": proc.stderr[-500:]}
    z = latest_result()
    metrics = parse_result(z)
    return metrics or {"error": "could not parse result"}


def main():
    out = []
    total = len(STRATS_15M) * len(COMBOS)
    i = 0
    for strat in STRATS_15M:
        for combo in COMBOS:
            i += 1
            print(f"[{i}/{total}] {strat} x {combo} ... ", flush=True, end="")
            r = run_one(strat, combo)
            r["strategy"] = strat
            r["combo"] = combo
            out.append(r)
            if "error" in r:
                print(f"ERROR: {r['error'][:200]}")
            else:
                print(f"profit={r['profit_pct']:+.2f}% sharpe={r['sharpe']:+.2f} dd={r['max_dd']:.1f}% trades={r['trades']}")
    with open(ROOT / OUT_NAME, "w") as f:
        json.dump(out, f, indent=2)
    print("\n=== Saved to sweep_results.json ===")


if __name__ == "__main__":
    main()
