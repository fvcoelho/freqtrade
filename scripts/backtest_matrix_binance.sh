#!/usr/bin/env bash
# Backtest matrix: combos × periods on Binance USDT futures.
set -e
cd "$(dirname "$0")/.."

ORIG_COMBO=$(.venv/bin/python -c "import json; print(json.load(open('user_data/scanner/pair_combos.json'))['active_combo'])")
RESULTS_DIR="/tmp/binance_combo_bt"
mkdir -p "$RESULTS_DIR"

restore() {
  .venv/bin/python - <<PYEOF
import json
p = "user_data/scanner/pair_combos.json"
d = json.load(open(p))
d["active_combo"] = "$ORIG_COMBO"
# Strip research_top* combos so they don't pollute live config
d["combos"] = {k: v for k, v in d["combos"].items() if not k.startswith("bn_")}
json.dump(d, open(p, "w"), indent=4)
print(f"Restored active_combo={d['active_combo']}, dropped bn_* combos")
PYEOF
}
trap restore EXIT

# Define combos as USDT versions
.venv/bin/python - <<'PYEOF'
import json
p = "user_data/scanner/pair_combos.json"
d = json.load(open(p))

USDT = lambda lst: [s.replace("USDC:USDC", "USDT:USDT") for s in lst]

combos = {
    "bn_top1_eth_sol_link_sui":  {"description": "HL top1 USDT", "group_a": ["ETH/USDT:USDT","SOL/USDT:USDT"],   "group_b": ["LINK/USDT:USDT","SUI/USDT:USDT"]},
    "bn_top2_avax_link_sui_ada": {"description": "HL top2 USDT", "group_a": ["AVAX/USDT:USDT","LINK/USDT:USDT"], "group_b": ["SUI/USDT:USDT","ADA/USDT:USDT"]},
    "bn_top3_avax_sui_link_ada": {"description": "HL top3 USDT", "group_a": ["AVAX/USDT:USDT","SUI/USDT:USDT"],  "group_b": ["LINK/USDT:USDT","ADA/USDT:USDT"]},
    "bn_top4_btc_link_eth_sol":  {"description": "HL top4 USDT", "group_a": ["BTC/USDT:USDT","LINK/USDT:USDT"],  "group_b": ["ETH/USDT:USDT","SOL/USDT:USDT"]},
    "bn_top5_avax_ada_link_sui": {"description": "HL top5 USDT", "group_a": ["AVAX/USDT:USDT","ADA/USDT:USDT"],  "group_b": ["LINK/USDT:USDT","SUI/USDT:USDT"]},
    "bn_dydx_xrp_ada_eth_sol":   {"description": "dydx winner USDT", "group_a": ["XRP/USDT:USDT","ADA/USDT:USDT"], "group_b": ["ETH/USDT:USDT","SOL/USDT:USDT"]},
    "bn_hl_doge_ada_eth_sol":    {"description": "hl_5m USDT",    "group_a": ["DOGE/USDT:USDT","ADA/USDT:USDT"], "group_b": ["ETH/USDT:USDT","SOL/USDT:USDT"]},
    "bn_btc_eth_sol_link":       {"description": "BTC+ETH vs SOL+LINK USDT", "group_a": ["BTC/USDT:USDT","ETH/USDT:USDT"], "group_b": ["SOL/USDT:USDT","LINK/USDT:USDT"]},
}
d["combos"].update(combos)
json.dump(d, open(p, "w"), indent=4)
print(f"Merged {len(combos)} bn_ combos")
PYEOF

# Periods (ending 2026-05-02)
declare -A PERIODS=(
  ["30d"]="20260402-20260502"
  ["90d"]="20260202-20260502"
  ["180d"]="20251104-20260502"
  ["365d"]="20250502-20260502"
)

COMBOS=(bn_top1_eth_sol_link_sui bn_top2_avax_link_sui_ada bn_top3_avax_sui_link_ada bn_top4_btc_link_eth_sol bn_top5_avax_ada_link_sui bn_dydx_xrp_ada_eth_sol bn_hl_doge_ada_eth_sol bn_btc_eth_sol_link)

for COMBO_NAME in "${COMBOS[@]}"; do
  for PERIOD_NAME in "${!PERIODS[@]}"; do
    RANGE="${PERIODS[$PERIOD_NAME]}"
    .venv/bin/python - <<PYEOF
import json
p = "user_data/scanner/pair_combos.json"
d = json.load(open(p))
d["active_combo"] = "$COMBO_NAME"
json.dump(d, open(p, "w"), indent=4)
print(f"=== $COMBO_NAME × $PERIOD_NAME ($RANGE) ===")
print(f"  A={d['combos']['$COMBO_NAME']['group_a']}")
print(f"  B={d['combos']['$COMBO_NAME']['group_b']}")
PYEOF

    LOG="$RESULTS_DIR/${COMBO_NAME}__${PERIOD_NAME}.log"
    .venv/bin/freqtrade backtesting \
        -c user_data/configs/config_binance_research_bt.json \
        --timerange "$RANGE" \
        --timeframe 5m \
        --strategy ZScorePairsTradingV24 \
        --cache none \
        > "$LOG" 2>&1 || echo "  bt FAILED ($LOG)"

    .venv/bin/python - <<PYEOF
import re
log = open("$LOG").read()
m = re.search(r"Total profit %\s+│\s+([-\d.]+)%", log)
t = re.search(r"Total/Daily Avg Trades\s+│\s+([\d.]+)", log)
s = re.search(r"Sharpe\s+│\s+([-\d.]+)", log)
dd = re.search(r"Max % of account underwater\s+│\s+([-\d.]+)%", log)
mc = re.search(r"Market change\s+│\s+([-\d.]+)%", log)
if m and t:
    print(f"  result: trades={t.group(1)} pnl={m.group(1)}% sharpe={s.group(1) if s else 'n/a'} dd={dd.group(1) if dd else 'n/a'}% market={mc.group(1) if mc else 'n/a'}%")
else:
    err = re.search(r"ERROR.*\n", log)
    print(f"  result: NO_TRADES_OR_FAILED  err={err.group(0).strip() if err else ''}")
PYEOF
  done
done

echo "Matrix done. Logs in $RESULTS_DIR"
