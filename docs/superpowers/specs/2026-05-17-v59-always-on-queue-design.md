# V59: Always-On Queue with Regime Scoring

## Summary

All 20 pairs are always ranked in two queues (LONG and SHORT) based on their basket z-score sign. The regime BTC is no longer a binary gate — it's a score multiplier. The #1 pair in each queue enters a trade if its adjusted score passes min_score and safety filters. Queues are never empty.

## Problem with V58

V58's queue is empty ~99% of the time because `basket_z` must cross ±2.0 before a pair enters the queue. This makes the queue panel in the UI mostly blank and limits the strategy to extreme divergence events only.

## Design

### Queue Assignment (every candle, every pair except BTC)

- `basket_z < 0` → pair goes to **LONG queue** (lagging behind basket)
- `basket_z > 0` → pair goes to **SHORT queue** (ahead of basket)
- `basket_z == 0` → neither queue (extremely rare)

No threshold. All pairs with any deviation are queued.

### Score Computation (same 4 factors as V58)

```
bz_norm = min(abs(basket_z), 4.0) / 4.0          weight: 0.5
vol_norm = min(vol_ratio, 3.0) / 3.0              weight: 0.2
vel_norm = min(abs(bz[i] - bz[i-3]), 2.0) / 2.0  weight: 0.2
cd_norm = 1.0 if cooldown expired, else 0.0        weight: 0.1

score_raw = 0.5 * bz_norm + 0.2 * vol_norm + 0.2 * vel_norm + 0.1 * cd_norm
```

### Regime Multiplier (NEW — replaces binary gate)

The regime adjusts the score based on whether the trade direction aligns with BTC momentum:

```
score_adjusted = score_raw * regime_multiplier
```

| Regime | Condition | LONG multiplier | SHORT multiplier |
|---|---|---|---|
| BULL | `btc_mom > 0.0` | 1.0 | 0.3 |
| RANGING | `-1.0 < btc_mom <= 0.0` | 0.6 | 0.6 |
| BEAR | `btc_mom <= -1.0` | 0.3 | 1.0 |

Multipliers are configurable:
```json
"regime_multipliers": {
    "bull_long": 1.0, "bull_short": 0.3,
    "ranging_long": 0.6, "ranging_short": 0.6,
    "bear_long": 0.3, "bear_short": 1.0
}
```

**Effect:** A pair with score_raw=0.76 in BULL regime:
- LONG queue: 0.76 * 1.0 = 0.76 (passes min_score 0.45)
- SHORT queue: 0.76 * 0.3 = 0.23 (rejected by min_score)

Counter-trend trades need extremely high raw scores to pass.

### Queue Ranking

Each queue is sorted by `score_adjusted` descending. Position #1 is the best candidate.

All pairs appear in the ranking with their adjusted score, even if below min_score. The UI shows the full ranking — the min_score line separates "would enter" from "would not".

### Entry Gate

The **#1 pair** in each queue can enter a trade if ALL conditions are met:

1. `score_adjusted >= min_score` (0.45)
2. `vol_ok == true` (volume above average)
3. Safety: `!btc_high_vol` (no chaos)
4. Safety: `!btc_dump` (for LONG) or `!btc_pump` (for SHORT)
5. `open_trades < max_positions` (4)
6. Pair has no open trade

Only #1 enters. #2 and below wait. If #1 is blocked (open trade, safety), #2 does NOT get promoted — the queue waits for next candle.

### Exits

Identical to V58/V57:
- `basket_revert_profit`: z reverted + profit > 0.2%
- `basket_revert_neutral`: z crossed zero + profit > 0
- `basket_diverge_stop`: z diverged to ±4.0 + loss > 2%
- `basket_max_loss`: profit < -15%
- `basket_time_stop`: trade age >= 24 candles (2h)
- Trailing stop: activates at 1.2%, trails at 0.6%

### Trade Type Classification

Same as V58:
- **Breakout**: `velocity >= 1.0 AND vol_ratio >= 2.0` (orange)
- **Trending**: `abs(btc_mom) >= 1.5 AND btc_atr_z < 2.0` (blue)
- **Mean Reversion**: default (teal)

### Configuration

```json
{
    "timeframe": "5m",
    "startup_candle_count": 900,
    "basket": {
        "pairs": ["BTC/USDC:USDC", "ETH/USDC:USDC", ...20 pairs...],
        "btc_ref": "BTC/USDC:USDC",
        "exit_z": 0.3,
        "profit_lock": 0.002,
        "loss_exit_z": -4.0,
        "max_positions": 4,
        "time_stop_candles": 24,
        "max_loss_per_trade": -0.15,
        "zscore_method": "kalman",
        "kalman_gain": 0.05
    },
    "zscore": {
        "zscore_window": 288
    },
    "risk": {
        "stoploss": -0.99,
        "trailing_stop_positive": 0.006,
        "trailing_stop_positive_offset": 0.012
    },
    "btc_trend": {
        "timeframe": "1h",
        "pump_threshold": 3.0,
        "dump_threshold": -3.0,
        "high_vol_threshold": 2.0,
        "mom_period": 4,
        "atr_period": 14,
        "atr_z_window": 72
    },
    "volume": {
        "vol_ma_window": 144,
        "vol_ok_threshold": 1.0
    },
    "leverage": {
        "base_multiplier": 6.0
    },
    "dca": {
        "max_adds": 2,
        "thresholds": [0.01, 0.02],
        "multipliers": [0.5, 0.3]
    },
    "stake": {
        "mode": "dynamic",
        "reserve_pct": 0.1,
        "dca_reserve_pct": 0.15,
        "stake_cap": 200.0,
        "min_stake": 10.0,
        "rebalance_secs": 300
    },
    "queue": {
        "min_score": 0.45,
        "cooldown_candles": 36,
        "weights": {
            "basket_z": 0.5,
            "vol_ratio": 0.2,
            "spread_velocity": 0.2,
            "cooldown": 0.1
        },
        "regime_multipliers": {
            "bull_long": 1.0, "bull_short": 0.3,
            "ranging_long": 0.6, "ranging_short": 0.6,
            "bear_long": 0.3, "bear_short": 1.0
        }
    }
}
```

Note: `entry_z`, `top_k`, `confirm_candles` removed from queue config — no longer needed.
`bear_mom_threshold` and `bull_mom_threshold` removed from basket config — regime is now in the multiplier logic.

## Architecture

### File changes from V58

| File | Action | Changes |
|---|---|---|
| `zscore_v59/entry_queue.py` | Copy + modify | Remove entry_z filter from build_queues, add regime_multiplier to scoring, queue all pairs by z sign, only #1 enters |
| `zscore_v59/strategy.py` | Copy + modify | Update populate_entry_trend to signal all pairs (no threshold), update confirm_trade_entry for V59 queue logic |
| `v59_config.json` | Create | V58 config minus entry_z/top_k/confirm_candles, plus regime_multipliers |
| `bot_controller.py` | Modify | Update bt-signals queue loop for V59 (no threshold, regime multiplier, all pairs in queue) |
| `Monitor2View.vue` | Modify | Queue panels always show all pairs, score shows raw + multiplier |

All other modules (basket.py, btc_trend.py, volume.py, dca.py, leverage.py, stake.py, state.py, config.py) copied from V58 unchanged.

## Success Criteria

- Backtest on 2026-01-17 to 2026-05-17:
  - More trades than V58 (179) due to lower effective threshold
  - Comparable or better win rate than V58 (89.9%)
  - Profit comparable to V57 baseline (+176%)
- Queue panels in replay UI always show ranked pairs (never empty)
- Regime multiplier visible in UI: raw score, multiplier, adjusted score per pair
