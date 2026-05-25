#!/usr/bin/env bash
# Backtest each candidate combo from scripts/hl_top_combos.json sequentially.
# Restores active_combo to hl_5m on exit (trap).
set -e
cd "$(dirname "$0")/.."

ORIG_COMBO=$(.venv/bin/python -c "import json; print(json.load(open('user_data/scanner/pair_combos.json'))['active_combo'])")
TOPS_FILE="scripts/hl_top_combos.json"
RESULTS_DIR="/tmp/hl_combo_bt"
mkdir -p "$RESULTS_DIR"

restore() {
  .venv/bin/python - <<PYEOF
import json
p = "user_data/scanner/pair_combos.json"
d = json.load(open(p))
d["active_combo"] = "$ORIG_COMBO"
json.dump(d, open(p, "w"), indent=4)
print(f"Restored active_combo={d['active_combo']}")
PYEOF
}
trap restore EXIT

# Build candidate combo list and merge into pair_combos.json
.venv/bin/python - <<'PYEOF'
import json
tops = json.load(open("scripts/hl_top_combos.json"))
combos = json.load(open("user_data/scanner/pair_combos.json"))
combos["combos"].update(tops["combos"])
json.dump(combos, open("user_data/scanner/pair_combos.json", "w"), indent=4)
print(f"Merged {len(tops['combos'])} research combos into pair_combos.json")
PYEOF

# Build extended whitelist covering all candidates
ALL_PAIRS=$(.venv/bin/python -c "
import json
tops = json.load(open('scripts/hl_top_combos.json'))
pairs = set()
for combo in tops['combos'].values():
    pairs.update(combo['group_a'])
    pairs.update(combo['group_b'])
print(','.join(sorted(pairs)))
")
echo "Pairs needed: $ALL_PAIRS"

# Write a backtest config with extended whitelist
.venv/bin/python - <<PYEOF
import json
src = json.load(open("user_data/configs/config_hyperliquid_backtest.json"))
src["exchange"]["pair_whitelist"] = "$ALL_PAIRS".split(",")
json.dump(src, open("user_data/configs/config_hl_research_bt.json", "w"), indent=4)
print(f"Backtest config: {len(src['exchange']['pair_whitelist'])} pairs in whitelist")
PYEOF

# Run each combo
for i in $(seq 1 8); do
  COMBO_NAME="research_top$i"
  .venv/bin/python - <<PYEOF
import json
p = "user_data/scanner/pair_combos.json"
d = json.load(open(p))
d["active_combo"] = "$COMBO_NAME"
json.dump(d, open(p, "w"), indent=4)
print(f"=== Now testing: $COMBO_NAME ===")
print(f"  groupA={d['combos']['$COMBO_NAME']['group_a']}")
print(f"  groupB={d['combos']['$COMBO_NAME']['group_b']}")
PYEOF

  LOG="$RESULTS_DIR/${COMBO_NAME}.log"
  .venv/bin/freqtrade backtesting \
      -c user_data/configs/config_hl_research_bt.json \
      --timerange 20260415-20260502 \
      --timeframe 5m \
      --strategy ZScorePairsTradingV24 \
      --cache none \
      > "$LOG" 2>&1 || echo "  bt FAILED for $COMBO_NAME (see $LOG)"

  # Parse summary line
  .venv/bin/python - <<PYEOF
import re
log = open("$LOG").read()
for line in log.splitlines():
    if "ZScorePairsTradingV24" in line and "│" in line:
        parts = [p.strip() for p in line.split("│") if p.strip()]
        if len(parts) >= 7:
            print(f"  result: trades={parts[1]} avg={parts[2]} pnl_usdc={parts[3]} pnl_pct={parts[4]} winrate={parts[6].split()[-1]} dd={parts[7]}")
            break
else:
    # try summary block parse
    m = re.search(r"Total profit %\s+│\s+([-\d.]+%)\s+", log)
    t = re.search(r"Total/Daily Avg Trades\s+│\s+([\d.]+)", log)
    s = re.search(r"Sharpe\s+│\s+([-\d.]+)", log)
    if m and t:
        print(f"  result: trades={t.group(1)} pnl={m.group(1)} sharpe={s.group(1) if s else 'n/a'}")
    else:
        print("  result: NOT PARSED — check log")
PYEOF
done

echo "All done. Logs in $RESULTS_DIR"
