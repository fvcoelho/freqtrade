"""Test V26 + V28L6 + V28L8 + V28L12 on T3 combo over last month."""
import json, os, subprocess, glob, zipfile
from pathlib import Path

ROOT = Path("/root/freqtrade")
COMBOS_PATH = ROOT / "user_data/scanner/pair_combos.json"
CFG_TPL = ROOT / "user_data/configs/config_binance_research_bt.json"
CFG_OUT = ROOT / "user_data/configs/config_lev_test.json"
RESULTS = ROOT / "user_data/backtest_results"

TIMEFRAME = "20m"

# T3 (most robust walk-forward winner)
COMBO = {
    "id": "T3_BTCXRP_vs_ADAAVAX",
    "group_a": ["BTC/USDT:USDT", "XRP/USDT:USDT"],
    "group_b": ["ADA/USDT:USDT", "AVAX/USDT:USDT"],
}

STRATEGIES = ["ZScorePTV26", "ZScorePTV28L6", "ZScorePTV28L8", "ZScorePTV28L12"]
WINDOWS = [
    ("Last_month_Apr26",     "20260402-20260502"),
    ("Last_3_months",        "20260202-20260502"),
    ("Q4_only",              "20260202-20260502"),  # same as last_3
    ("Full_year",            "20250502-20260502"),
]
# Dedup
WINDOWS = [
    ("Last_month_Apr26",     "20260402-20260502"),
    ("Last_3_months",        "20260202-20260502"),
    ("Full_year",            "20250502-20260502"),
]


def upsert_combo():
    with open(COMBOS_PATH) as f: d = json.load(f)
    d["combos"][COMBO["id"]] = {
        "description": COMBO["id"],
        "group_a": COMBO["group_a"],
        "group_b": COMBO["group_b"],
    }
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
        "profit_abs": s.get("profit_total_abs", 0),
        "cagr": s.get("cagr", 0),
        "sharpe": s.get("sharpe", 0),
        "sortino": s.get("sortino", 0),
        "calmar": s.get("calmar", 0),
        "max_dd": (s.get("max_drawdown_account") or 0) * 100,
        "winrate": (s.get("winrate") or 0) * 100,
        "profit_factor": s.get("profit_factor", 0),
        "best_trade": s.get("best_trade", 0)*100,
        "worst_trade": s.get("worst_trade", 0)*100,
        "long_trades": s.get("trade_count_long", 0),
        "short_trades": s.get("trade_count_short", 0),
    }


def main():
    upsert_combo()
    out = []
    total = len(STRATEGIES) * len(WINDOWS)
    i = 0
    for strat in STRATEGIES:
        write_cfg(strat)
        for win_name, win_range in WINDOWS:
            i += 1
            cmd = [".venv/bin/freqtrade", "backtesting",
                   "-c", str(CFG_OUT), "-s", strat,
                   "--timerange", win_range, "--timeframe", TIMEFRAME,
                   "--cache", "none"]
            proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=600)
            if proc.returncode != 0:
                r = {"error": proc.stderr[-500:]}
            else:
                try:
                    r = parse(latest())
                except Exception as e:
                    r = {"error": f"parse: {e}"}
            r["strategy"] = strat
            r["window"] = win_name
            r["timerange"] = win_range
            out.append(r)
            if "error" in r:
                print(f"[{i:>2}/{total}] {strat:<18} {win_name:<18} ERROR: {r['error'][:120]}", flush=True)
            else:
                print(f"[{i:>2}/{total}] {strat:<18} {win_name:<18} profit={r['profit_pct']:+7.2f}% sharpe={r['sharpe']:+5.2f} dd={r['max_dd']:5.1f}% trades={r['trades']:>4}", flush=True)
    with open(ROOT / "leverage_test_results.json", "w") as f:
        json.dump(out, f, indent=2)
    print("\n=== Saved to leverage_test_results.json ===", flush=True)


if __name__ == "__main__":
    main()
