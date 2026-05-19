#!/bin/bash
# Turbo fill parser: lz4cat + grep (native C) → Python only for candle aggregation
# ~15 min for 199 days vs 2.5h in pure Python
set -e
cd /root/freqtrade

PAIRS="ONDO TON"
FILLS_DIR="/tmp/hl_fills"
FILTERED="/tmp/hl_filtered_ondo_ton.jsonl"

echo "=== Step 1: lz4cat + grep (all days) ==="
GREP_PATTERN='"ONDO"\|"TON"'
TOTAL=$(ls -d $FILLS_DIR/20* 2>/dev/null | wc -l)
NUM=0

> "$FILTERED"  # clear

for day_dir in $(ls -d $FILLS_DIR/20* | sort); do
    NUM=$((NUM + 1))
    day=$(basename $day_dir)

    if [ $((NUM % 20)) -eq 0 ] || [ $NUM -eq $TOTAL ]; then
        echo "  [$NUM/$TOTAL] $day..."
    fi

    for f in $day_dir/*.lz4; do
        lz4cat "$f" 2>/dev/null
    done | grep -E "$GREP_PATTERN" >> "$FILTERED" 2>/dev/null || true
done

LINES=$(wc -l < "$FILTERED")
echo "  Filtered: $LINES lines"

echo
echo "=== Step 2: Building candles ==="
.venv/bin/python3 << 'PYEOF'
import json
import pandas as pd
from pathlib import Path

pairs = ["ONDO", "TON"]
target = set(pairs)
out_dir = Path("user_data/data/hyperliquid/futures")

all_trades = {c: [] for c in pairs}
total_lines = 0

with open("/tmp/hl_filtered_ondo_ton.jsonl") as f:
    for line in f:
        total_lines += 1
        if total_lines % 500000 == 0:
            print(f"  {total_lines} lines processed...", flush=True)
        try:
            block = json.loads(line)
            for event in block.get("events", []):
                if not isinstance(event, list) or len(event) < 2:
                    continue
                fill = event[1]
                coin = fill.get("coin", "")
                if coin in target:
                    all_trades[coin].append((
                        int(fill["time"]),
                        float(fill["px"]),
                        float(fill["sz"]),
                    ))
        except:
            pass

print(f"  Total: {total_lines} lines, {sum(len(v) for v in all_trades.values())} fills")
print()

for coin in pairs:
    trades = all_trades[coin]
    if not trades:
        print(f"  {coin}: no trades")
        continue

    df = pd.DataFrame(trades, columns=["time", "price", "size"])
    df["date"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    df = df.sort_values("date")

    candles = df.resample("5min", on="date").agg(
        open=("price", "first"),
        high=("price", "max"),
        low=("price", "min"),
        close=("price", "last"),
        volume=("size", "sum"),
    ).dropna(subset=["open"]).reset_index()

    out_file = out_dir / f"{coin}_USDC_USDC-5m-futures.feather"
    if out_file.exists():
        existing = pd.read_feather(out_file)
        candles = pd.concat([existing, candles]).drop_duplicates(
            subset=["date"]).sort_values("date").reset_index(drop=True)

    candles.to_feather(out_file)
    print(f"  {coin}: {len(candles)} candles ({df['date'].min().date()} -> {df['date'].max().date()})")

print()
print("Done!")
PYEOF
