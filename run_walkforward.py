"""Walk-forward stress test of top 3 V26+20m combos in 3-month windows."""
import json, os, subprocess, glob, zipfile
from pathlib import Path

ROOT = Path("/root/freqtrade")
COMBOS_PATH = ROOT / "user_data/scanner/pair_combos.json"
CFG_TPL = ROOT / "user_data/configs/config_binance_research_bt.json"
CFG_OUT = ROOT / "user_data/configs/config_walkfwd.json"
RESULTS = ROOT / "user_data/backtest_results"

STRATEGY = "ZScorePTV26"
TIMEFRAME = "20m"

# Top 3 combos. NOTE: order within group matters (first pair is "leader").
TOP_COMBOS = [
    {"id": "T1_C2_BTCETH_vs_SOLLINK",  "group_a": ["BTC/USDT:USDT","ETH/USDT:USDT"], "group_b": ["SOL/USDT:USDT","LINK/USDT:USDT"]},
    {"id": "T2_BTCSUI_vs_ADAAVAX",     "group_a": ["BTC/USDT:USDT","SUI/USDT:USDT"], "group_b": ["ADA/USDT:USDT","AVAX/USDT:USDT"]},
    {"id": "T3_BTCXRP_vs_ADAAVAX",     "group_a": ["BTC/USDT:USDT","XRP/USDT:USDT"], "group_b": ["ADA/USDT:USDT","AVAX/USDT:USDT"]},
]

# 4 quarters covering 2025-05-02 -> 2026-05-02
WINDOWS = [
    ("Q1_May-Jul25",  "20250502-20250802"),
    ("Q2_Aug-Oct25",  "20250802-20251102"),
    ("Q3_Nov-Jan26",  "20251102-20260202"),
    ("Q4_Feb-Apr26",  "20260202-20260502"),
]
# Plus full-year for reference
WINDOWS.append(("Full_year",      "20250502-20260502"))


def upsert(combo):
    with open(COMBOS_PATH) as f: d = json.load(f)
    d["combos"][combo["id"]] = {
        "description": combo["id"],
        "group_a": combo["group_a"],
        "group_b": combo["group_b"],
    }
    d["active_combo"] = combo["id"]
    with open(COMBOS_PATH, "w") as f: json.dump(d, f, indent=4)
    return d["combos"][combo["id"]]


def write_cfg(combo):
    with open(CFG_TPL) as f: c = json.load(f)
    c["strategy"] = STRATEGY
    c["exchange"]["pair_whitelist"] = combo["group_a"] + combo["group_b"]
    c["max_open_trades"] = 4
    with open(CFG_OUT, "w") as f: json.dump(c, f, indent=2)


def latest():
    return sorted(glob.glob(str(RESULTS / "*.zip")))[-1]


def parse(zp):
    base = os.path.basename(zp).replace(".zip","")
    with zipfile.ZipFile(zp) as z:
        with z.open(base + ".json") as f: d = json.load(f)
    s = list(d["strategy"].values())[0]
    return {
        "trades": s.get("total_trades",0),
        "profit_pct": s.get("profit_total",0)*100,
        "profit_abs": s.get("profit_total_abs",0),
        "cagr": s.get("cagr",0),
        "sharpe": s.get("sharpe",0),
        "sortino": s.get("sortino",0),
        "calmar": s.get("calmar",0),
        "max_dd": (s.get("max_drawdown_account") or 0)*100,
        "winrate": (s.get("winrate") or 0)*100,
        "profit_factor": s.get("profit_factor",0),
    }


def main():
    out = []
    total = len(TOP_COMBOS) * len(WINDOWS)
    i = 0
    for combo in TOP_COMBOS:
        upsert(combo)
        write_cfg(combo)
        for win_name, win_range in WINDOWS:
            i += 1
            cmd = [".venv/bin/freqtrade", "backtesting",
                   "-c", str(CFG_OUT), "-s", STRATEGY,
                   "--timerange", win_range, "--timeframe", TIMEFRAME,
                   "--cache", "none"]
            proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=600)
            if proc.returncode != 0:
                r = {"error": proc.stderr[-300:]}
            else:
                try:
                    r = parse(latest())
                except Exception as e:
                    r = {"error": f"parse: {e}"}
            r["combo_id"] = combo["id"]
            r["window"] = win_name
            r["timerange"] = win_range
            out.append(r)
            print(f"[{i:>2}/{total}] {combo['id']:<28} {win_name:<14} profit={r.get('profit_pct',0):+7.2f}% sharpe={r.get('sharpe',0):+5.2f} dd={r.get('max_dd',0):5.1f}% trades={r.get('trades',0):>4}", flush=True)
    with open(ROOT / "walkforward_v26_20m.json", "w") as f:
        json.dump(out, f, indent=2)
    print("\n=== Saved to walkforward_v26_20m.json ===", flush=True)


if __name__ == "__main__":
    main()
