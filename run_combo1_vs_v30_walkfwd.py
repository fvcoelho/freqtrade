"""Walk-forward: Combo1USDT @ 15m vs V30Score @ 20m on T3 across 4 quarters.

Both strategies run on Binance USDT futures, T3_BTCXRP_vs_ADAAVAX.
Pairs (BTC, XRP, ADA, AVAX) all exist on Hyperliquid for live deploy.
"""
import glob, json, os, subprocess, zipfile
from pathlib import Path

ROOT = Path("/root/freqtrade")
CFG = ROOT / "user_data/configs/config_combo1_vs_v30_15m.json"
RES_DIR = ROOT / "user_data/backtest_results"
WINDOWS = [
    ("Q1 May-Jul 25", "20250502-20250801"),
    ("Q2 Aug-Oct 25", "20250801-20251101"),
    ("Q3 Nov-Jan 26", "20251101-20260201"),
    ("Q4 Feb-May 26", "20260201-20260502"),
    ("Apr 26 (1mo)",  "20260403-20260502"),
    ("Full year",     "20250502-20260502"),
]
TASKS = [
    ("ZScorePTCombo1USDT", "15m"),
    ("ZScorePTV30Score",   "20m"),
]


def latest():
    files = sorted(glob.glob(str(RES_DIR / "*.zip")))
    return files[-1] if files else None


def parse(zp):
    base = os.path.basename(zp).replace(".zip", "")
    with zipfile.ZipFile(zp) as z:
        with z.open(base + ".json") as f:
            d = json.load(f)
    s = list(d.get("strategy", {}).values())[0]
    return {
        "trades": s.get("total_trades", 0),
        "p":   round(s.get("profit_total", 0) * 100, 2),
        "dd":  round((s.get("max_drawdown_account") or 0) * 100, 2),
        "sh":  round(s.get("sharpe", 0), 2),
        "win": round((s.get("winrate") or 0) * 100, 1),
        "pf":  round(s.get("profit_factor", 0), 2),
    }


def run(strategy, tf, timerange):
    cmd = [
        ".venv/bin/freqtrade", "backtesting",
        "-c", str(CFG), "-s", strategy,
        "--timeframe", tf, "--timerange", timerange,
        "--cache", "none",
    ]
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        return {"error": proc.stderr[-300:]}
    return parse(latest())


def main():
    out = []
    for name, tr in WINDOWS:
        row = {"window": name, "timerange": tr}
        for strat, tf in TASKS:
            tag = f"{strat.replace('ZScorePT','').replace('Score','S')}_{tf}"
            print(f"  {name} | {strat} {tf} ... ", end="", flush=True)
            r = run(strat, tf, tr)
            row[tag] = r
            if "error" in r:
                print(f"ERROR: {r['error'][:120]}")
            else:
                print(f"p={r['p']:+.2f}% dd={r['dd']:.2f}% sh={r['sh']:.2f} tr={r['trades']}")
        out.append(row)
    with open(ROOT / "combo1_vs_v30_walkfwd.json", "w") as f:
        json.dump(out, f, indent=2)
    print("\n=== Saved combo1_vs_v30_walkfwd.json ===")


if __name__ == "__main__":
    main()
