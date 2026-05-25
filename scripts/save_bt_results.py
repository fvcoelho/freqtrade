"""Parse freqtrade backtest logs from a directory and persist structured results.

Usage: save_bt_results.py <log_dir> <out_prefix> [--meta exchange=hyperliquid period=20260415-20260502 ...]
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

METRICS = {
    "trades": (r"Total/Daily Avg Trades\s+│\s+([\d.]+)\s*/\s*([\d.]+)", 1, float),
    "trades_per_day": (r"Total/Daily Avg Trades\s+│\s+[\d.]+\s*/\s*([\d.]+)", 1, float),
    "starting_balance": (r"Starting balance\s+│\s+([\d.]+)\s+USDC?T?", 1, float),
    "final_balance": (r"Final balance\s+│\s+([\d.]+)\s+USDC?T?", 1, float),
    "abs_profit": (r"Absolute profit\s+│\s+([-\d.]+)\s+USDC?T?", 1, float),
    "total_profit_pct": (r"Total profit %\s+│\s+([-\d.]+)%", 1, float),
    "cagr_pct": (r"CAGR %\s+│\s+([-\d.]+)%", 1, float),
    "sortino": (r"Sortino\s+│\s+([-\d.]+)", 1, float),
    "sharpe": (r"Sharpe\s+│\s+([-\d.]+)", 1, float),
    "calmar": (r"Calmar\s+│\s+([-\d.]+)", 1, float),
    "sqn": (r"SQN\s+│\s+([-\d.]+)", 1, float),
    "profit_factor": (r"Profit factor\s+│\s+([-\d.]+)", 1, float),
    "expectancy": (r"Expectancy \(Ratio\)\s+│\s+([-\d.]+)\s+\(([-\d.]+)\)", 1, float),
    "long_trades": (r"Long / Short trades\s+│\s+(\d+)\s*/\s*(\d+)", 1, int),
    "short_trades": (r"Long / Short trades\s+│\s+\d+\s*/\s*(\d+)", 1, int),
    "long_pnl_pct": (r"Long / Short profit %\s+│\s+([-\d.]+)%\s*/\s*([-\d.]+)%", 1, float),
    "short_pnl_pct": (r"Long / Short profit %\s+│\s+[-\d.]+%\s*/\s*([-\d.]+)%", 1, float),
    "best_pair": (r"Best Pair\s+│\s+([^│]+?)\s*\|", 1, str),
    "worst_pair": (r"Worst Pair\s+│\s+([^│]+?)\s*\|", 1, str),
    "best_trade_pct": (r"Best trade\s+│\s+\S+\s+([-\d.]+)%", 1, float),
    "worst_trade_pct": (r"Worst trade\s+│\s+\S+\s+([-\d.]+)%", 1, float),
    "max_dd_pct": (r"Max % of account underwater\s+│\s+([-\d.]+)%", 1, float),
    "abs_dd": (r"Absolute drawdown\s+│\s+([-\d.]+)\s+USDC?T?", 1, float),
    "dd_duration": (r"Drawdown duration\s+│\s+([^│]+?)\s*\|", 1, str),
    "market_change_pct": (r"Market change\s+│\s+([-\d.]+)%", 1, float),
    "win_rate_pct": (r"\s+(\d+)\s+\d+\s+\d+\s+([\d.]+)\s*\|", 2, float),  # Win Draw Loss Win%
    "wins": (r"\s+(\d+)\s+\d+\s+\d+\s+[\d.]+\s*\|", 1, int),
    "losses": (r"\s+\d+\s+\d+\s+(\d+)\s+[\d.]+\s*\|", 1, int),
}


def parse_log(text: str) -> dict:
    out = {}
    for key, (pat, group_idx, cast) in METRICS.items():
        m = re.search(pat, text)
        if m:
            try:
                val = m.group(group_idx).strip()
                out[key] = cast(val) if cast is not str else val
            except (ValueError, IndexError):
                out[key] = None
        else:
            out[key] = None
    # Backtesting from / to
    m = re.search(r"Backtesting from\s+│\s+(\S+ \S+)", text)
    if m: out["bt_from"] = m.group(1)
    m = re.search(r"Backtesting to\s+│\s+(\S+ \S+)", text)
    if m: out["bt_to"] = m.group(1)
    # If parsing failed entirely, mark as failed
    if not out.get("trades"):
        out["status"] = "FAILED"
    else:
        out["status"] = "OK"
    return out


def load_combos_meta() -> dict:
    p = Path("user_data/scanner/pair_combos.json")
    if not p.exists():
        return {}
    return json.load(open(p)).get("combos", {})


def main():
    if len(sys.argv) < 3:
        print("Usage: save_bt_results.py <log_dir> <out_prefix> [--meta k=v ...]")
        sys.exit(1)
    log_dir = Path(sys.argv[1])
    out_prefix = sys.argv[2]
    meta = {}
    for arg in sys.argv[3:]:
        if "=" in arg:
            k, v = arg.split("=", 1)
            meta[k.lstrip("-")] = v

    combos_meta = load_combos_meta()
    rows = []
    for log_path in sorted(log_dir.glob("*.log")):
        combo_name = log_path.stem
        text = log_path.read_text()
        result = parse_log(text)
        cinfo = combos_meta.get(combo_name, {})
        row = {
            "combo": combo_name,
            "group_a": "+".join(p.split("/")[0] for p in cinfo.get("group_a", [])),
            "group_b": "+".join(p.split("/")[0] for p in cinfo.get("group_b", [])),
            "description": cinfo.get("description", ""),
            **result,
            **{f"meta_{k}": v for k, v in meta.items()},
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        print("No logs parsed")
        sys.exit(1)

    # Sort: status OK first, then by sharpe desc
    df["_ok"] = (df["status"] == "OK").astype(int)
    df = df.sort_values(["_ok", "sharpe"], ascending=[False, False]).drop(columns="_ok").reset_index(drop=True)

    out_dir = Path("scripts/results")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_path = out_dir / f"{out_prefix}_{ts}.json"
    csv_path = out_dir / f"{out_prefix}_{ts}.csv"
    json_path.write_text(json.dumps(rows, indent=2, default=str))
    df.to_csv(csv_path, index=False)
    print(f"Saved {len(rows)} results")
    print(f"  JSON: {json_path}")
    print(f"  CSV:  {csv_path}")

    # Print top summary
    cols = ["combo", "group_a", "group_b", "trades", "total_profit_pct", "sharpe", "max_dd_pct", "win_rate_pct", "status"]
    available = [c for c in cols if c in df.columns]
    print(f"\nRanked summary:")
    print(df[available].head(20).to_string(index=False))


if __name__ == "__main__":
    main()
