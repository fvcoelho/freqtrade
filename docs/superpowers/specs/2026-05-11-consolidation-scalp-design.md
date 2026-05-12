# Consolidation Scalp Strategy — Design Spec

**Date:** 2026-05-11
**Pair:** BTC/USDT:USDT (dedicated)
**Timeframe:** 5m
**Concept:** Mean-reversion scalper that only operates during BTC consolidation/range-bound periods. Detects support/resistance levels and trades bounces between them.

---

## Architecture

Modular strategy following V52/V53 pattern:

```
user_data/strategies/
└── consolidation_scalp/
    ├── __init__.py
    ├── strategy.py          — IStrategy orchestrator
    ├── config.py            — JSON config loader
    ├── consolidation.py     — Regime filter: is market consolidating?
    ├── levels.py            — 3 S/R engines (order_blocks, pivot_fractal, rolling_minmax)
    ├── entries.py           — Entry logic (level touch + confirmation)
    ├── exits.py             — TP opposite level + time-stop + SL
    └── leverage.py          — Dynamic leverage based on range size
```

Config JSON selects which engine to use via `level_engine` field. All 3 engines share the same interface: receive dataframe, return `support` and `resistance` columns.

---

## Consolidation Filter

Determines **when** to trade. All conditions must be true simultaneously.

**Criteria:**
1. ATR Z-Score < 0.0 — volatility at or below average (ATR 14, z-score window 96 candles = 8h)
2. Range contained — `(rolling_max - rolling_min) / close < 3.5%` over last 96 candles
3. No directional momentum — `abs(close.pct_change(12))` < 1.2% (last 1h)
4. Volume stable — volume z-score between -2.0 and +2.0

**Kill switch (breakout detection):**
- ATR z-score crosses above +1.5 → close all open positions
- Momentum > 2.0% in 1h → close all open positions

```json
{
  "consolidation": {
    "atr_period": 14,
    "atr_zscore_max": 0.0,
    "range_window": 96,
    "range_pct_max": 0.035,
    "momentum_window": 12,
    "momentum_max": 0.012,
    "volume_zscore_range": [-2.0, 2.0],
    "breakout_atr_z": 1.5,
    "breakout_momentum": 0.02
  }
}
```

---

## Level Engines

### Engine 1: Order Blocks (primary, implement first)

Identifies high-volume candles that precede directional moves — institutional accumulation/distribution zones.

**Detection:**
1. Candle with `volume > volume.rolling(20).mean() * 1.5`
2. Followed by directional move of at least 0.3% in next 3 candles
3. Zone = `[low, high]` of the high-volume candle
4. Bullish OB (support): bearish candle followed by rise → demand zone
5. Bearish OB (resistance): bullish candle followed by drop → supply zone
6. OBs expire after 48 candles (4h) without touch, or after 2 touches

**Entry confirmation:** Price enters OB zone + wick rejection (shadow > 60% of body)

```json
{
  "order_blocks": {
    "volume_mult": 1.5,
    "move_threshold": 0.003,
    "move_candles": 3,
    "expiry_candles": 48,
    "max_touches": 2,
    "wick_ratio": 0.6
  }
}
```

### Engine 2: Pivot Fractal

Williams fractal — a point is S/R if it's the min/max of N candles left and right.

**Detection:**
1. Fractal low: `low[i] = min(low[i-N:i+N+1])`, N=5
2. Fractal high: `high[i] = max(high[i-N:i+N+1])`, N=5
3. Cluster: group fractals within 0.15% of each other → average level
4. Level strength = number of touches in cluster

**Entry confirmation:** Price within 0.1% of level + reversal candle (close in opposite direction)

```json
{
  "pivot_fractal": {
    "fractal_window": 5,
    "cluster_pct": 0.0015,
    "min_touches": 2,
    "proximity_pct": 0.001
  }
}
```

### Engine 3: Rolling Min/Max

Simplest approach — adaptive rolling min and max.

**Detection:**
1. `support = rolling_min(low, window)`
2. `resistance = rolling_max(high, window)`
3. Adaptive window: `base_window * (1 + atr_z)` — higher vol = larger window
4. Base window: 48 candles (4h)

**Entry confirmation:** Price within 0.15% of level

```json
{
  "rolling_minmax": {
    "base_window": 48,
    "proximity_pct": 0.0015
  }
}
```

---

## Entries

**Conditions (all simultaneous):**
1. Consolidation filter active
2. Level detected by selected engine
3. Price within proximity zone of level
4. Confirmation candle (wick rejection or close reversal)

**Signals:**
- `enter_long` → price touches support + confirmation
- `enter_short` → price touches resistance + confirmation
- `enter_tag` → `"{engine}_long_support"` or `"{engine}_short_resistance"`

**Cooldown:** 6 candles (30min) between trades on the same level

```json
{
  "entries": {
    "cooldown_candles": 6,
    "require_confirmation": true
  }
}
```

---

## Exits (by priority)

| # | Type | Condition | Tag |
|---|------|-----------|-----|
| 1 | Breakout kill | ATR z > 1.5 or momentum > 2% | `breakout_stop` |
| 2 | SL fixo | -0.5% from entry | `stoploss` |
| 3 | TP opposite level | Price reaches opposite S/R level | `tp_level` |
| 4 | TP partial | +0.3% → close 50% of position | `tp_partial` |
| 5 | Trailing | Activates at +0.4%, trails 0.2% | `trailing` |
| 6 | Time-stop | 36 candles (3h) without TP | `time_stop` |

```json
{
  "exits": {
    "stoploss": -0.005,
    "tp_partial_pct": 0.003,
    "tp_partial_ratio": 0.5,
    "trailing_activate": 0.004,
    "trailing_distance": 0.002,
    "time_stop_candles": 36
  }
}
```

---

## Dynamic Leverage

Based on current range size:

```
range_pct = (rolling_max - rolling_min) / close
leverage = max_lev - (range_pct / range_pct_max) * (max_lev - min_lev)
```

| Range | Leverage |
|-------|----------|
| < 1% (tight) | 6x |
| ~2% | 4x |
| ~3.5% (limit) | 2x |

```json
{
  "leverage": {
    "min_leverage": 2,
    "max_leverage": 6
  }
}
```

---

## Strategy Class Attributes

```python
INTERFACE_VERSION = 3
can_short = True
process_only_new_candles = True
timeframe = "5m"
startup_candle_count = 200
stoploss = -0.05            # safety net, dynamic SL at -0.5% handles most exits
minimal_roi = {}             # disabled, exits handled by custom logic
trailing_stop = False        # handled in custom_stoploss
position_adjustment_enable = False  # no DCA for scalp
```

---

## Backtesting Plan

1. Download BTC/USDT 5m data for last 3 months
2. Run each engine separately via config swap
3. Compare: total profit, win rate, max drawdown, avg trade duration
4. Pick best engine or combine signals
