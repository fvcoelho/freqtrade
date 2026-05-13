# ZScoreV55 Grid Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create V55 strategy — a hybrid that uses grid trading during consolidation and V54 mean-reversion during ranging.

**Architecture:** Fork V54 into `zscore_v55/`, add a new `grid.py` module for grid level computation and signal generation, modify `exits.py` for per-regime time stops, and wire it all together in `strategy.py`.

**Tech Stack:** Python 3.13, Freqtrade, pandas, numpy

---

### Task 1: Scaffold zscore_v55 package from V54

**Files:**
- Create: `user_data/strategies/zscore_v55/__init__.py`
- Create: `user_data/strategies/zscore_v55/strategy.py` (copy from V54)
- Create: `user_data/strategies/zscore_v55/grid.py` (empty placeholder)
- Create: `user_data/strategies/zscore_v55/exits.py` (copy from V54)
- Copy unchanged: `config.py`, `groups.py`, `zscore.py`, `leverage.py`, `state.py`, `risk.py`, `dca.py`, `entries.py`
- Create: `user_data/strategies/v55_config.json` (copy from V54)

- [ ] **Step 1: Copy V54 modules to zscore_v55**

```bash
mkdir -p user_data/strategies/zscore_v55
for f in config.py groups.py zscore.py leverage.py state.py risk.py dca.py entries.py; do
  cp user_data/strategies/zscore_v54/$f user_data/strategies/zscore_v55/$f
done
cp user_data/strategies/zscore_v54/exits.py user_data/strategies/zscore_v55/exits.py
cp user_data/strategies/zscore_v54/strategy.py user_data/strategies/zscore_v55/strategy.py
```

- [ ] **Step 2: Create `__init__.py`**

```python
from .strategy import ZScoreV55Strategy  # noqa: F401
```

- [ ] **Step 3: Update `strategy.py` — rename class and imports**

Change all occurrences in `user_data/strategies/zscore_v55/strategy.py`:
- `ZScoreV54Strategy` → `ZScoreV55Strategy`
- `from zscore_v54 import` → `from zscore_v55 import`
- `from zscore_v54.state` → `from zscore_v55.state`
- `v54_config.json` → `v55_config.json`
- `"V54` → `"V55` (log messages)
- `"ZScoreV54Strategy"` → `"ZScoreV55Strategy"` (metadata)
- `v54_` → `v55_` (run_id prefix)

- [ ] **Step 4: Create `v55_config.json`**

Copy `v54_config.json` and add grid section + per-regime time stops:

```bash
cp user_data/strategies/v54_config.json user_data/strategies/v55_config.json
```

Then edit `v55_config.json` to add after the `"consolidation"` section:

```json
"grid": {
    "enabled": true,
    "n_levels": 5,
    "cooldown_candles": 4,
    "require_confirmation": true,
    "rsi_filter": true,
    "rsi_oversold": 40,
    "rsi_overbought": 60
},
```

And update the `"consolidation"` section to activate it (replace 99.0 thresholds):

```json
"consolidation": {
    "consol_zscore_entry": 1.5,
    "consol_pair_z_entry": 1.0,
    "consol_time_stop_candles": 12,
    "loss_cooldown_hours": 0
},
```

And add per-regime time stops inside `"exits"`:

```json
"grid_time_stop_candles": 6,
"ranging_time_stop_candles": 12,
```

- [ ] **Step 5: Create empty `grid.py` placeholder**

```python
"""Grid trading module for ZScore V55 — consolidation regime."""
from __future__ import annotations
```

- [ ] **Step 6: Verify import works**

Run:
```bash
cd user_data/strategies && python3 -c "from zscore_v55.strategy import ZScoreV55Strategy; print('V55 OK')"
```
Expected: `V55 OK`

- [ ] **Step 7: Commit**

```bash
git add -f user_data/strategies/zscore_v55/*.py user_data/strategies/v55_config.json
git commit -m "feat(v55): scaffold zscore_v55 package from V54"
```

---

### Task 2: Implement `grid.py` — compute_levels

**Files:**
- Modify: `user_data/strategies/zscore_v55/grid.py`

- [ ] **Step 1: Implement `compute_levels`**

Write the full `grid.py` with `compute_levels`:

```python
"""Grid trading module for ZScore V55 — consolidation regime.

Computes dynamic grid levels within the consolidation range and
generates buy/sell signals when price crosses levels.
"""
from __future__ import annotations

import numpy as np
from pandas import DataFrame


def compute_levels(dataframe: DataFrame, cfg: dict) -> DataFrame:
    """Add grid level columns and position-in-range to dataframe.

    Requires consolidation columns (rolling_high, rolling_low) to
    already exist — computed by the regime filter or inline here.

    Adds columns:
        - pos_in_range: float 0 (bottom) to 1 (top)
        - grid_level_0 through grid_level_N
    """
    grid_cfg = cfg["grid"]
    n_levels = grid_cfg["n_levels"]
    regime_cfg = cfg["regime"]

    close = dataframe["close"]
    high = dataframe["high"]
    low = dataframe["low"]

    # Use range_window from consolidation config if rolling_high not present
    range_window = regime_cfg.get("consolidation_range_window",
                                   cfg.get("consolidation", {}).get("range_window", 96))

    rolling_high = high.rolling(range_window).max()
    rolling_low = low.rolling(range_window).min()
    range_size = rolling_high - rolling_low

    dataframe["grid_rolling_high"] = rolling_high
    dataframe["grid_rolling_low"] = rolling_low

    # Position in range: 0 = at bottom, 1 = at top
    dataframe["pos_in_range"] = (
        (close - rolling_low) / range_size.replace(0, np.nan)
    ).fillna(0.5)

    # Compute grid levels
    for i in range(n_levels + 1):
        frac = i / n_levels
        dataframe[f"grid_level_{i}"] = rolling_low + frac * range_size

    # RSI (if not already computed)
    if "rsi" not in dataframe.columns:
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0).rolling(14).mean()
        loss_s = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
        rs = gain / loss_s.replace(0, np.nan)
        dataframe["rsi"] = (100 - (100 / (1 + rs))).fillna(50)

    return dataframe
```

- [ ] **Step 2: Verify syntax**

Run:
```bash
cd user_data/strategies && python3 -c "from zscore_v55.grid import compute_levels; print('compute_levels OK')"
```
Expected: `compute_levels OK`

- [ ] **Step 3: Commit**

```bash
git add -f user_data/strategies/zscore_v55/grid.py
git commit -m "feat(v55): implement grid.compute_levels"
```

---

### Task 3: Implement `grid.py` — generate signals

**Files:**
- Modify: `user_data/strategies/zscore_v55/grid.py`

- [ ] **Step 1: Add `generate` function to `grid.py`**

Append to `grid.py`:

```python
def generate(
    dataframe: DataFrame,
    pair: str,
    cfg: dict,
    group_sub1: list[str],
    group_sub2: list[str],
    group_name: str,
) -> DataFrame:
    """Generate grid entry signals during consolidation.

    Buy when price crosses DOWN through a grid level.
    Sell when price crosses UP through a grid level.

    Only fires on rows where is_consolidating is True and no signal
    has been set by a previous group.

    Parameters
    ----------
    dataframe : DataFrame
        Must contain: is_consolidating, pos_in_range, grid_level_*,
        btc_high_vol, btc_dump, btc_pump, vol_ok, rsi.
    pair : str
        Trading pair.
    cfg : dict
        Full strategy config with "grid" section.
    group_sub1 : list[str]
        Pairs in this group's sub1 (long side).
    group_sub2 : list[str]
        Pairs in this group's sub2 (short side).
    group_name : str
        Group identifier, e.g. "A" or "B".
    """
    grid_cfg = cfg["grid"]
    n_levels = grid_cfg["n_levels"]
    cooldown = grid_cfg["cooldown_candles"]
    require_confirm = grid_cfg["require_confirmation"]
    use_rsi = grid_cfg["rsi_filter"]
    rsi_oversold = grid_cfg["rsi_oversold"]
    rsi_overbought = grid_cfg["rsi_overbought"]

    is_a = pair in group_sub1
    is_b = pair in group_sub2
    if not is_a and not is_b:
        return dataframe

    consolidating = dataframe["is_consolidating"]

    # Safety filters
    no_chaos = ~dataframe["btc_high_vol"]
    safe_long = ~dataframe["btc_dump"] & no_chaos
    safe_short = ~dataframe["btc_pump"] & no_chaos
    vol = dataframe["vol_ok"] == 1

    # Confirmation filters
    if require_confirm:
        bullish = dataframe["close"] > dataframe["open"]
        bearish = dataframe["close"] < dataframe["open"]
    else:
        bullish = True
        bearish = True

    if use_rsi:
        rsi_long_ok = dataframe["rsi"] < rsi_oversold
        rsi_short_ok = dataframe["rsi"] > rsi_overbought
    else:
        rsi_long_ok = True
        rsi_short_ok = True

    # Guard: only set signals on rows not already claimed
    no_long = dataframe["enter_long"] == 0
    no_short = dataframe["enter_short"] == 0

    # Detect grid level crossings
    pos = dataframe["pos_in_range"]
    pos_prev = pos.shift(1)

    long_cross = np.zeros(len(dataframe), dtype=bool)
    short_cross = np.zeros(len(dataframe), dtype=bool)
    cross_level = np.zeros(len(dataframe), dtype=int)

    for lv in range(1, n_levels):
        frac = lv / n_levels
        # Price crosses DOWN through level → buy signal
        crossed_down = (pos_prev > frac) & (pos <= frac)
        # Price crosses UP through level → sell signal
        crossed_up = (pos_prev < frac) & (pos >= frac)

        down_mask = crossed_down.values.astype(bool)
        up_mask = crossed_up.values.astype(bool)

        long_cross = long_cross | down_mask
        short_cross = short_cross | up_mask
        cross_level[down_mask | up_mask] = lv

    # Combine: consolidating + safety + confirmation + crossing
    gn = group_name

    long_signal = (
        consolidating & vol & safe_long & bullish & rsi_long_ok
        & long_cross & no_long
    )
    short_signal = (
        consolidating & vol & safe_short & bearish & rsi_short_ok
        & short_cross & no_short
    )

    # Apply cooldown
    long_arr = long_signal.values.astype(bool).copy()
    short_arr = short_signal.values.astype(bool).copy()
    long_arr, short_arr = _apply_cooldown(long_arr, short_arr, cooldown)

    # Set signals
    dataframe.loc[long_arr, "enter_long"] = 1
    dataframe.loc[long_arr, "enter_tag"] = ""  # will be set per-level below
    dataframe.loc[short_arr, "enter_short"] = 1
    dataframe.loc[short_arr, "enter_tag"] = ""

    # Tag with level number
    for i in range(len(dataframe)):
        if long_arr[i]:
            dataframe.iat[i, dataframe.columns.get_loc("enter_tag")] = (
                f"grid_long_L{cross_level[i]}_{gn}"
            )
        elif short_arr[i]:
            dataframe.iat[i, dataframe.columns.get_loc("enter_tag")] = (
                f"grid_short_L{cross_level[i]}_{gn}"
            )

    return dataframe


def _apply_cooldown(long_arr, short_arr, cooldown):
    """Suppress signals within cooldown candles of previous signal."""
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
    return long_arr, short_arr
```

- [ ] **Step 2: Verify import**

Run:
```bash
cd user_data/strategies && python3 -c "from zscore_v55.grid import compute_levels, generate; print('grid OK')"
```
Expected: `grid OK`

- [ ] **Step 3: Commit**

```bash
git add -f user_data/strategies/zscore_v55/grid.py
git commit -m "feat(v55): implement grid.generate with level crossing signals"
```

---

### Task 4: Modify exits.py — per-regime time stop

**Files:**
- Modify: `user_data/strategies/zscore_v55/exits.py`

- [ ] **Step 1: Update time stop logic in `check_exit`**

In `user_data/strategies/zscore_v55/exits.py`, find the section (around line 140-147):

```python
    # --- 2. CONSOLIDATION TIME STOP ---
    if entry_tag.startswith("consol_"):
        if trade_minutes / 5 >= consol_cfg["consol_time_stop_candles"]:
            return "consol_time_stop"

    # --- 2b. GLOBAL TIME STOP ---
    if trade_minutes >= 360:
        return "time_stop"
```

Replace it with:

```python
    # --- 2. PER-REGIME TIME STOP ---
    candle_minutes = 5  # default for 5m timeframe
    trade_candles = trade_minutes / candle_minutes

    if entry_tag.startswith("grid_"):
        grid_time_stop = exit_cfg.get("grid_time_stop_candles", 6)
        if trade_candles >= grid_time_stop:
            return "grid_time_stop"
    elif entry_tag.startswith("consol_"):
        if trade_candles >= consol_cfg["consol_time_stop_candles"]:
            return "consol_time_stop"
    else:
        ranging_time_stop = exit_cfg.get("ranging_time_stop_candles", 12)
        if trade_candles >= ranging_time_stop:
            return "time_stop"
```

- [ ] **Step 2: Verify syntax**

Run:
```bash
cd user_data/strategies && python3 -c "from zscore_v55.exits import check_exit; print('exits OK')"
```
Expected: `exits OK`

- [ ] **Step 3: Commit**

```bash
git add -f user_data/strategies/zscore_v55/exits.py
git commit -m "feat(v55): add per-regime time stop in exits"
```

---

### Task 5: Wire grid into strategy.py

**Files:**
- Modify: `user_data/strategies/zscore_v55/strategy.py`

- [ ] **Step 1: Add grid import**

In `user_data/strategies/zscore_v55/strategy.py`, find the import line:

```python
from zscore_v55 import zscore, entries, exits, leverage as lev_mod, risk, dca
```

Replace with:

```python
from zscore_v55 import zscore, entries, exits, leverage as lev_mod, risk, dca, grid
```

- [ ] **Step 2: Add grid.compute_levels to populate_indicators**

In `populate_indicators`, after the line `volume.compute(dataframe, self._cfg)` (around line 209), add:

```python
        # Grid levels (for consolidation regime)
        if self._cfg.get("grid", {}).get("enabled", False):
            grid.compute_levels(dataframe, self._cfg)
```

- [ ] **Step 3: Replace populate_entry_trend with regime dispatch**

Replace the entire `populate_entry_trend` method with:

```python
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]

        # Initialize columns
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe["enter_tag"] = ""

        # Regime classification (mirrors entries.py logic)
        regime_cfg = self._cfg["regime"]
        btc_mom = dataframe["btc_mom"]
        btc_atr_z = dataframe["btc_atr_z"]

        is_trending = (
            (btc_mom.abs() > regime_cfg["trending_btc_mom"])
            | (btc_atr_z > regime_cfg["trending_atr_z"])
        )
        is_consolidation = (
            (btc_atr_z < regime_cfg["consolidation_atr_z"])
            & (btc_mom.abs() < regime_cfg["consolidation_btc_mom_max"])
        )

        grid_enabled = self._cfg.get("grid", {}).get("enabled", False)

        for g in self._groups:
            if pair not in g.all_pairs:
                continue
            col = f"spread_z_{g.name.lower()}"

            if grid_enabled:
                # Consolidation → grid signals
                grid.generate(
                    dataframe, pair, self._cfg,
                    g.sub1, g.sub2, g.name,
                )

            # Ranging → mean-reversion signals (V54)
            # entries.generate only fills rows where enter_long/short == 0
            entries.generate(
                dataframe, pair, self._cfg, self._btc_trend,
                g.sub1, g.sub2, g.name, col,
            )

        return dataframe
```

- [ ] **Step 4: Add consolidation regime columns in populate_indicators**

The grid needs `is_consolidating` column. Add after `volume.compute(dataframe, self._cfg)` and before the grid compute_levels call:

```python
        # Consolidation regime flag (for grid module)
        regime_cfg = self._cfg["regime"]
        is_consolidating = (
            (dataframe["btc_atr_z"] < regime_cfg["consolidation_atr_z"])
            & (dataframe["btc_mom"].abs() < regime_cfg["consolidation_btc_mom_max"])
        )
        # Also check spread is small (using first group's spread)
        if self._groups:
            spread_col = f"spread_z_{self._groups[0].name.lower()}"
            if spread_col in dataframe.columns:
                is_consolidating = is_consolidating & (
                    dataframe[spread_col].abs() < regime_cfg["consolidation_spread_max"]
                )
        dataframe["is_consolidating"] = is_consolidating
```

- [ ] **Step 5: Verify import**

Run:
```bash
cd user_data/strategies && python3 -c "from zscore_v55.strategy import ZScoreV55Strategy; print('V55 strategy OK')"
```
Expected: `V55 strategy OK`

- [ ] **Step 6: Commit**

```bash
git add -f user_data/strategies/zscore_v55/strategy.py
git commit -m "feat(v55): wire grid into strategy with regime dispatch"
```

---

### Task 6: Backtest V55 and compare with V54

**Files:** None (test only)

- [ ] **Step 1: Run V55 backtest for April**

```bash
source .venv/bin/activate
freqtrade backtesting \
  --config user_data/configs/config_v54_backtest.json \
  --timerange 20260401-20260501 \
  --timeframe 5m \
  --strategy-list ZScoreV54Strategy ZScoreV55Strategy \
  --cache none
```

Verify V55 loads and produces trades. Compare profit, win rate, drawdown with V54.

- [ ] **Step 2: Check grid trades specifically**

Look at the ENTER TAG STATS and EXIT REASON STATS in the output:
- Confirm `grid_long_L*` and `grid_short_L*` tags appear
- Confirm `grid_time_stop` exit reason appears
- Confirm ranging tags (`mr_long_*`, `mr_short_*`) still appear

- [ ] **Step 3: Run 4-month backtest**

```bash
freqtrade backtesting \
  --config user_data/configs/config_v54_backtest.json \
  --timerange 20260112-20260508 \
  --timeframe 5m \
  --strategy-list ZScoreV54Strategy ZScoreV55Strategy \
  --cache none
```

Compare full period results.

- [ ] **Step 4: Commit config and add strategy to git**

```bash
git add -f user_data/strategies/zscore_v55/*.py user_data/strategies/v55_config.json
git commit -m "feat(v55): complete ZScoreV55Strategy with grid consolidation"
```

---

### Task 7: Create backtest config for V55

**Files:**
- Create: `user_data/configs/config_v55_backtest.json`

- [ ] **Step 1: Create V55 backtest config**

```bash
cp user_data/configs/config_v54_backtest.json user_data/configs/config_v55_backtest.json
```

Edit `config_v55_backtest.json` to change strategy:

```json
{"trading_mode": "futures", "margin_mode": "isolated", "max_open_trades": 2, "stake_currency": "USDC", "stake_amount": "unlimited", "tradable_balance_ratio": 0.95, "fiat_display_currency": "USD", "dry_run": true, "dry_run_wallet": 100, "strategy": "ZScoreV55Strategy", "recursive_strategy_search": true, "exchange": {"name": "hyperliquid", "key": "", "secret": "", "pair_whitelist": ["XRP/USDC:USDC", "ADA/USDC:USDC", "SOL/USDC:USDC", "LINK/USDC:USDC", "BTC/USDC:USDC", "ETH/USDC:USDC"], "pair_blacklist": []}, "entry_pricing": {"price_side": "other", "use_order_book": true, "order_book_top": 1}, "exit_pricing": {"price_side": "other", "use_order_book": true, "order_book_top": 1}, "pairlists": [{"method": "StaticPairList"}]}
```

- [ ] **Step 2: Commit**

```bash
git add -f user_data/configs/config_v55_backtest.json
git commit -m "feat(v55): add backtest config"
```
