# V59 Always-On Queue — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build V59 strategy where all pairs are always in queues (LONG/SHORT by z sign), scored with regime multiplier, and only #1 enters if score >= min_score.

**Architecture:** Copy V58 modules to zscore_v59/, rewrite `entry_queue.py` (remove threshold/top_k, add regime multiplier), simplify strategy entries. Backend queue loop updated. Exits unchanged.

**Tech Stack:** Python 3.13, freqtrade 2026.3, pandas, numpy

**Spec:** `docs/superpowers/specs/2026-05-17-v59-always-on-queue-design.md`

---

### Task 1: Scaffold V59 + config + entry_queue.py + tests

**Files:**
- Create: `user_data/strategies/zscore_v59/` (copy from V58)
- Create: `user_data/strategies/v59_config.json`
- Rewrite: `user_data/strategies/zscore_v59/entry_queue.py`
- Rewrite: `tests/test_v59_queue.py`

- [ ] **Step 1: Copy V58 modules to V59**

```bash
mkdir -p user_data/strategies/zscore_v59
for f in config.py basket.py btc_trend.py volume.py dca.py leverage.py stake.py state.py; do
  cp user_data/strategies/zscore_v58/$f user_data/strategies/zscore_v59/$f
done
echo "# V59 — will export ZScoreV59Strategy once strategy.py exists" > user_data/strategies/zscore_v59/__init__.py
```

- [ ] **Step 2: Create v59_config.json**

Create `user_data/strategies/v59_config.json`:

```json
{
    "timeframe": "5m",
    "startup_candle_count": 900,
    "basket": {
        "pairs": [
            "BTC/USDC:USDC", "ETH/USDC:USDC", "SOL/USDC:USDC", "LINK/USDC:USDC",
            "BNB/USDC:USDC", "XRP/USDC:USDC", "SUI/USDC:USDC", "DOGE/USDC:USDC",
            "AAVE/USDC:USDC", "ENA/USDC:USDC", "ONDO/USDC:USDC", "NEAR/USDC:USDC",
            "INJ/USDC:USDC", "HYPE/USDC:USDC", "TON/USDC:USDC", "TAO/USDC:USDC",
            "ZEC/USDC:USDC", "FARTCOIN/USDC:USDC", "PENDLE/USDC:USDC", "TRUMP/USDC:USDC"
        ],
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

- [ ] **Step 3: Write entry_queue.py for V59**

Create `user_data/strategies/zscore_v59/entry_queue.py`:

```python
"""Always-on queue with regime scoring for V59.

All pairs are always in queues (LONG if z<0, SHORT if z>0).
Score = raw_score * regime_multiplier.
Only #1 in each queue enters if score >= min_score.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_last_exit_candle: dict[str, int] = {}
_score_cache: dict = {}


def reset():
    global _last_exit_candle, _score_cache
    _last_exit_candle = {}
    _score_cache = {}


def _get_regime(btc_mom: float) -> str:
    if btc_mom > 0.0:
        return "bull"
    if btc_mom <= -1.0:
        return "bear"
    return "ranging"


def compute_scores(
    pair_data: dict[str, dict],
    cfg: dict,
    candle_index: int,
) -> dict[str, float]:
    """Compute raw score (before regime multiplier) for each pair."""
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

        bz_norm = min(bz, 4.0) / 4.0
        vol_norm = min(vr, 3.0) / 3.0
        vel_norm = min(velocity, 2.0) / 2.0

        last_exit = _last_exit_candle.get(pair, -999)
        cd_norm = 0.0 if (candle_index - last_exit) < cooldown_candles else 1.0

        score = w_bz * bz_norm + w_vol * vol_norm + w_vel * vel_norm + w_cd * cd_norm
        scores[pair] = round(score, 6)

    return scores


def apply_regime_multiplier(
    raw_scores: dict[str, float],
    pair_data: dict[str, dict],
    cfg: dict,
) -> tuple[dict[str, float], dict[str, float]]:
    """Apply regime multiplier. Returns (long_adjusted, short_adjusted) dicts.

    All pairs with z<0 get a long adjusted score.
    All pairs with z>0 get a short adjusted score.
    """
    mults = cfg["queue"].get("regime_multipliers", {})
    # Determine regime from first pair's btc_mom (all pairs share the same btc data)
    btc_mom = 0.0
    for d in pair_data.values():
        btc_mom = d.get("btc_mom", 0.0)
        break
    regime = _get_regime(btc_mom)

    long_mult = mults.get(f"{regime}_long", 0.6)
    short_mult = mults.get(f"{regime}_short", 0.6)

    long_adj: dict[str, float] = {}
    short_adj: dict[str, float] = {}

    for pair, d in pair_data.items():
        bz = d.get("basket_z", 0.0)
        raw = raw_scores.get(pair, 0.0)
        if bz < 0:
            long_adj[pair] = round(raw * long_mult, 6)
        elif bz > 0:
            short_adj[pair] = round(raw * short_mult, 6)

    return long_adj, short_adj


def build_queues(
    long_adjusted: dict[str, float],
    short_adjusted: dict[str, float],
    pair_data: dict[str, dict],
    open_pairs: set[str],
) -> tuple[list[tuple[str, float]], list[tuple[str, float]]]:
    """Build ranked queues. ALL pairs included, sorted by adjusted score desc.

    Returns (long_queue, short_queue) where each is [(pair, adj_score), ...].
    Pairs with open trades are included in ranking but marked.
    """
    long_q: list[tuple[str, float]] = []
    for pair, adj in long_adjusted.items():
        if pair in open_pairs:
            continue
        long_q.append((pair, adj))
    long_q.sort(key=lambda x: x[1], reverse=True)

    short_q: list[tuple[str, float]] = []
    for pair, adj in short_adjusted.items():
        if pair in open_pairs:
            continue
        short_q.append((pair, adj))
    short_q.sort(key=lambda x: x[1], reverse=True)

    return long_q, short_q


def get_entry_candidate(
    long_queue: list[tuple[str, float]],
    short_queue: list[tuple[str, float]],
    pair_data: dict[str, dict],
    cfg: dict,
) -> list[tuple[str, str, float]]:
    """Get #1 from each queue if it passes min_score + safety.

    Returns list of (pair, side, adjusted_score) ready to enter.
    """
    min_score = cfg["queue"].get("min_score", 0.45)
    ready: list[tuple[str, str, float]] = []

    # #1 LONG
    if long_queue:
        pair, adj = long_queue[0]
        d = pair_data.get(pair, {})
        if (adj >= min_score
                and d.get("vol_ok", False)
                and not d.get("btc_high_vol", False)
                and not d.get("btc_dump", False)):
            ready.append((pair, "long", adj))

    # #1 SHORT
    if short_queue:
        pair, adj = short_queue[0]
        d = pair_data.get(pair, {})
        if (adj >= min_score
                and d.get("vol_ok", False)
                and not d.get("btc_high_vol", False)
                and not d.get("btc_pump", False)):
            ready.append((pair, "short", adj))

    return ready


def record_exit(pair: str, candle_index: int):
    _last_exit_candle[pair] = candle_index
```

- [ ] **Step 4: Write tests**

Create `tests/test_v59_queue.py`:

```python
"""Tests for V59 always-on queue."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "user_data" / "strategies"))

from zscore_v59.entry_queue import (
    compute_scores, apply_regime_multiplier, build_queues,
    get_entry_candidate, reset, _get_regime,
)


def _cfg():
    return {
        "queue": {
            "min_score": 0.45,
            "cooldown_candles": 36,
            "weights": {"basket_z": 0.5, "vol_ratio": 0.2, "spread_velocity": 0.2, "cooldown": 0.1},
            "regime_multipliers": {
                "bull_long": 1.0, "bull_short": 0.3,
                "ranging_long": 0.6, "ranging_short": 0.6,
                "bear_long": 0.3, "bear_short": 1.0,
            },
        },
    }


def _pair(basket_z=-2.0, vol_ratio=1.5, btc_mom=1.0, vol_ok=True,
          btc_pump=False, btc_dump=False, btc_high_vol=False, basket_z_prev3=None):
    return {
        "basket_z": basket_z, "basket_z_prev3": basket_z_prev3 if basket_z_prev3 is not None else basket_z,
        "vol_ratio": vol_ratio, "vol_ok": vol_ok, "btc_mom": btc_mom,
        "btc_pump": btc_pump, "btc_dump": btc_dump, "btc_high_vol": btc_high_vol,
    }


def test_regime_detection():
    assert _get_regime(1.0) == "bull"
    assert _get_regime(0.1) == "bull"
    assert _get_regime(0.0) == "ranging"  # 0 is not > 0
    assert _get_regime(-0.5) == "ranging"
    assert _get_regime(-1.0) == "bear"
    assert _get_regime(-2.0) == "bear"


def test_all_pairs_in_queues():
    """All pairs with z!=0 appear in a queue."""
    reset()
    cfg = _cfg()
    pair_data = {
        "ETH": _pair(basket_z=-2.0, btc_mom=1.0),
        "SOL": _pair(basket_z=-0.5, btc_mom=1.0),
        "LINK": _pair(basket_z=1.5, btc_mom=1.0),
        "XRP": _pair(basket_z=3.0, btc_mom=1.0),
    }
    raw = compute_scores(pair_data, cfg, 100)
    long_adj, short_adj = apply_regime_multiplier(raw, pair_data, cfg)

    # z<0 → long queue, z>0 → short queue
    assert "ETH" in long_adj
    assert "SOL" in long_adj
    assert "LINK" in short_adj
    assert "XRP" in short_adj
    assert "ETH" not in short_adj
    assert "LINK" not in long_adj


def test_regime_multiplier_bull():
    """In BULL, long scores are full, short scores penalized."""
    reset()
    cfg = _cfg()
    pair_data = {
        "ETH": _pair(basket_z=-2.0, btc_mom=1.0, vol_ratio=2.0),
        "SOL": _pair(basket_z=2.0, btc_mom=1.0, vol_ratio=2.0),
    }
    raw = compute_scores(pair_data, cfg, 100)
    long_adj, short_adj = apply_regime_multiplier(raw, pair_data, cfg)

    # Both have same raw score (same |z|, same vol)
    assert raw["ETH"] == raw["SOL"]
    # But adjusted: LONG gets 1.0x, SHORT gets 0.3x
    assert long_adj["ETH"] > short_adj["SOL"]
    assert abs(long_adj["ETH"] - raw["ETH"] * 1.0) < 0.001
    assert abs(short_adj["SOL"] - raw["SOL"] * 0.3) < 0.001


def test_regime_multiplier_bear():
    """In BEAR, short scores are full, long scores penalized."""
    reset()
    cfg = _cfg()
    pair_data = {
        "ETH": _pair(basket_z=-2.0, btc_mom=-2.0),
        "SOL": _pair(basket_z=2.0, btc_mom=-2.0),
    }
    raw = compute_scores(pair_data, cfg, 100)
    long_adj, short_adj = apply_regime_multiplier(raw, pair_data, cfg)

    assert long_adj["ETH"] < short_adj["SOL"]  # LONG penalized in BEAR


def test_queue_ranking_by_score():
    """Queues are sorted by adjusted score descending."""
    reset()
    cfg = _cfg()
    pair_data = {
        "ETH": _pair(basket_z=-3.0, btc_mom=1.0, vol_ratio=2.5),
        "SOL": _pair(basket_z=-1.0, btc_mom=1.0, vol_ratio=1.0),
        "LINK": _pair(basket_z=-2.0, btc_mom=1.0, vol_ratio=1.5),
    }
    raw = compute_scores(pair_data, cfg, 100)
    long_adj, short_adj = apply_regime_multiplier(raw, pair_data, cfg)
    long_q, short_q = build_queues(long_adj, short_adj, pair_data, set())

    # ETH has highest z + vol → should be #1
    assert long_q[0][0] == "ETH"
    assert len(long_q) == 3  # all 3 in long queue


def test_only_number_one_enters():
    """Only #1 from each queue can enter."""
    reset()
    cfg = _cfg()
    pair_data = {
        "ETH": _pair(basket_z=-3.0, btc_mom=1.0, vol_ratio=2.0, basket_z_prev3=-1.5),
        "SOL": _pair(basket_z=-2.5, btc_mom=1.0, vol_ratio=1.5, basket_z_prev3=-1.0),
    }
    raw = compute_scores(pair_data, cfg, 100)
    long_adj, short_adj = apply_regime_multiplier(raw, pair_data, cfg)
    long_q, short_q = build_queues(long_adj, short_adj, pair_data, set())
    ready = get_entry_candidate(long_q, short_q, pair_data, cfg)

    assert len(ready) <= 1  # only #1 long (no short candidates)
    if ready:
        assert ready[0][0] == "ETH"  # ETH is #1


def test_min_score_rejects():
    """Pairs below min_score don't enter even if #1."""
    reset()
    cfg = _cfg()
    # Low z, low vol → low score
    pair_data = {
        "ETH": _pair(basket_z=-0.2, btc_mom=0.5, vol_ratio=0.5, basket_z_prev3=-0.2),
    }
    raw = compute_scores(pair_data, cfg, 100)
    long_adj, _ = apply_regime_multiplier(raw, pair_data, cfg)
    long_q, short_q = build_queues(long_adj, {}, pair_data, set())
    ready = get_entry_candidate(long_q, short_q, pair_data, cfg)

    assert len(ready) == 0  # score too low


def test_open_trade_excluded_from_queue():
    """Pairs with open trades are excluded from queue ranking."""
    reset()
    cfg = _cfg()
    pair_data = {
        "ETH": _pair(basket_z=-3.0, btc_mom=1.0),
        "SOL": _pair(basket_z=-2.0, btc_mom=1.0),
    }
    raw = compute_scores(pair_data, cfg, 100)
    long_adj, short_adj = apply_regime_multiplier(raw, pair_data, cfg)
    long_q, _ = build_queues(long_adj, short_adj, pair_data, {"ETH"})

    assert long_q[0][0] == "SOL"  # ETH excluded, SOL is #1


def test_safety_blocks_entry():
    """BTC dump blocks long entry, BTC pump blocks short entry."""
    reset()
    cfg = _cfg()
    pair_data = {
        "ETH": _pair(basket_z=-3.0, btc_mom=1.0, vol_ratio=3.0, btc_dump=True, basket_z_prev3=-1.5),
    }
    raw = compute_scores(pair_data, cfg, 100)
    long_adj, short_adj = apply_regime_multiplier(raw, pair_data, cfg)
    long_q, short_q = build_queues(long_adj, short_adj, pair_data, set())
    ready = get_entry_candidate(long_q, short_q, pair_data, cfg)

    assert len(ready) == 0  # blocked by btc_dump
```

- [ ] **Step 5: Run tests**

```bash
.venv/bin/python -m pytest tests/test_v59_queue.py -v
```

Expected: all 9 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add -f user_data/strategies/zscore_v59/ user_data/strategies/v59_config.json tests/test_v59_queue.py
git commit -m "feat(v59): always-on queue with regime scoring — module + tests"
```

---

### Task 2: Strategy.py + flat file + backtest

**Files:**
- Create: `user_data/strategies/zscore_v59/strategy.py`
- Create: `user_data/strategies/ZScoreV59Strategy.py`

- [ ] **Step 1: Create strategy.py**

Create `user_data/strategies/zscore_v59/strategy.py`. This is a modified copy of V58's strategy. Key differences:

1. `populate_entry_trend`: marks ALL pairs as candidates (z<0→queue_long, z>0→queue_short), no threshold
2. `confirm_trade_entry`: computes scores, applies regime multiplier, builds queues, checks if pair is #1 + min_score + safety. No persistence check.
3. Imports from `zscore_v59` instead of `zscore_v58`
4. Config path: `v59_config.json`

```python
"""
ZScoreV59Strategy — Always-On Queue with Regime Scoring
=========================================================

All pairs always ranked in LONG/SHORT queues by z-score sign.
Score = raw_score * regime_multiplier.
Only #1 in each queue enters if adjusted score >= min_score.
"""
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from pandas import DataFrame

_STRATEGIES_DIR = str(Path(__file__).resolve().parent.parent)
if _STRATEGIES_DIR not in sys.path:
    sys.path.insert(0, _STRATEGIES_DIR)

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy

from zscore_v59 import btc_trend, volume, basket, config as cfg_loader, dca, entry_queue
from zscore_v59.stake import DynamicStake
from zscore_v59.state import StrategyState

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "v59_config.json"


class ZScoreV59Strategy(IStrategy):

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

        run_id = f"v59_{self.timeframe}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        self._state = StrategyState(run_id)
        self._state.initial_balance = 100.0
        self._state.balance = 100.0
        self._dynamic_stake = DynamicStake(c)

        if "queue" in self.config:
            c["queue"] = {**c.get("queue", {}), **self.config["queue"]}

        entry_queue.reset()
        logger.info("V59 loaded — %d pairs, always-on queue, min_score=%.2f",
                     len(self._basket_pairs), c.get("queue", {}).get("min_score", 0.45))

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
            self.timeframe, self.dp, self._df_cache, self._cfg,
        )
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """V59: ALL pairs are candidates. z<0 → queue_long, z>0 → queue_short."""
        pair = metadata["pair"]
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe["enter_tag"] = ""
        if pair == self.BTC_REF or dataframe.empty or "basket_z" not in dataframe.columns:
            return dataframe

        # Mark every candle where z != 0 as a candidate
        mask_long = dataframe["basket_z"] < 0
        mask_short = dataframe["basket_z"] > 0
        dataframe.loc[mask_long, ["enter_long", "enter_tag"]] = (1, "queue_long")
        dataframe.loc[mask_short, ["enter_short", "enter_tag"]] = (1, "queue_short")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        tag = trade.enter_tag or ""
        if not tag.startswith("queue_"):
            return None
        orig_tag = trade.enter_tag
        trade.enter_tag = tag.replace("queue_", "basket_")
        result = basket.check_basket_exit(
            pair, trade, current_profit, self._cfg,
            self.dp, self._df_cache, self.timeframe, self._basket_pairs,
        )
        trade.enter_tag = orig_tag
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
        entry_queue.record_exit(pair, self._candle_index)
        return True

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float,
                            rate: float, time_in_force: str, current_time: datetime,
                            entry_tag: Optional[str], side: str, **kwargs) -> bool:
        """V59: Score all pairs, apply regime multiplier, check if this pair is #1."""
        open_trades = Trade.get_trades_proxy(is_open=True)
        max_pos = self._cfg.get("basket", {}).get("max_positions", 4)
        if len(open_trades) >= max_pos:
            return False
        if pair in {t.pair for t in open_trades}:
            return False
        if not self.dp:
            return False

        import pandas as pd
        ct = pd.Timestamp(current_time)

        # Gather data for all pairs at current candle
        pair_data: dict[str, dict] = {}
        for p in self._basket_pairs:
            if p == self.BTC_REF:
                continue
            p_df, _ = self.dp.get_analyzed_dataframe(p, self.timeframe)
            if p_df is None or p_df.empty or len(p_df) < 4:
                continue
            if p_df["date"].dt.tz is not None:
                ct_tz = ct.tz_localize("UTC") if ct.tz is None else ct.tz_convert("UTC")
            else:
                ct_tz = ct
            p_mask = p_df["date"] <= ct_tz
            if not p_mask.any():
                continue
            p_idx = p_mask.sum() - 1
            if p_idx < 3:
                continue
            row = p_df.iloc[p_idx]
            pair_data[p] = {
                "basket_z": float(row.get("basket_z", 0.0)),
                "basket_z_prev3": float(p_df["basket_z"].iloc[p_idx - 3]),
                "vol_ratio": float(row.get("vol_ratio", 1.0)),
                "vol_ok": bool(row.get("vol_ok", False)),
                "btc_mom": float(row.get("btc_mom", 0.0)),
                "btc_pump": bool(row.get("btc_pump", False)),
                "btc_dump": bool(row.get("btc_dump", False)),
                "btc_high_vol": bool(row.get("btc_high_vol", False)),
            }

        self._candle_index += 1
        open_pairs = {t.pair for t in open_trades}

        raw_scores = entry_queue.compute_scores(pair_data, self._cfg, self._candle_index)
        long_adj, short_adj = entry_queue.apply_regime_multiplier(raw_scores, pair_data, self._cfg)
        long_q, short_q = entry_queue.build_queues(long_adj, short_adj, pair_data, open_pairs)
        ready = entry_queue.get_entry_candidate(long_q, short_q, pair_data, self._cfg)

        for ready_pair, ready_side, adj_score in ready:
            if ready_pair == pair:
                return True
        return False

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

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float,
                 entry_tag: Optional[str], side: str, **kwargs) -> float:
        return min(self._cfg.get("leverage", {}).get("base_multiplier", 3.0), max_leverage)

    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: Optional[float], max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs) -> Optional[float]:
        return dca.adjust_position(trade, current_profit, self._cfg, min_stake, max_stake)

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

- [ ] **Step 2: Create flat strategy file**

Copy the strategy file and fix paths for the flat file (same as V58 pattern):

```bash
cp user_data/strategies/zscore_v59/strategy.py user_data/strategies/ZScoreV59Strategy.py
```

Then edit `ZScoreV59Strategy.py`:
- Change `_STRATEGIES_DIR = str(Path(__file__).resolve().parent.parent)` to `_STRATEGIES_DIR = str(Path(__file__).resolve().parent)`
- Change `CONFIG_PATH = Path(__file__).parent.parent / "v59_config.json"` to `CONFIG_PATH = Path(__file__).parent / "v59_config.json"`

- [ ] **Step 3: Update __init__.py**

```python
from .strategy import ZScoreV59Strategy  # noqa: F401
```

- [ ] **Step 4: Run backtest**

```bash
.venv/bin/freqtrade backtesting --strategy ZScoreV59Strategy --timerange 20260117-20260517 --config user_data/strategies/v57_backtest_config.json --config user_data/strategies/v59_config.json -v 2>&1 | tail -40
```

Expected: Backtest runs with trades. Compare against V57 (291 trades, 88.3%, +176%) and V58 (179 trades, 89.9%, +173%).

- [ ] **Step 5: Commit**

```bash
git add -f user_data/strategies/zscore_v59/strategy.py user_data/strategies/zscore_v59/__init__.py user_data/strategies/ZScoreV59Strategy.py
git commit -m "feat(v59): always-on queue strategy with regime scoring"
```

---

### Task 3: Parameter sweep + comparison

**Files:** None (analysis only)

- [ ] **Step 1: Run V59 baseline**

```bash
.venv/bin/freqtrade backtesting --strategy ZScoreV59Strategy --timerange 20260117-20260517 --config user_data/strategies/v57_backtest_config.json --config user_data/strategies/v59_config.json -v 2>&1 | grep -E "STRATEGY SUMMARY" -A 5
```

- [ ] **Step 2: Sweep min_score and regime multipliers**

Test different min_score values (0.3, 0.35, 0.4, 0.45, 0.5) and regime multiplier strengths. Use the same sweep pattern from V58 optimization:

```bash
.venv/bin/python -c "
import json, subprocess, re, os
os.chdir('/Users/fvcoelho/Working/freqtrade')
BASE = 'user_data/strategies/v59_config.json'
EX = 'user_data/strategies/v57_backtest_config.json'
FT = '.venv/bin/freqtrade'

configs = [
    {'min_score': 0.30, 'label': 'ms30'},
    {'min_score': 0.35, 'label': 'ms35'},
    {'min_score': 0.40, 'label': 'ms40'},
    {'min_score': 0.45, 'label': 'ms45'},
    {'min_score': 0.50, 'label': 'ms50'},
]

for c in configs:
    with open(BASE) as f: data = json.load(f)
    data['queue']['min_score'] = c['min_score']
    tmp = f'/tmp/v59_{c[\"label\"]}.json'
    with open(tmp, 'w') as f: json.dump(data, f)
    out = subprocess.run([FT, 'backtesting', '--strategy', 'ZScoreV59Strategy',
        '--timerange', '20260117-20260517', '--config', EX, '--config', tmp],
        capture_output=True, text=True, timeout=300)
    for line in out.stdout.split('\n'):
        if 'ZScoreV59Strategy' in line and '│' in line:
            cells = [x.strip() for x in line.split('│')]
            if len(cells) >= 9:
                wm = re.search(r'(\d+(?:\.\d+)?)\s*$', cells[7])
                dm = re.search(r'(\d+(?:\.\d+)?)%', cells[8])
                print(f'{c[\"label\"]:6s} | trades={cells[2]:>4s} | win%={wm.group(1) if wm else \"?\":>5s} | profit={cells[5]:>8s} | dd={dm.group(1) if dm else \"?\"}%')
"
```

- [ ] **Step 3: Print comparison table**

Record V57, V58, V59 results side by side.
