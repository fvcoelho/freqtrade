# ZScoreV55Strategy — Grid Consolidation + Mean-Reversion Hybrid

## Summary

V55 extends V54 with a grid trading module for consolidation regimes. During consolidation, the strategy divides the price range into N configurable levels and trades the bounces (buy on descent, sell on ascent). During ranging, it uses the existing V54 mean-reversion z-score logic. During trending, it does nothing.

## Architecture

```
zscore_v55/
├── __init__.py          # exports ZScoreV55Strategy
├── strategy.py          # orchestrator (fork V54, adds grid dispatch)
├── grid.py              # NEW — grid level computation + signal generation
├── entries.py           # ranging entries (from V54, unchanged)
├── exits.py             # exits with per-regime time_stop
├── config.py            # config loader (from V54, unchanged)
├── groups.py            # group management (from V54, unchanged)
├── zscore.py            # z-score computation (from V54, unchanged)
├── leverage.py          # leverage sizing (from V54, unchanged)
├── state.py             # persistent state (from V54, unchanged)
├── risk.py              # risk gates (from V54, unchanged)
├── dca.py               # DCA logic (from V54, unchanged)
```

### Modules unchanged from V54
config, groups, zscore, leverage, state, risk, dca, entries

### Modules modified
- **strategy.py** — adds grid dispatch in `populate_indicators` and `populate_entry_trend`
- **exits.py** — adds per-regime time_stop based on entry tag

### New module
- **grid.py** — grid level computation and buy/sell signal generation

## Grid Module (`grid.py`)

### Range Detection
Uses rolling high/low from the consolidation regime filter (already computed):
- `rolling_high = high.rolling(range_window).max()`
- `rolling_low = low.rolling(range_window).min()`

These values update dynamically each candle, so levels adapt as the range shifts.

### Level Computation
Divides the range into N configurable levels (default 5):
```
range_size = rolling_high - rolling_low
level[i] = rolling_low + (i / N) * range_size

Example with 5 levels, range 100-105:
  level_0 = 100.0 (bottom)
  level_1 = 101.0
  level_2 = 102.0
  level_3 = 103.0
  level_4 = 104.0
  level_5 = 105.0 (top)
```

### Signal Generation

**Buy (enter_long):** price crosses DOWN through a level + `is_consolidating` + `safe_long` + confirmations
**Sell (enter_short):** price crosses UP through a level + `is_consolidating` + `safe_short` + confirmations

Confirmations (configurable):
- `require_confirmation`: bullish candle for long, bearish for short
- `rsi_filter`: RSI < `rsi_oversold` for long, RSI > `rsi_overbought` for short

Cooldown: configurable candles between signals to avoid overtrading.

Entry tags identify level and group: `grid_long_L2_A`, `grid_short_L4_B`

### Safety Filters
- Only operates during `is_consolidating` (ATR z-score low, momentum low, range tight)
- BTC regime filter (blocks during pump/dump/high vol)
- Volume filter (`vol_ok`)

### Functions

```python
def compute_levels(dataframe, cfg) -> DataFrame:
    """Add grid level columns to dataframe. Returns dataframe with:
    - grid_level_0 through grid_level_N
    - pos_in_range (0=bottom, 1=top)
    """

def generate(dataframe, pair, cfg, group_sub1, group_sub2, group_name) -> DataFrame:
    """Generate grid entry signals during consolidation.
    Adds enter_long, enter_short, enter_tag where is_consolidating.
    """
```

## Strategy Orchestration (`strategy.py`)

### Indicator Flow
```
populate_indicators():
  1. BTC trend (from V54)
  2. Z-score per pair (from V54)
  3. Per-group spread z-score (from V54)
  4. Regime filter (from V54)
  5. Spread volatility filter (from V54)
  6. Volume filter (from V54)
  7. NEW: grid.compute_levels() — compute grid levels
```

### Entry Flow
```
populate_entry_trend():
  For each group:
    1. If is_consolidating → grid.generate() — grid signals
    2. If is_ranging → entries.generate() — mean-reversion (V54)
    3. If is_trending → no signals
```

Consolidation has priority. A candle classified as consolidating uses grid; ranging uses mean-reversion. They never fire on the same candle.

## Exits — Per-Regime Time Stop

The `check_exit()` function inspects the trade's `enter_tag` to determine which time stop to apply:
- Tag starts with `grid_` → uses `grid_time_stop_candles`
- Tag starts with `mr_` or `duo_` or `consol_` → uses `ranging_time_stop_candles`

All other exit logic (trailing, tp_level, breakout kill, market stops) applies identically to both regimes.

## Configuration (`v55_config.json`)

Inherits all V54 config. Adds `grid` section and per-regime time stops:

```json
{
    "grid": {
        "enabled": true,
        "n_levels": 5,
        "cooldown_candles": 4,
        "require_confirmation": true,
        "rsi_filter": true,
        "rsi_oversold": 40,
        "rsi_overbought": 60
    },
    "exits": {
        "grid_time_stop_candles": 6,
        "ranging_time_stop_candles": 12
    }
}
```

### Grid Parameters

| Param | Default | Description |
|---|---|---|
| `enabled` | true | Enable/disable grid module |
| `n_levels` | 5 | Number of divisions in the range |
| `cooldown_candles` | 4 | Minimum candles between grid signals |
| `require_confirmation` | true | Require bullish (long) or bearish (short) candle |
| `rsi_filter` | true | Filter by RSI oversold/overbought |
| `rsi_oversold` | 40 | RSI below this confirms long |
| `rsi_overbought` | 60 | RSI above this confirms short |

### Exit Parameters

| Param | Default | Description |
|---|---|---|
| `grid_time_stop_candles` | 6 | Time stop for grid trades (30min at 5m) |
| `ranging_time_stop_candles` | 12 | Time stop for ranging trades (1h at 5m) |

### Consolidation Regime (activated, was disabled in V53/V54)

The regime thresholds from V54 are kept but with real values:
- `consolidation_atr_z`: -0.5 (ATR z-score must be below this)
- `consolidation_spread_max`: 1.5 (spread z-score must be below this)
- `consolidation_btc_mom_max`: 0.8 (BTC momentum must be below this)

## Regime Summary

| Regime | Condition | Strategy | Entry Tags |
|---|---|---|---|
| Consolidation | ATR z low + spread small + BTC mom low | Grid buy/sell at levels | `grid_long_L*`, `grid_short_L*` |
| Ranging | Not trending, not consolidation | Mean-reversion z-score (V54) | `mr_long_*`, `mr_short_*`, `duo_*` |
| Trending | BTC momentum high or ATR z high | No trades | — |
