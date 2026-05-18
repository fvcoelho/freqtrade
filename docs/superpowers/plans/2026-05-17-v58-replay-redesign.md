# V58 Replay UI Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the replay page (Monitor2View.vue) to visually represent every decision layer of V58, with pre-computed scoring/queue/trade_type data from the backend.

**Architecture:** Backend (`bot_controller.py`) adds a candle-by-candle loop computing scores, queues, trade types for all pairs. Frontend (`Monitor2View.vue`) is rewritten top-to-bottom following the 7-layer pipeline. Types extended in `types.ts`.

**Tech Stack:** Python 3.13 (backend), Vue 3 + TypeScript + ECharts (frontend), vite build

**Spec:** `docs/superpowers/specs/2026-05-17-v58-replay-redesign.md`

---

### Task 1: Backend — Add scoring, queue, trade_type computation to bot_controller.py

**Files:**
- Modify: `user_data/bot_controller.py` — `_handle_bt_signals` method

This is the largest single task. The backend must add a candle-by-candle loop after the existing per-pair result dict is built (after line 343 in current file, before the equity curve section).

- [ ] **Step 1: Update config loading to use v58_config.json**

In `_handle_bt_signals`, change the config path from v57 to v58:

```python
# Change this line:
cfg_path = BASE_DIR / "user_data" / "strategies" / "v57_config.json"
# To:
cfg_path = BASE_DIR / "user_data" / "strategies" / "v58_config.json"
```

Also update `_meta` bot_name:

```python
result["_meta"] = {
    "strategy": strat, "bot_name": "V58 Queue",
    ...
    "queue_config": cfg.get("queue", {}),
}
```

- [ ] **Step 2: Add scoring + queue + trade_type computation**

Insert the following code block AFTER the per-pair result dict loop (after the line `result[pair] = { "labels": labels, ... }` for all pairs) and BEFORE the equity curve section (`# Build equity curve`).

Add this complete code block to `_handle_bt_signals`:

```python
        # ── V58: Pre-compute scoring, queue, and trade_type per candle ──
        queue_cfg = cfg.get("queue", {})
        weights = queue_cfg.get("weights", {})
        w_bz = weights.get("basket_z", 0.5)
        w_vol = weights.get("vol_ratio", 0.2)
        w_vel = weights.get("spread_velocity", 0.2)
        w_cd = weights.get("cooldown", 0.1)
        top_k = queue_cfg.get("top_k", 3)
        entry_z = cfg["basket"].get("entry_z", 2.0)
        bull_th = cfg["basket"].get("bull_mom_threshold", 0.0)
        bear_th = cfg["basket"].get("bear_mom_threshold", -1.0)
        cooldown_candles = queue_cfg.get("cooldown_candles", 36)

        tradable = [p for p in result if not p.startswith("_") and not p.startswith("BTC")]

        # Initialize new arrays
        for pair in tradable:
            n = result[pair]["count"]
            result[pair]["score"] = [0.0] * n
            result[pair]["score_bz"] = [0.0] * n
            result[pair]["score_vol"] = [0.0] * n
            result[pair]["score_vel"] = [0.0] * n
            result[pair]["score_cd"] = [0.0] * n
            result[pair]["queue_side"] = [""] * n
            result[pair]["queue_rank"] = [0] * n
            result[pair]["cooldown_remaining"] = [0] * n
            result[pair]["trade_type"] = ["mean_reversion"] * n
        # Also init for BTC (won't have queue data but needs trade_type array)
        for pair in result:
            if pair.startswith("_") or pair in [p for p in tradable]:
                continue
            if pair.startswith("BTC"):
                n = result[pair]["count"]
                result[pair]["score"] = [0.0] * n
                result[pair]["score_bz"] = [0.0] * n
                result[pair]["score_vol"] = [0.0] * n
                result[pair]["score_vel"] = [0.0] * n
                result[pair]["score_cd"] = [0.0] * n
                result[pair]["queue_side"] = [""] * n
                result[pair]["queue_rank"] = [0] * n
                result[pair]["cooldown_remaining"] = [0] * n
                result[pair]["trade_type"] = ["mean_reversion"] * n

        last_exit = {}

        for i in range(n_frames):
            # Determine open trades at this candle
            open_at_i = set()
            for pair in tradable:
                for tr in result[pair].get("trade_ranges", []):
                    if tr["entry_index"] <= i <= tr["exit_index"]:
                        open_at_i.add(pair)
                    if tr["exit_index"] == i:
                        last_exit[pair] = i

            # Compute scores + trade_type for all pairs
            for pair in tradable:
                r = result[pair]
                if i >= r["count"]:
                    continue

                bz = abs(r["basket_z"][i])
                vr = r["vol_ratio"][i] if i < len(r.get("vol_ratio", [])) else 1.0
                bz_prev = r["basket_z"][i - 3] if i >= 3 else r["basket_z"][i]
                velocity = abs(r["basket_z"][i] - bz_prev)

                bz_norm = min(bz, 4.0) / 4.0
                vol_norm = min(vr, 3.0) / 3.0
                vel_norm = min(velocity, 2.0) / 2.0
                le = last_exit.get(pair, -999)
                cd_norm = 0.0 if (i - le) < cooldown_candles else 1.0
                cd_remaining = max(0, cooldown_candles - (i - le)) if le >= 0 else 0

                score = w_bz * bz_norm + w_vol * vol_norm + w_vel * vel_norm + w_cd * cd_norm

                r["score"][i] = round(score, 4)
                r["score_bz"][i] = round(bz_norm, 4)
                r["score_vol"][i] = round(vol_norm, 4)
                r["score_vel"][i] = round(vel_norm, 4)
                r["score_cd"][i] = round(cd_norm, 4)
                r["cooldown_remaining"][i] = cd_remaining

                # Trade type classification
                mom = r["btc_mom"][i] if i < len(r.get("btc_mom", [])) else 0.0
                atr_z = r["btc_atr_z"][i] if i < len(r.get("btc_atr_z", [])) else 0.0
                if velocity >= 1.0 and vr >= 2.0:
                    r["trade_type"][i] = "breakout"
                elif abs(mom) >= 1.5 and atr_z < 2.0:
                    r["trade_type"][i] = "trending"
                else:
                    r["trade_type"][i] = "mean_reversion"

            # Build queues
            long_cand = []
            short_cand = []
            for pair in tradable:
                r = result[pair]
                if i >= r["count"]:
                    continue
                if pair in open_at_i:
                    continue

                bz_val = r["basket_z"][i]
                vol_ok = r["vol_ok"][i] if i < len(r.get("vol_ok", [])) else False
                btc_mom = r["btc_mom"][i] if i < len(r.get("btc_mom", [])) else 0
                btc_pump = r["btc_pump"][i] if i < len(r.get("btc_pump", [])) else False
                btc_dump = r["btc_dump"][i] if i < len(r.get("btc_dump", [])) else False
                btc_hv = r["btc_high_vol"][i] if i < len(r.get("btc_high_vol", [])) else False

                if not vol_ok or btc_hv:
                    continue
                s = r["score"][i]

                if bz_val < -entry_z and btc_mom > bull_th and not btc_dump:
                    long_cand.append((pair, s))
                if bz_val > entry_z and btc_mom < bear_th and not btc_pump:
                    short_cand.append((pair, s))

            long_cand.sort(key=lambda x: x[1], reverse=True)
            short_cand.sort(key=lambda x: x[1], reverse=True)

            for rank, (pair, _) in enumerate(long_cand[:top_k], 1):
                result[pair]["queue_side"][i] = "long"
                result[pair]["queue_rank"][i] = rank
            for rank, (pair, _) in enumerate(short_cand[:top_k], 1):
                result[pair]["queue_side"][i] = "short"
                result[pair]["queue_rank"][i] = rank

        # Tag each trade_range with its entry trade_type
        for pair in tradable:
            for tr in result[pair].get("trade_ranges", []):
                ei = tr["entry_index"]
                if ei < len(result[pair]["trade_type"]):
                    tr["trade_type"] = result[pair]["trade_type"][ei]
                else:
                    tr["trade_type"] = "mean_reversion"
                # Also store entry score
                if ei < len(result[pair]["score"]):
                    tr["entry_score"] = result[pair]["score"][ei]
                else:
                    tr["entry_score"] = 0.0
```

- [ ] **Step 3: Test the backend**

```bash
# Start bot_controller
pkill -f bot_controller 2>/dev/null; sleep 1
.venv/bin/python user_data/bot_controller.py &
sleep 3

# Test new fields exist
curl -s "http://localhost:8084/bt-signals?start=2026-04-01&end=2026-04-10&timeframe=5m" | \
  .venv/bin/python -c "
import sys, json
data = json.load(sys.stdin)
pair = 'ETH/USDC:USDC'
r = data[pair]
print('score len:', len(r.get('score', [])))
print('queue_side len:', len(r.get('queue_side', [])))
print('trade_type len:', len(r.get('trade_type', [])))
print('score sample [500]:', r['score'][500] if len(r.get('score',[])) > 500 else 'N/A')
print('queue_side sample [500]:', r['queue_side'][500] if len(r.get('queue_side',[])) > 500 else 'N/A')
print('trade_type sample [500]:', r['trade_type'][500] if len(r.get('trade_type',[])) > 500 else 'N/A')
print('queue_config:', data.get('_meta', {}).get('queue_config', 'MISSING'))
# Check trade_range has trade_type
trades = r.get('trade_ranges', [])
if trades:
    print('trade_range[0] trade_type:', trades[0].get('trade_type', 'MISSING'))
    print('trade_range[0] entry_score:', trades[0].get('entry_score', 'MISSING'))
else:
    print('no trades for ETH in this range')
"
```

Expected: All new arrays present with correct lengths, trade_type values are "breakout"/"trending"/"mean_reversion", queue_config in _meta.

- [ ] **Step 4: Commit**

```bash
git add -f user_data/bot_controller.py
git commit -m "feat(v58): add scoring, queue, trade_type pre-computation to bt-signals"
```

---

### Task 2: Update types.ts with new fields

**Files:**
- Modify: `/Users/fvcoelho/Working/frequi/src/components/monitor/types.ts`

- [ ] **Step 1: Add new fields to PairRawData and TradeRange**

Update the `PairRawData` interface to add:

```typescript
// Add these fields to the PairRawData interface:
  score?: number[];
  score_bz?: number[];
  score_vol?: number[];
  score_vel?: number[];
  score_cd?: number[];
  queue_side?: string[];
  queue_rank?: number[];
  cooldown_remaining?: number[];
  trade_type?: string[];
```

Update the `TradeRange` interface to add:

```typescript
// Add these fields to the TradeRange interface:
  trade_type?: string;
  entry_score?: number;
```

Add trade type constants after the existing exports:

```typescript
// Trade Type classification
export const TRADE_TYPES = {
  breakout: { id: 'breakout', label: 'BREAKOUT', icon: '\u26A1', color: '#ff9800', bg: '#ff980020', border: '#ff980033' },
  trending: { id: 'trending', label: 'TRENDING', icon: '\u2197', color: '#42a5f5', bg: '#42a5f520', border: '#42a5f533' },
  mean_reversion: { id: 'mean_reversion', label: 'REVERSION', icon: '\u3030', color: '#64ffda', bg: '#64ffda20', border: '#64ffda33' },
} as const;

export type TradeType = keyof typeof TRADE_TYPES;

export function getTradeType(id: string) {
  return TRADE_TYPES[id as TradeType] || TRADE_TYPES.mean_reversion;
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/fvcoelho/Working/frequi
git add src/components/monitor/types.ts
git commit -m "feat(v58): add score, queue, trade_type fields to monitor types"
```

---

### Task 3: Rewrite Monitor2View.vue — Script section

**Files:**
- Rewrite: `/Users/fvcoelho/Working/frequi/src/views/Monitor2View.vue`

This task rewrites only the `<script setup>` section. The template comes in Task 4.

The script must:
1. Keep existing: transport bar state, frame sync, BTC chart, equity chart, trade history
2. Add new: pairGrid computed (with score + queue + trade_type), entryQueues computed, exitConditions computed
3. Remove: old group-based entry/exit conditions (pairEntryConditions, pairExitConditions)

- [ ] **Step 1: Write the complete new script section**

The `<script setup>` section should contain all the imports, state, data loading, frame sync, and computed properties. Write it as the FULL replacement of the existing script section (lines 1-937 of current file).

Key computed properties to implement:

**`pairGrid`** — For each non-BTC pair at current frame, produce:
```typescript
interface PairGridItem {
  pair: string;
  coinName: string;
  price: string;
  basketZ: number;
  basketSpread: number;
  volRatio: number;
  volOk: boolean;
  score: number;
  scoreBz: number;
  scoreVol: number;
  scoreVel: number;
  scoreCd: number;
  queueSide: string;
  queueRank: number;
  cooldownRemaining: number;
  tradeType: string;
  signal: string;
  hasTrade: boolean;
  tradeSide: string;
  tradeProfit: number;
  tradeType_trade: string; // trade_type from the active trade_range
}
```

**`entryQueues`** — Build long and short queues from pairGrid:
```typescript
interface QueueEntry {
  pair: string;
  coinName: string;
  rank: number;
  score: number;
  basketZ: number;
  volRatio: number;
  velocity: number;
  cooldownRemaining: number;
  tradeType: string;
  passMinScore: boolean;
}
const longQueue = computed<QueueEntry[]>(() => ...)
const shortQueue = computed<QueueEntry[]>(() => ...)
```

**`exitConditions`** — For each open trade at current frame:
```typescript
interface ExitCondition {
  name: string;
  met: boolean;
  value: string;
  detail: string;
  pct: number;
}
interface OpenTradeInfo {
  pair: string;
  coinName: string;
  side: string;
  tradeType: string;
  entryPrice: number;
  currentPrice: number;
  profit: number;
  duration: number;
  durationFmt: string;
  entryScore: number;
  conditions: ExitCondition[];
}
```

**`tradeTypeSummary`** — Breakdown by trade type:
```typescript
const tradeTypeSummary = computed(() => {
  const h = tradeHistory.value;
  const types = ['breakout', 'trending', 'mean_reversion'];
  return types.map(t => {
    const trades = h.filter(tr => tr.tradeType === t);
    const wins = trades.filter(tr => tr.win).length;
    return { type: t, total: trades.length, wins, winPct: trades.length > 0 ? (wins/trades.length*100).toFixed(1) : '0' };
  });
});
```

This is a large file. The subagent should write it completely, using the current Monitor2View.vue as reference for the parts that don't change (transport bar, frame sync, data loading, BTC chart, equity chart).

- [ ] **Step 2: Verify script compiles**

```bash
cd /Users/fvcoelho/Working/frequi && npx vite build 2>&1 | tail -5
```

Expected: Build succeeds (template errors OK at this point since template comes in Task 4).

- [ ] **Step 3: Commit**

```bash
git add src/views/Monitor2View.vue
git commit -m "feat(v58): rewrite Monitor2View script with score, queue, trade_type computeds"
```

---

### Task 4: Rewrite Monitor2View.vue — Template section

**Files:**
- Modify: `/Users/fvcoelho/Working/frequi/src/views/Monitor2View.vue` (template only)

The template follows the 7-layer pipeline layout. Each section is collapsible.

- [ ] **Step 1: Write the complete template**

The `<template>` section must contain these sections in order:

1. **Transport Bar** (same as current — TransportBar component, inline + floating via Teleport)
2. **Config Summary** (updated text for V58)
3. **Trade Summary** (TradeSummary component, same as current)
4. **BTC Regime** (BTC chart + metrics, add "Allowed trades" text and regime badge)
5. **Basket Z-Score Chart** (same as current — single chart, top 10 pairs)
6. **All Pairs Grid** (5 cols, with score bar, trade_type badge, queue rank, factor breakdown)
7. **Entry Queues** (NEW — two side-by-side panels for long/short queue)
8. **Open Trades + Exit Conditions** (trade cards with exit progress bars)
9. **Equity Curve** (same as current)
10. **Trade History** (add Type + Score columns, add type breakdown in summary)

Each pair card in the grid (section 6) must show:
- Header: pair name (colored), trade_type badge (icon + label + color), signal badge, queue rank
- Price
- Z-score bar (horizontal, -4 to +4)
- Metrics: Z, Spread %, Vol
- Score bar (horizontal, 0-100%) with min_score threshold marker
- Factor breakdown text: bz=X% vol=X% vel=X% cd=X%
- Active trade row (if any): side, profit, leverage, trade_type icon

The Entry Queue section (section 7) must show:
- Two panels side by side: Long Queue / Short Queue
- Per queue entry: rank, pair name, trade_type badge, score bar, factors, min_score pass/fail
- Footer: slots used / max, pairs in cooldown with time remaining

Add `<style scoped>` with `@keyframes pulse` for active trade animation.

- [ ] **Step 2: Build and verify**

```bash
cd /Users/fvcoelho/Working/frequi && npx vite build 2>&1 | tail -5
```

Expected: Build succeeds with no errors.

- [ ] **Step 3: Deploy to freqtrade**

```bash
rm -rf /Users/fvcoelho/Working/freqtrade/freqtrade/rpc/api_server/ui/installed/assets/
cp -r /Users/fvcoelho/Working/frequi/dist/* /Users/fvcoelho/Working/freqtrade/freqtrade/rpc/api_server/ui/installed/
```

- [ ] **Step 4: Commit**

```bash
git add src/views/Monitor2View.vue
git commit -m "feat(v58): rewrite Monitor2View template with 7-layer pipeline layout"
```

---

### Task 5: Integration test — run replay end-to-end

**Files:** None (testing only)

- [ ] **Step 1: Start bot_controller**

```bash
pkill -f bot_controller 2>/dev/null; sleep 1
cd /Users/fvcoelho/Working/freqtrade
.venv/bin/python user_data/bot_controller.py &
sleep 3
curl -s http://localhost:8084/status
```

Expected: `{"status": "stopped", ...}`

- [ ] **Step 2: Start freqtrade for UI serving**

```bash
pkill -f "freqtrade trade" 2>/dev/null; sleep 1
.venv/bin/freqtrade trade --config user_data/config_hyperliquid.json --strategy ZScoreV57Monitor --userdir user_data &
sleep 10
curl -s http://localhost:8080/api/v1/ping
```

Expected: `{"status":"pong"}`

- [ ] **Step 3: Verify bt-signals has all new fields**

```bash
curl -s "http://localhost:8084/bt-signals?start=2026-03-01&end=2026-04-01&timeframe=5m" | \
  .venv/bin/python -c "
import sys, json
data = json.load(sys.stdin)
# Check a tradable pair
pair = [p for p in data if not p.startswith('_') and not p.startswith('BTC')][0]
r = data[pair]
fields = ['score','score_bz','score_vol','score_vel','score_cd','queue_side','queue_rank','cooldown_remaining','trade_type']
for f in fields:
    arr = r.get(f, [])
    print(f'{f}: len={len(arr)}, sample={arr[1000] if len(arr)>1000 else \"short\"}')
# Check trade_ranges
for tr in r.get('trade_ranges', [])[:3]:
    print(f'trade: {tr.get(\"side\")} type={tr.get(\"trade_type\")} score={tr.get(\"entry_score\")}')
# Check _meta
print('queue_config:', json.dumps(data['_meta'].get('queue_config', {})))
"
```

Expected: All fields present, trade_type values are breakout/trending/mean_reversion, queue_config in _meta.

- [ ] **Step 4: Open replay in browser**

Open `http://localhost:8080/replay` in a browser.

Verify:
- Page loads without JS errors (check browser console)
- Load button fetches data (set dates to 2026-03-01 → 2026-04-01)
- Transport bar works (play, pause, step, seek)
- BTC chart renders with regime badge
- Pair grid shows 5 columns with score bars, trade_type badges, queue ranks
- Entry queues show long/short panels with ranked pairs
- Trade history shows Type and Score columns
- Trade type summary shows breakdown by type

- [ ] **Step 5: Commit deployed UI**

```bash
cd /Users/fvcoelho/Working/freqtrade
git add -f freqtrade/rpc/api_server/ui/installed/
git commit -m "feat(v58): deploy V58 replay UI with full pipeline visualization"
```
