"""V26 + 20m sweep over all BTC-anchored 4-pair arrangements (BTC+X vs Y+Z).
Total: 8 partners × C(7,2)=21 group_b combos = 168 backtests.
"""
import json, os, subprocess, glob, zipfile
from itertools import combinations
from pathlib import Path

ROOT = Path("/root/freqtrade")
COMBOS_PATH = ROOT / "user_data/scanner/pair_combos.json"
CFG_TPL = ROOT / "user_data/configs/config_binance_research_bt.json"
CFG_OUT = ROOT / "user_data/configs/config_btc_anchored.json"
RESULTS = ROOT / "user_data/backtest_results"

STRATEGY = "ZScorePTV26"
TIMEFRAME = "20m"
TIMERANGE = "20250502-20260502"

ALL_PAIRS = ["ADA", "AVAX", "DOGE", "ETH", "LINK", "SOL", "SUI", "XRP"]  # excluding BTC
QUOTE = "/USDT:USDT"


def build_combos():
    """Returns list of (combo_id, group_a_syms, group_b_syms)."""
    out = []
    for x in ALL_PAIRS:
        remaining = [p for p in ALL_PAIRS if p != x]
        for (y, z) in combinations(remaining, 2):
            cid = f"BTC{x}_vs_{y}{z}"
            out.append((cid, ("BTC", x), (y, z)))
    return out


def upsert_combo(name, ga, gb):
    with open(COMBOS_PATH) as f: d = json.load(f)
    d["combos"][name] = {
        "description": name,
        "group_a": [f"{p}{QUOTE}" for p in ga],
        "group_b": [f"{p}{QUOTE}" for p in gb],
    }
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
        "long_trades": s.get("trade_count_long", 0),
        "short_trades": s.get("trade_count_short", 0),
    }


def main():
    combos = build_combos()
    out = []
    out_path = ROOT / "btc_anchored_v26_20m.json"
    for i, (cid, ga, gb) in enumerate(combos, 1):
        combo = upsert_combo(cid, ga, gb)
        write_cfg(combo)
        cmd = [".venv/bin/freqtrade", "backtesting",
               "-c", str(CFG_OUT), "-s", STRATEGY,
               "--timerange", TIMERANGE, "--timeframe", TIMEFRAME,
               "--cache", "none"]
        proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=600)
        if proc.returncode != 0:
            r = {"error": proc.stderr[-300:]}
        else:
            try:
                r = parse(latest())
            except Exception as e:
                r = {"error": f"parse: {e}"}
        r["combo"] = cid
        r["group_a"] = list(ga)
        r["group_b"] = list(gb)
        out.append(r)

        # Progress: every 10 + always for top results
        if i % 10 == 0 or i == len(combos):
            with open(out_path, "w") as f: json.dump(out, f, indent=2)
            print(f"[{i:>3}/{len(combos)}] saved checkpoint", flush=True)
        # Highlight strong positives
        if "error" not in r and r.get("sharpe", 0) >= 1.0:
            print(f"[{i:>3}/{len(combos)}] {cid}: profit={r['profit_pct']:+7.2f}% sharpe={r['sharpe']:+5.2f} dd={r['max_dd']:5.1f}% trades={r['trades']:>4} 🚀", flush=True)
        elif "error" not in r and r.get("sharpe", 0) >= 0.5:
            print(f"[{i:>3}/{len(combos)}] {cid}: profit={r['profit_pct']:+7.2f}% sharpe={r['sharpe']:+5.2f} ✅", flush=True)
        # Errors always reported
        if "error" in r:
            print(f"[{i:>3}/{len(combos)}] {cid}: ERROR", flush=True)

    with open(out_path, "w") as f: json.dump(out, f, indent=2)
    print(f"\n=== Saved to {out_path} ({len(out)} runs) ===", flush=True)


if __name__ == "__main__":
    main()
