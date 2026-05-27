#!/usr/bin/env bash
# Sweep variants of breakout_long Design C. Edits config in place between runs.
set -e
cd /root/freqtrade

CONFIG=user_data/strategies/breakout_long/breakout_long_config.json
BTCONFIG=config_breakout_long_backtest.json
PY=/root/freqtrade/.venv/bin/python

run_window() {
  local label="$1"; local tr="$2"
  /root/freqtrade/.venv/bin/freqtrade backtesting \
    --strategy BreakoutLongStrategy \
    --config "$BTCONFIG" \
    --timerange "$tr" \
    --timeframe 15m \
    --userdir user_data \
    --strategy-path user_data/strategies \
    --cache none 2>&1 | grep -E "^│ *TOTAL " | head -2 | tail -1 \
      | awk -v lbl="$label" '{
          # cols: Pair Trades AvgProfit% TotProfitUSDC TotProfit% AvgDuration WinDrawLossWin%
          # Match the simpler "│ TOTAL │ N │ ..." row
          for(i=1;i<=NF;i++){ if($i=="│") c=i; }
        }
        END { print lbl }' >/dev/null
}

# Helper: extract trades + total% from a backtest run
metric() {
  local label="$1"; local tr="$2"
  out=$(/root/freqtrade/.venv/bin/freqtrade backtesting \
    --strategy BreakoutLongStrategy \
    --config "$BTCONFIG" \
    --timerange "$tr" \
    --timeframe 15m \
    --userdir user_data \
    --strategy-path user_data/strategies \
    --cache none 2>&1)
  trades=$(echo "$out" | grep "Total/Daily Avg Trades" | awk -F'│' '{print $3}' | awk '{print $1}')
  pnl=$(echo "$out" | grep "Total profit %" | awk -F'│' '{print $3}' | awk '{print $1}' | tr -d '%')
  printf "%-30s | trades=%-4s pnl=%-7s\n" "$label" "$trades" "$pnl"
}

echo "=== Current config snapshot ==="
$PY -c "import json; c=json.load(open('$CONFIG')); print('pairs:', c['basket']['pairs']); print('climax_vol_mult:', c['entry']['climax_vol_mult']); print('confirm:', c['entry']['retest_confirm_candles']); print('require_1h:', c['entry']['require_1h_breakout'])"
echo
echo "=== Run ==="
for w in "W1:20251115-20260115" "W2:20260115-20260315" "IS:20260323-20260523"; do
  label="${w%%:*}"; tr="${w##*:}"
  metric "$label" "$tr"
done
