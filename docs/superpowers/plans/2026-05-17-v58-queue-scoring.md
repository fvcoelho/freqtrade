# V58 Queue-Based Scoring Entry — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build V58 strategy that replaces V57's independent per-pair entry with a centralized scoring + queue + confirmation system. Exits stay identical to V57.

**Architecture:** New `queue.py` module handles scoring, queue ranking, and confirmation tracking. `strategy.py` orchestrates: indicators (V57) → queue scoring → confirmed entries → V57 basket exits. All other modules copied from V57 unchanged.

**Tech Stack:** Python 3.13, freqtrade 2026.3, pandas, numpy

**Spec:** `docs/superpowers/specs/2026-05-17-v58-queue-scoring-design.md`

---

### Task 1: Scaffold V58 module directory and config

**Files:**
- Create: `user_data/strategies/zscore_v58/__init__.py`
- Create: `user_data/strategies/v58_config.json`
- Copy: `user_data/strategies/zscore_v57/config.py` → `user_data/strategies/zscore_v58/config.py`
- Copy: `user_data/strategies/zscore_v57/basket.py` → `user_data/strategies/zscore_v58/basket.py`
- Copy: `user_data/strategies/zscore_v57/btc_trend.py` → `user_data/strategies/zscore_v58/btc_trend.py`
- Copy: `user_data/strategies/zscore_v57/volume.py` → `user_data/strategies/zscore_v58/volume.py`
- Copy: `user_data/strategies/zscore_v57/dca.py` → `user_data/strategies/zscore_v58/dca.py`
- Copy: `user_data/strategies/zscore_v57/leverage.py` → `user_data/strategies/zscore_v58/leverage.py`
- Copy: `user_data/strategies/zscore_v57/stake.py` → `user_data/strategies/zscore_v58/stake.py`
- Copy: `user_data/strategies/zscore_v57/state.py` → `user_data/strategies/zscore_v58/state.py`

- [ ] **Step 1: Copy V57 modules to V58 directory**

```bash
mkdir -p user_data/strategies/zscore_v58
for f in config.py basket.py btc_trend.py volume.py dca.py leverage.py stake.py state.py; do
  cp user_data/strategies/zscore_v57/$f user_data/strategies/zscore_v58/$f
done
```

- [ ] **Step 2: Create `__init__.py`**

Create `user_data/strategies/zscore_v58/__init__.py`:

```python
from .strategy import ZScoreV58Strategy  # noqa: F401
```

(This will fail to import until strategy.py is created in Task 3 — that's expected.)

- [ ] **Step 3: Create `v58_config.json`**

Create `user_data/strategies/v58_config.json` — copy of V57 config with new `queue` section added:

```json
{
    "timeframe": "5m",
    "startup_candle_count": 900,
    "basket": {
        "pairs": [
            "BTC/USDC:USDC",
            "ETH/USDC:USDC",
            "SOL/USDC:USDC",
            "LINK/USDC:USDC",
            "BNB/USDC:USDC",
            "XRP/USDC:USDC",
            "SUI/USDC:USDC",
            "DOGE/USDC:USDC",
            "AAVE/USDC:USDC",
            "ENA/USDC:USDC",
            "ONDO/USDC:USDC",
            "NEAR/USDC:USDC",
            "INJ/USDC:USDC",
            "HYPE/USDC:USDC",
            "TON/USDC:USDC",
            "TAO/USDC:USDC",
            "ZEC/USDC:USDC",
            "FARTCOIN/USDC:USDC",
            "PENDLE/USDC:USDC",
            "TRUMP/USDC:USDC"
        ],
        "btc_ref": "BTC/USDC:USDC",
        "entry_z": 2.0,
        "exit_z": 0.3,
        "profit_lock": 0.002,
        "loss_exit_z": -4.0,
        "max_positions": 4,
        "stake_per_position": 100,
        "time_stop_candles": 24,
        "bear_mom_threshold": -1.0,
        "bull_mom_threshold": 0.0,
        "max_loss_per_trade": -0.15,
        "zscore_method": "kalman",
        "kalman_gain": 0.05
    },
    "zscore": {
        "zscore_window": 288,
        "cum_return_window": 24
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
        "vol_ended_threshold": 1.5,
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

- [ ] **Step 4: Commit scaffold**

```bash
git add user_data/strategies/zscore_v58/ user_data/strategies/v58_config.json
git commit -m "feat(v58): scaffold module directory and config with queue section"
```

---

### Task 2: Implement `queue.py` — scoring function

**Files:**
- Create: `user_data/strategies/zscore_v58/queue.py`
- Create: `tests/test_v58_queue.py`

- [ ] **Step 1: Write failing test for `compute_scores`**

Create `tests/test_v58_queue.py`:

```python
"""Tests for V58 queue scoring module."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "user_data" / "strategies"))

from zscore_v58.queue import compute_scores, reset


def _make_cfg():
    return {
        "queue": {
            "top_k": 3,
            "confirm_candles": 3,
            "cooldown_candles": 36,
            "weights": {
                "basket_z": 0.5,
                "vol_ratio": 0.2,
                "spread_velocity": 0.2,
                "cooldown": 0.1,
            },
        },
        "basket": {"entry_z": 2.0, "bull_mom_threshold": 0.0, "bear_mom_threshold": -1.0},
    }


def test_compute_scores_basic():
    reset()
    cfg = _make_cfg()
    pair_data = {
        "ETH/USDC:USDC": {
            "basket_z": -3.0,
            "basket_z_prev3": -1.5,
            "vol_ratio": 2.0,
            "vol_ok": True,
            "btc_mom": 1.0,
            "btc_pump": False,
            "btc_dump": False,
            "btc_high_vol": False,
        },
        "SOL/USDC:USDC": {
            "basket_z": -1.0,
            "basket_z_prev3": -0.5,
            "vol_ratio": 1.0,
            "vol_ok": True,
            "btc_mom": 1.0,
            "btc_pump": False,
            "btc_dump": False,
            "btc_high_vol": False,
        },
    }
    scores = compute_scores(pair_data, cfg, candle_index=100)
    assert "ETH/USDC:USDC" in scores
    assert "SOL/USDC:USDC" in scores
    # ETH has more extreme z and faster spread → higher score
    assert scores["ETH/USDC:USDC"] > scores["SOL/USDC:USDC"]


def test_compute_scores_normalization_caps():
    """Scores are capped to 0.0-1.0 range."""
    reset()
    cfg = _make_cfg()
    pair_data = {
        "ETH/USDC:USDC": {
            "basket_z": -10.0,  # extreme, should cap at 4.0
            "basket_z_prev3": -5.0,
            "vol_ratio": 10.0,  # extreme, should cap at 3.0
            "vol_ok": True,
            "btc_mom": 1.0,
            "btc_pump": False,
            "btc_dump": False,
            "btc_high_vol": False,
        },
    }
    scores = compute_scores(pair_data, cfg, candle_index=100)
    assert 0.0 <= scores["ETH/USDC:USDC"] <= 1.0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_v58_queue.py -v
```

Expected: FAIL — `ModuleNotFoundError` or `ImportError` (queue.py doesn't exist yet).

- [ ] **Step 3: Implement `compute_scores` in `queue.py`**

Create `user_data/strategies/zscore_v58/queue.py`:

```python
"""Queue-based scoring and confirmation for V58.

Each candle, all pairs receive a multi-factor score. Top-K pairs per side
(long/short) enter a confirmation queue. A pair must stay in top-K for N
consecutive candles before it can trade.

State is module-level (persisted across candles within a single run).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ── Module-level state ──
_confirm_long: dict[str, int] = {}
_confirm_short: dict[str, int] = {}
_last_exit_candle: dict[str, int] = {}
_candle_count: int = 0

# Cache: scores computed once per candle cycle, reused across pairs
_score_cache: dict = {}  # {"cycle": int, "scores": {}, "ready": []}


def reset():
    """Reset all queue state. Called on strategy init."""
    global _confirm_long, _confirm_short, _last_exit_candle, _candle_count, _score_cache
    _confirm_long = {}
    _confirm_short = {}
    _last_exit_candle = {}
    _candle_count = 0
    _score_cache = {}


def compute_scores(
    pair_data: dict[str, dict],
    cfg: dict,
    candle_index: int,
) -> dict[str, float]:
    """Compute composite score for each pair.

    Parameters
    ----------
    pair_data : dict
        {pair: {basket_z, basket_z_prev3, vol_ratio, vol_ok, btc_mom, ...}}
    cfg : dict
        Full strategy config with "queue" section.
    candle_index : int
        Current candle index (for cooldown check).

    Returns
    -------
    dict[str, float]
        {pair: score} where score is 0.0-1.0.
    """
    weights = cfg["queue"]["weights"]
    w_bz = weights.get("basket_z", 0.5)
    w_vol = weights.get("vol_ratio", 0.2)
    w_vel = weights.get("spread_velocity", 0.2)
    w_cd = weights.get("cooldown", 0.1)
    cooldown_candles = cfg["queue"].get("cooldown_candles", 36)

    scores: dict[str, float] = {}

    for pair, d in pair_data.items():
        bz = abs(d.get("basket_z", 0.0))
        vr = d.get("vol_ratio", 1.0)
        bz_prev = d.get("basket_z_prev3", d.get("basket_z", 0.0))
        velocity = abs(d.get("basket_z", 0.0) - bz_prev)

        # Normalize to 0-1
        bz_norm = min(bz, 4.0) / 4.0
        vol_norm = min(vr, 3.0) / 3.0
        vel_norm = min(velocity, 2.0) / 2.0

        # Cooldown: 1.0 if no recent exit, 0.0 if within cooldown window
        last_exit = _last_exit_candle.get(pair, -999)
        cd_norm = 0.0 if (candle_index - last_exit) < cooldown_candles else 1.0

        score = w_bz * bz_norm + w_vol * vol_norm + w_vel * vel_norm + w_cd * cd_norm
        scores[pair] = round(score, 6)

    return scores
```

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/bin/pytest tests/test_v58_queue.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add user_data/strategies/zscore_v58/queue.py tests/test_v58_queue.py
git commit -m "feat(v58): implement queue scoring with 4 weighted factors"
```

---

### Task 3: Implement `queue.py` — queue building and confirmation

**Files:**
- Modify: `user_data/strategies/zscore_v58/queue.py`
- Modify: `tests/test_v58_queue.py`

- [ ] **Step 1: Write failing tests for `build_queues` and `update_confirmation`**

Append to `tests/test_v58_queue.py`:

```python
from zscore_v58.queue import build_queues, update_confirmation


def test_build_queues_long():
    reset()
    cfg = _make_cfg()
    pair_data = {
        "ETH/USDC:USDC": {"basket_z": -3.0, "btc_mom": 1.0, "btc_pump": False, "btc_dump": False, "btc_high_vol": False, "vol_ok": True},
        "SOL/USDC:USDC": {"basket_z": -2.5, "btc_mom": 1.0, "btc_pump": False, "btc_dump": False, "btc_high_vol": False, "vol_ok": True},
        "LINK/USDC:USDC": {"basket_z": -1.0, "btc_mom": 1.0, "btc_pump": False, "btc_dump": False, "btc_high_vol": False, "vol_ok": True},
        "XRP/USDC:USDC": {"basket_z": 3.0, "btc_mom": 1.0, "btc_pump": False, "btc_dump": False, "btc_high_vol": False, "vol_ok": True},
    }
    scores = {"ETH/USDC:USDC": 0.9, "SOL/USDC:USDC": 0.7, "LINK/USDC:USDC": 0.3, "XRP/USDC:USDC": 0.8}
    open_pairs = set()
    long_q, short_q = build_queues(scores, pair_data, cfg, open_pairs)
    # ETH and SOL qualify for long (z < -2.0, bull). LINK doesn't (z > -2.0). XRP doesn't (z positive).
    assert long_q == ["ETH/USDC:USDC", "SOL/USDC:USDC"]
    assert short_q == []  # btc_mom > 0, not bear


def test_build_queues_short():
    reset()
    cfg = _make_cfg()
    pair_data = {
        "ETH/USDC:USDC": {"basket_z": 3.0, "btc_mom": -2.0, "btc_pump": False, "btc_dump": False, "btc_high_vol": False, "vol_ok": True},
        "SOL/USDC:USDC": {"basket_z": 2.5, "btc_mom": -2.0, "btc_pump": False, "btc_dump": False, "btc_high_vol": False, "vol_ok": True},
    }
    scores = {"ETH/USDC:USDC": 0.9, "SOL/USDC:USDC": 0.7}
    open_pairs = set()
    long_q, short_q = build_queues(scores, pair_data, cfg, open_pairs)
    assert long_q == []
    assert short_q == ["ETH/USDC:USDC", "SOL/USDC:USDC"]


def test_build_queues_excludes_open_trades():
    reset()
    cfg = _make_cfg()
    pair_data = {
        "ETH/USDC:USDC": {"basket_z": -3.0, "btc_mom": 1.0, "btc_pump": False, "btc_dump": False, "btc_high_vol": False, "vol_ok": True},
    }
    scores = {"ETH/USDC:USDC": 0.9}
    open_pairs = {"ETH/USDC:USDC"}
    long_q, short_q = build_queues(scores, pair_data, cfg, open_pairs)
    assert long_q == []


def test_confirmation_3_candles():
    reset()
    cfg = _make_cfg()
    # Candle 1: ETH in top-K → confirm=1
    ready = update_confirmation(["ETH/USDC:USDC"], [], cfg)
    assert ready == []
    # Candle 2: ETH still in top-K → confirm=2
    ready = update_confirmation(["ETH/USDC:USDC"], [], cfg)
    assert ready == []
    # Candle 3: ETH still in top-K → confirm=3 → READY
    ready = update_confirmation(["ETH/USDC:USDC"], [], cfg)
    assert ready == [("ETH/USDC:USDC", "long")]


def test_confirmation_resets_on_drop():
    reset()
    cfg = _make_cfg()
    # 2 candles in queue
    update_confirmation(["ETH/USDC:USDC"], [], cfg)
    update_confirmation(["ETH/USDC:USDC"], [], cfg)
    # Drops out of queue
    update_confirmation([], [], cfg)
    # Back in queue — counter restarted
    ready = update_confirmation(["ETH/USDC:USDC"], [], cfg)
    assert ready == []  # only 1 candle since reset
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_v58_queue.py -v
```

Expected: new tests FAIL — `build_queues` and `update_confirmation` not defined.

- [ ] **Step 3: Implement `build_queues` and `update_confirmation`**

Append to `user_data/strategies/zscore_v58/queue.py`:

```python
def build_queues(
    scores: dict[str, float],
    pair_data: dict[str, dict],
    cfg: dict,
    open_pairs: set[str],
) -> tuple[list[str], list[str]]:
    """Build long and short queues from scored pairs.

    Filters by entry_z threshold, BTC regime, safety, and vol.
    Excludes pairs with open trades.
    Returns top-K pairs per queue, sorted by score descending.
    """
    basket_cfg = cfg["basket"]
    entry_z = basket_cfg.get("entry_z", 2.0)
    bull_th = basket_cfg.get("bull_mom_threshold", 0.0)
    bear_th = basket_cfg.get("bear_mom_threshold", -1.0)
    top_k = cfg["queue"].get("top_k", 3)

    long_candidates = []
    short_candidates = []

    for pair, d in pair_data.items():
        if pair in open_pairs:
            continue
        if not d.get("vol_ok", False):
            continue
        if d.get("btc_high_vol", False):
            continue

        bz = d.get("basket_z", 0.0)
        btc_mom = d.get("btc_mom", 0.0)
        score = scores.get(pair, 0.0)

        # Long: pair lagging (z < -entry_z), bull regime, no dump
        if bz < -entry_z and btc_mom > bull_th and not d.get("btc_dump", False):
            long_candidates.append((pair, score))

        # Short: pair leading (z > entry_z), bear regime, no pump
        if bz > entry_z and btc_mom < bear_th and not d.get("btc_pump", False):
            short_candidates.append((pair, score))

    # Sort by score descending, keep top-K
    long_candidates.sort(key=lambda x: x[1], reverse=True)
    short_candidates.sort(key=lambda x: x[1], reverse=True)

    long_queue = [p for p, _ in long_candidates[:top_k]]
    short_queue = [p for p, _ in short_candidates[:top_k]]

    return long_queue, short_queue


def update_confirmation(
    long_queue: list[str],
    short_queue: list[str],
    cfg: dict,
) -> list[tuple[str, str]]:
    """Update confirmation counters and return ready-to-enter pairs.

    A pair must stay in its queue's top-K for `confirm_candles` consecutive
    candles. If it drops out, its counter resets to 0.

    Returns list of (pair, side) tuples that are confirmed and ready.
    """
    confirm_needed = cfg["queue"].get("confirm_candles", 3)
    ready: list[tuple[str, str]] = []

    long_set = set(long_queue)
    short_set = set(short_queue)

    # Update long confirmations
    for pair in list(_confirm_long.keys()):
        if pair not in long_set:
            _confirm_long[pair] = 0
    for pair in long_queue:
        _confirm_long[pair] = _confirm_long.get(pair, 0) + 1
        if _confirm_long[pair] >= confirm_needed:
            ready.append((pair, "long"))

    # Update short confirmations
    for pair in list(_confirm_short.keys()):
        if pair not in short_set:
            _confirm_short[pair] = 0
    for pair in short_queue:
        _confirm_short[pair] = _confirm_short.get(pair, 0) + 1
        if _confirm_short[pair] >= confirm_needed:
            ready.append((pair, "short"))

    return ready


def record_exit(pair: str, candle_index: int):
    """Record that a trade on this pair exited at the given candle.

    Used by cooldown_bonus scoring factor.
    """
    _last_exit_candle[pair] = candle_index
    # Also reset confirmation counters for this pair
    _confirm_long[pair] = 0
    _confirm_short[pair] = 0
```

- [ ] **Step 4: Run all tests to verify they pass**

```bash
.venv/bin/pytest tests/test_v58_queue.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add user_data/strategies/zscore_v58/queue.py tests/test_v58_queue.py
git commit -m "feat(v58): implement queue building and confirmation tracking"
```

---

### Task 4: Implement `strategy.py` — V58 strategy class

**Files:**
- Create: `user_data/strategies/zscore_v58/strategy.py`

- [ ] **Step 1: Create V58 strategy**

Create `user_data/strategies/zscore_v58/strategy.py`:

```python
"""
ZScoreV58Strategy — Queue-Based Scoring Entry
===============================================

Replaces V57's per-pair independent entry with centralized scoring.
Each candle, all pairs receive a multi-factor score. Top-K pairs per
side enter a confirmation queue. A pair must stay in top-K for N
consecutive candles before it can trade.

Exits identical to V57 (basket reversion, time stop, max loss).

Modules (self-contained in zscore_v58/):
    queue.py      — NEW: scoring, queue ranking, confirmation
    basket.py     — basket z-score computation + exit logic (from V57)
    btc_trend.py  — BTC momentum + volatility from 1h
    volume.py     — volume filter
    dca.py        — DCA on winners
    stake.py      — dynamic stake sizing
    state.py      — persistent state
    config.py     — JSON config loader
"""
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from pandas import DataFrame

_STRATEGIES_DIR = str(Path(__file__).resolve().parent.parent)
if _STRATEGIES_DIR not in sys.path:
    sys.path.insert(0, _STRATEGIES_DIR)

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy

from zscore_v58 import btc_trend, volume, basket, config as cfg_loader, dca, queue
from zscore_v58.stake import DynamicStake
from zscore_v58.state import StrategyState

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "v58_config.json"


class ZScoreV58Strategy(IStrategy):
    """Queue-based scoring entry — pairs compete, best confirmed entries win."""

    INTERFACE_VERSION = 3
    can_short = True
    process_only_new_candles = True
    timeframe = "5m"
    startup_candle_count = 900
    stoploss = -0.99
    minimal_roi = {"0": 10}
    trailing_stop = False
    use_custom_stoploss = True
    position_adjustment_enable = True
    max_entry_position_adjustment = 3

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        c = cfg_loader.load(CONFIG_PATH)
        self._cfg = c

        self._basket_pairs: list[str] = c["basket"]["pairs"]
        self.BTC_REF: str = c["basket"]["btc_ref"]

        self.timeframe = c.get("timeframe", "5m")
        self.startup_candle_count = c.get("startup_candle_count", 900)
        self.stoploss = c["risk"]["stoploss"]
        self.max_entry_position_adjustment = c.get("dca", {}).get("max_adds", 3)

        self._df_cache: dict[str, DataFrame] = {}
        self._df_cache_cycle: int = 0
        self._btc_trend: dict = {}
        self._candle_index: int = 0

        run_id = f"v58_{self.timeframe}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        self._state = StrategyState(run_id)
        self._state.initial_balance = 100.0
        self._state.balance = 100.0

        self._dynamic_stake = DynamicStake(c)

        # Reset queue state on init
        queue.reset()

        logger.info(
            "V58 loaded — basket=%d pairs, BTC=%s, queue top_k=%d confirm=%d",
            len(self._basket_pairs), self.BTC_REF,
            c.get("queue", {}).get("top_k", 3),
            c.get("queue", {}).get("confirm_candles", 3),
        )

    def _get_pair_df(self, pair: str, timeframe: str | None = None) -> DataFrame | None:
        tf = timeframe or self.timeframe
        key = f"{pair}__{tf}"
        if key in self._df_cache:
            return self._df_cache[key]
        if not self.dp:
            return None
        df = self.dp.get_pair_dataframe(pair=pair, timeframe=tf)
        if df is not None:
            self._df_cache[key] = df
        return df

    def informative_pairs(self):
        pairs = self.dp.current_whitelist() if self.dp else []
        btc_tf = self._cfg.get("btc_trend", {}).get("timeframe", "1h")
        return [(pair, "1d") for pair in pairs] + [(self.BTC_REF, btc_tf)]

    # ── Indicators ────────────────────────────────────────────────

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]
        cycle_id = id(dataframe)
        if cycle_id != self._df_cache_cycle:
            self._df_cache.clear()
            self._df_cache_cycle = cycle_id
            self._btc_trend = {}

        if not self._btc_trend:
            btc_tf = self._cfg.get("btc_trend", {}).get("timeframe", "1h")
            btc_df = self._get_pair_df(self.BTC_REF, btc_tf)
            if btc_df is not None and len(btc_df) >= 50:
                self._btc_trend = btc_trend.compute(btc_df, self._cfg)
        dataframe = btc_trend.map_to_timeframe(self._btc_trend, dataframe)

        volume.compute(dataframe, self._cfg)

        basket.compute_basket_zscore(
            dataframe, pair, self._basket_pairs,
            self._cfg["zscore"]["zscore_window"],
            self.timeframe, self.dp, self._df_cache,
            self._cfg,
        )
        return dataframe

    # ── Entry ─────────────────────────────────────────────────────

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe["enter_tag"] = ""

        if pair == self.BTC_REF or dataframe.empty:
            return dataframe

        # Queue logic runs once per candle cycle (first pair triggers it)
        cycle_id = id(dataframe)
        if queue._score_cache.get("cycle") != cycle_id:
            self._candle_index += 1
            self._run_queue_cycle(cycle_id)

        # Check if this pair is in the ready list
        ready_list = queue._score_cache.get("ready", [])
        for ready_pair, side in ready_list:
            if ready_pair == pair:
                if side == "long":
                    dataframe.iloc[-1, dataframe.columns.get_loc("enter_long")] = 1
                    dataframe.iloc[-1, dataframe.columns.get_loc("enter_tag")] = "queue_long"
                else:
                    dataframe.iloc[-1, dataframe.columns.get_loc("enter_short")] = 1
                    dataframe.iloc[-1, dataframe.columns.get_loc("enter_tag")] = "queue_short"
                break

        return dataframe

    def _run_queue_cycle(self, cycle_id: int):
        """Run scoring → queue → confirmation for current candle. Cache results."""
        # Gather current candle data for all pairs
        pair_data: dict[str, dict] = {}
        for p in self._basket_pairs:
            if p == self.BTC_REF:
                continue
            df = self._get_pair_df(p)
            if df is None or df.empty or len(df) < 4:
                continue
            last = df.iloc[-1]
            pair_data[p] = {
                "basket_z": float(last.get("basket_z", 0.0)),
                "basket_z_prev3": float(df["basket_z"].iloc[-4]) if "basket_z" in df.columns and len(df) >= 4 else 0.0,
                "vol_ratio": float(last.get("vol_ratio", 1.0)),
                "vol_ok": bool(last.get("vol_ok", False)),
                "btc_mom": float(last.get("btc_mom", 0.0)),
                "btc_pump": bool(last.get("btc_pump", False)),
                "btc_dump": bool(last.get("btc_dump", False)),
                "btc_high_vol": bool(last.get("btc_high_vol", False)),
            }

        open_trades = Trade.get_trades_proxy(is_open=True)
        open_pairs = {t.pair for t in open_trades}

        scores = queue.compute_scores(pair_data, self._cfg, self._candle_index)
        long_q, short_q = queue.build_queues(scores, pair_data, self._cfg, open_pairs)
        ready = queue.update_confirmation(long_q, short_q, self._cfg)

        # Sort ready by score descending
        ready.sort(key=lambda x: scores.get(x[0], 0), reverse=True)

        queue._score_cache = {"cycle": cycle_id, "scores": scores, "ready": ready}

    # ── Exit ──────────────────────────────────────────────────────

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        tag = trade.enter_tag or ""
        if not tag.startswith("queue_"):
            return None

        result = basket.check_basket_exit(
            pair, trade, current_profit, self._cfg,
            self.dp, self._df_cache, self.timeframe, self._basket_pairs,
        )
        if result:
            return result

        max_candles = self._cfg.get("basket", {}).get("time_stop_candles", 72)
        trade_age = (current_time - trade.open_date_utc).total_seconds() / 300
        if trade_age >= max_candles:
            return "basket_time_stop"

        return None

    def confirm_trade_exit(self, pair: str, trade: Trade, order_type: str,
                           amount: float, rate: float, time_in_force: str,
                           exit_reason: str, current_time: datetime, **kwargs) -> bool:
        profit = trade.calc_profit_ratio(rate)
        self._state.record_trade(
            pair=pair, profit_ratio=profit, profit_abs=profit * trade.stake_amount,
            leverage=trade.leverage, entry_tag=trade.enter_tag or "",
            exit_reason=exit_reason, open_date=trade.open_date_utc,
            close_date=current_time, open_rate=trade.open_rate,
            close_rate=rate, is_short=trade.is_short,
        )
        self._state.save()
        # Record exit for cooldown scoring
        queue.record_exit(pair, self._candle_index)
        return True

    # ── Confirm entry ─────────────────────────────────────────────

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float,
                            rate: float, time_in_force: str, current_time: datetime,
                            entry_tag: Optional[str], side: str, **kwargs) -> bool:
        open_trades = Trade.get_trades_proxy(is_open=True)
        max_pos = self._cfg.get("basket", {}).get("max_positions", 4)
        if len(open_trades) >= max_pos:
            return False
        if pair in {t.pair for t in open_trades}:
            return False
        # Reset confirmation counter after entry
        queue._confirm_long[pair] = 0
        queue._confirm_short[pair] = 0
        return True

    # ── Stoploss ──────────────────────────────────────────────────

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float,
                        after_fill: bool, **kwargs) -> float | None:
        tag = trade.enter_tag or ""
        if tag.startswith("queue_"):
            return -0.99
        r = self._cfg["risk"]
        if current_profit >= r.get("trailing_stop_positive_offset", 0.012):
            return -r.get("trailing_stop_positive", 0.006)
        return r.get("stoploss", -0.07)

    # ── Leverage ──────────────────────────────────────────────────

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float,
                 entry_tag: Optional[str], side: str, **kwargs) -> float:
        return min(self._cfg.get("leverage", {}).get("base_multiplier", 3.0), max_leverage)

    # ── DCA ───────────────────────────────────────────────────────

    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: Optional[float], max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs) -> Optional[float]:
        return dca.adjust_position(trade, current_profit, self._cfg, min_stake, max_stake)

    # ── Stake ─────────────────────────────────────────────────────

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float],
                            max_stake: float, leverage: float, entry_tag: Optional[str],
                            side: str, **kwargs) -> float:
        open_trades = Trade.get_trades_proxy(is_open=True)
        stake = self._dynamic_stake.compute(
            wallets=self.wallets,
            stake_currency=self.config["stake_currency"],
            open_trade_count=len(open_trades),
            max_stake=max_stake,
            open_trades=open_trades,
        )
        if min_stake and stake < min_stake:
            stake = min_stake
        return stake
```

- [ ] **Step 2: Verify strategy loads without errors**

```bash
.venv/bin/freqtrade backtesting --strategy ZScoreV58Strategy --timerange 20260401-20260410 --config user_data/strategies/v57_backtest_config.json --config user_data/strategies/v58_config.json -v 2>&1 | tail -5
```

Expected: backtest runs (may have 0 trades since confirmation needs 3 candles — that's OK at this stage).

- [ ] **Step 3: Commit**

```bash
git add user_data/strategies/zscore_v58/strategy.py
git commit -m "feat(v58): implement strategy with queue-based entry orchestration"
```

---

### Task 5: Fix `__init__.py` and run full backtest

**Files:**
- Modify: `user_data/strategies/zscore_v58/__init__.py`

- [ ] **Step 1: Update `__init__.py` to export V58**

Write `user_data/strategies/zscore_v58/__init__.py`:

```python
from .strategy import ZScoreV58Strategy  # noqa: F401
```

- [ ] **Step 2: Run full 4-month backtest**

```bash
.venv/bin/freqtrade backtesting --strategy ZScoreV58Strategy --timerange 20260117-20260517 --config user_data/strategies/v57_backtest_config.json --config user_data/strategies/v58_config.json -v 2>&1 | tail -40
```

Expected: Backtest completes with trades. Compare against V57 baseline (291 trades, 88.3% win, +176%):
- Fewer trades (queue filters weak entries)
- Higher or comparable win rate
- Comparable profit

- [ ] **Step 3: Run all tests**

```bash
.venv/bin/pytest tests/test_v58_queue.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add user_data/strategies/zscore_v58/__init__.py
git commit -m "feat(v58): complete V58 queue strategy — ready for backtest comparison"
```

---

### Task 6: Backtest comparison V57 vs V58

**Files:** None (analysis only)

- [ ] **Step 1: Run V57 baseline backtest**

```bash
.venv/bin/freqtrade backtesting --strategy ZScoreV57Monitor --timerange 20260117-20260517 --config user_data/strategies/v57_backtest_config.json --config user_data/strategies/v57_config.json -v 2>&1 | grep -E "TOTAL|STRATEGY|Trades|Win|Profit|Drawdown|balance"
```

- [ ] **Step 2: Run V58 backtest**

```bash
.venv/bin/freqtrade backtesting --strategy ZScoreV58Strategy --timerange 20260117-20260517 --config user_data/strategies/v57_backtest_config.json --config user_data/strategies/v58_config.json -v 2>&1 | grep -E "TOTAL|STRATEGY|Trades|Win|Profit|Drawdown|balance"
```

- [ ] **Step 3: Compare and document results**

Record in commit message:
- V57: trades, win%, profit%, drawdown
- V58: trades, win%, profit%, drawdown
- Delta analysis

- [ ] **Step 4: Commit results**

```bash
git add -A
git commit -m "test(v58): backtest comparison V57 vs V58 — queue scoring entry"
```
