# MicroRevert Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a 5m individual z-score mean reversion scalp strategy with penny+scale mechanics, 1-candle eval, and 18 expanded pairs.

**Architecture:** Modular strategy under `user_data/strategies/micro_revert/`. Reuses TwinPennies btc_trend and volume modules (copied). New zscore.py computes individual price-vs-EMA z-score. Strategy follows TwinPennies pattern: penny entry, 1-candle eval, z-confirmed scaling, z-reversion exit.

**Tech Stack:** Python 3.13, freqtrade IStrategy v3, pandas, numpy

---

### Task 1: Create module skeleton and config

**Files:**
- Create: `user_data/strategies/micro_revert/__init__.py`
- Create: `user_data/strategies/micro_revert/config.py`
- Create: `user_data/strategies/micro_revert_config.json`

- [ ] **Step 1: Create `__init__.py`**

```python
from .strategy import MicroRevertStrategy  # noqa: F401
```

- [ ] **Step 2: Create `config.py`** (copy from TwinPennies)

```python
"""Configuration loader for MicroRevert strategy."""
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

- [ ] **Step 3: Create `micro_revert_config.json`**

```json
{
    "timeframe": "5m",
    "startup_candle_count": 200,
    "pairs": [
        "BTC/USDC:USDC", "ETH/USDC:USDC", "SOL/USDC:USDC", "XRP/USDC:USDC",
        "DOGE/USDC:USDC", "SUI/USDC:USDC", "ONDO/USDC:USDC", "TON/USDC:USDC",
        "LINK/USDC:USDC", "ADA/USDC:USDC", "AVAX/USDC:USDC", "PEPE/USDC:USDC",
        "WIF/USDC:USDC", "HYPE/USDC:USDC", "AAVE/USDC:USDC", "OP/USDC:USDC",
        "ARB/USDC:USDC", "SEI/USDC:USDC"
    ],
    "btc_ref": "BTC/USDC:USDC",
    "zscore": {
        "ema_window": 30,
        "zscore_window": 30,
        "entry_z": 2.0,
        "exit_z": 0.1
    },
    "risk": {
        "stoploss": -0.99
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
    "twin": {
        "eval_candles": 1,
        "max_positions": 8,
        "initial_leverage": 3,
        "winner_exit_z": 0.1,
        "max_candles": 5,
        "loser_max_candles": 1,
        "safety_stop": -0.05,
        "min_winner_profit": 0.0001,
        "scale_stake": 100.0,
        "max_scale_times": 2,
        "z_revert_min": 0.3,
        "scale_min_profit": 0.0003
    }
}
```

- [ ] **Step 4: Commit**

```bash
git add user_data/strategies/micro_revert/__init__.py \
       user_data/strategies/micro_revert/config.py \
       user_data/strategies/micro_revert_config.json
git commit -m "feat(micro-revert): add module skeleton and config"
```

---

### Task 2: Copy btc_trend and volume modules

**Files:**
- Create: `user_data/strategies/micro_revert/btc_trend.py`
- Create: `user_data/strategies/micro_revert/volume.py`

These are direct copies from TwinPennies — identical logic, no changes needed.

- [ ] **Step 1: Copy `btc_trend.py`**

Copy the full file from `user_data/strategies/twin_pennies/btc_trend.py` to `user_data/strategies/micro_revert/btc_trend.py`. The file contains two functions:
- `compute(btc_df, cfg)` — computes BTC momentum, ATR z-score, pump/dump/chaos signals from 1h candles
- `map_to_timeframe(btc_state, dataframe)` — forward-fills 1h signals onto 5m pair dataframe

No modifications needed.

- [ ] **Step 2: Copy `volume.py`**

Copy the full file from `user_data/strategies/twin_pennies/volume.py` to `user_data/strategies/micro_revert/volume.py`. Contains one function:
- `compute(dataframe, cfg)` — adds `vol_ratio` and `vol_ok` columns using rolling volume MA

No modifications needed.

- [ ] **Step 3: Commit**

```bash
git add user_data/strategies/micro_revert/btc_trend.py \
       user_data/strategies/micro_revert/volume.py
git commit -m "feat(micro-revert): copy btc_trend and volume from TwinPennies"
```

---

### Task 3: Create individual z-score module

**Files:**
- Create: `user_data/strategies/micro_revert/zscore.py`

- [ ] **Step 1: Create `zscore.py`**

```python
"""Individual Z-Score — price deviation from its own EMA.

Unlike basket z-score which compares pairs against each other,
this computes how far each pair's price deviates from its own
exponential moving average. Fast-reacting signal suitable for
ultra-short scalps.

    ema = close.ewm(span=ema_window).mean()
    std = close.rolling(zscore_window).std()
    z = (close - ema) / std

    z << 0 -> price below its mean -> LONG (mean reversion up)
    z >> 0 -> price above its mean -> SHORT (mean reversion down)
"""
from __future__ import annotations

import numpy as np
from pandas import DataFrame


def compute(dataframe: DataFrame, cfg: dict) -> DataFrame:
    """Compute individual z-score for a single pair.

    Adds columns: ind_z, ind_ema, ind_std

    Config keys used from cfg["zscore"]:
        ema_window: int — EMA span for mean (default 30)
        zscore_window: int — rolling window for std (default 30)
    """
    c = cfg["zscore"]
    ema_window = c.get("ema_window", 30)
    zscore_window = c.get("zscore_window", 30)

    close = dataframe["close"]
    ema = close.ewm(span=ema_window, adjust=False).mean()
    std = close.rolling(window=zscore_window).std()

    z = ((close - ema) / std.replace(0, np.nan)).fillna(0.0)

    dataframe["ind_z"] = z
    dataframe["ind_ema"] = ema
    dataframe["ind_std"] = std

    return dataframe
```

- [ ] **Step 2: Verify the module loads**

```bash
cd /Users/fvcoelho/Working/freqtrade
python -c "
import pandas as pd, numpy as np
from user_data.strategies.micro_revert.zscore import compute
df = pd.DataFrame({'close': np.random.randn(100).cumsum() + 100})
df = compute(df, {'zscore': {'ema_window': 30, 'zscore_window': 30}})
print(df[['close','ind_z','ind_ema','ind_std']].tail(3))
print('OK - z range:', df['ind_z'].min(), 'to', df['ind_z'].max())
"
```

Expected: prints 3 rows with z-score values, no errors.

- [ ] **Step 3: Commit**

```bash
git add user_data/strategies/micro_revert/zscore.py
git commit -m "feat(micro-revert): add individual z-score module"
```

---

### Task 4: Create the strategy — init, data, and indicators

**Files:**
- Create: `user_data/strategies/micro_revert/strategy.py`

This task creates the first half of the strategy: class skeleton, `__init__`, data caching, `informative_pairs`, and `populate_indicators`.

- [ ] **Step 1: Create `strategy.py` with init and indicators**

```python
"""
MicroRevert — Individual Z-Score Mean Reversion Scalp
======================================================

Ultra-short mean reversion on 5m using individual z-score
(price vs its own EMA). Penny entry, 1-candle eval, z-confirmed
scaling, z-reversion exit.

Flow:
    1. Enter with tiered penny ($5-12) when |ind_z| > entry_z
    2. After 1 candle (5 min), classify winner/loser
    3. Losers: close immediately
    4. Winners: scale +$100 when z-delta confirms reversion
    5. Exit on z-reversion to ~0 or time stop (5 candles)
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

from micro_revert import btc_trend, volume, zscore, config as cfg_loader

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "micro_revert_config.json"

_trade_state: dict[int, dict] = {}


class MicroRevertStrategy(IStrategy):

    INTERFACE_VERSION = 3
    can_short = True
    process_only_new_candles = True
    timeframe = "5m"
    startup_candle_count = 200
    stoploss = -0.99
    minimal_roi = {"0": 10}
    trailing_stop = False
    use_custom_stoploss = True
    position_adjustment_enable = True
    max_entry_position_adjustment = 5

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        c = cfg_loader.load(CONFIG_PATH)
        self._cfg = c
        self.BTC_REF: str = c["btc_ref"]
        self.timeframe = c.get("timeframe", "5m")
        self.startup_candle_count = c.get("startup_candle_count", 200)
        self.stoploss = c["risk"]["stoploss"]

        self._df_cache: dict[str, DataFrame] = {}
        self._df_cache_cycle: int = 0
        self._btc_trend: dict = {}

        tc = c.get("twin", {})
        self._eval_candles = tc.get("eval_candles", 1)
        self._max_positions = tc.get("max_positions", 8)
        self._winner_exit_z = tc.get("winner_exit_z", 0.1)
        self._max_candles = tc.get("max_candles", 5)
        self._loser_max_candles = tc.get("loser_max_candles", 1)
        self._safety_stop = tc.get("safety_stop", -0.05)
        self._min_winner_profit = tc.get("min_winner_profit", 0.0001)

        self._scale_stake = tc.get("scale_stake", 100.0)
        self._z_revert_min = tc.get("z_revert_min", 0.3)
        self._scale_min_profit = tc.get("scale_min_profit", 0.0003)

        self._entry_z = c["zscore"]["entry_z"]
        self._exit_z = c["zscore"].get("exit_z", 0.1)

        global _trade_state
        _trade_state = {}

        logger.info(
            "MicroRevert — entry_z=%.1f, ema=%d, eval=%dc, max=%dc, "
            "scale=$%.0f, exit_z=%.2f, %d max_pos",
            self._entry_z, c["zscore"]["ema_window"],
            self._eval_candles, self._max_candles,
            self._scale_stake, self._exit_z, self._max_positions,
        )

    # ────────────────────────── Data ──────────────────────────

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
        btc_tf = self._cfg.get("btc_trend", {}).get("timeframe", "1h")
        return [(self.BTC_REF, btc_tf)]

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
        zscore.compute(dataframe, self._cfg)
        return dataframe
```

- [ ] **Step 2: Commit partial strategy**

```bash
git add user_data/strategies/micro_revert/strategy.py
git commit -m "feat(micro-revert): strategy init, data cache, indicators"
```

---

### Task 5: Add entry, exit trends, and helper methods

**Files:**
- Modify: `user_data/strategies/micro_revert/strategy.py`

Append the entry/exit trends, z-score helper, tiered stake, leverage, and trade state methods to the strategy class.

- [ ] **Step 1: Add entry/exit trends and helpers to strategy.py**

Append after `populate_indicators`:

```python
    # ────────────────────────── Entries ──────────────────────────

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe["enter_tag"] = ""

        if dataframe.empty or "ind_z" not in dataframe.columns:
            return dataframe

        vol_ok = dataframe.get("vol_ok", pd.Series(1, index=dataframe.index)) == 1
        no_chaos = ~dataframe.get("btc_high_vol", pd.Series(False, index=dataframe.index)).astype(bool)

        is_below = dataframe["ind_z"] < -self._entry_z
        safe_long = ~dataframe.get("btc_dump", pd.Series(False, index=dataframe.index)).astype(bool)
        mask_long = is_below & safe_long & no_chaos & vol_ok
        dataframe.loc[mask_long, ["enter_long", "enter_tag"]] = (1, "mr_long")

        is_above = dataframe["ind_z"] > self._entry_z
        safe_short = ~dataframe.get("btc_pump", pd.Series(False, index=dataframe.index)).astype(bool)
        mask_short = is_above & safe_short & no_chaos & vol_ok
        dataframe.loc[mask_short, ["enter_short", "enter_tag"]] = (1, "mr_short")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    # ────────────────────────── Helpers ──────────────────────────

    def _get_current_z(self, pair: str, current_time) -> float | None:
        if not self.dp:
            return None
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or df.empty or "ind_z" not in df.columns:
            return None
        ct = pd.Timestamp(current_time)
        if df["date"].dt.tz is not None:
            ct = ct.tz_localize("UTC") if ct.tz is None else ct.tz_convert("UTC")
        mask = df["date"] <= ct
        if not mask.any():
            return None
        return float(df["ind_z"].iloc[mask.sum() - 1])

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float,
                            rate: float, time_in_force: str, current_time: datetime,
                            entry_tag: Optional[str], side: str, **kwargs) -> bool:
        open_trades = Trade.get_trades_proxy(is_open=True)
        if len(open_trades) >= self._max_positions:
            return False
        if pair in {t.pair for t in open_trades}:
            return False
        return True

    # ────────────────────────── Tiered stake ──────────────────────────

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float],
                            max_stake: float, leverage: float, entry_tag: Optional[str],
                            side: str, **kwargs) -> float:
        if not self.dp:
            return min_stake or 5.0

        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or len(df) < 5 or "ind_z" not in df.columns:
            return min_stake or 5.0

        z_abs = abs(float(df["ind_z"].iloc[-1]))

        if z_abs >= 3.0:
            stake = 12.0
        elif z_abs >= 2.5:
            stake = 9.0
        elif z_abs >= 2.0:
            stake = 7.0
        else:
            stake = min_stake or 5.0

        stake = min(stake, max_stake * 0.3)
        if min_stake and stake < min_stake:
            stake = min_stake
        return stake

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float,
                 entry_tag: Optional[str], side: str, **kwargs) -> float:
        initial_lev = self._cfg.get("twin", {}).get("initial_leverage", 3)
        return float(max(1, min(initial_lev, int(max_leverage))))

    # ────────────────────────── Trade state ──────────────────────────

    def _get_ts(self, trade_id: int) -> dict:
        global _trade_state
        if trade_id not in _trade_state:
            _trade_state[trade_id] = {
                "evaluated": False,
                "is_winner": None,
                "scale_count": 0,
                "entry_z": None,
                "last_scale_z": None,
                "peak_profit": 0.0,
            }
        return _trade_state[trade_id]
```

- [ ] **Step 2: Commit**

```bash
git add user_data/strategies/micro_revert/strategy.py
git commit -m "feat(micro-revert): entry/exit trends, helpers, tiered stake"
```

---

### Task 6: Add scaling, stoploss, and exit logic

**Files:**
- Modify: `user_data/strategies/micro_revert/strategy.py`

Append adjust_trade_position, custom_stoploss, custom_exit, and confirm_trade_exit to the strategy class.

- [ ] **Step 1: Add scaling, stoploss, exit logic to strategy.py**

Append after `_get_ts`:

```python
    # ────────────────────────── Z-confirmed scaling ──────────────────────────

    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: Optional[float], max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs) -> Optional[float]:
        trade_age = (current_time - trade.open_date_utc).total_seconds() / 300
        ts = self._get_ts(trade.id)
        ts["peak_profit"] = max(ts["peak_profit"], current_profit)

        if ts["entry_z"] is None:
            z = self._get_current_z(trade.pair, current_time)
            if z is not None:
                ts["entry_z"] = z

        # Evaluate after eval_candles
        if not ts["evaluated"] and trade_age >= self._eval_candles:
            ts["evaluated"] = True
            ts["is_winner"] = current_profit >= self._min_winner_profit
            label = "W" if ts["is_winner"] else "L"
            logger.info(
                "EVAL %s %s[%s] profit=%.2f%% z_entry=%.3f @%.0fc",
                trade.pair, "S" if trade.is_short else "L", label,
                current_profit * 100, ts["entry_z"] or 0, trade_age,
            )

        # Progressive scaling for winners
        max_scales = self._cfg.get("twin", {}).get("max_scale_times", 2)
        if (ts["is_winner"]
                and ts["scale_count"] < max_scales
                and ts["entry_z"] is not None
                and current_profit >= self._scale_min_profit):

            current_z = self._get_current_z(trade.pair, current_time)
            if current_z is None:
                return None

            entry_z = ts["entry_z"]
            is_long = not trade.is_short

            if is_long:
                z_delta = current_z - entry_z
            else:
                z_delta = entry_z - current_z

            scale_n = ts["scale_count"]
            z_threshold = self._z_revert_min * (1.0 + scale_n * 0.8)

            if ts["last_scale_z"] is not None:
                if is_long:
                    z_since_last = current_z - ts["last_scale_z"]
                else:
                    z_since_last = ts["last_scale_z"] - current_z
                if z_since_last < self._z_revert_min * 0.3:
                    return None

            if z_delta >= z_threshold:
                ts["scale_count"] += 1
                ts["last_scale_z"] = current_z
                add = min(self._scale_stake, max_stake)
                if min_stake and add < min_stake:
                    add = min_stake
                logger.info(
                    "SCALE[%d/%d] %s | z: %.3f -> %.3f (delta=%.3f >= %.2f) | "
                    "profit=%.2f%% | +$%.2f",
                    ts["scale_count"], max_scales, trade.pair,
                    entry_z, current_z, z_delta, z_threshold,
                    current_profit * 100, add,
                )
                return add

        return None

    # ────────────────────────── Stoploss ──────────────────────────

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float,
                        after_fill: bool, **kwargs) -> float | None:
        return self._safety_stop

    # ────────────────────────── Exit ──────────────────────────

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        trade_age = (current_time - trade.open_date_utc).total_seconds() / 300
        ts = self._get_ts(trade.id)

        # Max loss
        if current_profit < self._safety_stop:
            return "mr_max_loss"

        # LOSER: close immediately after eval
        if ts["evaluated"] and not ts["is_winner"]:
            if trade_age >= self._loser_max_candles:
                return "mr_loser_close"

        # WINNER exits
        if ts["is_winner"]:
            z = self._get_current_z(pair, current_time)
            is_long = not trade.is_short

            # Z-reversion exit (primary profit engine)
            if z is not None and current_profit > 0.003:
                if is_long and z > -self._exit_z:
                    return "mr_winner_revert"
                if not is_long and z < self._exit_z:
                    return "mr_winner_revert"

        # Time stop
        if trade_age >= self._max_candles:
            return "mr_time_stop"

        return None

    def confirm_trade_exit(self, pair: str, trade: Trade, order_type: str,
                           amount: float, rate: float, time_in_force: str,
                           exit_reason: str, current_time: datetime, **kwargs) -> bool:
        ts = self._get_ts(trade.id)
        profit = trade.calc_profit_ratio(rate)
        label = "W" if ts.get("is_winner") else ("L" if ts.get("is_winner") is False else "?")
        sc = ts.get("scale_count", 0)
        scaled = f"+S{sc}" if sc > 0 else ""
        logger.info(
            "CLOSE %s %s[%s%s] profit=%.2f%% $%.2f lev=%.0fx | %s",
            pair, "S" if trade.is_short else "L", label, scaled,
            profit * 100, trade.stake_amount, trade.leverage, exit_reason,
        )
        return True
```

- [ ] **Step 2: Commit**

```bash
git add user_data/strategies/micro_revert/strategy.py
git commit -m "feat(micro-revert): scaling, stoploss, exit logic"
```

---

### Task 7: Create backtest config

**Files:**
- Create: `config_micro_revert_backtest_5m.json`

- [ ] **Step 1: Create backtest config**

```json
{
    "trading_mode": "futures",
    "margin_mode": "isolated",
    "max_open_trades": 8,
    "stake_currency": "USDC",
    "stake_amount": "unlimited",
    "tradable_balance_ratio": 0.99,
    "dry_run": true,
    "dry_run_wallet": 1000,
    "exchange": {
        "name": "hyperliquid",
        "key": "",
        "secret": "",
        "pair_whitelist": [
            "BTC/USDC:USDC",
            "ETH/USDC:USDC",
            "SOL/USDC:USDC",
            "XRP/USDC:USDC",
            "DOGE/USDC:USDC",
            "SUI/USDC:USDC",
            "ONDO/USDC:USDC",
            "TON/USDC:USDC",
            "LINK/USDC:USDC",
            "ADA/USDC:USDC",
            "AVAX/USDC:USDC",
            "PEPE/USDC:USDC",
            "WIF/USDC:USDC",
            "HYPE/USDC:USDC",
            "AAVE/USDC:USDC",
            "OP/USDC:USDC",
            "ARB/USDC:USDC",
            "SEI/USDC:USDC"
        ],
        "pair_blacklist": []
    },
    "entry_pricing": {
        "price_side": "same",
        "use_order_book": true,
        "order_book_top": 1
    },
    "exit_pricing": {
        "price_side": "same",
        "use_order_book": true,
        "order_book_top": 1
    },
    "dataformat_ohlcv": "feather",
    "pairlists": [
        {
            "method": "StaticPairList"
        }
    ]
}
```

- [ ] **Step 2: Commit**

```bash
git add config_micro_revert_backtest_5m.json
git commit -m "feat(micro-revert): backtest config with 18 pairs"
```

---

### Task 8: Download data for new pairs and run first backtest

**Files:** None (data download + validation)

- [ ] **Step 1: Check which pairs already have 5m data**

```bash
ls user_data/data/hyperliquid/
```

Look for existing feather files for the 18 pairs.

- [ ] **Step 2: Download missing pair data**

```bash
freqtrade download-data --config config_micro_revert_backtest_5m.json \
    --timerange 20260401-20260523 --timeframe 5m 1h
```

- [ ] **Step 3: Run first backtest (Apr 1 - May 18)**

```bash
freqtrade backtesting \
    --config config_micro_revert_backtest_5m.json \
    --strategy MicroRevertStrategy \
    --timerange 20260401-20260518
```

- [ ] **Step 4: Review results**

Check: total profit, drawdown, win rate, number of trades, exit reasons breakdown. Compare with TwinPennies V4 baseline (+$14.63, 1.15% DD, 99 trades).

- [ ] **Step 5: Commit any data/config adjustments**

```bash
git add -u
git commit -m "feat(micro-revert): first backtest results"
```
