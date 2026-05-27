#!/usr/bin/env bash
# Start BreakoutLong Design C in dry-run, parallel to V10 (port 8084).
set -e
cd /root/freqtrade

LOG=/root/freqtrade/breakout_long_dryrun.log
DB=sqlite:////root/freqtrade/breakout_long_dryrun.sqlite
CONFIG=/root/freqtrade/config_breakout_long_dryrun.json

# Refuse to start if another instance is already running
if pgrep -fa "BreakoutLongStrategy.*config_breakout_long_dryrun" >/dev/null; then
  echo "[start] BreakoutLong already running — refusing to spawn duplicate." >&2
  pgrep -fa "BreakoutLongStrategy.*config_breakout_long_dryrun" >&2
  exit 1
fi

# Wide terminal for clean log lines
export COLUMNS=300

exec /root/freqtrade/.venv/bin/freqtrade trade \
  --strategy BreakoutLongStrategy \
  --strategy-path /root/freqtrade/user_data/strategies \
  --config "$CONFIG" \
  --db-url "$DB" \
  --logfile "$LOG"
