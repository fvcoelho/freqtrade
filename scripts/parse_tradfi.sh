#!/bin/bash
set -e
cd /root/freqtrade
FILLS_DIR="/tmp/hl_fills"
FILTERED="/tmp/hl_tradfi.jsonl"

# Download fills Dec 2025 - May 2026 (if not already there)
echo "=== Step 1: Download fills ==="
TOTAL_DAYS=0
for month in 202512 202601 202602 202603 202604 202605; do
    year=${month:0:4}
    mon=${month:4:2}
    case $mon in
        01|03|05) days=31 ;;
        02) days=28 ;;
        04|06) days=30 ;;
        12) days=31 ;;
    esac
    for day in $(seq -w 1 $days); do
        date_str="${month}${day}"
        day_dir="$FILLS_DIR/$date_str"
        if [ -d "$day_dir" ] && [ $(ls "$day_dir"/*.lz4 2>/dev/null | wc -l) -ge 20 ]; then
            continue
        fi
        mkdir -p "$day_dir"
        aws s3 sync "s3://hl-mainnet-node-data/node_fills_by_block/hourly/$date_str/" "$day_dir/" \
            --request-payer requester --quiet --only-show-errors 2>/dev/null || true
        TOTAL_DAYS=$((TOTAL_DAYS + 1))
        [ $((TOTAL_DAYS % 20)) -eq 0 ] && echo "  Downloaded $TOTAL_DAYS days..."
    done
done
echo "  Download complete: $TOTAL_DAYS new days"

# Filter TradFi fills
echo "=== Step 2: Filter xyz: fills ==="
> "$FILTERED"
TOTAL=$(ls -d $FILLS_DIR/20* 2>/dev/null | wc -l)
NUM=0
for day_dir in $(ls -d $FILLS_DIR/20* | sort); do
    NUM=$((NUM + 1))
    [ $((NUM % 30)) -eq 0 ] && echo "  [$NUM/$TOTAL]..."
    for f in $day_dir/*.lz4; do
        lz4cat "$f" 2>/dev/null
    done | grep '"xyz:' >> "$FILTERED" 2>/dev/null || true
done
echo "  Filtered: $(wc -l < $FILTERED) lines"

# Build candles
echo "=== Step 3: Build 5m candles ==="
.venv/bin/python3 -c "
import json, pandas as pd
from pathlib import Path

coins = ['xyz:XYZ100','xyz:NVDA','xyz:AAPL','xyz:TSLA','xyz:GOOGL','xyz:AMZN',
         'xyz:META','xyz:MSFT','xyz:AMD','xyz:INTC','xyz:NFLX','xyz:PLTR',
         'xyz:MU','xyz:SNDK','xyz:MSTR','xyz:COIN']
target = set(coins)
out_dir = Path('user_data/data/hyperliquid/futures')

all_trades = {c: [] for c in coins}
n = 0
with open('/tmp/hl_tradfi.jsonl') as f:
    for line in f:
        n += 1
        if n % 200000 == 0:
            print(f'  {n} lines...', flush=True)
        try:
            block = json.loads(line)
            for event in block.get('events', []):
                if not isinstance(event, list) or len(event) < 2: continue
                fill = event[1]
                coin = fill.get('coin', '')
                if coin in target:
                    all_trades[coin].append((int(fill['time']), float(fill['px']), float(fill['sz'])))
        except: pass

print(f'  {n} lines total, {sum(len(v) for v in all_trades.values())} fills')
print()
for coin in coins:
    trades = all_trades[coin]
    if not trades:
        print(f'  {coin}: no trades'); continue
    df = pd.DataFrame(trades, columns=['time','price','size'])
    df['date'] = pd.to_datetime(df['time'], unit='ms', utc=True)
    df = df.sort_values('date')
    candles = df.resample('5min', on='date').agg(
        open=('price','first'), high=('price','max'),
        low=('price','min'), close=('price','last'),
        volume=('size','sum')
    ).dropna(subset=['open']).reset_index()
    
    safe = coin.replace('xyz:','XYZ-')
    out_file = out_dir / f'{safe}_USDC_USDC-5m-futures.feather'
    if out_file.exists():
        existing = pd.read_feather(out_file)
        candles = pd.concat([existing, candles]).drop_duplicates(subset=['date']).sort_values('date').reset_index(drop=True)
    candles.to_feather(out_file)
    print(f'  {coin}: {len(candles)} candles ({candles.iloc[0][\"date\"].date()} -> {candles.iloc[-1][\"date\"].date()})')

print('Done!')
"
