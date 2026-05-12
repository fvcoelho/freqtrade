# Consolidation Scalp Strategy — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a BTC-only mean-reversion scalper that detects consolidation regimes and trades bounces off dynamic support/resistance levels, with 3 swappable S/R engines.

**Architecture:** Modular strategy under `user_data/strategies/consolidation_scalp/` following V53 pattern. A JSON config selects one of 3 level engines (order_blocks, pivot_fractal, rolling_minmax). The strategy only trades BTC/USDT:USDT on 5m timeframe.

**Tech Stack:** Python 3.11+, pandas, numpy, freqtrade IStrategy v3

---

### Task 1: Config loader + JSON config

**Files:**
- Create: `user_data/strategies/consolidation_scalp/__init__.py`
- Create: `user_data/strategies/consolidation_scalp/config.py`
- Create: `user_data/strategies/consolidation_scalp_config.json`

- [ ] **Step 1: Create empty package**

```python
# user_data/strategies/consolidation_scalp/__init__.py
```

- [ ] **Step 2: Create config loader**

```python
# user_data/strategies/consolidation_scalp/config.py
"""Configuration loader for Consolidation Scalp strategy."""
from __future__ import annotations

import json
from pathlib import Path


def load(path: Path) -> dict:
    """Load and return JSON config dict."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path, "r") as f:
        return json.load(f)
```

- [ ] **Step 3: Create JSON config file**

```json
{
    "_comment": "Consolidation Scalp — BTC mean-reversion in range-bound markets",
    "pair": "BTC/USDT:USDT",
    "timeframe": "5m",
    "startup_candle_count": 200,
    "stake_per_position": 400.0,
    "max_open_trades": 1,

    "level_engine": "order_blocks",

    "consolidation": {
        "atr_period": 14,
        "atr_zscore_window": 96,
        "atr_zscore_max": 0.0,
        "range_window": 96,
        "range_pct_max": 0.035,
        "momentum_window": 12,
        "momentum_max": 0.012,
        "volume_zscore_window": 96,
        "volume_zscore_range": [-2.0, 2.0],
        "breakout_atr_z": 1.5,
        "breakout_momentum": 0.02
    },

    "order_blocks": {
        "volume_mult": 1.5,
        "volume_ma_window": 20,
        "move_threshold": 0.003,
        "move_candles": 3,
        "expiry_candles": 48,
        "max_touches": 2,
        "wick_ratio": 0.6
    },

    "pivot_fractal": {
        "fractal_window": 5,
        "cluster_pct": 0.0015,
        "min_touches": 2,
        "proximity_pct": 0.001
    },

    "rolling_minmax": {
        "base_window": 48,
        "proximity_pct": 0.0015
    },

    "entries": {
        "cooldown_candles": 6,
        "require_confirmation": true
    },

    "exits": {
        "stoploss": -0.005,
        "tp_partial_pct": 0.003,
        "tp_partial_ratio": 0.5,
        "trailing_activate": 0.004,
        "trailing_distance": 0.002,
        "time_stop_candles": 36,
        "breakout_atr_z": 1.5,
        "breakout_momentum": 0.02
    },

    "leverage": {
        "min_leverage": 2,
        "max_leverage": 6,
        "range_pct_max": 0.035
    }
}
```

- [ ] **Step 4: Commit**

```bash
git add user_data/strategies/consolidation_scalp/__init__.py \
        user_data/strategies/consolidation_scalp/config.py \
        user_data/strategies/consolidation_scalp_config.json
git commit -m "feat(scalp): add config loader and JSON config"
```

---

### Task 2: Consolidation filter module

**Files:**
- Create: `user_data/strategies/consolidation_scalp/consolidation.py`

- [ ] **Step 1: Create consolidation filter**

This module adds indicator columns to the dataframe and exposes a boolean mask for "is consolidating".

```python
# user_data/strategies/consolidation_scalp/consolidation.py
"""Consolidation regime filter.

Adds columns:
    - atr: ATR(period)
    - atr_zscore: z-score of ATR over window
    - range_pct: (rolling_max - rolling_min) / close
    - momentum: abs(close.pct_change(window))
    - vol_zscore: z-score of volume over window
    - is_consolidating: bool — all criteria met
    - is_breakout: bool — kill switch triggered
"""
from __future__ import annotations

import numpy as np
from pandas import DataFrame


def compute(dataframe: DataFrame, cfg: dict) -> DataFrame:
    """Add consolidation columns to dataframe. Mutates and returns dataframe."""
    c = cfg["consolidation"]

    # ATR
    high = dataframe["high"]
    low = dataframe["low"]
    close = dataframe["close"]
    prev_close = close.shift(1)

    tr = np.maximum(
        high - low,
        np.maximum(abs(high - prev_close), abs(low - prev_close)),
    )
    atr = tr.rolling(c["atr_period"]).mean()
    dataframe["atr"] = atr

    # ATR z-score
    atr_mean = atr.rolling(c["atr_zscore_window"]).mean()
    atr_std = atr.rolling(c["atr_zscore_window"]).std()
    dataframe["atr_zscore"] = (atr - atr_mean) / atr_std.replace(0, np.nan)
    dataframe["atr_zscore"] = dataframe["atr_zscore"].fillna(0)

    # Range percent
    rw = c["range_window"]
    rolling_high = high.rolling(rw).max()
    rolling_low = low.rolling(rw).min()
    dataframe["range_pct"] = (rolling_high - rolling_low) / close
    dataframe["rolling_high"] = rolling_high
    dataframe["rolling_low"] = rolling_low

    # Momentum
    mw = c["momentum_window"]
    dataframe["momentum"] = close.pct_change(mw).abs()

    # Volume z-score
    vol = dataframe["volume"]
    vw = c["volume_zscore_window"]
    vol_mean = vol.rolling(vw).mean()
    vol_std = vol.rolling(vw).std()
    dataframe["vol_zscore"] = (vol - vol_mean) / vol_std.replace(0, np.nan)
    dataframe["vol_zscore"] = dataframe["vol_zscore"].fillna(0)

    # Consolidation flag
    vz_min, vz_max = c["volume_zscore_range"]
    dataframe["is_consolidating"] = (
        (dataframe["atr_zscore"] < c["atr_zscore_max"])
        & (dataframe["range_pct"] < c["range_pct_max"])
        & (dataframe["momentum"] < c["momentum_max"])
        & (dataframe["vol_zscore"] >= vz_min)
        & (dataframe["vol_zscore"] <= vz_max)
    )

    # Breakout kill switch
    dataframe["is_breakout"] = (
        (dataframe["atr_zscore"] > c["breakout_atr_z"])
        | (dataframe["momentum"] > c["breakout_momentum"])
    )

    return dataframe
```

- [ ] **Step 2: Commit**

```bash
git add user_data/strategies/consolidation_scalp/consolidation.py
git commit -m "feat(scalp): add consolidation regime filter"
```

---

### Task 3: Levels module — 3 S/R engines

**Files:**
- Create: `user_data/strategies/consolidation_scalp/levels.py`

- [ ] **Step 1: Create levels module with all 3 engines**

```python
# user_data/strategies/consolidation_scalp/levels.py
"""Support/Resistance level detection engines.

All engines add these columns to the dataframe:
    - support: nearest support price level
    - resistance: nearest resistance price level
    - at_support: bool — price within proximity of support
    - at_resistance: bool — price within proximity of resistance

Engine selection via cfg["level_engine"]: "order_blocks" | "pivot_fractal" | "rolling_minmax"
"""
from __future__ import annotations

import numpy as np
from pandas import DataFrame


def compute(dataframe: DataFrame, cfg: dict) -> DataFrame:
    """Dispatch to the selected engine. Mutates and returns dataframe."""
    engine = cfg["level_engine"]
    if engine == "order_blocks":
        return _order_blocks(dataframe, cfg["order_blocks"])
    elif engine == "pivot_fractal":
        return _pivot_fractal(dataframe, cfg["pivot_fractal"])
    elif engine == "rolling_minmax":
        return _rolling_minmax(dataframe, cfg["rolling_minmax"], cfg["consolidation"])
    else:
        raise ValueError(f"Unknown level engine: {engine}")


# =============================================================================
# Engine 1: Order Blocks
# =============================================================================

def _order_blocks(dataframe: DataFrame, cfg: dict) -> DataFrame:
    """Detect order blocks — high-volume candles preceding directional moves.

    Bullish OB (support): bearish candle + subsequent rise → demand zone
    Bearish OB (resistance): bullish candle + subsequent drop → supply zone

    OBs expire after expiry_candles or max_touches.
    """
    close = dataframe["close"].values
    high = dataframe["high"].values
    low = dataframe["low"].values
    open_ = dataframe["open"].values
    volume = dataframe["volume"].values

    vol_ma_win = cfg["volume_ma_window"]
    vol_mult = cfg["volume_mult"]
    move_thresh = cfg["move_threshold"]
    move_candles = cfg["move_candles"]
    expiry = cfg["expiry_candles"]
    max_touches = cfg["max_touches"]
    wick_ratio = cfg["wick_ratio"]

    n = len(dataframe)
    support = np.full(n, np.nan)
    resistance = np.full(n, np.nan)
    at_support = np.zeros(n, dtype=bool)
    at_resistance = np.zeros(n, dtype=bool)

    # Rolling volume mean
    vol_ma = dataframe["volume"].rolling(vol_ma_win).mean().values

    # Track active OBs: list of (zone_low, zone_high, type, birth_idx, touches)
    active_obs: list[list] = []

    for i in range(vol_ma_win + move_candles, n):
        # Check for new OB formation at candle i - move_candles
        src = i - move_candles
        if volume[src] > vol_ma[src] * vol_mult and not np.isnan(vol_ma[src]):
            is_bearish_candle = close[src] < open_[src]
            is_bullish_candle = close[src] > open_[src]

            # Check subsequent move
            if i < n:
                future_max = max(close[src + 1 : i + 1]) if src + 1 <= i else close[src]
                future_min = min(close[src + 1 : i + 1]) if src + 1 <= i else close[src]
                move_up = (future_max - close[src]) / close[src]
                move_down = (close[src] - future_min) / close[src]

                if is_bearish_candle and move_up >= move_thresh:
                    # Bullish OB — demand zone (support)
                    active_obs.append([low[src], high[src], "support", src, 0])
                elif is_bullish_candle and move_down >= move_thresh:
                    # Bearish OB — supply zone (resistance)
                    active_obs.append([low[src], high[src], "resistance", src, 0])

        # Expire old OBs and count touches
        new_active = []
        best_support = np.nan
        best_resistance = np.nan
        best_sup_dist = float("inf")
        best_res_dist = float("inf")

        for ob in active_obs:
            zone_low, zone_high, ob_type, birth, touches = ob

            # Expire by age
            if i - birth > expiry:
                continue

            # Check touch
            price = close[i]
            in_zone = zone_low <= price <= zone_high

            if in_zone:
                ob[4] += 1
                if ob[4] > max_touches:
                    continue  # Expired by touches

            # Track nearest levels
            zone_mid = (zone_low + zone_high) / 2
            dist = abs(price - zone_mid)

            if ob_type == "support" and dist < best_sup_dist:
                best_sup_dist = dist
                best_support = zone_mid
                # Check wick rejection for at_support
                if in_zone:
                    body = abs(close[i] - open_[i])
                    lower_wick = min(close[i], open_[i]) - low[i]
                    total_range = high[i] - low[i]
                    if total_range > 0 and lower_wick / total_range >= wick_ratio:
                        at_support[i] = True
                    elif in_zone:
                        at_support[i] = True

            elif ob_type == "resistance" and dist < best_res_dist:
                best_res_dist = dist
                best_resistance = zone_mid
                if in_zone:
                    body = abs(close[i] - open_[i])
                    upper_wick = high[i] - max(close[i], open_[i])
                    total_range = high[i] - low[i]
                    if total_range > 0 and upper_wick / total_range >= wick_ratio:
                        at_resistance[i] = True
                    elif in_zone:
                        at_resistance[i] = True

            new_active.append(ob)

        active_obs = new_active
        support[i] = best_support
        resistance[i] = best_resistance

    dataframe["support"] = support
    dataframe["resistance"] = resistance
    dataframe["at_support"] = at_support
    dataframe["at_resistance"] = at_resistance

    return dataframe


# =============================================================================
# Engine 2: Pivot Fractal
# =============================================================================

def _pivot_fractal(dataframe: DataFrame, cfg: dict) -> DataFrame:
    """Detect S/R via Williams fractals — local min/max of N candles.

    Groups nearby fractals into clusters. Level strength = touch count.
    """
    n_window = cfg["fractal_window"]
    cluster_pct = cfg["cluster_pct"]
    min_touches = cfg["min_touches"]
    proximity_pct = cfg["proximity_pct"]

    high = dataframe["high"].values
    low = dataframe["low"].values
    close = dataframe["close"].values
    n = len(dataframe)

    support = np.full(n, np.nan)
    resistance = np.full(n, np.nan)
    at_support = np.zeros(n, dtype=bool)
    at_resistance = np.zeros(n, dtype=bool)

    # Collect fractal points
    fractal_lows: list[tuple[int, float]] = []
    fractal_highs: list[tuple[int, float]] = []

    for i in range(n_window, n - n_window):
        window_low = low[i - n_window : i + n_window + 1]
        window_high = high[i - n_window : i + n_window + 1]

        if low[i] == window_low.min():
            fractal_lows.append((i, low[i]))
        if high[i] == window_high.max():
            fractal_highs.append((i, high[i]))

    # Cluster fractals and assign levels
    def _cluster(points: list[tuple[int, float]], pct: float) -> list[tuple[float, int]]:
        """Group nearby levels, return (level, touch_count) sorted by recency."""
        if not points:
            return []
        sorted_pts = sorted(points, key=lambda x: x[1])
        clusters: list[list[tuple[int, float]]] = [[sorted_pts[0]]]
        for idx, val in sorted_pts[1:]:
            if abs(val - clusters[-1][-1][1]) / clusters[-1][-1][1] <= pct:
                clusters[-1].append((idx, val))
            else:
                clusters.append([(idx, val)])
        result = []
        for cluster in clusters:
            if len(cluster) >= min_touches:
                avg_level = sum(v for _, v in cluster) / len(cluster)
                max_idx = max(idx for idx, _ in cluster)
                result.append((avg_level, len(cluster), max_idx))
        return sorted(result, key=lambda x: -x[2])  # Most recent first

    support_clusters = _cluster(fractal_lows, cluster_pct)
    resistance_clusters = _cluster(fractal_highs, cluster_pct)

    # Assign nearest active levels for each candle
    for i in range(2 * n_window, n):
        price = close[i]

        # Find nearest support below or at price
        best_sup = np.nan
        best_sup_dist = float("inf")
        for level, touches, last_idx in support_clusters:
            if last_idx > i:
                continue
            if level <= price * (1 + proximity_pct):
                dist = abs(price - level)
                if dist < best_sup_dist:
                    best_sup_dist = dist
                    best_sup = level

        # Find nearest resistance above or at price
        best_res = np.nan
        best_res_dist = float("inf")
        for level, touches, last_idx in resistance_clusters:
            if last_idx > i:
                continue
            if level >= price * (1 - proximity_pct):
                dist = abs(price - level)
                if dist < best_res_dist:
                    best_res_dist = dist
                    best_res = level

        support[i] = best_sup
        resistance[i] = best_res

        # Check proximity
        if not np.isnan(best_sup) and abs(price - best_sup) / price <= proximity_pct:
            at_support[i] = True
        if not np.isnan(best_res) and abs(price - best_res) / price <= proximity_pct:
            at_resistance[i] = True

    dataframe["support"] = support
    dataframe["resistance"] = resistance
    dataframe["at_support"] = at_support
    dataframe["at_resistance"] = at_resistance

    return dataframe


# =============================================================================
# Engine 3: Rolling Min/Max
# =============================================================================

def _rolling_minmax(dataframe: DataFrame, cfg: dict, consol_cfg: dict) -> DataFrame:
    """Adaptive rolling min/max with ATR-adjusted window.

    Window expands when volatility is high, contracts when low.
    """
    base_window = cfg["base_window"]
    proximity_pct = cfg["proximity_pct"]

    close = dataframe["close"]
    high = dataframe["high"]
    low = dataframe["low"]

    # Use pre-computed atr_zscore if available, otherwise compute
    if "atr_zscore" in dataframe.columns:
        atr_z = dataframe["atr_zscore"].fillna(0)
    else:
        tr = np.maximum(
            high - low,
            np.maximum(
                abs(high - close.shift(1)),
                abs(low - close.shift(1)),
            ),
        )
        atr = tr.rolling(consol_cfg["atr_period"]).mean()
        atr_mean = atr.rolling(consol_cfg["atr_zscore_window"]).mean()
        atr_std = atr.rolling(consol_cfg["atr_zscore_window"]).std()
        atr_z = ((atr - atr_mean) / atr_std.replace(0, np.nan)).fillna(0)

    # Adaptive window: clamp between base_window/2 and base_window*2
    adaptive_window = (base_window * (1 + atr_z.clip(-0.5, 1.0))).astype(int)
    adaptive_window = adaptive_window.clip(base_window // 2, base_window * 2)

    # For vectorized operation, use the median adaptive window
    # (true per-bar adaptive would require a loop)
    median_win = int(adaptive_window.median()) if len(adaptive_window) > 0 else base_window

    support_vals = low.rolling(median_win).min()
    resistance_vals = high.rolling(median_win).max()

    dataframe["support"] = support_vals
    dataframe["resistance"] = resistance_vals

    # Proximity check
    dataframe["at_support"] = (
        ((close - support_vals).abs() / close) <= proximity_pct
    )
    dataframe["at_resistance"] = (
        ((close - resistance_vals).abs() / close) <= proximity_pct
    )

    return dataframe
```

- [ ] **Step 2: Commit**

```bash
git add user_data/strategies/consolidation_scalp/levels.py
git commit -m "feat(scalp): add 3 S/R engines (order_blocks, pivot_fractal, rolling_minmax)"
```

---

### Task 4: Entries module

**Files:**
- Create: `user_data/strategies/consolidation_scalp/entries.py`

- [ ] **Step 1: Create entries module**

```python
# user_data/strategies/consolidation_scalp/entries.py
"""Entry signal generation for Consolidation Scalp.

Generates enter_long / enter_short signals when:
1. Market is consolidating (is_consolidating == True)
2. Price is at a support or resistance level (at_support / at_resistance)
3. Optional confirmation: reversal candle detected

Adds cooldown tracking to avoid re-entering the same level repeatedly.
"""
from __future__ import annotations

import numpy as np
from pandas import DataFrame


def generate(dataframe: DataFrame, cfg: dict) -> DataFrame:
    """Generate entry signals. Mutates and returns dataframe."""
    entry_cfg = cfg["entries"]
    cooldown = entry_cfg["cooldown_candles"]
    require_confirm = entry_cfg["require_confirmation"]
    engine = cfg["level_engine"]

    consolidating = dataframe["is_consolidating"]
    at_sup = dataframe["at_support"]
    at_res = dataframe["at_resistance"]

    # Confirmation: close reversal (close > open for long, close < open for short)
    if require_confirm:
        bullish_confirm = dataframe["close"] > dataframe["open"]
        bearish_confirm = dataframe["close"] < dataframe["open"]
    else:
        bullish_confirm = True
        bearish_confirm = True

    # Long at support
    long_signal = consolidating & at_sup & bullish_confirm

    # Short at resistance
    short_signal = consolidating & at_res & bearish_confirm

    # Apply cooldown: suppress signals within N candles of previous signal
    long_arr = long_signal.values.copy().astype(bool)
    short_arr = short_signal.values.copy().astype(bool)

    last_long = -cooldown - 1
    last_short = -cooldown - 1

    for i in range(len(long_arr)):
        if long_arr[i]:
            if i - last_long <= cooldown:
                long_arr[i] = False
            else:
                last_long = i
        if short_arr[i]:
            if i - last_short <= cooldown:
                short_arr[i] = False
            else:
                last_short = i

    dataframe["enter_long"] = long_arr.astype(int)
    dataframe["enter_short"] = short_arr.astype(int)
    dataframe["enter_tag"] = ""

    tag = engine
    dataframe.loc[dataframe["enter_long"] == 1, "enter_tag"] = f"{tag}_long_support"
    dataframe.loc[dataframe["enter_short"] == 1, "enter_tag"] = f"{tag}_short_resistance"

    return dataframe
```

- [ ] **Step 2: Commit**

```bash
git add user_data/strategies/consolidation_scalp/entries.py
git commit -m "feat(scalp): add entry signal generation with cooldown"
```

---

### Task 5: Exits module

**Files:**
- Create: `user_data/strategies/consolidation_scalp/exits.py`

- [ ] **Step 1: Create exits module**

```python
# user_data/strategies/consolidation_scalp/exits.py
"""Exit logic for Consolidation Scalp.

Priority order:
1. Breakout kill — ATR z-score or momentum spike
2. TP at opposite level — price reaches opposite S/R
3. Trailing stop — activates at threshold, trails behind
4. Time stop — max candles in trade
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def check_exit(
    pair: str,
    trade,
    current_time: datetime,
    current_rate: float,
    current_profit: float,
    cfg: dict,
    dp,
    timeframe: str,
    peak_profit: dict,
) -> Optional[str]:
    """Check exit conditions in priority order. Returns exit reason or None."""
    exit_cfg = cfg["exits"]
    trade_minutes = (current_time - trade.open_date_utc).total_seconds() / 60
    trade_candles = trade_minutes / 5  # 5m timeframe

    # Track peak profit for trailing
    trade_key = f"{pair}_{trade.open_date_utc}"
    if trade_key not in peak_profit:
        peak_profit[trade_key] = current_profit
    peak_profit[trade_key] = max(peak_profit[trade_key], current_profit)
    peak = peak_profit[trade_key]

    # --- 1. BREAKOUT KILL SWITCH ---
    if dp:
        dataframe, _ = dp.get_analyzed_dataframe(pair, timeframe)
        if dataframe is not None and not dataframe.empty:
            last = dataframe.iloc[-1]

            if last.get("is_breakout", False):
                peak_profit.pop(trade_key, None)
                return "breakout_stop"

    # --- 2. TP AT OPPOSITE LEVEL ---
    if dp:
        dataframe, _ = dp.get_analyzed_dataframe(pair, timeframe)
        if dataframe is not None and not dataframe.empty:
            last = dataframe.iloc[-1]
            is_long = trade.is_short is False

            if is_long:
                res = last.get("resistance", None)
                if res and not _isnan(res) and current_rate >= res:
                    peak_profit.pop(trade_key, None)
                    return "tp_level"
            else:
                sup = last.get("support", None)
                if sup and not _isnan(sup) and current_rate <= sup:
                    peak_profit.pop(trade_key, None)
                    return "tp_level"

    # --- 3. TRAILING STOP ---
    trail_activate = exit_cfg["trailing_activate"]
    trail_dist = exit_cfg["trailing_distance"]

    if peak >= trail_activate:
        if current_profit <= peak - trail_dist:
            peak_profit.pop(trade_key, None)
            return "trailing"

    # --- 4. TIME STOP ---
    if trade_candles >= exit_cfg["time_stop_candles"]:
        peak_profit.pop(trade_key, None)
        return "time_stop"

    return None


def _isnan(val) -> bool:
    """Check if value is NaN (works for float and numpy)."""
    try:
        return val != val  # NaN != NaN is True
    except (TypeError, ValueError):
        return False
```

- [ ] **Step 2: Commit**

```bash
git add user_data/strategies/consolidation_scalp/exits.py
git commit -m "feat(scalp): add exit logic (breakout kill, TP level, trailing, time stop)"
```

---

### Task 6: Leverage module

**Files:**
- Create: `user_data/strategies/consolidation_scalp/leverage.py`

- [ ] **Step 1: Create leverage module**

```python
# user_data/strategies/consolidation_scalp/leverage.py
"""Dynamic leverage for Consolidation Scalp.

Leverage inversely proportional to range size:
    tight range (< 1%) → max leverage (6x)
    wide range (~3.5%)  → min leverage (2x)
"""
from __future__ import annotations


def compute(
    cfg: dict,
    dp,
    pair: str,
    timeframe: str,
    max_leverage: float,
) -> float:
    """Compute leverage based on current range size."""
    lev_cfg = cfg["leverage"]
    lev_min = lev_cfg["min_leverage"]
    lev_max = lev_cfg["max_leverage"]
    range_pct_max = lev_cfg["range_pct_max"]

    # Get current range_pct from analyzed dataframe
    dataframe, _ = dp.get_analyzed_dataframe(pair, timeframe)
    if dataframe is None or dataframe.empty:
        return lev_min

    range_pct = float(dataframe.iloc[-1].get("range_pct", range_pct_max))

    # Linear interpolation: tight range → high lev, wide range → low lev
    if range_pct <= 0:
        lev = lev_max
    elif range_pct >= range_pct_max:
        lev = lev_min
    else:
        t = range_pct / range_pct_max
        lev = lev_max - t * (lev_max - lev_min)

    lev = round(max(lev_min, min(lev, lev_max, max_leverage)), 1)
    return lev


def stake_amount(cfg: dict, max_stake: float) -> float:
    """Return fixed stake per position."""
    return min(cfg["stake_per_position"], max_stake)
```

- [ ] **Step 2: Commit**

```bash
git add user_data/strategies/consolidation_scalp/leverage.py
git commit -m "feat(scalp): add dynamic leverage based on range size"
```

---

### Task 7: Strategy orchestrator

**Files:**
- Create: `user_data/strategies/consolidation_scalp/strategy.py`

- [ ] **Step 1: Create main strategy class**

```python
# user_data/strategies/consolidation_scalp/strategy.py
"""
ConsolidationScalpStrategy — BTC Mean-Reversion Scalper
========================================================

Trades BTC/USDT bounces off S/R levels during consolidation.
3 swappable S/R engines: order_blocks, pivot_fractal, rolling_minmax.

Modules:
    consolidation_scalp/config.py         — JSON config loader
    consolidation_scalp/consolidation.py  — regime filter
    consolidation_scalp/levels.py         — S/R detection (3 engines)
    consolidation_scalp/entries.py        — entry signals
    consolidation_scalp/exits.py          — exit logic
    consolidation_scalp/leverage.py       — dynamic leverage
"""
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

_STRATEGIES_DIR = str(Path(__file__).resolve().parent.parent)
if _STRATEGIES_DIR not in sys.path:
    sys.path.insert(0, _STRATEGIES_DIR)

from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy

from consolidation_scalp import config as cfg_loader
from consolidation_scalp import consolidation, levels, entries, exits
from consolidation_scalp import leverage as lev_mod

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "consolidation_scalp_config.json"


class ConsolidationScalpStrategy(IStrategy):
    """BTC consolidation scalper — mean-reversion off S/R levels."""

    INTERFACE_VERSION = 3
    can_short = True
    process_only_new_candles = True
    timeframe = "5m"
    startup_candle_count = 200
    stoploss = -0.05
    minimal_roi = {}
    trailing_stop = False
    use_custom_stoploss = True
    position_adjustment_enable = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        c = cfg_loader.load(CONFIG_PATH)
        self._cfg = c

        self.timeframe = c.get("timeframe", "5m")
        self.startup_candle_count = c.get("startup_candle_count", 200)

        # Exit tracking
        self._peak_profit: dict[str, float] = {}

        engine = c["level_engine"]
        logger.info(
            "ConsolidationScalp loaded — engine=%s pair=%s tf=%s",
            engine, c["pair"], self.timeframe,
        )

    # =========================================================================
    # INDICATORS
    # =========================================================================

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 1. Consolidation filter (ATR, range, momentum, volume)
        dataframe = consolidation.compute(dataframe, self._cfg)

        # 2. S/R levels from selected engine
        dataframe = levels.compute(dataframe, self._cfg)

        return dataframe

    # =========================================================================
    # ENTRIES
    # =========================================================================

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = entries.generate(dataframe, self._cfg)
        return dataframe

    # =========================================================================
    # EXITS
    # =========================================================================

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        return exits.check_exit(
            pair, trade, current_time, current_rate, current_profit,
            self._cfg, self.dp, self.timeframe, self._peak_profit,
        )

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool,
                        **kwargs) -> float | None:
        """Fixed tight stoploss for scalping."""
        return self._cfg["exits"]["stoploss"]

    # =========================================================================
    # LEVERAGE
    # =========================================================================

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float,
                 entry_tag: Optional[str], side: str, **kwargs) -> float:
        return lev_mod.compute(
            self._cfg, self.dp, pair, self.timeframe, max_leverage,
        )

    # =========================================================================
    # STAKE
    # =========================================================================

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float],
                            max_stake: float, leverage: float, entry_tag: Optional[str],
                            side: str, **kwargs) -> float:
        return lev_mod.stake_amount(self._cfg, max_stake)
```

- [ ] **Step 2: Commit**

```bash
git add user_data/strategies/consolidation_scalp/strategy.py
git commit -m "feat(scalp): add strategy orchestrator"
```

---

### Task 8: Backtest — Order Blocks engine

**Files:**
- No new files, uses existing setup

- [ ] **Step 1: Verify BTC data is available**

```bash
freqtrade download-data --exchange binance --pairs BTC/USDT:USDT --timeframes 5m --days 90
```

- [ ] **Step 2: Run backtest with order_blocks engine**

Ensure `consolidation_scalp_config.json` has `"level_engine": "order_blocks"`.

```bash
freqtrade backtesting \
    --strategy ConsolidationScalpStrategy \
    --strategy-path user_data/strategies/consolidation_scalp \
    --timeframe 5m \
    --timerange 20260211-20260511 \
    --pairs BTC/USDT:USDT \
    --enable-protections \
    -c user_data/config.json
```

- [ ] **Step 3: Record results**

Note: total profit, win rate, max drawdown, avg trade duration, number of trades.

- [ ] **Step 4: Commit results**

```bash
git add -A
git commit -m "test(scalp): backtest order_blocks engine — record results"
```

---

### Task 9: Backtest — Pivot Fractal engine

- [ ] **Step 1: Update config to pivot_fractal**

Change `"level_engine": "pivot_fractal"` in `consolidation_scalp_config.json`.

- [ ] **Step 2: Run backtest**

```bash
freqtrade backtesting \
    --strategy ConsolidationScalpStrategy \
    --strategy-path user_data/strategies/consolidation_scalp \
    --timeframe 5m \
    --timerange 20260211-20260511 \
    --pairs BTC/USDT:USDT \
    --enable-protections \
    -c user_data/config.json
```

- [ ] **Step 3: Record and compare results**

---

### Task 10: Backtest — Rolling Min/Max engine

- [ ] **Step 1: Update config to rolling_minmax**

Change `"level_engine": "rolling_minmax"` in `consolidation_scalp_config.json`.

- [ ] **Step 2: Run backtest**

```bash
freqtrade backtesting \
    --strategy ConsolidationScalpStrategy \
    --strategy-path user_data/strategies/consolidation_scalp \
    --timeframe 5m \
    --timerange 20260211-20260511 \
    --pairs BTC/USDT:USDT \
    --enable-protections \
    -c user_data/config.json
```

- [ ] **Step 3: Record, compare all 3 engines, pick winner**

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "test(scalp): backtest all 3 engines — comparison complete"
```
