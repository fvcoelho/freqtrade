# V58 Replay UI Redesign

## Summary

Full redesign of the replay page (Monitor2View.vue) to visually represent every decision layer of the V58 queue-based scoring strategy. The layout follows the 7-layer pipeline from `docs/v58-strategy-architecture.md`. All scoring, queue, and confirmation data is pre-computed by the backend (`bot_controller.py /bt-signals`).

## Reference

- Strategy architecture: `docs/v58-strategy-architecture.md`
- Current replay: `frequi/src/views/Monitor2View.vue` (V53/V57 hybrid)
- Current live monitor: `frequi/src/views/MonitorLiveView.vue` (V57 pair grid)
- Backend: `user_data/bot_controller.py` (`_handle_bt_signals`)
- Config: `user_data/strategies/v58_config.json`

## Changes Required

### 1. Backend: `bot_controller.py` — New fields in `/bt-signals`

Add pre-computed scoring and queue data per pair per candle:

**New fields per pair (arrays, same length as `labels`):**

| Field | Type | Description |
|---|---|---|
| `score` | float[] | Composite score 0.0-1.0 per candle |
| `score_bz` | float[] | basket_z factor (normalized 0-1) |
| `score_vol` | float[] | vol_ratio factor (normalized 0-1) |
| `score_vel` | float[] | spread_velocity factor (normalized 0-1) |
| `score_cd` | float[] | cooldown factor (0 or 1) |
| `queue_side` | string[] | "long", "short", or "" per candle |
| `queue_rank` | int[] | 1-based rank in queue (0 = not in queue) |
| `cooldown_remaining` | int[] | Candles until cooldown expires (0 = clear) |
| `trade_type` | string[] | Market condition classification per candle: "breakout", "trending", or "mean_reversion" |

**New field per trade_range (added to each trade in `trade_ranges[]`):**

| Field | Type | Description |
|---|---|---|
| `trade_type` | string | Classification at entry time: "breakout", "trending", or "mean_reversion" |

**New global field `_meta`:**

| Field | Type | Description |
|---|---|---|
| `queue_config` | object | Copy of `queue` section from config (weights, top_k, min_score, etc.) |

**Computation approach:**

The backend iterates candle-by-candle across all pairs (same as the strategy does during backtesting). For each candle index `i`:

1. Gather `basket_z[i]`, `vol_ratio[i]`, `vol_ok[i]`, `btc_mom[i]`, etc. for all pairs
2. Compute `basket_z_prev3 = basket_z[i-3]` for velocity
3. Call scoring logic (same formulas as `entry_queue.py`):
   - `bz_norm = min(abs(basket_z), 4.0) / 4.0`
   - `vol_norm = min(vol_ratio, 3.0) / 3.0`
   - `vel_norm = min(abs(basket_z - basket_z_prev3), 2.0) / 2.0`
   - `cd_norm = 1.0 if (i - last_exit[pair]) >= cooldown_candles else 0.0`
   - `score = w_bz * bz_norm + w_vol * vol_norm + w_vel * vel_norm + w_cd * cd_norm`
4. Build long/short queues (filter by entry_z, regime, safety, vol_ok, exclude open trades)
5. Sort by score descending, keep top-K
6. Store: `score[i]`, factors, `queue_side[i]`, `queue_rank[i]` per pair
7. Track cooldown: when a trade exits at candle `i`, set `last_exit[pair] = i`

**Open trades tracking:** The backend already has `trade_ranges` (entry_index, exit_index). Use these to determine which pairs have open trades at each candle — a pair is "open" if `entry_index <= i <= exit_index` for any trade range.

### 1b. Backend: Trade Type Classification

Each candle and each trade receives a `trade_type` classification based on market conditions. The classification uses variables already available (no new indicators needed).

**3 Trade Types:**

| Type | ID | Color | Icon | Condition (priority order) |
|---|---|---|---|---|
| **Breakout** | `breakout` | Orange (#ff9800) | Lightning bolt | `spread_velocity >= 1.0 AND vol_ratio >= 2.0` |
| **Trending** | `trending` | Blue (#42a5f5) | Arrow up/down | `abs(btc_mom) >= 1.5 AND btc_atr_z < 2.0` |
| **Mean Reversion** | `mean_reversion` | Teal (#64ffda) | Wave | Default (neither breakout nor trending) |

**Classification logic (applied per pair per candle):**

```python
def classify_trade_type(btc_mom, btc_atr_z, spread_velocity, vol_ratio):
    """Classify market condition. Priority: breakout > trending > mean_reversion."""
    # Breakout: sudden divergence explosion with volume confirmation
    if spread_velocity >= 1.0 and vol_ratio >= 2.0:
        return "breakout"
    # Trending: strong BTC momentum with controlled volatility
    if abs(btc_mom) >= 1.5 and btc_atr_z < 2.0:
        return "trending"
    # Mean Reversion: calm market, classic reversion
    return "mean_reversion"
```

**Variables used:**

| Variable | Source | Breakout threshold | Trending threshold | Mean Reversion |
|---|---|---|---|---|
| `spread_velocity` | `abs(basket_z[i] - basket_z[i-3])` | >= 1.0 | any | < 1.0 |
| `vol_ratio` | Layer 3 | >= 2.0 | any | any |
| `btc_mom` | Layer 2 | any | abs >= 1.5 | abs < 1.5 |
| `btc_atr_z` | Layer 2 | any | < 2.0 | any |

**Per-candle array:** `trade_type[i]` = classification for the market at candle `i`. Stored per pair because `spread_velocity` and `vol_ratio` are pair-specific.

**Per-trade classification:** When a trade enters at candle `i`, the trade_range gets `trade_type = trade_type[entry_index]`. This is the type that's shown in trade history and on the open trade card.

**Backend computation (inside the candle loop, after scoring):**

```python
for pair in tradable:
    r = result[pair]
    if i >= len(r["labels"]): continue
    
    vel = abs(r["basket_z"][i] - (r["basket_z"][i-3] if i >= 3 else r["basket_z"][i]))
    vr = r["vol_ratio"][i] if i < len(r.get("vol_ratio", [])) else 1.0
    mom = r["btc_mom"][i] if i < len(r.get("btc_mom", [])) else 0.0
    atr_z = r["btc_atr_z"][i] if i < len(r.get("btc_atr_z", [])) else 0.0
    
    if vel >= 1.0 and vr >= 2.0:
        r["trade_type"][i] = "breakout"
    elif abs(mom) >= 1.5 and atr_z < 2.0:
        r["trade_type"][i] = "trending"
    else:
        r["trade_type"][i] = "mean_reversion"

# Also tag each trade_range with its entry type
for pair in tradable:
    for tr in result[pair].get("trade_ranges", []):
        ei = tr["entry_index"]
        tr["trade_type"] = result[pair]["trade_type"][ei]
```

### 2. Frontend: Monitor2View.vue — Full Redesign

All sections are collapsible (same pattern as current implementation). Transport bar stays at top (inline or detached/floating).

#### Section 0: Transport Bar
Same as current. Includes: play/pause, step forward/back, seek slider, speed control, date range, load button, visible candles, detach toggle.

No changes.

#### Section 1: Header + Trade Summary
Same as current TradeSummary component. Shows: open trades count, wins, losses, win%, equity, profit%.

Updated config summary line:
```
Basket Z-Score | Kalman | Lev 6x | Queue top-3 | min_score 0.45 | Max 4 trades | 20 pairs
```

No structural changes, just config text update.

#### Section 2: BTC Regime (Layer 2)

Left: BTC candlestick chart (same as current).
Right: Regime metrics panel.

Metrics to display:
- **Regime badge**: BULL (green) / BEAR (red) / RANGING (yellow)
- **btc_mom**: percentage with color (green if > 0, red if < -1)
- **btc_atr_z**: value with color (red if > 2.0)
- **Flags**: PUMP / DUMP / HIGH VOL badges (only shown when active)
- **Allowed trades**: "LONG only" / "SHORT only" / "No entries" based on regime

Implementation: Same as current BTC chart section, add "Allowed trades" text.

#### Section 3: Basket Z-Score Chart (Layer 1)

Single line chart showing basket_z for top-10 pairs (by |z| at current frame).

- Threshold lines at ±2.0 (entry_z)
- Per-pair colors from `PAIR_COLORS`
- Legend: pair names
- Current frame highlighted

Implementation: Same as current `zChartA`. Already updated for V58 in previous work.

#### Section 4: All Pairs Grid (Layers 1+3+5)

5-column grid, one card per pair. Each card shows the complete state of that pair at the current frame.

**Card layout:**
```
┌──────────────────────────────┐
│ DOGE    ⚡ BREAKOUT  LONG #1 │  ← name, trade type badge, signal, queue rank
│ $0.1823                      │  ← price
│ ▓▓▓▓▓▓▓▓▓▓░░░░░░░ z=-2.8   │  ← z-score bar + value
│                              │
│  Z      SPREAD    VOL        │
│ -2.80    -0.5%   2.1x       │  ← metrics row
│                              │
│ Score: ████████░░ 0.76       │  ← score bar + value
│  bz=75% vol=67% vel=75%     │  ← factor breakdown (small text)
│                              │
│ ▸ LONG  +1.23%  6x  ⚡       │  ← active trade (if any) + trade type icon
└──────────────────────────────┘
```

**Card elements:**
1. **Header**: Pair name (colored), trade type badge, signal badge (LONG/SHORT/NEUTRAL), queue rank (#1/#2/#3 or empty)
2. **Trade type badge**: Small colored pill showing current market classification:
   - `⚡ BREAKOUT` — orange (#ff9800), border #ff980033
   - `↗ TRENDING` — blue (#42a5f5), border #42a5f533
   - `〰 REVERSION` — teal (#64ffda), border #64ffda33
3. **Price**: Current close price
3. **Z-Score bar**: Horizontal bar from -4 to +4, filled from center. Green if < -1, red if > 1, gray otherwise.
4. **Metrics row**: Z value (colored by zColor), Spread %, Vol ratio (red if vol_ok=false)
5. **Score bar**: Horizontal bar 0-100%, colored by heatmap. Value shown. Min_score threshold line at 45%.
6. **Factor breakdown**: Small text below score bar: `bz=75% vol=67% vel=75% cd=100%`
7. **Active trade**: If pair has open trade at this frame, show side, profit%, leverage. Pulsing border.

**Card border color:**
- Active trade: cyan (#64ffda)
- In queue: side-dependent (green for long queue, red for short queue)
- Signal but not in queue: gray (#30363d)
- Neutral: dark gray

**Sort options**: Z-Score, Name, Score, Trade (buttons at section header, same pattern as current)

#### Section 5: Entry Queues (Layer 6) — NEW

Two side-by-side panels: Long Queue and Short Queue.

**Long Queue panel:**
```
┌─ LONG QUEUE (BULL regime) ──────────────────┐
│                                              │
│  #1  DOGE  ⚡ BREAKOUT   score 0.76  ███░ 76%│
│      z=-2.80  vol=2.1x  vel=0.75  cd=clear  │
│      ✓ PASS min_score                        │
│                                              │
│  #2  SOL   〰 REVERSION  score 0.58  ██░ 58% │
│      z=-2.31  vol=1.3x  vel=0.40  cd=clear  │
│      ✓ PASS min_score                        │
│                                              │
│  #3  LINK  〰 REVERSION  score 0.42  █░░ 42% │
│      z=-2.05  vol=1.1x  vel=0.20  cd=clear  │
│      ✗ BELOW min_score (0.45)                │
│                                              │
│  ─── min_score: 0.45 ───────────────────     │
│  Slots: 2/4 used                             │
│  Cooldown: XRP (1h20m), ETH (25m)           │
└──────────────────────────────────────────────┘
```

**Short Queue panel:** Same layout, shown when regime is BEAR.

**Queue elements:**
1. **Rank**: #1, #2, #3 (position in top-K)
2. **Pair name**: Colored
3. **Score**: Value + horizontal bar
4. **Factors**: z, vol, velocity, cooldown status (one line, compact)
5. **Min score gate**: Pass/fail with threshold value
6. **Slots counter**: Open trades / max_positions
7. **Cooldown list**: Pairs currently in cooldown with time remaining

**States per queue entry:**
- Green: score >= min_score, slot available → would enter
- Yellow: score >= min_score, no slot → waiting for slot
- Red: score < min_score → rejected
- Gray: in cooldown

**When queue is empty:** Show "No candidates — basket_z within ±2.0 for all pairs" or "BEAR regime — no long entries" etc.

#### Section 6: Open Trades + Exit Conditions (Layer 7)

Per open trade, show exit condition progress. Same concept as current "Out Conditions" but updated for V58 exit reasons.

**Per-trade card:**
```
┌─ DOGE/USDC  LONG  ⚡ BREAKOUT  queue_long  6x ┐
│  Entry: $0.1801  Current: $0.1823  +1.22%      │
│  Score at entry: 0.76  │  Duration: 15m / 2h   │
│  DCA: 0/2 fills                                │
│                                              │
│  Exit Conditions:                            │
│  ✅ Revert Profit   z=-0.28 (need >-0.3) +P │
│  ⚪ Revert Neutral  z=-0.28 (need > 0)      │
│  ⚪ Diverge Stop    z=-0.28 (need <-4.0)    │
│  ⚪ Max Loss        +1.22% (trigger <-15%)  │
│  ⚪ Time Stop       15m / 120m              │
│  ⚪ Trailing         +1.22% (activate >1.2%) │
└──────────────────────────────────────────────┘
```

**Exit condition bars:**
Each condition has a progress bar showing proximity to trigger:
- `basket_revert_profit`: z progress from entry_z toward exit_z (0.3) + profit > profit_lock
- `basket_revert_neutral`: z progress toward 0 + profit > 0
- `basket_diverge_stop`: z progress toward loss_exit_z (-4.0) + loss > 2%
- `basket_max_loss`: profit progress toward -15%
- `basket_time_stop`: time progress toward 24 candles (2h)
- `trailing_stop`: profit progress toward 1.2% activation

**Condition indicators:**
- Green check: condition MET (would exit on this one)
- Yellow circle: condition approaching (>50% progress)
- Gray circle: condition far from triggering

**When no trades open:** Show "No open trades" with link to "Jump to next trade" (same as current).

#### Section 7: Equity Curve

Same as current. Line chart of cumulative P&L.

No changes.

#### Section 8: Trade History

Same as current table with new columns. Full column list:

`#, Pair, Type, Side, Lev, Score, Entry time, Exit time, Entry $, Exit $, P&L %, P&L $, Duration, Exit Reason`

**New columns:**
- **Type**: Trade type badge at entry (`⚡`, `↗`, `〰`) with color
- **Score**: Entry score value (0.00-1.00)

Clickable entry/exit timestamps to seek to that frame.

**Summary stats row above table** (same as current, add type breakdown):
```
Total: 179 | W/L: 161/18 | Win%: 89.9% | P&L: +$1732 (+173.2%)
Types: ⚡ Breakout 23 (91.3% win) | ↗ Trending 45 (88.9% win) | 〰 Reversion 111 (89.2% win)
```

### 3. Data Flow

```
bot_controller.py                    Monitor2View.vue
─────────────────                    ────────────────
                                     
GET /bt-signals ─────────────────▶  loadAllData()
  response: {                        │
    "ETH/USDC:USDC": {              │  rawData[pair] = response data
      labels, ohlc, price,           │
      basket_z, basket_spread,       │  For each frame (play/seek):
      vol_ratio, vol_ok,             │    syncToFrame()
      btc_mom, btc_atr_z,           │    │
      btc_pump, btc_dump,           │    ├─ Read rawData[pair] at frameIndex
      btc_high_vol,                  │    ├─ Render BTC regime panel
      score, score_bz,              │    ├─ Render Basket Z chart
      score_vol, score_vel,         │    ├─ Render Pair Grid (z + score + rank)
      score_cd,                      │    ├─ Render Entry Queues
      queue_side, queue_rank,       │    ├─ Render Open Trades + Exits
      cooldown_remaining,            │    ├─ Render Equity Curve
      trade_ranges, signals          │    └─ Render Trade History
    },                               │
    "_equity": {...},                │
    "_summary": {...},               │
    "_meta": {                       │
      queue_config: {...}            │
    }                                │
  }                                  │
```

### 4. File Changes

| File | Action | Description |
|---|---|---|
| `user_data/bot_controller.py` | Modify | Add score/queue/cooldown computation to `_handle_bt_signals` |
| `frequi/src/views/Monitor2View.vue` | Rewrite | Full redesign following 7-layer pipeline |
| `frequi/src/components/monitor/types.ts` | Modify | Add score, queue, trade_type fields to `PairRawData` and `TradeRange` interfaces |
| `frequi/src/components/monitor/TradeSummary.vue` | No change | Reused as-is |
| `frequi/src/components/monitor/TransportBar.vue` | No change | Reused as-is |
| `frequi/src/components/monitor/chartBuilders.ts` | No change | BTC chart + equity chart builders reused |

### 5. Backend Computation Detail

In `_handle_bt_signals`, after loading trades and indicators, add a candle-by-candle loop:

```python
# Pre-compute scoring and queue data
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
min_score = queue_cfg.get("min_score", 0.45)

# Initialize per-pair arrays
for pair in result:
    if pair.startswith("_"): continue
    n = len(result[pair]["labels"])
    result[pair]["score"] = [0.0] * n
    result[pair]["score_bz"] = [0.0] * n
    result[pair]["score_vol"] = [0.0] * n
    result[pair]["score_vel"] = [0.0] * n
    result[pair]["score_cd"] = [0.0] * n
    result[pair]["queue_side"] = [""] * n
    result[pair]["queue_rank"] = [0] * n
    result[pair]["cooldown_remaining"] = [0] * n

last_exit = {}  # pair -> candle index
tradable = [p for p in result if not p.startswith("_") and not p.startswith("BTC")]

for i in range(n_frames):
    # Determine open trades at this candle
    open_at_i = set()
    for pair in tradable:
        for tr in result[pair].get("trade_ranges", []):
            if tr["entry_index"] <= i <= tr["exit_index"]:
                open_at_i.add(pair)
            # Track exits for cooldown
            if tr["exit_index"] == i:
                last_exit[pair] = i

    # Compute scores
    for pair in tradable:
        r = result[pair]
        if i >= len(r["labels"]): continue
        
        bz = abs(r["basket_z"][i])
        vr = r["vol_ratio"][i] if i < len(r.get("vol_ratio",[])) else 1.0
        bz_prev = r["basket_z"][i-3] if i >= 3 else r["basket_z"][i]
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

    # Build queues
    long_cand = []
    short_cand = []
    for pair in tradable:
        r = result[pair]
        if i >= len(r["labels"]): continue
        if pair in open_at_i: continue
        
        bz_val = r["basket_z"][i]
        vol_ok = r["vol_ok"][i] if i < len(r.get("vol_ok",[])) else False
        btc_mom = r["btc_mom"][i] if i < len(r.get("btc_mom",[])) else 0
        btc_pump = r["btc_pump"][i] if i < len(r.get("btc_pump",[])) else False
        btc_dump = r["btc_dump"][i] if i < len(r.get("btc_dump",[])) else False
        btc_hv = r["btc_high_vol"][i] if i < len(r.get("btc_high_vol",[])) else False
        
        if not vol_ok or btc_hv: continue
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
```

### 6. Performance Consideration

The candle-by-candle loop processes ~32,000 frames x 20 pairs = 640,000 iterations. Each iteration does basic arithmetic (no pandas). Expected time: < 2 seconds on a modern machine. The resulting JSON will be ~30-40% larger than V57 due to the extra arrays, but still under 10MB for a 4-month period.

### 7. Success Criteria

- Every layer of the V58 pipeline is visually represented
- At any frame, the user can see: why a pair entered the queue, its score breakdown, its rank, whether it passed min_score, and why it exited
- The queue panel shows the competition between pairs in real-time as frames advance
- Exit conditions show clear progress bars toward each trigger
- Every pair card and trade shows its **trade type** (Breakout/Trending/Mean Reversion) with distinct color and icon
- Trade history summary shows **win rate breakdown by trade type** so the user can see which market conditions produce the best results
- Replay playback is smooth (no lag from rendering extra data)
- All data comes pre-computed from the backend (no frontend calculation)
