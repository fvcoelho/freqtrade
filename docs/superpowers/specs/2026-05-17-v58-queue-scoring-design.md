# V58: Queue-Based Scoring Entry

## Summary

Replace V57's per-pair independent entry logic with a centralized scoring and queue system. Each candle, all pairs receive a multi-factor score. The highest-scoring pairs enter ranked queues (long/short). A pair must persist in the top-K of its queue for N consecutive candles before it can enter a trade. Exits remain identical to V57.

## Problem

V57 enters any pair the moment `basket_z` crosses the threshold. When multiple pairs cross simultaneously, selection is arbitrary (first processed wins). There is no prioritization — a weak signal with barely-crossed threshold gets the same treatment as a strong divergence with high volume confirmation.

## Design

### Scoring

Each candle, every non-BTC pair receives a composite score from 4 weighted factors:

| Factor | Computation | Range | Default Weight |
|---|---|---|---|
| `basket_z` | `min(abs(basket_z), 4.0) / 4.0` | 0.0–1.0 | 0.5 |
| `vol_ratio` | `min(vol_ratio, 3.0) / 3.0` | 0.0–1.0 | 0.2 |
| `spread_velocity` | `min(abs(basket_z - basket_z_3_candles_ago), 2.0) / 2.0` | 0.0–1.0 | 0.2 |
| `cooldown_bonus` | 1.0 if no trade closed on this pair within last `cooldown_candles`, else 0.0 | 0.0 or 1.0 | 0.1 |

**Final score** = `w_bz * basket_z_norm + w_vol * vol_norm + w_vel * velocity_norm + w_cd * cooldown_norm`

All factors are normalized to 0.0–1.0 before weighting. Final score range: 0.0–1.0.

### Queue Construction

Each candle, two queues are built:

**Long Queue** — pairs where ALL of:
- `basket_z < -entry_z` (lagging behind basket)
- `btc_mom > bull_threshold` (bull/ranging regime)
- `btc_dump == False` and `btc_high_vol == False` (safety)
- `vol_ok == True`
- No open trade on this pair

Sorted by score descending. Only top-K kept.

**Short Queue** — pairs where ALL of:
- `basket_z > entry_z` (ahead of basket)
- `btc_mom < bear_threshold` (bear regime)
- `btc_pump == False` and `btc_high_vol == False` (safety)
- `vol_ok == True`
- No open trade on this pair

Sorted by score descending. Only top-K kept.

### Confirmation

Each pair tracks a `confirm_count` (integer, persisted in module-level state):
- If the pair is in the top-K of its queue this candle: `confirm_count += 1`
- If the pair is NOT in the top-K: `confirm_count = 0` (reset)
- When `confirm_count >= confirm_candles`: pair is **ready to enter**

The confirmation counter is per-pair and per-side (long/short tracked separately).

### Entry Execution

On each candle, after queue construction and confirmation update:
1. Collect all pairs with `confirm_count >= confirm_candles` (ready pairs)
2. Sort ready pairs by score descending
3. For each ready pair, in order:
   - If `open_trades < max_positions` and pair has no open trade: **enter**
   - Reset that pair's `confirm_count` to 0 after entry
4. Entry tag: `"queue_long"` or `"queue_short"`

### Exits

Identical to V57. No changes:
- `basket_revert_profit` — z reverted + profit > profit_lock
- `basket_revert_neutral` — z crossed zero + positive profit
- `basket_diverge_stop` — z diverged further + loss > 2%
- `basket_max_loss` — profit < -15%
- `basket_time_stop` — trade age >= time_stop_candles

### Configuration

Added to `v58_config.json` under a new `queue` section:

```json
{
  "queue": {
    "top_k": 3,
    "confirm_candles": 3,
    "cooldown_candles": 36,
    "weights": {
      "basket_z": 0.5,
      "vol_ratio": 0.2,
      "spread_velocity": 0.2,
      "cooldown": 0.1
    }
  }
}
```

All other config sections (`basket`, `zscore`, `risk`, `btc_trend`, `volume`, `leverage`, `dca`, `stake`) are inherited from V57 unchanged.

## Architecture

### File Structure

```
user_data/strategies/
  zscore_v58/
    __init__.py
    strategy.py       — main strategy class, orchestrates queue + basket exits
    queue.py          — NEW: scoring, queue construction, confirmation tracking
    basket.py         — copied from V57 (z-score computation + exit logic)
    btc_trend.py      — copied from V57
    volume.py         — copied from V57
    config.py         — copied from V57
    dca.py            — copied from V57
    leverage.py       — copied from V57
    stake.py          — copied from V57
    state.py          — copied from V57
  v58_config.json     — V57 config + queue section
```

### New Module: `queue.py` (~150 lines)

**Module-level state** (persisted across candles via dict):
- `_confirm_long: dict[str, int]` — per-pair long confirmation counter
- `_confirm_short: dict[str, int]` — per-pair short confirmation counter
- `_last_exit_candle: dict[str, int]` — per-pair last exit candle index (for cooldown)
- `_candle_count: int` — global candle counter

**Functions:**

```python
def compute_scores(
    pair_data: dict[str, dict],  # {pair: {basket_z, vol_ratio, vol_ok, btc_mom, ...}}
    cfg: dict,
    candle_index: int,
) -> dict[str, float]:
    """Compute score for each pair. Returns {pair: score}."""

def build_queues(
    scores: dict[str, float],
    pair_data: dict[str, dict],
    cfg: dict,
) -> tuple[list[str], list[str]]:
    """Build long and short queues (top-K, sorted by score desc)."""

def update_confirmation(
    long_queue: list[str],
    short_queue: list[str],
    cfg: dict,
) -> list[tuple[str, str]]:
    """Update confirm counters. Returns list of (pair, side) ready to enter."""

def record_exit(pair: str, candle_index: int):
    """Record exit for cooldown tracking."""

def reset():
    """Reset all state (called on strategy init)."""
```

### Changes to `strategy.py`

**`populate_indicators`**: Same as V57 — computes basket_z, btc_trend, volume for each pair.

**`populate_entry_trend`**: Instead of calling `basket.generate_basket_entries()`:
1. Collect current candle data for all pairs (from `_df_cache`)
2. Call `queue.compute_scores()` → `queue.build_queues()` → `queue.update_confirmation()`
3. For pairs returned as "ready", set `enter_long=1` or `enter_short=1`

**`confirm_trade_entry`**: Same as V57 — enforce `max_positions` and no duplicate pairs.

**`custom_exit`**: Same as V57 — delegates to `basket.check_basket_exit()`.

**`confirm_trade_exit`**: Added: call `queue.record_exit(pair, candle_index)` for cooldown tracking.

## Implementation Notes

- The queue module uses module-level dicts for state (same pattern as V57's `basket.py` cache). This works in backtesting because `process_only_new_candles = True` means each candle is processed once per pair.
- In backtesting, `populate_entry_trend` is called per-pair, not globally. The queue logic must handle this: scores are computed on the first pair of each candle cycle, cached, and reused for subsequent pairs in the same cycle.
- `spread_velocity` uses a 3-candle lookback on `basket_z`. This is read from the dataframe directly (`basket_z.shift(3)`), not from state.

## Success Criteria

- Backtest on same 4-month period (2026-01-17 to 2026-05-10) should show:
  - Fewer total trades than V57 (queue filters weak entries)
  - Higher win rate (only strongest setups enter)
  - Comparable or better total profit
  - Lower drawdown (better entry selection)
