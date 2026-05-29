# ZAP (ZScore Agent Pipeline) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a 4-agent pipeline strategy with FreqAI-driven entry ranking, two passive queues (LONG/SHORT), and ~50+ pre-computed features per pair across multiple timeframes.

**Architecture:** Modular strategy under `user_data/strategies/zap/`. Feature computation is split into 6 category modules. Four agents (Scanner, Regime, Entry, Manager) operate on passive LONG/SHORT queues. FreqAI LightGBMRegressor predicts forward returns, which become the queue ranking score. The strategy orchestrator (`strategy.py`) wires agents into freqtrade callbacks.

**Tech Stack:** Python 3.13, freqtrade, FreqAI, LightGBM, talib, numpy, pandas

---

## File Structure

```
user_data/strategies/zap/
├── __init__.py              # Package init, exports ZAPStrategy
├── strategy.py              # IStrategy subclass — orchestrates 4 agents via callbacks
├── config.py                # ZAP_CONFIG dict with all parameters
├── queues.py                # LONG/SHORT queue state + update/rank logic
├── features/
│   ├── __init__.py          # compute_all_features() dispatcher
│   ├── statistical.py       # z-score, half-life, hurst, cointegration, spread velocity
│   ├── momentum.py          # RSI, MACD, ADX, EMA slopes, ROC, StochRSI
│   ├── microstructure.py    # funding rate, OI delta, volume profile, CVD
│   ├── cross_pair.py        # spread z, rolling beta, lead-lag, relative strength
│   ├── volatility.py        # ATR, BB width, realized vol, Keltner, vol ratio
│   └── macro.py             # BTC trend, momentum, dominance, ADX, alt corr
├── agents/
│   ├── __init__.py
│   ├── scanner.py           # Calls features/, updates queues
│   ├── regime.py            # BTC trend analysis, regime state
│   ├── entry.py             # Reads queues + FreqAI predictions, generates signals
│   └── manager.py           # Exit logic, DCA, trailing, time stop
```

Config file: `user_data/strategies/zap_config.json`
Backtest config: `config_zap_backtest_5m.json`

---

### Task 1: Config and Package Skeleton

**Files:**
- Create: `user_data/strategies/zap/__init__.py`
- Create: `user_data/strategies/zap/config.py`
- Create: `user_data/strategies/zap_config.json`

- [ ] **Step 1: Create `config.py` with all ZAP parameters**

```python
"""ZAP Strategy configuration."""
from __future__ import annotations

import json
from pathlib import Path

ZAP_CONFIG = {
    "pairs_count": 20,
    "max_open_trades": 6,
    "leverage": {"min": 2, "max": 8},

    "scanner": {
        "zscore_window": 288,
        "half_life_max": 100,
        "correlation_window": 144,
        "hurst_window": 100,
    },

    "regime": {
        "adx_ranging": 18,
        "adx_trending": 25,
        "btc_momentum_window": 48,
        "btc_dump_threshold": -1.0,
        "btc_pump_threshold": 1.0,
    },

    "entry": {
        "top_k": 3,
        "min_predicted_return": 0.005,
        "cooldown_candles": 36,
        "regime_multipliers": {
            "bull_long": 1.0, "bull_short": 0.3,
            "bear_long": 0.3, "bear_short": 1.0,
            "ranging_long": 0.5, "ranging_short": 0.5,
        },
    },

    "manager": {
        "stoploss": -0.10,
        "trailing_activate": 0.02,
        "trailing_offset": 0.005,
        "time_stop_candles": 48,
        "dca_threshold": -0.03,
        "dca_min_predicted": 0.008,
        "dca_multipliers": [1.5, 2.5],
    },
}


def load_config(path: Path | None = None) -> dict:
    """Load ZAP config from JSON, falling back to defaults."""
    cfg = ZAP_CONFIG.copy()
    if path and path.exists():
        with open(path) as f:
            overrides = json.load(f).get("zap", {})
        for section, values in overrides.items():
            if isinstance(values, dict) and section in cfg:
                cfg[section].update(values)
            else:
                cfg[section] = values
    return cfg
```

- [ ] **Step 2: Create `__init__.py`**

```python
"""ZAP — ZScore Agent Pipeline Strategy."""
from user_data.strategies.zap.strategy import ZAPStrategy  # noqa: F401
```

Note: This import will fail until `strategy.py` exists — that's expected. We'll create it in Task 8.

- [ ] **Step 3: Create `zap_config.json` with strategy-specific overrides**

```json
{
    "zap": {
        "pairs_count": 20,
        "max_open_trades": 6,
        "leverage": {"min": 2, "max": 8},
        "entry": {
            "top_k": 3,
            "min_predicted_return": 0.005
        }
    }
}
```

- [ ] **Step 4: Commit**

```bash
git add user_data/strategies/zap/__init__.py user_data/strategies/zap/config.py user_data/strategies/zap_config.json
git commit -m "feat(zap): add config and package skeleton"
```

---

### Task 2: Statistical Features Module

**Files:**
- Create: `user_data/strategies/zap/features/__init__.py`
- Create: `user_data/strategies/zap/features/statistical.py`

- [ ] **Step 1: Create `features/__init__.py` dispatcher**

```python
"""Feature computation dispatcher."""
from __future__ import annotations

from pandas import DataFrame

from user_data.strategies.zap.features.statistical import compute as compute_statistical
from user_data.strategies.zap.features.momentum import compute as compute_momentum
from user_data.strategies.zap.features.microstructure import compute as compute_microstructure
from user_data.strategies.zap.features.cross_pair import compute as compute_cross_pair
from user_data.strategies.zap.features.volatility import compute as compute_volatility
from user_data.strategies.zap.features.macro import compute as compute_macro


def compute_all_features(
    df: DataFrame,
    pair: str,
    cfg: dict,
    dp=None,
    all_pairs: list[str] | None = None,
    btc_df: DataFrame | None = None,
    df_cache: dict | None = None,
) -> DataFrame:
    """Compute all ~46 features for a single pair. Adds %-prefixed columns."""
    df_cache = df_cache or {}
    all_pairs = all_pairs or []

    df = compute_statistical(df, pair, cfg, dp, all_pairs, df_cache)
    df = compute_momentum(df, cfg)
    df = compute_microstructure(df, cfg)
    df = compute_cross_pair(df, pair, cfg, dp, all_pairs, df_cache)
    df = compute_volatility(df, cfg)
    df = compute_macro(df, btc_df, cfg)

    return df
```

Note: This will fail to import until all feature modules exist — we create them in Tasks 2-7. That's expected.

- [ ] **Step 2: Create `statistical.py` with 10 features**

```python
"""Statistical features: z-score, half-life, hurst, cointegration, spread."""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from pandas import DataFrame

logger = logging.getLogger(__name__)

# Module-level cache for basket average (shared across pairs in a cycle)
_basket_cache: dict = {}


def reset_cache():
    global _basket_cache
    _basket_cache = {}


def _compute_basket_avg(
    all_pairs: list[str],
    n: int,
    timeframe: str,
    dp,
    df_cache: dict,
    window: int,
) -> np.ndarray | None:
    """Compute basket average of normalized log prices. Cached per cycle."""
    cache_key = f"basket_avg_{n}"
    if cache_key in _basket_cache:
        return _basket_cache[cache_key]

    log_prices = []
    for p in all_pairs:
        key = f"{p}__{timeframe}"
        if key in df_cache:
            other_df = df_cache[key]
        elif dp is not None:
            other_df = dp.get_pair_dataframe(pair=p, timeframe=timeframe)
            if other_df is not None and len(other_df) > 0:
                df_cache[key] = other_df
            else:
                continue
        else:
            continue

        close = other_df["close"].values
        if len(close) < window:
            continue
        log_p = np.log(close[-n:])
        log_p = log_p - log_p[0]  # normalize to start at 0
        log_prices.append(log_p)

    if len(log_prices) < 2:
        return None

    min_len = min(len(lp) for lp in log_prices)
    aligned = np.array([lp[-min_len:] for lp in log_prices])
    avg = aligned.mean(axis=0)

    _basket_cache[cache_key] = avg
    return avg


def _hurst_exponent(series: np.ndarray, max_lag: int = 20) -> float:
    """Compute Hurst exponent via R/S analysis."""
    if len(series) < max_lag * 2:
        return 0.5
    lags = range(2, min(max_lag, len(series) // 2))
    tau = []
    for lag in lags:
        chunks = [series[i:i+lag] for i in range(0, len(series) - lag, lag)]
        if len(chunks) < 2:
            continue
        rs_values = []
        for chunk in chunks:
            if len(chunk) < 2:
                continue
            mean_c = np.mean(chunk)
            dev = chunk - mean_c
            cumdev = np.cumsum(dev)
            r = np.max(cumdev) - np.min(cumdev)
            s = np.std(chunk, ddof=1)
            if s > 0:
                rs_values.append(r / s)
        if rs_values:
            tau.append((lag, np.mean(rs_values)))
    if len(tau) < 3:
        return 0.5
    lags_arr = np.log([t[0] for t in tau])
    rs_arr = np.log([t[1] for t in tau])
    coeffs = np.polyfit(lags_arr, rs_arr, 1)
    return float(np.clip(coeffs[0], 0, 1))


def _half_life(spread: pd.Series) -> float:
    """Compute half-life of mean reversion via OLS on lagged spread."""
    spread_lag = spread.shift(1).dropna()
    spread_diff = spread.diff().dropna()
    n = min(len(spread_lag), len(spread_diff))
    if n < 10:
        return 100.0
    y = spread_diff.values[-n:]
    x = spread_lag.values[-n:]
    x = x - x.mean()
    beta = np.dot(x, y) / (np.dot(x, x) + 1e-10)
    if beta >= 0:
        return 100.0
    hl = -np.log(2) / beta
    return float(np.clip(hl, 1, 200))


def compute(
    df: DataFrame,
    pair: str,
    cfg: dict,
    dp=None,
    all_pairs: list[str] | None = None,
    df_cache: dict | None = None,
) -> DataFrame:
    """Add statistical features to dataframe. All prefixed with %-."""
    all_pairs = all_pairs or []
    df_cache = df_cache or {}
    scfg = cfg.get("scanner", {})
    window = scfg.get("zscore_window", 288)

    n = len(df)
    close = df["close"].values
    log_close = np.log(close + 1e-10)
    log_norm = log_close - log_close[0]

    # 1. Basket z-score (SMA)
    basket_avg = _compute_basket_avg(
        all_pairs, n, "5m", dp, df_cache, window
    )
    if basket_avg is not None and len(basket_avg) == n:
        spread = log_norm - basket_avg
        spread_series = pd.Series(spread)
        roll_mean = spread_series.rolling(window, min_periods=20).mean()
        roll_std = spread_series.rolling(window, min_periods=20).std()
        df["%-zscore"] = ((spread_series - roll_mean) / (roll_std + 1e-10)).values

        # 2. Spread velocity
        df["%-spread_velocity"] = spread_series.diff(5).values

        # 3. Spread acceleration
        df["%-spread_accel"] = spread_series.diff(5).diff(5).values

        # 4. Half-life
        hl = _half_life(spread_series.iloc[-window:])
        df["%-half_life"] = hl

        # 5. Hurst exponent
        hurst = _hurst_exponent(spread[-min(window, n):])
        df["%-hurst"] = hurst

        # 6. Cointegration score (simplified: correlation of levels)
        if len(basket_avg) >= window:
            corr = np.corrcoef(log_norm[-window:], basket_avg[-window:])[0, 1]
            df["%-coint_score"] = corr if not np.isnan(corr) else 0.0
        else:
            df["%-coint_score"] = 0.0

        # 7. EWM z-score
        ewm_mean = spread_series.ewm(span=window, min_periods=20).mean()
        ewm_std = spread_series.ewm(span=window, min_periods=20).std()
        df["%-zscore_ewm"] = ((spread_series - ewm_mean) / (ewm_std + 1e-10)).values

        # 8. Log spread raw
        df["%-log_spread"] = spread

        # 9. Kalman filtered z-score
        kalman_gain = 0.05
        kalman_est = np.zeros(n)
        kalman_est[0] = spread[0]
        for i in range(1, n):
            kalman_est[i] = kalman_est[i-1] + kalman_gain * (spread[i] - kalman_est[i-1])
        kalman_resid = spread - kalman_est
        k_std = pd.Series(kalman_resid).rolling(window, min_periods=20).std().values
        df["%-zscore_kalman"] = kalman_resid / (k_std + 1e-10)

        # 10. Cumulative returns z-score
        cum_ret = df["close"].pct_change().cumsum()
        cr_mean = cum_ret.rolling(window, min_periods=20).mean()
        cr_std = cum_ret.rolling(window, min_periods=20).std()
        df["%-zscore_cumret"] = ((cum_ret - cr_mean) / (cr_std + 1e-10)).values
    else:
        # No basket data — fill with zeros
        for col in [
            "%-zscore", "%-spread_velocity", "%-spread_accel",
            "%-half_life", "%-hurst", "%-coint_score",
            "%-zscore_ewm", "%-log_spread", "%-zscore_kalman",
            "%-zscore_cumret",
        ]:
            df[col] = 0.0

    return df
```

- [ ] **Step 3: Test by importing and running on sample data**

```bash
cd /Users/fvcoelho/Working/freqtrade && source .venv/bin/activate
python -c "
import pandas as pd, numpy as np
from user_data.strategies.zap.features.statistical import compute
df = pd.DataFrame({'close': np.random.uniform(100, 110, 300), 'volume': np.random.uniform(1000, 5000, 300)})
result = compute(df, 'TEST/USDT', {'scanner': {'zscore_window': 50}})
print('Statistical features:', [c for c in result.columns if c.startswith('%-')])
print('Shape:', result.shape)
"
```

Expected: prints 10 `%-` prefixed columns, shape (300, 12+).

- [ ] **Step 4: Commit**

```bash
git add -f user_data/strategies/zap/features/__init__.py user_data/strategies/zap/features/statistical.py
git commit -m "feat(zap): add statistical features module (10 features)"
```

---

### Task 3: Momentum Features Module

**Files:**
- Create: `user_data/strategies/zap/features/momentum.py`

- [ ] **Step 1: Create `momentum.py` with 8 features**

```python
"""Momentum features: RSI, MACD, ADX, EMA slopes, ROC, StochRSI."""
from __future__ import annotations

import numpy as np
import talib.abstract as ta
from pandas import DataFrame


def compute(df: DataFrame, cfg: dict) -> DataFrame:
    """Add momentum features to dataframe. All prefixed with %-."""

    # 1. RSI (14)
    df["%-rsi"] = ta.RSI(df, timeperiod=14)

    # 2-3. MACD signal + histogram
    macd, macd_signal, macd_hist = ta.MACD(
        df, fastperiod=12, slowperiod=26, signalperiod=9
    )
    df["%-macd_signal"] = macd_signal
    df["%-macd_hist"] = macd_hist

    # 4. ADX (14)
    df["%-adx"] = ta.ADX(df, timeperiod=14)

    # 5-7. EMA slopes (8, 21, 55)
    for period in [8, 21, 55]:
        ema = ta.EMA(df, timeperiod=period)
        df[f"%-ema_slope_{period}"] = ema.pct_change(3) * 100  # slope as pct

    # 8. Rate of change (12)
    df["%-roc"] = ta.ROC(df, timeperiod=12)

    return df
```

- [ ] **Step 2: Test import**

```bash
python -c "
import pandas as pd, numpy as np
from user_data.strategies.zap.features.momentum import compute
n = 300
df = pd.DataFrame({
    'open': np.random.uniform(100, 110, n),
    'high': np.random.uniform(105, 115, n),
    'low': np.random.uniform(95, 105, n),
    'close': np.random.uniform(100, 110, n),
    'volume': np.random.uniform(1000, 5000, n),
})
result = compute(df, {})
print('Momentum features:', [c for c in result.columns if c.startswith('%-')])
"
```

Expected: 8 `%-` prefixed columns.

- [ ] **Step 3: Commit**

```bash
git add -f user_data/strategies/zap/features/momentum.py
git commit -m "feat(zap): add momentum features module (8 features)"
```

---

### Task 4: Microstructure Features Module

**Files:**
- Create: `user_data/strategies/zap/features/microstructure.py`

- [ ] **Step 1: Create `microstructure.py` with 6 features**

```python
"""Microstructure features: funding rate, OI, volume profile, CVD."""
from __future__ import annotations

import numpy as np
from pandas import DataFrame


def compute(df: DataFrame, cfg: dict) -> DataFrame:
    """Add microstructure features. All prefixed with %-.

    Note: funding_rate and open_interest columns may not be available
    in all data sources. Features default to 0.0 if missing.
    """
    # 1. Funding rate (if available from exchange data)
    if "funding_rate" in df.columns:
        df["%-funding_rate"] = df["funding_rate"]
        # 2. Funding rate delta
        df["%-funding_delta"] = df["funding_rate"].diff(3)
    else:
        df["%-funding_rate"] = 0.0
        df["%-funding_delta"] = 0.0

    # 3. Open interest delta (if available)
    if "open_interest" in df.columns:
        df["%-oi_delta"] = df["open_interest"].pct_change(6)
    else:
        df["%-oi_delta"] = 0.0

    # 4. VWAP deviation (intra-session proxy)
    typical = (df["high"] + df["low"] + df["close"]) / 3
    cum_tp_vol = (typical * df["volume"]).rolling(48, min_periods=1).sum()
    cum_vol = df["volume"].rolling(48, min_periods=1).sum()
    vwap = cum_tp_vol / (cum_vol + 1e-10)
    df["%-vwap_dev"] = (df["close"] - vwap) / (vwap + 1e-10) * 100

    # 5. CVD (cumulative volume delta) — approximated from candle direction
    direction = np.where(df["close"] >= df["open"], 1.0, -1.0)
    vol_delta = df["volume"].values * direction
    df["%-cvd"] = np.cumsum(vol_delta)
    # Normalize CVD as z-score over rolling window
    cvd_series = df["%-cvd"]
    cvd_mean = cvd_series.rolling(144, min_periods=20).mean()
    cvd_std = cvd_series.rolling(144, min_periods=20).std()
    df["%-cvd"] = ((cvd_series - cvd_mean) / (cvd_std + 1e-10)).values

    # 6. Volume ratio (current vs rolling average)
    vol_avg = df["volume"].rolling(48, min_periods=1).mean()
    df["%-vol_ratio"] = df["volume"] / (vol_avg + 1e-10)

    return df
```

- [ ] **Step 2: Test import**

```bash
python -c "
import pandas as pd, numpy as np
from user_data.strategies.zap.features.microstructure import compute
n = 300
df = pd.DataFrame({
    'open': np.random.uniform(100, 110, n),
    'high': np.random.uniform(105, 115, n),
    'low': np.random.uniform(95, 105, n),
    'close': np.random.uniform(100, 110, n),
    'volume': np.random.uniform(1000, 5000, n),
})
result = compute(df, {})
print('Micro features:', [c for c in result.columns if c.startswith('%-')])
"
```

Expected: 6 `%-` prefixed columns.

- [ ] **Step 3: Commit**

```bash
git add -f user_data/strategies/zap/features/microstructure.py
git commit -m "feat(zap): add microstructure features module (6 features)"
```

---

### Task 5: Cross-pair Features Module

**Files:**
- Create: `user_data/strategies/zap/features/cross_pair.py`

- [ ] **Step 1: Create `cross_pair.py` with 8 features**

```python
"""Cross-pair features: spread z, beta, lead-lag, relative strength."""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from pandas import DataFrame

logger = logging.getLogger(__name__)


def _rolling_beta(pair_ret: np.ndarray, ref_ret: np.ndarray, window: int) -> np.ndarray:
    """Compute rolling beta of pair returns vs reference returns."""
    beta = np.full(len(pair_ret), np.nan)
    for i in range(window, len(pair_ret)):
        x = ref_ret[i-window:i]
        y = pair_ret[i-window:i]
        cov = np.cov(x, y)
        if cov.shape == (2, 2) and cov[0, 0] > 1e-10:
            beta[i] = cov[0, 1] / cov[0, 0]
        else:
            beta[i] = 0.0
    return np.nan_to_num(beta, nan=0.0)


def _lead_lag_score(pair_ret: np.ndarray, ref_ret: np.ndarray, max_lag: int = 6) -> float:
    """Compute lead-lag score: max cross-correlation at lags 1..max_lag."""
    if len(pair_ret) < max_lag * 2:
        return 0.0
    best_corr = 0.0
    for lag in range(1, max_lag + 1):
        if len(ref_ret) > lag:
            corr = np.corrcoef(ref_ret[:-lag], pair_ret[lag:])[0, 1]
            if not np.isnan(corr) and abs(corr) > abs(best_corr):
                best_corr = corr
    return float(best_corr)


def compute(
    df: DataFrame,
    pair: str,
    cfg: dict,
    dp=None,
    all_pairs: list[str] | None = None,
    df_cache: dict | None = None,
) -> DataFrame:
    """Add cross-pair features. All prefixed with %-."""
    all_pairs = all_pairs or []
    df_cache = df_cache or {}
    scfg = cfg.get("scanner", {})
    corr_window = scfg.get("correlation_window", 144)

    pair_ret = df["close"].pct_change().fillna(0).values
    n = len(df)

    # Load BTC and ETH returns for beta/lead-lag
    btc_ret = np.zeros(n)
    eth_ret = np.zeros(n)
    for ref_pair, target in [("BTC/USDT:USDT", btc_ret), ("ETH/USDT:USDT", eth_ret)]:
        key = f"{ref_pair}__5m"
        ref_df = df_cache.get(key)
        if ref_df is None and dp is not None:
            ref_df = dp.get_pair_dataframe(pair=ref_pair, timeframe="5m")
            if ref_df is not None and len(ref_df) > 0:
                df_cache[key] = ref_df
        if ref_df is not None and len(ref_df) >= n:
            target[:] = ref_df["close"].pct_change().fillna(0).values[-n:]

    # 1. Rolling beta vs BTC
    df["%-beta_btc"] = _rolling_beta(pair_ret, btc_ret, corr_window)

    # 2. Rolling beta vs ETH
    df["%-beta_eth"] = _rolling_beta(pair_ret, eth_ret, corr_window)

    # 3. Lead-lag score vs BTC (scalar, broadcast)
    ll_btc = _lead_lag_score(pair_ret[-corr_window:], btc_ret[-corr_window:])
    df["%-lead_lag_btc"] = ll_btc

    # 4. Relative strength vs basket
    basket_rets = []
    for p in all_pairs:
        if p == pair:
            continue
        key = f"{p}__5m"
        other_df = df_cache.get(key)
        if other_df is None and dp is not None:
            other_df = dp.get_pair_dataframe(pair=p, timeframe="5m")
            if other_df is not None and len(other_df) > 0:
                df_cache[key] = other_df
        if other_df is not None and len(other_df) >= n:
            basket_rets.append(other_df["close"].pct_change().fillna(0).values[-n:])

    if basket_rets:
        basket_avg_ret = np.mean(basket_rets, axis=0)
        # 4. Relative strength
        cum_pair = np.cumsum(pair_ret)
        cum_basket = np.cumsum(basket_avg_ret)
        df["%-rel_strength"] = cum_pair - cum_basket

        # 5. Pair correlation matrix rank (avg corr with all others)
        corrs = []
        for br in basket_rets:
            if len(br) >= corr_window:
                c = np.corrcoef(pair_ret[-corr_window:], br[-corr_window:])[0, 1]
                if not np.isnan(c):
                    corrs.append(c)
        df["%-corr_rank"] = np.mean(corrs) if corrs else 0.0

        # 6. Spread velocity rank (how fast pair diverges from basket)
        spread = cum_pair - cum_basket
        spread_vel = np.diff(spread, prepend=spread[0])
        df["%-spread_vel_rank"] = pd.Series(spread_vel).rolling(
            12, min_periods=1
        ).mean().values

        # 7. Mean spread divergence
        spread_z = pd.Series(spread)
        sp_mean = spread_z.rolling(corr_window, min_periods=20).mean()
        sp_std = spread_z.rolling(corr_window, min_periods=20).std()
        df["%-spread_div"] = ((spread_z - sp_mean) / (sp_std + 1e-10)).values
    else:
        df["%-rel_strength"] = 0.0
        df["%-corr_rank"] = 0.0
        df["%-spread_vel_rank"] = 0.0
        df["%-spread_div"] = 0.0

    # 8. Pair return momentum (12-candle rolling return)
    df["%-pair_momentum"] = pd.Series(pair_ret).rolling(12, min_periods=1).sum().values

    return df
```

- [ ] **Step 2: Test import**

```bash
python -c "
import pandas as pd, numpy as np
from user_data.strategies.zap.features.cross_pair import compute
n = 300
df = pd.DataFrame({
    'open': np.random.uniform(100, 110, n),
    'high': np.random.uniform(105, 115, n),
    'low': np.random.uniform(95, 105, n),
    'close': np.random.uniform(100, 110, n),
    'volume': np.random.uniform(1000, 5000, n),
})
result = compute(df, 'TEST/USDT', {'scanner': {'correlation_window': 50}})
print('Cross-pair features:', [c for c in result.columns if c.startswith('%-')])
"
```

Expected: 8 `%-` prefixed columns.

- [ ] **Step 3: Commit**

```bash
git add -f user_data/strategies/zap/features/cross_pair.py
git commit -m "feat(zap): add cross-pair features module (8 features)"
```

---

### Task 6: Volatility Features Module

**Files:**
- Create: `user_data/strategies/zap/features/volatility.py`

- [ ] **Step 1: Create `volatility.py` with 8 features**

```python
"""Volatility features: ATR, BB width, realized vol, Keltner, vol ratio."""
from __future__ import annotations

import numpy as np
import talib.abstract as ta
from pandas import DataFrame
from technical import qtpylib


def compute(df: DataFrame, cfg: dict) -> DataFrame:
    """Add volatility features. All prefixed with %-."""

    # 1. ATR (14)
    df["%-atr"] = ta.ATR(df, timeperiod=14)

    # 2. Bollinger Band width
    bb = qtpylib.bollinger_bands(
        qtpylib.typical_price(df), window=20, stds=2.0
    )
    bb_width = (bb["upper"] - bb["lower"]) / (bb["mid"] + 1e-10)
    df["%-bb_width"] = bb_width

    # 3. Realized volatility (close-close, 20-period)
    log_ret = np.log(df["close"] / df["close"].shift(1))
    df["%-realized_vol"] = log_ret.rolling(20, min_periods=5).std() * np.sqrt(288)

    # 4. Volume-weighted volatility
    vol_weight = df["volume"] / (df["volume"].rolling(20, min_periods=1).mean() + 1e-10)
    df["%-vol_weighted_vol"] = (log_ret.abs() * vol_weight).rolling(
        20, min_periods=5
    ).mean()

    # 5. Keltner Channel squeeze (BB inside Keltner = 1, else 0)
    atr = df["%-atr"]
    ema20 = ta.EMA(df, timeperiod=20)
    kc_upper = ema20 + 1.5 * atr
    kc_lower = ema20 - 1.5 * atr
    df["%-keltner_squeeze"] = (
        (bb["lower"] > kc_lower) & (bb["upper"] < kc_upper)
    ).astype(float)

    # 6. Volatility ratio (short/long ATR)
    atr_short = ta.ATR(df, timeperiod=7)
    atr_long = ta.ATR(df, timeperiod=28)
    df["%-vol_ratio_sl"] = atr_short / (atr_long + 1e-10)

    # 7. Parkinson volatility (high-low based)
    hl_ratio = np.log(df["high"] / (df["low"] + 1e-10))
    df["%-parkinson_vol"] = (
        hl_ratio.pow(2).rolling(20, min_periods=5).mean() / (4 * np.log(2))
    ).pow(0.5)

    # 8. ATR percentile rank (current ATR vs 288-candle history)
    atr_series = df["%-atr"]
    df["%-atr_pctile"] = atr_series.rolling(288, min_periods=20).apply(
        lambda x: (x.iloc[-1] <= x).mean() if len(x) > 0 else 0.5,
        raw=False,
    )

    return df
```

- [ ] **Step 2: Test import**

```bash
python -c "
import pandas as pd, numpy as np
from user_data.strategies.zap.features.volatility import compute
n = 300
df = pd.DataFrame({
    'open': np.random.uniform(100, 110, n),
    'high': np.random.uniform(105, 115, n),
    'low': np.random.uniform(95, 105, n),
    'close': np.random.uniform(100, 110, n),
    'volume': np.random.uniform(1000, 5000, n),
})
result = compute(df, {})
print('Volatility features:', [c for c in result.columns if c.startswith('%-')])
"
```

Expected: 8 `%-` prefixed columns.

- [ ] **Step 3: Commit**

```bash
git add -f user_data/strategies/zap/features/volatility.py
git commit -m "feat(zap): add volatility features module (8 features)"
```

---

### Task 7: Macro Features Module

**Files:**
- Create: `user_data/strategies/zap/features/macro.py`

- [ ] **Step 1: Create `macro.py` with 6 features**

```python
"""Macro features: BTC trend, momentum, dominance, alt correlation."""
from __future__ import annotations

import numpy as np
import talib.abstract as ta
from pandas import DataFrame


def compute(df: DataFrame, btc_df: DataFrame | None, cfg: dict) -> DataFrame:
    """Add macro features. All prefixed with %-.

    These features are derived from BTC data and broadcast to all pairs.
    btc_df should be the BTC/USDT dataframe aligned or longer than df.
    """
    rcfg = cfg.get("regime", {})
    mom_window = rcfg.get("btc_momentum_window", 48)

    if btc_df is not None and len(btc_df) >= len(df):
        btc_close = btc_df["close"].values[-len(df):]
        btc_series = DataFrame({
            "open": btc_df["open"].values[-len(df):],
            "high": btc_df["high"].values[-len(df):],
            "low": btc_df["low"].values[-len(df):],
            "close": btc_close,
            "volume": btc_df["volume"].values[-len(df):],
        })

        # 1. BTC trend direction (EMA21 slope sign: +1, 0, -1)
        btc_ema = ta.EMA(btc_series, timeperiod=21)
        btc_slope = btc_ema.pct_change(3)
        df["%-btc_trend"] = np.sign(btc_slope.fillna(0)).values

        # 2. BTC momentum (ROC)
        df["%-btc_momentum"] = ta.ROC(btc_series, timeperiod=mom_window).values

        # 3. BTC ADX
        df["%-btc_adx"] = ta.ADX(btc_series, timeperiod=14).values

        # 4. BTC dominance delta (approximated as BTC strength vs pair)
        btc_ret = np.diff(np.log(btc_close + 1e-10), prepend=0)
        pair_ret = np.diff(np.log(df["close"].values + 1e-10), prepend=0)
        dom_delta = btc_ret - pair_ret
        df["%-btc_dom_delta"] = (
            DataFrame({"d": dom_delta})["d"]
            .rolling(mom_window, min_periods=5).mean().values
        )

        # 5. Total market volatility index (BTC ATR normalized)
        btc_atr = ta.ATR(btc_series, timeperiod=14)
        btc_atr_norm = btc_atr / (btc_series["close"] + 1e-10) * 100
        df["%-mkt_vol_index"] = btc_atr_norm.values

        # 6. Altcoin correlation mean (pair vs BTC rolling corr)
        pair_rets = df["close"].pct_change().fillna(0).values
        btc_rets = np.diff(btc_close, prepend=btc_close[0]) / (btc_close + 1e-10)
        corr_window = rcfg.get("btc_momentum_window", 48)
        rolling_corr = np.full(len(df), 0.0)
        for i in range(corr_window, len(df)):
            c = np.corrcoef(
                pair_rets[i-corr_window:i],
                btc_rets[i-corr_window:i],
            )[0, 1]
            rolling_corr[i] = c if not np.isnan(c) else 0.0
        df["%-alt_corr_btc"] = rolling_corr
    else:
        # No BTC data available
        df["%-btc_trend"] = 0.0
        df["%-btc_momentum"] = 0.0
        df["%-btc_adx"] = 0.0
        df["%-btc_dom_delta"] = 0.0
        df["%-mkt_vol_index"] = 0.0
        df["%-alt_corr_btc"] = 0.0

    return df
```

- [ ] **Step 2: Test import**

```bash
python -c "
import pandas as pd, numpy as np
from user_data.strategies.zap.features.macro import compute
n = 300
df = pd.DataFrame({
    'open': np.random.uniform(100, 110, n),
    'high': np.random.uniform(105, 115, n),
    'low': np.random.uniform(95, 105, n),
    'close': np.random.uniform(100, 110, n),
    'volume': np.random.uniform(1000, 5000, n),
})
btc_df = pd.DataFrame({
    'open': np.random.uniform(60000, 65000, n),
    'high': np.random.uniform(62000, 67000, n),
    'low': np.random.uniform(58000, 63000, n),
    'close': np.random.uniform(60000, 65000, n),
    'volume': np.random.uniform(100, 500, n),
})
result = compute(df, btc_df, {'regime': {'btc_momentum_window': 24}})
print('Macro features:', [c for c in result.columns if c.startswith('%-')])
"
```

Expected: 6 `%-` prefixed columns.

- [ ] **Step 3: Commit**

```bash
git add -f user_data/strategies/zap/features/macro.py
git commit -m "feat(zap): add macro features module (6 features)"
```

---

### Task 8: Queue System

**Files:**
- Create: `user_data/strategies/zap/queues.py`

- [ ] **Step 1: Create `queues.py` with LONG/SHORT queue logic**

```python
"""Passive LONG/SHORT queues with feature storage and ranking."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PairEntry:
    """Single pair entry in a queue."""
    pair: str
    features: dict[str, float] = field(default_factory=dict)
    predicted_return: float = 0.0
    regime_adjusted_score: float = 0.0
    rank: int = 0
    last_updated: int = 0  # candle index
    cooldown_until: int = 0  # candle index


class QueueManager:
    """Manages LONG and SHORT queues for all pairs.

    Queues are passive — they store features and scores but don't decide.
    The Entry agent reads queues and makes decisions.
    """

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.long_queue: dict[str, PairEntry] = {}
        self.short_queue: dict[str, PairEntry] = {}
        self._cooldown_candles = cfg.get("entry", {}).get("cooldown_candles", 36)

    def reset(self):
        self.long_queue.clear()
        self.short_queue.clear()

    def update_pair(
        self,
        pair: str,
        features: dict[str, float],
        predicted_return: float,
        regime_multiplier: float,
        candle_idx: int,
    ):
        """Update a pair's features and score in the appropriate queue.

        Positive predicted_return -> LONG queue
        Negative predicted_return -> SHORT queue
        """
        entry = PairEntry(
            pair=pair,
            features=features,
            predicted_return=predicted_return,
            regime_adjusted_score=predicted_return * regime_multiplier,
            last_updated=candle_idx,
        )

        # Check cooldown
        old_long = self.long_queue.get(pair)
        old_short = self.short_queue.get(pair)
        if old_long and old_long.cooldown_until > candle_idx:
            entry.cooldown_until = old_long.cooldown_until
        elif old_short and old_short.cooldown_until > candle_idx:
            entry.cooldown_until = old_short.cooldown_until

        # Place in appropriate queue, remove from other
        if predicted_return >= 0:
            self.long_queue[pair] = entry
            self.short_queue.pop(pair, None)
        else:
            self.short_queue[pair] = entry
            self.long_queue.pop(pair, None)

    def set_cooldown(self, pair: str, candle_idx: int):
        """Set cooldown for a pair after a trade closes."""
        until = candle_idx + self._cooldown_candles
        if pair in self.long_queue:
            self.long_queue[pair].cooldown_until = until
        if pair in self.short_queue:
            self.short_queue[pair].cooldown_until = until

    def rank_queues(self, candle_idx: int):
        """Rank pairs in each queue by regime_adjusted_score (descending)."""
        for queue in [self.long_queue, self.short_queue]:
            eligible = [
                (p, e) for p, e in queue.items()
                if e.cooldown_until <= candle_idx
            ]
            eligible.sort(key=lambda x: abs(x[1].regime_adjusted_score), reverse=True)
            for rank, (pair, _) in enumerate(eligible):
                queue[pair].rank = rank

    def get_top_k(
        self, side: str, k: int, candle_idx: int, min_score: float = 0.0
    ) -> list[PairEntry]:
        """Get top-K pairs from a queue, filtered by min score and cooldown."""
        queue = self.long_queue if side == "long" else self.short_queue
        eligible = [
            e for e in queue.values()
            if e.cooldown_until <= candle_idx
            and abs(e.regime_adjusted_score) >= min_score
        ]
        eligible.sort(key=lambda x: abs(x.regime_adjusted_score), reverse=True)
        return eligible[:k]

    def get_pair_features(self, pair: str) -> dict[str, float]:
        """Get current features for a pair from whichever queue it's in."""
        entry = self.long_queue.get(pair) or self.short_queue.get(pair)
        return entry.features if entry else {}

    def log_state(self, candle_idx: int, top_n: int = 5):
        """Log current queue state for debugging."""
        long_top = sorted(
            self.long_queue.values(),
            key=lambda x: abs(x.regime_adjusted_score), reverse=True
        )[:top_n]
        short_top = sorted(
            self.short_queue.values(),
            key=lambda x: abs(x.regime_adjusted_score), reverse=True
        )[:top_n]

        logger.info(
            f"[ZAP] Candle {candle_idx} | "
            f"LONG Q ({len(self.long_queue)}): "
            + ", ".join(f"{e.pair}={e.regime_adjusted_score:.4f}" for e in long_top)
            + f" | SHORT Q ({len(self.short_queue)}): "
            + ", ".join(f"{e.pair}={e.regime_adjusted_score:.4f}" for e in short_top)
        )
```

- [ ] **Step 2: Test queue operations**

```bash
python -c "
from user_data.strategies.zap.queues import QueueManager
qm = QueueManager({'entry': {'cooldown_candles': 5}})
qm.update_pair('XRP', {'rsi': 30}, 0.012, 1.0, 100)
qm.update_pair('SOL', {'rsi': 70}, -0.008, 0.5, 100)
qm.update_pair('ETH', {'rsi': 45}, 0.005, 1.0, 100)
qm.rank_queues(100)
top = qm.get_top_k('long', 2, 100, min_score=0.003)
print('Top long:', [(e.pair, e.regime_adjusted_score) for e in top])
top_short = qm.get_top_k('short', 2, 100)
print('Top short:', [(e.pair, e.regime_adjusted_score) for e in top_short])
print('XRP features:', qm.get_pair_features('XRP'))
"
```

Expected: XRP and ETH in long queue (XRP #1), SOL in short queue.

- [ ] **Step 3: Commit**

```bash
git add -f user_data/strategies/zap/queues.py
git commit -m "feat(zap): add queue manager with LONG/SHORT ranking"
```

---

### Task 9: Regime Agent

**Files:**
- Create: `user_data/strategies/zap/agents/__init__.py`
- Create: `user_data/strategies/zap/agents/regime.py`

- [ ] **Step 1: Create `agents/__init__.py`**

```python
"""ZAP agents."""
```

- [ ] **Step 2: Create `regime.py`**

```python
"""Regime Agent: determines market state from BTC data."""
from __future__ import annotations

import logging

import numpy as np
import talib.abstract as ta
from pandas import DataFrame

logger = logging.getLogger(__name__)


class RegimeState:
    """Current market regime state."""

    def __init__(self):
        self.regime: str = "ranging"  # bull, bear, ranging
        self.strength: float = 0.0  # 0-1 regime confidence
        self.btc_momentum: float = 0.0
        self.btc_adx: float = 0.0

    def get_multiplier(self, side: str, cfg: dict) -> float:
        """Get regime multiplier for a given side (long/short)."""
        mults = cfg.get("entry", {}).get("regime_multipliers", {})
        key = f"{self.regime}_{side}"
        return mults.get(key, 0.5)

    def __repr__(self):
        return f"Regime({self.regime}, str={self.strength:.2f}, mom={self.btc_momentum:.2f})"


class RegimeAgent:
    """Analyzes BTC data to determine market regime.

    Runs on every candle, uses 1h informative for stability.
    """

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.state = RegimeState()
        self._rcfg = cfg.get("regime", {})

    def update(self, btc_df: DataFrame) -> RegimeState:
        """Update regime state from BTC dataframe.

        Parameters
        ----------
        btc_df : DataFrame
            BTC/USDT dataframe (5m or 1h). Must have OHLCV columns.
        """
        if btc_df is None or len(btc_df) < 30:
            return self.state

        adx_ranging = self._rcfg.get("adx_ranging", 18)
        adx_trending = self._rcfg.get("adx_trending", 25)
        mom_window = self._rcfg.get("btc_momentum_window", 48)

        # Compute indicators
        adx = ta.ADX(btc_df, timeperiod=14)
        ema21 = ta.EMA(btc_df, timeperiod=21)
        momentum = ta.ROC(btc_df, timeperiod=mom_window)

        last_adx = adx.iloc[-1] if not adx.empty else 0
        last_mom = momentum.iloc[-1] if not momentum.empty else 0
        last_slope = (ema21.iloc[-1] - ema21.iloc[-4]) / (ema21.iloc[-4] + 1e-10) * 100 if len(ema21) >= 4 else 0

        # Determine regime
        if last_adx < adx_ranging:
            regime = "ranging"
            strength = 1.0 - (last_adx / adx_ranging)
        elif last_mom > 0 and last_slope > 0:
            regime = "bull"
            strength = min(last_adx / 50.0, 1.0)
        elif last_mom < 0 and last_slope < 0:
            regime = "bear"
            strength = min(last_adx / 50.0, 1.0)
        else:
            regime = "ranging"
            strength = 0.3

        self.state.regime = regime
        self.state.strength = float(strength)
        self.state.btc_momentum = float(last_mom) if not np.isnan(last_mom) else 0.0
        self.state.btc_adx = float(last_adx) if not np.isnan(last_adx) else 0.0

        logger.info(f"[ZAP:Regime] {self.state}")

        return self.state
```

- [ ] **Step 3: Test regime agent**

```bash
python -c "
import pandas as pd, numpy as np
from user_data.strategies.zap.agents.regime import RegimeAgent
n = 300
btc_df = pd.DataFrame({
    'open': np.cumsum(np.random.randn(n)) + 60000,
    'high': np.cumsum(np.random.randn(n)) + 60500,
    'low': np.cumsum(np.random.randn(n)) + 59500,
    'close': np.cumsum(np.random.randn(n)) + 60000,
    'volume': np.random.uniform(100, 500, n),
})
btc_df['high'] = btc_df[['open','close']].max(axis=1) + 100
btc_df['low'] = btc_df[['open','close']].min(axis=1) - 100
agent = RegimeAgent({'regime': {'adx_ranging': 18, 'adx_trending': 25, 'btc_momentum_window': 24}})
state = agent.update(btc_df)
print('State:', state)
print('Bull long mult:', state.get_multiplier('long', {'entry': {'regime_multipliers': {'bull_long': 1.0, 'ranging_long': 0.5}}}))
"
```

Expected: prints regime state and multiplier.

- [ ] **Step 4: Commit**

```bash
git add -f user_data/strategies/zap/agents/__init__.py user_data/strategies/zap/agents/regime.py
git commit -m "feat(zap): add regime agent with BTC-based state detection"
```

---

### Task 10: Scanner Agent

**Files:**
- Create: `user_data/strategies/zap/agents/scanner.py`

- [ ] **Step 1: Create `scanner.py`**

```python
"""Scanner Agent: computes all features for a pair, updates queues."""
from __future__ import annotations

import logging
from typing import Any

from pandas import DataFrame

from user_data.strategies.zap.features import compute_all_features
from user_data.strategies.zap.queues import QueueManager

logger = logging.getLogger(__name__)


class ScannerAgent:
    """Computes features for each pair and updates queues.

    Runs in populate_indicators() for each pair.
    """

    def __init__(self, cfg: dict, queue_manager: QueueManager):
        self.cfg = cfg
        self.qm = queue_manager
        self._df_cache: dict[str, DataFrame] = {}

    def reset_cache(self):
        """Reset df cache at start of new backtest cycle."""
        self._df_cache.clear()
        from user_data.strategies.zap.features.statistical import reset_cache
        reset_cache()

    def update(
        self,
        df: DataFrame,
        pair: str,
        all_pairs: list[str],
        btc_df: DataFrame | None = None,
        dp: Any = None,
    ) -> DataFrame:
        """Compute all features for a pair and update queues.

        Parameters
        ----------
        df : DataFrame
            Pair OHLCV dataframe (5m).
        pair : str
            Current pair name.
        all_pairs : list[str]
            All pairs in whitelist (for cross-pair features).
        btc_df : DataFrame, optional
            BTC dataframe for macro features.
        dp : DataProvider, optional
            For fetching other pair data.

        Returns
        -------
        DataFrame with all %-prefixed feature columns added.
        """
        # Cache this pair's df for cross-pair use
        self._df_cache[f"{pair}__5m"] = df

        # Compute all features
        df = compute_all_features(
            df=df,
            pair=pair,
            cfg=self.cfg,
            dp=dp,
            all_pairs=all_pairs,
            btc_df=btc_df,
            df_cache=self._df_cache,
        )

        # Extract last row features for queue update
        last = df.iloc[-1]
        features = {
            col: float(last[col])
            for col in df.columns
            if col.startswith("%-") and not (last[col] != last[col])  # skip NaN
        }

        logger.debug(
            f"[ZAP:Scanner] {pair}: {len(features)} features computed"
        )

        return df
```

- [ ] **Step 2: Commit**

```bash
git add -f user_data/strategies/zap/agents/scanner.py
git commit -m "feat(zap): add scanner agent for feature computation"
```

---

### Task 11: Entry Agent

**Files:**
- Create: `user_data/strategies/zap/agents/entry.py`

- [ ] **Step 1: Create `entry.py`**

```python
"""Entry Agent: reads queues + FreqAI predictions, generates entry signals."""
from __future__ import annotations

import logging

from pandas import DataFrame

from user_data.strategies.zap.agents.regime import RegimeState
from user_data.strategies.zap.queues import QueueManager

logger = logging.getLogger(__name__)


class EntryAgent:
    """Decides entries based on FreqAI predictions and queue ranking.

    Runs in populate_entry_trend() and confirm_trade_entry().
    """

    def __init__(self, cfg: dict, queue_manager: QueueManager):
        self.cfg = cfg
        self.qm = queue_manager
        self._ecfg = cfg.get("entry", {})

    def generate_signals(
        self,
        df: DataFrame,
        pair: str,
        regime: RegimeState,
    ) -> DataFrame:
        """Mark entry signals based on FreqAI prediction and queue position.

        The FreqAI prediction column (&-s_close) contains the predicted
        forward return. We use this as the queue score.
        """
        df["enter_long"] = 0
        df["enter_short"] = 0
        df["enter_tag"] = ""

        min_pred = self._ecfg.get("min_predicted_return", 0.005)

        # Check if FreqAI predictions are available
        has_freqai = "&-s_close" in df.columns and "do_predict" in df.columns

        if has_freqai:
            # Long entries: high predicted return + model confidence
            long_mask = (
                (df["do_predict"] == 1)
                & (df["&-s_close"] > min_pred)
            )
            df.loc[long_mask, "enter_long"] = 1
            df.loc[long_mask, "enter_tag"] = "zap_long"

            # Short entries: negative predicted return + model confidence
            short_mask = (
                (df["do_predict"] == 1)
                & (df["&-s_close"] < -min_pred)
            )
            df.loc[short_mask, "enter_short"] = 1
            df.loc[short_mask, "enter_tag"] = "zap_short"

        return df

    def confirm_entry(
        self,
        pair: str,
        side: str,
        rate: float,
        regime: RegimeState,
        candle_idx: int,
        current_open_trades: int,
        current_prediction: float,
    ) -> bool:
        """Gate entry: only allow if pair is in top-K of its queue.

        Called from strategy.confirm_trade_entry().
        """
        max_trades = self.cfg.get("max_open_trades", 6)
        if current_open_trades >= max_trades:
            logger.info(f"[ZAP:Entry] REJECT {pair} {side}: max trades reached")
            return False

        top_k = self._ecfg.get("top_k", 3)
        min_score = self._ecfg.get("min_predicted_return", 0.005)

        # Update queue with current prediction
        mult = regime.get_multiplier(side, self.cfg)
        self.qm.update_pair(pair, {}, current_prediction, mult, candle_idx)
        self.qm.rank_queues(candle_idx)

        # Check if pair is in top-K
        top = self.qm.get_top_k(side, top_k, candle_idx, min_score)
        top_pairs = [e.pair for e in top]

        if pair in top_pairs:
            rank = top_pairs.index(pair)
            score = top[rank].regime_adjusted_score
            logger.info(
                f"[ZAP:Entry] ACCEPT {pair} {side} "
                f"rank={rank+1}/{len(top_pairs)} score={score:.4f} "
                f"regime={regime.regime}"
            )
            return True
        else:
            logger.info(
                f"[ZAP:Entry] REJECT {pair} {side}: not in top-{top_k} "
                f"(top: {top_pairs[:3]})"
            )
            return False
```

- [ ] **Step 2: Commit**

```bash
git add -f user_data/strategies/zap/agents/entry.py
git commit -m "feat(zap): add entry agent with FreqAI + queue ranking"
```

---

### Task 12: Manager Agent

**Files:**
- Create: `user_data/strategies/zap/agents/manager.py`

- [ ] **Step 1: Create `manager.py`**

```python
"""Manager Agent: handles exits, DCA, trailing, time stops."""
from __future__ import annotations

import logging
from typing import Any, Optional

from pandas import DataFrame

logger = logging.getLogger(__name__)


class ManagerAgent:
    """Manages open trades: exits, DCA, trailing, time stops.

    Runs in custom_exit(), custom_stoploss(), adjust_trade_position().
    """

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self._mcfg = cfg.get("manager", {})

    def check_exit(
        self,
        pair: str,
        trade: Any,
        current_rate: float,
        current_profit: float,
        current_prediction: float,
        do_predict: int,
        candles_open: int,
    ) -> Optional[str]:
        """Check if a trade should be exited.

        Returns exit tag string or None to keep holding.
        """
        # 1. ML exit: predicted return flipped sign
        if do_predict == 1 and current_prediction != 0:
            is_long = trade.is_short is False
            if is_long and current_prediction < -0.002:
                logger.info(
                    f"[ZAP:Manager] ML EXIT {pair}: pred flipped to "
                    f"{current_prediction:.4f}"
                )
                return "zap_ml_exit"
            elif not is_long and current_prediction > 0.002:
                logger.info(
                    f"[ZAP:Manager] ML EXIT {pair}: pred flipped to "
                    f"{current_prediction:.4f}"
                )
                return "zap_ml_exit"

        # 2. Time stop
        time_stop = self._mcfg.get("time_stop_candles", 48)
        if candles_open >= time_stop:
            logger.info(
                f"[ZAP:Manager] TIME STOP {pair}: {candles_open} candles, "
                f"profit={current_profit:.2%}"
            )
            return "zap_time_stop"

        # 3. Profit lock (if profit > trailing_activate, exit if prediction weakening)
        trailing_act = self._mcfg.get("trailing_activate", 0.02)
        if current_profit > trailing_act and do_predict == 1:
            if abs(current_prediction) < 0.001:
                logger.info(
                    f"[ZAP:Manager] PROFIT LOCK {pair}: profit={current_profit:.2%}, "
                    f"pred weakened to {current_prediction:.4f}"
                )
                return "zap_profit_lock"

        return None

    def get_stoploss(
        self,
        pair: str,
        current_profit: float,
        current_prediction: float,
    ) -> float:
        """Dynamic stoploss based on profit and prediction.

        Returns stoploss as negative float (e.g., -0.10 = -10%).
        """
        base_sl = self._mcfg.get("stoploss", -0.10)
        trailing_act = self._mcfg.get("trailing_activate", 0.02)
        trailing_off = self._mcfg.get("trailing_offset", 0.005)

        if current_profit > trailing_act:
            # Trail behind current profit
            return -(current_profit - trailing_off)

        return base_sl

    def check_dca(
        self,
        pair: str,
        trade: Any,
        current_profit: float,
        current_prediction: float,
        do_predict: int,
        wallet_balance: float,
    ) -> Optional[float]:
        """Check if DCA should be applied. Returns stake amount or None.

        DCA only if:
        1. Trade is in loss beyond threshold
        2. Model re-confirms direction with strong score
        """
        dca_threshold = self._mcfg.get("dca_threshold", -0.03)
        dca_min_pred = self._mcfg.get("dca_min_predicted", 0.008)
        dca_multipliers = self._mcfg.get("dca_multipliers", [1.5, 2.5])

        if current_profit > dca_threshold:
            return None  # Not in enough loss

        if do_predict != 1:
            return None

        # Check prediction confirms direction
        is_long = trade.is_short is False
        if is_long and current_prediction < dca_min_pred:
            return None
        if not is_long and current_prediction > -dca_min_pred:
            return None

        # Determine DCA level (how many times already DCA'd)
        dca_count = getattr(trade, "nr_of_successful_entries", 1) - 1
        if dca_count >= len(dca_multipliers):
            return None

        multiplier = dca_multipliers[dca_count]
        base_stake = trade.stake_amount
        dca_stake = base_stake * multiplier

        # Safety: don't exceed 10% of wallet
        max_stake = wallet_balance * 0.10
        dca_stake = min(dca_stake, max_stake)

        logger.info(
            f"[ZAP:Manager] DCA #{dca_count+1} {pair}: "
            f"${dca_stake:.2f} (mult={multiplier}x), "
            f"profit={current_profit:.2%}, pred={current_prediction:.4f}"
        )

        return dca_stake
```

- [ ] **Step 2: Commit**

```bash
git add -f user_data/strategies/zap/agents/manager.py
git commit -m "feat(zap): add manager agent with ML exit, trailing, DCA"
```

---

### Task 13: Strategy Orchestrator

**Files:**
- Create: `user_data/strategies/zap/strategy.py`

- [ ] **Step 1: Create `strategy.py` — the IStrategy subclass that wires all agents**

```python
"""ZAP Strategy — ZScore Agent Pipeline.

Orchestrates 4 agents via freqtrade callbacks:
- Scanner: populate_indicators() — computes features
- Regime: populate_indicators() — determines market state
- Entry: populate_entry_trend() + confirm_trade_entry() — generates signals
- Manager: custom_exit() + custom_stoploss() + adjust_trade_position() — manages trades
"""
from __future__ import annotations

import logging
from functools import reduce
from pathlib import Path

from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy

from user_data.strategies.zap.agents.entry import EntryAgent
from user_data.strategies.zap.agents.manager import ManagerAgent
from user_data.strategies.zap.agents.regime import RegimeAgent
from user_data.strategies.zap.agents.scanner import ScannerAgent
from user_data.strategies.zap.config import load_config
from user_data.strategies.zap.queues import QueueManager

logger = logging.getLogger(__name__)


class ZAPStrategy(IStrategy):
    """ZScore Agent Pipeline Strategy with FreqAI."""

    INTERFACE_VERSION = 3

    # --- Strategy params ---
    minimal_roi = {"0": 0.10, "60": 0.05, "120": 0.02}
    stoploss = -0.10
    trailing_stop = False
    use_exit_signal = True
    process_only_new_candles = True
    can_short = True
    startup_candle_count = 300

    timeframe = "5m"

    # FreqAI
    freqai_info = {}  # populated from config

    def __init__(self, config: dict) -> None:
        super().__init__(config)

        # Load ZAP config
        zap_cfg_path = Path(config.get("user_data_dir", "user_data")) / "strategies" / "zap_config.json"
        self._cfg = load_config(zap_cfg_path)

        # Initialize agents
        self._qm = QueueManager(self._cfg)
        self._scanner = ScannerAgent(self._cfg, self._qm)
        self._regime = RegimeAgent(self._cfg)
        self._entry = EntryAgent(self._cfg, self._qm)
        self._manager = ManagerAgent(self._cfg)

        # Cache
        self._btc_df: DataFrame | None = None
        self._candle_idx: int = 0

        logger.info("[ZAP] Strategy initialized")

    def informative_pairs(self):
        """Request BTC on 5m and 1h for regime detection."""
        pairs = []
        btc = "BTC/USDT:USDT"
        for tf in ["5m", "1h"]:
            pairs.append((btc, tf))
        return pairs

    # ========== FreqAI Feature Engineering ==========

    def feature_engineering_expand_all(
        self, dataframe: DataFrame, period: int, metadata: dict, **kwargs
    ) -> DataFrame:
        """Features auto-expanded by FreqAI across timeframes and periods."""
        import talib.abstract as ta

        dataframe["%-rsi-period"] = ta.RSI(dataframe, timeperiod=period)
        dataframe["%-adx-period"] = ta.ADX(dataframe, timeperiod=period)
        dataframe["%-mfi-period"] = ta.MFI(dataframe, timeperiod=period)
        dataframe["%-ema-period"] = ta.EMA(dataframe, timeperiod=period)
        dataframe["%-roc-period"] = ta.ROC(dataframe, timeperiod=period)
        dataframe["%-relative_volume-period"] = (
            dataframe["volume"] / dataframe["volume"].rolling(period).mean()
        )

        return dataframe

    def feature_engineering_expand_basic(
        self, dataframe: DataFrame, metadata: dict, **kwargs
    ) -> DataFrame:
        """Features expanded by timeframe only (no period multiplication)."""
        dataframe["%-pct-change"] = dataframe["close"].pct_change()
        dataframe["%-raw_volume"] = dataframe["volume"]
        dataframe["%-raw_price"] = dataframe["close"]

        return dataframe

    def feature_engineering_standard(
        self, dataframe: DataFrame, metadata: dict, **kwargs
    ) -> DataFrame:
        """Custom features — no auto-expansion. Computed once on base TF."""
        pair = metadata["pair"]
        all_pairs = self.dp.current_whitelist() if self.dp else []

        # Load BTC df for macro features
        if self.dp:
            btc_df = self.dp.get_pair_dataframe(pair="BTC/USDT:USDT", timeframe="5m")
        else:
            btc_df = None

        # Scanner agent: compute all 46 custom features
        dataframe = self._scanner.update(
            df=dataframe,
            pair=pair,
            all_pairs=all_pairs,
            btc_df=btc_df,
            dp=self.dp,
        )

        # Time features
        dataframe["%-day_of_week"] = dataframe["date"].dt.dayofweek
        dataframe["%-hour_of_day"] = dataframe["date"].dt.hour

        return dataframe

    def set_freqai_targets(
        self, dataframe: DataFrame, metadata: dict, **kwargs
    ) -> DataFrame:
        """Define prediction target: forward return over next 12 candles."""
        label_period = self.freqai_info.get(
            "feature_parameters", {}
        ).get("label_period_candles", 12)

        dataframe["&-s_close"] = (
            dataframe["close"]
            .shift(-label_period)
            .rolling(label_period)
            .mean()
            / dataframe["close"]
            - 1
        )

        return dataframe

    # ========== Freqtrade Callbacks ==========

    def populate_indicators(
        self, dataframe: DataFrame, metadata: dict
    ) -> DataFrame:
        """Run FreqAI pipeline (which calls feature_engineering_* methods)."""
        # Regime agent: update from BTC data
        if self.dp:
            btc_df = self.dp.get_pair_dataframe(
                pair="BTC/USDT:USDT", timeframe="5m"
            )
            self._regime.update(btc_df)
            self._btc_df = btc_df

        # FreqAI: computes features + predictions
        dataframe = self.freqai.start(dataframe, metadata, self)

        # Update queue with prediction
        if "&-s_close" in dataframe.columns:
            last = dataframe.iloc[-1]
            pred = float(last.get("&-s_close", 0))
            pair = metadata["pair"]
            side = "long" if pred >= 0 else "short"
            mult = self._regime.state.get_multiplier(side, self._cfg)

            features = {
                col: float(last[col])
                for col in dataframe.columns
                if col.startswith("%-") and last[col] == last[col]
            }

            self._candle_idx = len(dataframe)
            self._qm.update_pair(pair, features, pred, mult, self._candle_idx)
            self._qm.rank_queues(self._candle_idx)

        return dataframe

    def populate_entry_trend(
        self, dataframe: DataFrame, metadata: dict
    ) -> DataFrame:
        """Entry agent: generate entry signals from FreqAI predictions."""
        return self._entry.generate_signals(
            dataframe, metadata["pair"], self._regime.state
        )

    def populate_exit_trend(
        self, dataframe: DataFrame, metadata: dict
    ) -> DataFrame:
        """Exit signals handled by custom_exit(), not here."""
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        return dataframe

    def confirm_trade_entry(
        self,
        pair: str,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        current_time,
        entry_tag,
        side: str,
        **kwargs,
    ) -> bool:
        """Gate entry through queue ranking."""
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df.empty:
            return False

        last = df.iloc[-1]
        pred = float(last.get("&-s_close", 0))
        do_pred = int(last.get("do_predict", 0))

        if do_pred != 1:
            return False

        open_trades = Trade.get_trades_proxy(is_open=True)
        return self._entry.confirm_entry(
            pair=pair,
            side=side,
            rate=rate,
            regime=self._regime.state,
            candle_idx=self._candle_idx,
            current_open_trades=len(open_trades),
            current_prediction=pred,
        )

    def custom_exit(
        self,
        pair: str,
        trade: Trade,
        current_time,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> str | bool:
        """Manager agent: check for ML exit, time stop, profit lock."""
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df.empty:
            return False

        last = df.iloc[-1]
        pred = float(last.get("&-s_close", 0))
        do_pred = int(last.get("do_predict", 0))

        candles_open = (current_time - trade.open_date).total_seconds() / 300

        exit_tag = self._manager.check_exit(
            pair=pair,
            trade=trade,
            current_rate=current_rate,
            current_profit=current_profit,
            current_prediction=pred,
            do_predict=do_pred,
            candles_open=int(candles_open),
        )

        if exit_tag:
            self._qm.set_cooldown(pair, self._candle_idx)
            return exit_tag

        return False

    def custom_stoploss(
        self,
        pair: str,
        trade: Trade,
        current_time,
        current_rate: float,
        current_profit: float,
        after_fill: bool,
        **kwargs,
    ) -> float:
        """Manager agent: dynamic stoploss with trailing."""
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        pred = 0.0
        if not df.empty:
            pred = float(df.iloc[-1].get("&-s_close", 0))

        return self._manager.get_stoploss(pair, current_profit, pred)

    def leverage(
        self,
        pair: str,
        current_time,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        """Dynamic leverage based on prediction strength and regime."""
        lev_cfg = self._cfg.get("leverage", {})
        min_lev = lev_cfg.get("min", 2)
        max_lev = lev_cfg.get("max", 8)

        # Get prediction strength
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df.empty:
            return float(min_lev)

        pred = abs(float(df.iloc[-1].get("&-s_close", 0)))

        # Scale leverage with prediction confidence
        # pred 0.005 -> min_lev, pred 0.02+ -> max_lev
        scale = min(pred / 0.02, 1.0)
        lev = min_lev + scale * (max_lev - min_lev)

        # Reduce in ranging regime
        if self._regime.state.regime == "ranging":
            lev = min(lev, (min_lev + max_lev) / 2)

        lev = min(lev, max_leverage)
        return float(round(lev, 1))

    def adjust_trade_position(
        self,
        trade: Trade,
        current_time,
        current_rate: float,
        current_profit: float,
        min_stake: float | None,
        max_stake: float,
        current_entry_rate: float,
        current_exit_rate: float,
        current_entry_profit: float,
        current_exit_profit: float,
        **kwargs,
    ) -> float | None:
        """Manager agent: DCA if model re-confirms."""
        df, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
        if df.empty:
            return None

        last = df.iloc[-1]
        pred = float(last.get("&-s_close", 0))
        do_pred = int(last.get("do_predict", 0))

        wallet = self.wallets.get_available_stake_amount() if self.wallets else 0

        return self._manager.check_dca(
            pair=trade.pair,
            trade=trade,
            current_profit=current_profit,
            current_prediction=pred,
            do_predict=do_pred,
            wallet_balance=wallet,
        )
```

- [ ] **Step 2: Verify strategy can be listed by freqtrade**

```bash
cd /Users/fvcoelho/Working/freqtrade && source .venv/bin/activate
freqtrade list-strategies --strategy-path user_data/strategies/zap/ 2>&1 | head -20
```

Expected: `ZAPStrategy` appears in the list (may show warnings about FreqAI not configured — that's OK).

- [ ] **Step 3: Commit**

```bash
git add -f user_data/strategies/zap/strategy.py
git commit -m "feat(zap): add strategy orchestrator wiring all 4 agents"
```

---

### Task 14: Backtest Configuration

**Files:**
- Create: `config_zap_backtest_5m.json`

- [ ] **Step 1: Create backtest config with FreqAI settings**

```json
{
    "trading_mode": "futures",
    "margin_mode": "isolated",
    "max_open_trades": 6,
    "stake_currency": "USDT",
    "stake_amount": 50,
    "tradable_balance_ratio": 0.99,
    "dry_run": true,
    "dry_run_wallet": 1000,
    "cancel_open_orders_on_exit": false,

    "exchange": {
        "name": "hyperliquid",
        "key": "",
        "secret": "",
        "pair_whitelist": [
            "BTC/USDT:USDT",
            "ETH/USDT:USDT",
            "SOL/USDT:USDT",
            "XRP/USDT:USDT",
            "ADA/USDT:USDT",
            "DOGE/USDT:USDT",
            "LINK/USDT:USDT",
            "SUI/USDT:USDT",
            "TON/USDT:USDT",
            "ONDO/USDT:USDT",
            "AVAX/USDT:USDT",
            "DOT/USDT:USDT",
            "NEAR/USDT:USDT",
            "ATOM/USDT:USDT",
            "INJ/USDT:USDT",
            "SEI/USDT:USDT",
            "OP/USDT:USDT",
            "ARB/USDT:USDT",
            "FTM/USDT:USDT",
            "MATIC/USDT:USDT"
        ],
        "pair_blacklist": []
    },

    "pairlists": [
        {"method": "StaticPairList"}
    ],

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

    "freqai": {
        "enabled": true,
        "purge_old_models": 2,
        "train_period_days": 30,
        "backtest_period_days": 7,
        "identifier": "zap_v1",
        "feature_parameters": {
            "include_timeframes": ["5m", "15m", "1h"],
            "include_corr_pairlist": [
                "BTC/USDT:USDT",
                "ETH/USDT:USDT",
                "SOL/USDT:USDT"
            ],
            "label_period_candles": 12,
            "include_shifted_candles": 2,
            "indicator_periods_candles": [10, 20, 40],
            "DI_threshold": 0.9,
            "weight_factor": 0.9,
            "principal_component_analysis": false,
            "plot_feature_importances": 0
        },
        "data_split_parameters": {
            "test_size": 0.33,
            "random_state": 1
        },
        "model_training_parameters": {
            "n_estimators": 800,
            "learning_rate": 0.02,
            "max_depth": 8,
            "num_leaves": 64,
            "min_child_samples": 20,
            "reg_alpha": 0.1,
            "reg_lambda": 0.1,
            "verbosity": -1
        }
    },

    "strategy": "ZAPStrategy",
    "strategy_path": "user_data/strategies/zap/",
    "timeframe": "5m",

    "zap": {
        "pairs_count": 20,
        "max_open_trades": 6,
        "leverage": {"min": 2, "max": 8},
        "entry": {
            "top_k": 3,
            "min_predicted_return": 0.005
        }
    }
}
```

- [ ] **Step 2: Verify config is valid JSON**

```bash
python -c "import json; json.load(open('config_zap_backtest_5m.json')); print('Valid JSON')"
```

Expected: `Valid JSON`

- [ ] **Step 3: Commit**

```bash
git add config_zap_backtest_5m.json
git commit -m "feat(zap): add backtest config with FreqAI + 20 pairs"
```

---

### Task 15: Update `__init__.py` and First Backtest

**Files:**
- Modify: `user_data/strategies/zap/__init__.py`

- [ ] **Step 1: Fix `__init__.py` to use proper import**

```python
"""ZAP — ZScore Agent Pipeline Strategy."""
from user_data.strategies.zap.strategy import ZAPStrategy  # noqa: F401

__all__ = ["ZAPStrategy"]
```

- [ ] **Step 2: Download data for all 20 pairs if not already available**

```bash
cd /Users/fvcoelho/Working/freqtrade && source .venv/bin/activate
freqtrade download-data --config config_zap_backtest_5m.json -t 5m 15m 1h --timerange 20260301-20260528 2>&1 | tail -10
```

- [ ] **Step 3: Run first backtest (short timerange to validate pipeline)**

```bash
freqtrade backtesting --config config_zap_backtest_5m.json --strategy ZAPStrategy --timerange 20260401-20260415 --freqaimodel LightGBMRegressor 2>&1 | tail -30
```

Expected: Backtest completes (even with poor results — this validates the full pipeline works end-to-end).

- [ ] **Step 4: Fix any import/runtime errors found in step 3**

Iterate until the backtest runs without crashes. Common issues:
- Missing imports
- Column name mismatches
- FreqAI feature prefix errors (must start with `%`)
- NaN handling in features

- [ ] **Step 5: Commit final working state**

```bash
git add -f user_data/strategies/zap/
git commit -m "feat(zap): working end-to-end pipeline with FreqAI backtest"
```

---

## Execution Order Summary

| Task | Component | Features/Output |
|------|-----------|-----------------|
| 1 | Config + skeleton | `config.py`, `__init__.py`, `zap_config.json` |
| 2 | Statistical features | 10 features (z-score, half-life, hurst, etc.) |
| 3 | Momentum features | 8 features (RSI, MACD, ADX, EMA slopes, ROC) |
| 4 | Microstructure features | 6 features (funding, OI, VWAP, CVD, vol ratio) |
| 5 | Cross-pair features | 8 features (beta, lead-lag, rel strength, corr) |
| 6 | Volatility features | 8 features (ATR, BB, realized vol, Keltner) |
| 7 | Macro features | 6 features (BTC trend, momentum, dominance) |
| 8 | Queue system | LONG/SHORT queues with ranking |
| 9 | Regime agent | BTC-based bull/bear/ranging detection |
| 10 | Scanner agent | Feature computation orchestrator |
| 11 | Entry agent | FreqAI + queue ranking → entry signals |
| 12 | Manager agent | ML exit, trailing, DCA, time stop |
| 13 | Strategy orchestrator | IStrategy wiring all agents |
| 14 | Backtest config | 20 pairs, FreqAI LightGBM, HL futures |
| 15 | Integration test | Download data + first backtest run |
