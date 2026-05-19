#!/bin/bash
# Fast fill parser: lz4cat | grep pre-filters, Python only parses matching lines
# 10-50x faster than pure Python JSON parsing of all lines
#
# Usage: bash scripts/parse_fills_fast.sh

set -e
cd /root/freqtrade

PAIRS="BNB AAVE ENA ONDO NEAR INJ TON TAO FARTCOIN PENDLE TRUMP LINK"
FILLS_DIR="/tmp/hl_fills"
OUT_DIR="/tmp/hl_filtered"

mkdir -p "$OUT_DIR"

# Step 1: Extract only lines containing our target coins using lz4cat + grep
echo "=== Step 1: Filtering fills with lz4cat+grep ==="
GREP_PATTERN=$(echo $PAIRS | tr ' ' '|')

TOTAL_DAYS=$(ls -d $FILLS_DIR/20* 2>/dev/null | wc -l)
DAY_NUM=0

for day_dir in $(ls -d $FILLS_DIR/20* | sort); do
    DAY_NUM=$((DAY_NUM + 1))
    day=$(basename $day_dir)
    outfile="$OUT_DIR/${day}.jsonl"

    if [ -f "$outfile" ] && [ -s "$outfile" ]; then
        continue  # already filtered
    fi

    echo -n "  [$DAY_NUM/$TOTAL_DAYS] $day..."

    # Decompress + grep in parallel for all 24 hours
    for f in $day_dir/*.lz4; do
        lz4cat "$f" 2>/dev/null
    done | grep -E "$GREP_PATTERN" > "$outfile" 2>/dev/null || true

    lines=$(wc -l < "$outfile")
    echo " $lines lines"
done

echo
echo "=== Step 2: Building candles ==="
.venv/bin/python3 -c "
import json, sys
from pathlib import Path
import pandas as pd

pairs = '$PAIRS'.split()
target = set(pairs)
filtered_dir = Path('$OUT_DIR')
out_dir = Path('user_data/data/hyperliquid/futures')

all_trades = {c: [] for c in pairs}
files = sorted(filtered_dir.glob('*.jsonl'))
total = len(files)

for i, f in enumerate(files):
    if i % 20 == 0:
        print(f'  Reading {i+1}/{total}...', flush=True)
    with open(f) as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                block = json.loads(line)
                for event in block.get('events', []):
                    if not isinstance(event, list) or len(event) < 2:
                        continue
                    fill = event[1]
                    coin = fill.get('coin', '')
                    if coin in target:
                        all_trades[coin].append({
                            'time': int(fill['time']),
                            'price': float(fill['px']),
                            'size': float(fill['sz']),
                        })
            except:
                pass

print()
print('=== Step 3: Saving feather files ===')
for coin in pairs:
    trades = all_trades[coin]
    if not trades:
        print(f'  {coin}: no trades')
        continue
    df = pd.DataFrame(trades)
    df['date'] = pd.to_datetime(df['time'], unit='ms', utc=True)
    df = df.sort_values('date')
    candles = df.resample('5min', on='date').agg(
        open=('price', 'first'),
        high=('price', 'max'),
        low=('price', 'min'),
        close=('price', 'last'),
        volume=('size', 'sum'),
    ).dropna(subset=['open']).reset_index()

    out_file = out_dir / f'{coin}_USDC_USDC-5m-futures.feather'
    if out_file.exists():
        existing = pd.read_feather(out_file)
        candles = pd.concat([existing, candles]).drop_duplicates(
            subset=['date']).sort_values('date').reset_index(drop=True)
    candles.to_feather(out_file)
    print(f'  {coin}: {len(candles)} candles ({df[\"date\"].min().date()} → {df[\"date\"].max().date()})')

print()
print('Done!')
"
