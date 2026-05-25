"""V26 in 20m on all 11 4-pair combos."""
import json, os, subprocess, glob, zipfile
from pathlib import Path

ROOT = Path("/root/freqtrade")
COMBOS_PATH = ROOT / "user_data/scanner/pair_combos.json"
CFG_TPL = ROOT / "user_data/configs/config_binance_research_bt.json"
CFG_OUT = ROOT / "user_data/configs/config_v26_20m_sweep.json"
RESULTS = ROOT / "user_data/backtest_results"

STRATEGY = "ZScorePTV26"
TIMEFRAME = "20m"
TIMERANGE = "20250502-20260502"
COMBOS = [
    "C1_AVAXETH_SUISOL", "C2_BTCETH_SOLLINK", "C3_DOGEXRP_SUIAVAX",
    "C4_ETHXRP_LINKSOL", "C5_AVAXSUI_LINKADA", "C6_AVAXLINK_SUIADA",
    "C7_BTCLINK_ETHSOL", "C8_AVAXADA_LINKSUI", "C9_BTCSOL_ETHLINK",
    "C10_BTCETH_XRPLINK", "C11_ETHSOL_LINKSUI",
]


def set_active(name):
    with open(COMBOS_PATH) as f: d = json.load(f)
    d["active_combo"] = name
    with open(COMBOS_PATH, "w") as f: json.dump(d, f, indent=4)
    return d["combos"][name]


def write_cfg(combo):
    with open(CFG_TPL) as f: c = json.load(f)
    c["strategy"] = STRATEGY
    c["exchange"]["pair_whitelist"] = combo["group_a"] + combo["group_b"]
    c["max_open_trades"] = 4
    with open(CFG_OUT, "w") as f: json.dump(c, f, indent=2)


def latest():
    files = sorted(glob.glob(str(RESULTS / "*.zip")))
    return files[-1]


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
        "long_trades": s.get("trade_count_long",0),
        "short_trades": s.get("trade_count_short",0),
    }


def main():
    out = []
    for i, name in enumerate(COMBOS, 1):
        combo = set_active(name)
        write_cfg(combo)
        cmd = [".venv/bin/freqtrade", "backtesting",
               "-c", str(CFG_OUT), "-s", STRATEGY,
               "--timerange", TIMERANGE, "--timeframe", TIMEFRAME,
               "--cache", "none"]
        proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=600)
        if proc.returncode != 0:
            r = {"error": proc.stderr[-300:]}
        else:
            r = parse(latest())
        r["combo"] = name
        r["pairs"] = combo["group_a"] + combo["group_b"]
        out.append(r)
        if "error" in r:
            print(f"[{i:>2}/{len(COMBOS)}] {name}: ERROR")
        else:
            print(f"[{i:>2}/{len(COMBOS)}] {name}: profit={r['profit_pct']:+7.2f}% sharpe={r['sharpe']:+5.2f} dd={r['max_dd']:5.1f}% trades={r['trades']:>4} pf={r['profit_factor']:.2f}", flush=True)
    with open(ROOT / "v26_20m_results.json", "w") as f:
        json.dump(out, f, indent=2)
    print("\n=== Saved to v26_20m_results.json ===")


if __name__ == "__main__":
    main()
