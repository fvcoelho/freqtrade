# V58 — Queue-Based Scoring Strategy: Architecture Complete

## Overview

V58 is a crypto futures mean-reversion strategy that trades 20 pairs against a common basket average. Every 5 minutes, it computes how far each pair has deviated from the basket, scores each pair on 4 factors, ranks them into entry queues, and only allows the best-scoring pairs to trade. Exits happen when the deviation reverts toward zero.

The key innovation over V57: **pairs compete for limited trade slots** instead of entering independently. A multi-factor score determines who gets in.

---

## Pipeline: 7 Layers from Data to Trade

```
LAYER 1: Basket Z-Score (per pair, every 5m candle)
    │
    ▼
LAYER 2: BTC Regime Detection (from 1h BTC candles)
    │
    ▼
LAYER 3: Volume Filter (per pair)
    │
    ▼
LAYER 4: Candidate Signal Generation (vectorized, per pair)
    │
    ▼
LAYER 5: Multi-Factor Scoring (all pairs simultaneously)
    │
    ▼
LAYER 6: Queue Ranking + Entry Gate (top-K + min_score)
    │
    ▼
LAYER 7: Exit Conditions (per open trade)
```

---

## LAYER 1: Basket Z-Score

**Purpose:** Measure how far each pair has diverged from the average of all 20 pairs.

**How it works:**

1. Load the close price for all 20 pairs
2. Compute `log(close)` for each pair
3. Normalize: subtract the first value so all pairs start at 0
4. Compute `basket_avg = mean(all normalized log prices)`
5. For each pair: `spread = normalized_log_price - basket_avg`
6. Apply Kalman filter to the spread to get adaptive mean and variance
7. `basket_z = (spread - kalman_mean) / kalman_std`

**Variables produced (per pair, per candle):**

| Variable | Type | Description |
|---|---|---|
| `basket_z` | float | Z-score of this pair vs basket. Negative = lagging behind. Positive = ahead. |
| `basket_spread` | float | Raw spread (pair normalized log price minus basket average) |

**Kalman Filter parameters:**
- `kalman_gain`: 0.05 — controls how quickly the filter adapts (lower = smoother, higher = more reactive)

**Z-Score interpretation:**
- `basket_z < -2.0` → pair is significantly lagging behind the basket → **LONG candidate**
- `basket_z > +2.0` → pair is significantly ahead of the basket → **SHORT candidate**
- `basket_z ≈ 0` → pair is at basket average → **no signal**

**Config:**
```json
"zscore": {
    "zscore_window": 288,        // 288 candles = 24 hours of 5m data
    "cum_return_window": 24      // not used in V58 Kalman mode
},
"basket": {
    "zscore_method": "kalman",
    "kalman_gain": 0.05,
    "entry_z": 2.0               // threshold for entry candidacy
}
```

**UI representation:**
- Per-pair: color-coded z-score value + horizontal bar showing position (-4 to +4)
- Chart: line chart of basket_z for top-10 pairs by |z|, with ±2.0 threshold lines

---

## LAYER 2: BTC Regime Detection

**Purpose:** Determine the market regime from BTC's 1-hour data. The regime decides whether the strategy goes LONG, SHORT, or neither.

**How it works:**

1. Load BTC/USDC 1h candles
2. Compute `btc_mom = price_change_pct(last 4 hours)` — BTC momentum
3. Compute `btc_atr = average_true_range(14 periods)` — BTC volatility
4. Compute `btc_atr_z = z-score(atr, window=72)` — normalized volatility
5. Derive boolean flags from thresholds

**Variables produced (global, same for all pairs):**

| Variable | Type | Threshold | Description |
|---|---|---|---|
| `btc_mom` | float | — | BTC 4h momentum (% change). Positive = bull, negative = bear. |
| `btc_atr_z` | float | — | BTC volatility z-score. How unusual current vol is vs recent history. |
| `btc_pump` | bool | `btc_mom > 3.0` | BTC is pumping hard — **block SHORT entries** |
| `btc_dump` | bool | `btc_mom < -3.0` | BTC is dumping hard — **block LONG entries** |
| `btc_high_vol` | bool | `btc_atr_z > 2.0` | BTC volatility is extreme — **block ALL entries** |

**Regime classification (derived from btc_mom):**

| Regime | Condition | Allowed Trades |
|---|---|---|
| **BULL** | `btc_mom > 0.0` (bull_mom_threshold) | LONG only |
| **BEAR** | `btc_mom < -1.0` (bear_mom_threshold) | SHORT only |
| **RANGING** | between thresholds | Neither (no entries) |

**Config:**
```json
"btc_trend": {
    "timeframe": "1h",
    "pump_threshold": 3.0,
    "dump_threshold": -3.0,
    "high_vol_threshold": 2.0,
    "mom_period": 4,
    "atr_period": 14,
    "atr_z_window": 72
},
"basket": {
    "bull_mom_threshold": 0.0,
    "bear_mom_threshold": -1.0
}
```

**UI representation:**
- BTC panel: regime badge (BULL/BEAR/RANGING) with color
- Metrics: Mom %, ATR Z, Pump/Dump/High Vol flags
- BTC candlestick chart

---

## LAYER 3: Volume Filter

**Purpose:** Only allow entries when the pair has adequate trading volume. Low volume = unreliable signals.

**How it works:**

1. Compute `vol_ma = rolling_mean(volume, 144 candles)` — 12-hour volume average
2. `vol_ratio = current_volume / vol_ma`
3. `vol_ok = (vol_ratio > 1.0)`

**Variables produced (per pair):**

| Variable | Type | Description |
|---|---|---|
| `vol_ratio` | float | Current volume relative to 12h average. 2.0 = double the average. |
| `vol_ok` | bool | True if volume is above threshold. Required for entry. |

**Config:**
```json
"volume": {
    "vol_ma_window": 144,       // 144 candles × 5m = 12 hours
    "vol_ok_threshold": 1.0     // volume must be above average
}
```

**UI representation:**
- Per-pair: vol_ratio value with color (red if vol_ok=false)

---

## LAYER 4: Candidate Signal Generation

**Purpose:** Mark every candle where basic entry conditions are met. These are CANDIDATES — not actual trades. The queue in Layer 5-6 decides which candidates actually enter.

**Logic (vectorized, applied to entire dataframe at once):**

```
FOR EACH CANDLE:
    LONG candidate if ALL true:
        basket_z < -entry_z (-2.0)     // pair lagging behind basket
        btc_mom > bull_threshold (0.0)  // bull regime
        btc_dump == false               // no BTC crash
        btc_high_vol == false           // no chaos
        vol_ok == true                  // volume present

    SHORT candidate if ALL true:
        basket_z > +entry_z (+2.0)     // pair ahead of basket
        btc_mom < bear_threshold (-1.0) // bear regime
        btc_pump == false               // no BTC pump
        btc_high_vol == false           // no chaos
        vol_ok == true                  // volume present
```

**Entry tags:** `queue_long` or `queue_short`

**UI representation:**
- Per-pair signal badge: LONG (green), SHORT (red), NEUTRAL (gray)
- Entry condition checklist (like V53 replay):
  - Basket Z: value + pass/fail
  - Regime: BULL/BEAR/RANGING + pass/fail
  - BTC Safety: pump/dump/high_vol flags
  - Volume: vol_ratio + pass/fail

---

## LAYER 5: Multi-Factor Scoring

**Purpose:** Rank all candidate pairs by quality. Not all signals are equal — a pair with extreme z-score + high volume + fast-moving spread is a better entry than one barely crossing the threshold.

**How it works:**

For each pair (including non-candidates), compute 4 normalized factors:

### Factor 1: `basket_z` (weight: 0.5)
```
bz_norm = min(abs(basket_z), 4.0) / 4.0
```
- Range: 0.0 to 1.0
- A z of -2.0 → 0.50, a z of -3.5 → 0.875, a z of -4.0+ → 1.0
- **Higher = more extreme divergence = stronger signal**

### Factor 2: `vol_ratio` (weight: 0.2)
```
vol_norm = min(vol_ratio, 3.0) / 3.0
```
- Range: 0.0 to 1.0
- vol_ratio of 1.0 → 0.33, vol_ratio of 2.0 → 0.67, vol_ratio of 3.0+ → 1.0
- **Higher = more volume conviction = more reliable signal**

### Factor 3: `spread_velocity` (weight: 0.2)
```
velocity = abs(basket_z_now - basket_z_3_candles_ago)
vel_norm = min(velocity, 2.0) / 2.0
```
- Range: 0.0 to 1.0
- Measures how fast the z-score is moving (15-minute delta)
- **Higher = spread opening faster = fresher opportunity**

### Factor 4: `cooldown_bonus` (weight: 0.1)
```
candles_since_last_exit = current_candle - last_exit_candle_for_this_pair
cd_norm = 1.0 if candles_since_last_exit >= 36 else 0.0
```
- Binary: 0.0 or 1.0
- 36 candles × 5m = 3 hours cooldown
- **Penalizes immediate re-entry after an exit on the same pair**

### Final Score
```
score = (0.5 × bz_norm) + (0.2 × vol_norm) + (0.2 × vel_norm) + (0.1 × cd_norm)
```
- Range: 0.0 to 1.0
- Example: basket_z=-3.0, vol_ratio=2.0, velocity=1.5, no cooldown:
  - `0.5×0.75 + 0.2×0.67 + 0.2×0.75 + 0.1×1.0 = 0.375 + 0.134 + 0.15 + 0.1 = 0.759`

**Config:**
```json
"queue": {
    "weights": {
        "basket_z": 0.5,
        "vol_ratio": 0.2,
        "spread_velocity": 0.2,
        "cooldown": 0.1
    },
    "cooldown_candles": 36
}
```

**UI representation:**
- Per-pair: composite score (0-100%) with heatmap color (red→yellow→green)
- Score breakdown: 4 bars showing each factor's contribution
- Ranking position (#1, #2, #3, etc.)

---

## LAYER 6: Queue Ranking + Entry Gate

**Purpose:** From all candidate signals, select only the best to actually trade. This is the core V58 innovation.

### Step 1: Build Queues

From all pairs that passed Layer 4 (candidate signals):

**Long Queue:** pairs with `basket_z < -entry_z` AND regime=BULL AND safety OK AND vol OK
- Sorted by score descending
- Keep only top-K (default: 3)

**Short Queue:** pairs with `basket_z > +entry_z` AND regime=BEAR AND safety OK AND vol OK
- Sorted by score descending
- Keep only top-K (default: 3)

Pairs with open trades are **excluded** from both queues.

### Step 2: Persistence Check

For the pair that triggered the signal, verify z-score was past threshold for `confirm_candles` consecutive candles:
- With `confirm_candles=1`: just check the current candle (no extra filtering)
- With `confirm_candles=2`: z must have been past threshold this candle AND the previous one
- `confirm_z_ratio` relaxes the threshold (e.g., 0.7 means z needs to be 70% of entry_z for confirmation)

### Step 3: Minimum Score Gate

The pair's score must be `>= min_score` (default: 0.45) to enter. This filters out weak setups even if they're in the top-K.

### Step 4: Position Limits

- Maximum `max_positions` trades open simultaneously (default: 4)
- No duplicate pairs (one trade per pair at a time)

### Entry Decision Flow
```
Signal detected on pair X at candle T
    │
    ├─ open_trades >= max_positions? → REJECT
    ├─ pair X already has open trade? → REJECT
    ├─ z-score persistent for N candles? → if no: REJECT
    │
    ├─ Compute scores for ALL 20 pairs at candle T
    ├─ Build Long Queue (top-K by score)
    ├─ Build Short Queue (top-K by score)
    │
    ├─ Pair X in the right queue? → if no: REJECT (outranked by better pairs)
    ├─ Score >= min_score (0.45)? → if no: REJECT (too weak)
    │
    └─ ENTER TRADE ✓
        Tag: "queue_long" or "queue_short"
        Leverage: 6x
        Stake: dynamic (wallet_balance / max_positions)
```

**Config:**
```json
"queue": {
    "top_k": 3,
    "confirm_candles": 1,
    "confirm_z_ratio": 1.0,
    "min_score": 0.45
},
"basket": {
    "max_positions": 4,
    "entry_z": 2.0
}
```

**UI representation:**
- **Long Queue panel:** ordered list of top-K pairs with score, rank, and status (WAITING/READY/ENTERED)
- **Short Queue panel:** same for short side
- Per-pair: queue position badge (#1, #2, #3, or "—" if not in queue)
- Rejected entries: show reason (outranked, below min_score, max positions, cooldown)
- Score bar: shows min_score threshold line with pair's score position

---

## LAYER 7: Exit Conditions

**Purpose:** Close trades when the mean-reversion thesis completes (z reverts to zero) or when safety limits are hit.

Exits are checked every candle for every open trade, in priority order:

### Exit 1: `basket_max_loss` (safety net)
```
current_profit < -15%  →  EXIT immediately
```
- Catastrophe protection. Should rarely trigger.
- **UI:** red danger bar at -15%

### Exit 2: `basket_revert_profit` (primary exit — the happy path)
```
LONG:  basket_z reverted above -exit_z (-0.3) AND profit > profit_lock (0.2%)
SHORT: basket_z reverted below +exit_z (+0.3) AND profit > profit_lock (0.2%)
```
- The thesis worked: pair caught up to the basket, and we have profit.
- This is the most common exit (73% of all exits in backtest).
- **UI:** green progress bar showing z reverting toward 0

### Exit 3: `basket_revert_neutral` (breakeven exit)
```
LONG:  basket_z crossed above 0 AND profit > 0
SHORT: basket_z crossed below 0 AND profit > 0
```
- Z fully reverted past zero. Take any positive profit.
- **UI:** yellow "break even" indicator

### Exit 4: `basket_diverge_stop` (thesis failed)
```
LONG:  basket_z fell below loss_exit_z (-4.0) AND profit < -2%
SHORT: basket_z rose above +4.0 AND profit < -2%
```
- The pair kept diverging instead of reverting. Cut losses.
- **UI:** red divergence warning

### Exit 5: `basket_time_stop` (patience limit)
```
trade_age >= time_stop_candles (24 candles = 2 hours)
```
- No reversion happened in 2 hours. Exit regardless of profit.
- **UI:** clock/timer showing remaining time

### Exit 6: Trailing Stop (via custom_stoploss)
```
if profit >= 1.2%: activate trailing stop at 0.6% below peak
```
- Locks in profit on winning trades that keep running.
- Not an exit reason itself — creates a dynamic stoploss.

**Config:**
```json
"basket": {
    "exit_z": 0.3,
    "profit_lock": 0.002,
    "loss_exit_z": -4.0,
    "max_loss_per_trade": -0.15,
    "time_stop_candles": 24
},
"risk": {
    "trailing_stop_positive": 0.006,
    "trailing_stop_positive_offset": 0.012
}
```

**UI representation:**
- Per open trade: exit condition progress panel with 5 bars:
  - Revert Profit: z progress toward exit_z + profit status
  - Revert Neutral: z progress toward 0
  - Diverge Stop: z progress toward loss_exit_z
  - Max Loss: profit progress toward -15%
  - Time Stop: time remaining (candles/minutes)
- Active trailing stop indicator when profit > 1.2%

---

## DCA (Dollar Cost Average)

**Purpose:** Add to winning positions to increase exposure when the trade is working.

**Logic:**
```
After 1st fill, if profit >= 1.0%:  add 50% of original stake
After 2nd fill, if profit >= 2.0%:  add 30% of original stake
Maximum 2 additional entries per trade.
```

**Config:**
```json
"dca": {
    "max_adds": 2,
    "thresholds": [0.01, 0.02],
    "multipliers": [0.5, 0.3]
}
```

**UI representation:**
- Per trade: DCA fills count (0/2, 1/2, 2/2) with threshold progress bars

---

## Dynamic Stake Sizing

**Purpose:** Divide wallet balance across trade slots dynamically.

**Logic:**
```
available = wallet_balance × (1 - reserve_pct - dca_reserve_pct)
stake = available / max_positions
stake = clamp(stake, min_stake, stake_cap)
```

**Config:**
```json
"stake": {
    "mode": "dynamic",
    "reserve_pct": 0.10,        // 10% reserve (never traded)
    "dca_reserve_pct": 0.15,    // 15% reserved for DCA adds
    "stake_cap": 200.0,         // max $200 per position
    "min_stake": 10.0           // minimum $10
}
```

---

## State Summary: All Variables per Candle

### Per-pair variables (20 pairs):

| Variable | Source | Range | Used In |
|---|---|---|---|
| `basket_z` | Layer 1 | -inf to +inf (typically -4 to +4) | Scoring, Entry, Exit |
| `basket_spread` | Layer 1 | float | UI only |
| `vol_ratio` | Layer 3 | 0+ (typically 0.5 to 3.0) | Scoring, Entry filter |
| `vol_ok` | Layer 3 | bool | Entry filter |
| `score` | Layer 5 | 0.0 to 1.0 | Queue ranking |
| `queue_position` | Layer 6 | 1 to top_k, or null | Entry gate |
| `confirm_count` | Layer 6 | 0 to confirm_candles | Entry gate |
| `cooldown_remaining` | Layer 5 | 0 to 36 candles | Score factor |

### Global variables (from BTC):

| Variable | Source | Range | Used In |
|---|---|---|---|
| `btc_mom` | Layer 2 | -10% to +10% | Regime, Entry filter |
| `btc_atr_z` | Layer 2 | -2 to +5 | Regime |
| `btc_pump` | Layer 2 | bool | Entry safety |
| `btc_dump` | Layer 2 | bool | Entry safety |
| `btc_high_vol` | Layer 2 | bool | Entry safety |
| `regime` | Layer 2 | BULL / BEAR / RANGING | Entry direction |

### Per-trade variables (0 to max_positions):

| Variable | Source | Range | Used In |
|---|---|---|---|
| `side` | Entry | "long" / "short" | Exit logic |
| `entry_tag` | Entry | "queue_long" / "queue_short" | Exit routing |
| `current_profit` | Runtime | -100% to +inf | All exit conditions |
| `trade_age` | Runtime | 0 to time_stop_candles | Time stop |
| `current_z` | Layer 7 | float | Reversion exits |
| `dca_fills` | DCA | 0, 1, 2 | DCA logic |
| `leverage` | Entry | 6.0x | Profit calculation |
| `stake_amount` | Entry | dynamic | Position size |

---

## Web UI: Recommended Panels

### 1. Strategy Header
- Strategy name: "V58 Queue Scoring"
- Config summary: Kalman, 6x lev, top-3, min_score 0.45, 20 pairs
- Live/Replay status

### 2. BTC Regime Panel
- Candlestick chart
- Regime badge (BULL/BEAR/RANGING)
- btc_mom, btc_atr_z values
- Pump/Dump/High Vol flags

### 3. Basket Z-Score Chart
- Line chart: basket_z for top-10 pairs
- Threshold lines at ±2.0
- Pair colors matching grid

### 4. All Pairs Grid (5 columns)
- Per pair card:
  - Name + color
  - Signal badge (LONG/SHORT/NEUTRAL)
  - Price
  - Z-score bar (-4 to +4)
  - Z value, Spread %, Vol ratio
  - Queue position (#1, #2, #3) if in queue
  - Score (0-100%) if scored
  - Active trade with profit % if trading

### 5. Entry Queue Panel (NEW for V58)
```
┌─────────────────────────────────────────────────┐
│  LONG QUEUE                    SHORT QUEUE       │
│  ┌─────────────────────┐  ┌─────────────────────┐│
│  │ #1 DOGE  score 0.76 │  │ #1 ETH   score 0.62 ││
│  │    z=-3.2 vol=2.1x  │  │    z=+2.8 vol=1.5x  ││
│  │    ██████████░░ 76%  │  │    ██████░░░░ 62%    ││
│  ├─────────────────────┤  ├─────────────────────┤│
│  │ #2 SOL   score 0.58 │  │ (empty)              ││
│  │    z=-2.5 vol=1.3x  │  │                      ││
│  │    █████░░░░░░ 58%   │  │                      ││
│  ├─────────────────────┤  └─────────────────────┘│
│  │ #3 LINK  score 0.47 │                         │
│  │    z=-2.1 vol=1.1x  │  min_score: ─── 0.45   │
│  │    ████░░░░░░░ 47%   │  ▲ DOGE, SOL pass      │
│  │    ⚠ BELOW MIN 0.45 │  ▼ LINK rejected        │
│  └─────────────────────┘                         │
│                                                   │
│  Slots: 2/4 open │ Cooldown: XRP (1h 20m left)  │
└─────────────────────────────────────────────────┘
```

### 6. Score Breakdown Panel (per pair, expandable)
```
┌─────────────────────────────────────────┐
│  DOGE/USDC — Score: 0.76               │
│                                          │
│  basket_z    ████████████████░░░ 75%  ×0.5 = 0.375 │
│  vol_ratio   █████████████░░░░░ 67%  ×0.2 = 0.134 │
│  velocity    ███████████████░░░ 75%  ×0.2 = 0.150 │
│  cooldown    ████████████████████ 100% ×0.1 = 0.100 │
│              ─────────────────────────────────────── │
│              TOTAL                           0.759  │
│              min_score ──────── 0.45   ✓ PASS       │
└─────────────────────────────────────────┘
```

### 7. Open Trades Panel
- Per trade: pair, side, leverage, profit %, duration, entry score
- Exit conditions with progress bars (same as V53 Out Conditions)

### 8. Trade History
- All closed trades with entry/exit times, profit, exit reason
- Clickable to seek to that candle in replay mode

### 9. Equity Curve
- Cumulative P&L over time

### 10. Activity Log
- Raw events: entries, exits, queue changes, regime changes

---

## Config Reference (v58_config.json)

| Section | Key | Default | Description |
|---|---|---|---|
| **basket** | `pairs` | 20 pairs | Tradeable universe |
| | `btc_ref` | BTC/USDC:USDC | Reference pair for regime |
| | `entry_z` | 2.0 | Z-score threshold for entry candidacy |
| | `exit_z` | 0.3 | Z-score threshold for profit exit |
| | `profit_lock` | 0.002 | Minimum profit to allow reversion exit |
| | `loss_exit_z` | -4.0 | Z-score threshold for divergence stop |
| | `max_positions` | 4 | Max simultaneous open trades |
| | `time_stop_candles` | 24 | Max trade duration (2h at 5m) |
| | `max_loss_per_trade` | -0.15 | Catastrophe stop (-15%) |
| | `bear_mom_threshold` | -1.0 | BTC momentum below this = BEAR |
| | `bull_mom_threshold` | 0.0 | BTC momentum above this = BULL |
| | `zscore_method` | "kalman" | Z-score calculation method |
| | `kalman_gain` | 0.05 | Kalman filter reactivity |
| **queue** | `top_k` | 3 | Max pairs in each queue |
| | `confirm_candles` | 1 | Required candles with signal before entry |
| | `confirm_z_ratio` | 1.0 | Relaxation factor for confirmation threshold |
| | `min_score` | 0.45 | Minimum score to allow entry |
| | `cooldown_candles` | 36 | Cooldown after exit (3 hours) |
| | `weights.basket_z` | 0.5 | Weight for z-score in scoring |
| | `weights.vol_ratio` | 0.2 | Weight for volume in scoring |
| | `weights.spread_velocity` | 0.2 | Weight for spread speed in scoring |
| | `weights.cooldown` | 0.1 | Weight for cooldown bonus in scoring |
| **leverage** | `base_multiplier` | 6.0 | Fixed leverage for all trades |
| **risk** | `trailing_stop_positive` | 0.006 | Trailing distance (0.6%) |
| | `trailing_stop_positive_offset` | 0.012 | Trailing activation (1.2%) |
| **volume** | `vol_ma_window` | 144 | Volume MA period (12h) |
| | `vol_ok_threshold` | 1.0 | Minimum vol_ratio for entry |
| **dca** | `max_adds` | 2 | Max DCA entries per trade |
| | `thresholds` | [0.01, 0.02] | Profit % triggers for DCA |
| | `multipliers` | [0.5, 0.3] | Stake multipliers for DCA |

---

## Backtest Results (Jan-May 2026)

| Metric | V57 (no queue) | V58 (queue) |
|---|---|---|
| Trades | 291 | 179 |
| Win Rate | 88.3% | 89.9% |
| Total Profit | +176.2% | +173.2% |
| Avg Profit/Trade | 2.62% | 4.61% |
| Losses | 34 | 18 |
| Drawdown | 12.82% | 12.67% |
| Avg Duration | 32min | 27min |
