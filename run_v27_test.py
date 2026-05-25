"""Test V27 baseline + V27NoWE on T3 across all walk-forward windows."""
import json, os, subprocess, glob, zipfile
from pathlib import Path

ROOT = Path("/root/freqtrade")
COMBOS_PATH = ROOT / "user_data/scanner/pair_combos.json"
CFG_TPL = ROOT / "user_data/configs/config_binance_research_bt.json"
CFG_OUT = ROOT / "user_data/configs/config_v27_test.json"
RESULTS = ROOT / "user_data/backtest_results"

TIMEFRAME = "20m"
COMBO = {
    "id": "T3_BTCXRP_vs_ADAAVAX",
    "group_a": ["BTC/USDT:USDT", "XRP/USDT:USDT"],
    "group_b": ["ADA/USDT:USDT", "AVAX/USDT:USDT"],
}
STRATEGIES = ["ZScorePTV27", "ZScorePTV27NoWE"]
WINDOWS = [
    ("Last_month_Apr26", "20260402-20260502"),
    ("Last_3_months",    "20260202-20260502"),
    ("Q1_May-Jul25",     "20250502-20250802"),
    ("Q2_Aug-Oct25",     "20250802-20251102"),
    ("Q3_Nov-Jan26",     "20251102-20260202"),
    ("Q4_Feb-Apr26",     "20260202-20260502"),
    ("Full_year",        "20250502-20260502"),
]


def upsert():
    with open(COMBOS_PATH) as f: d = json.load(f)
    d["combos"][COMBO["id"]] = {"description": COMBO["id"], **{k: v for k, v in COMBO.items() if k != "id"}}
    d["active_combo"] = COMBO["id"]
    with open(COMBOS_PATH, "w") as f: json.dump(d, f, indent=4)


def write_cfg(strat):
    with open(CFG_TPL) as f: c = json.load(f)
    c["strategy"] = strat
    c["exchange"]["pair_whitelist"] = COMBO["group_a"] + COMBO["group_b"]
    c["max_open_trades"] = 4
    with open(CFG_OUT, "w") as f: json.dump(c, f, indent=2)


def latest():
    return sorted(glob.glob(str(RESULTS / "*.zip")))[-1]


def parse(zp):
    base = os.path.basename(zp).replace(".zip", "")
    with zipfile.ZipFile(zp) as z:
        with z.open(base + ".json") as f: d = json.load(f)
    s = list(d["strategy"].values())[0]
    return {
        "trades": s.get("total_trades", 0),
        "profit_pct": s.get("profit_total", 0) * 100,
        "cagr": s.get("cagr", 0),
        "sharpe": s.get("sharpe", 0),
        "sortino": s.get("sortino", 0),
        "calmar": s.get("calmar", 0),
        "max_dd": (s.get("max_drawdown_account") or 0) * 100,
        "winrate": (s.get("winrate") or 0) * 100,
        "profit_factor": s.get("profit_factor", 0),
    }


def main():
    upsert()
    out = []
    total = len(STRATEGIES) * len(WINDOWS); i = 0
    for strat in STRATEGIES:
        write_cfg(strat)
        for win, rng in WINDOWS:
            i += 1
            cmd = [".venv/bin/freqtrade", "backtesting",
                   "-c", str(CFG_OUT), "-s", strat,
                   "--timerange", rng, "--timeframe", TIMEFRAME, "--cache", "none"]
            proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=600)
            if proc.returncode != 0:
                r = {"error": proc.stderr[-300:]}
            else:
                try: r = parse(latest())
                except Exception as e: r = {"error": f"parse: {e}"}
            r["strategy"] = strat; r["window"] = win
            out.append(r)
            if "error" in r:
                print(f"[{i:>2}/{total}] {strat:<20} {win:<18} ERROR: {r['error'][:100]}", flush=True)
            else:
                print(f"[{i:>2}/{total}] {strat:<20} {win:<18} profit={r['profit_pct']:+7.2f}% sharpe={r['sharpe']:+5.2f} dd={r['max_dd']:5.1f}% trades={r['trades']:>4}", flush=True)
    with open(ROOT / "v27_test_results.json", "w") as f:
        json.dump(out, f, indent=2)
    print("\n=== Saved to v27_test_results.json ===", flush=True)


if __name__ == "__main__":
    main()
