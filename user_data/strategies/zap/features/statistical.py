"""Statistical features for ZAP strategy.

Computes 10 %-prefixed columns per pair:
    %-zscore          basket z-score (SMA)
    %-spread_velocity spread diff(5)
    %-spread_accel    spread diff(5).diff(5)
    %-half_life       half-life of mean reversion via OLS
    %-hurst           Hurst exponent via R/S analysis
    %-coint_score     correlation of levels (simplified cointegration proxy)
    %-zscore_ewm      EWM z-score
    %-log_spread      raw log spread vs basket
    %-zscore_kalman   Kalman-filtered z-score
    %-zscore_cumret   cumulative returns z-score
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from pandas import DataFrame

# ---------------------------------------------------------------------------
# Module-level basket cache: {frozenset(pairs) -> Series(index=DatetimeIndex)}
# ---------------------------------------------------------------------------
_basket_cache: dict[frozenset, pd.Series] = {}


def reset_cache() -> None:
    """Clear the basket average cache (call between backtest runs)."""
    _basket_cache.clear()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compute_basket_avg(
    pair: str,
    all_pairs: list[str],
    df_cache: dict[str, DataFrame],
) -> pd.Series | None:
    """Load log prices for all pairs, normalise to start=0, return mean Series.

    Results are cached by the frozenset of available pairs so the expensive
    alignment is only done once per unique basket composition.

    Returns None when fewer than 2 pairs (including the current one) have data.
    """
    available = [p for p in all_pairs if p in df_cache and not df_cache[p].empty]
    if not available:
        return None

    cache_key = frozenset(available)
    if cache_key in _basket_cache:
        return _basket_cache[cache_key]

    log_prices: list[pd.Series] = []
    for p in available:
        df_p = df_cache[p]
        if "close" not in df_p.columns:
            continue
        lp = np.log(df_p["close"].replace(0, np.nan).ffill())
        lp = lp - lp.iloc[0]  # normalise to start at 0
        lp.name = p
        log_prices.append(lp)

    if len(log_prices) < 2:
        return None

    combined = pd.concat(log_prices, axis=1).ffill().bfill()
    basket_avg = combined.mean(axis=1)
    basket_avg.name = "basket_avg"

    _basket_cache[cache_key] = basket_avg
    return basket_avg


def _hurst_exponent(series: pd.Series, min_window: int = 10) -> float:
    """Estimate Hurst exponent via R/S analysis.

    Returns a value in [0, 1]:
        H < 0.5  -> mean-reverting
        H = 0.5  -> random walk
        H > 0.5  -> trending
    Falls back to 0.5 on insufficient data or numerical errors.
    """
    arr = series.dropna().values
    n = len(arr)
    if n < max(min_window * 2, 20):
        return 0.5

    lags = []
    rs_values = []
    max_lag = max(min_window, n // 4)
    step = max(1, max_lag // 10)

    for lag in range(min_window, max_lag + 1, step):
        sub = arr[:lag]
        mean_sub = sub.mean()
        deviation = sub - mean_sub
        cumdev = np.cumsum(deviation)
        r = cumdev.max() - cumdev.min()
        s = sub.std(ddof=1)
        if s > 0 and r > 0:
            lags.append(np.log(lag))
            rs_values.append(np.log(r / s))

    if len(lags) < 2:
        return 0.5

    try:
        slope, _ = np.polyfit(lags, rs_values, 1)
        return float(np.clip(slope, 0.0, 1.0))
    except Exception:
        return 0.5


def _half_life(spread: pd.Series) -> float:
    """Estimate half-life of mean reversion via OLS on lag-1 spread.

    half_life = -ln(2) / beta  where beta is the OLS slope of
    delta_spread ~ alpha + beta * spread_{t-1}.

    Returns np.nan when OLS fails or beta >= 0 (no mean reversion).
    """
    s = spread.dropna()
    if len(s) < 20:
        return np.nan

    delta = s.diff().dropna()
    lagged = s.shift(1).dropna()
    # align
    idx = delta.index.intersection(lagged.index)
    delta = delta.loc[idx]
    lagged = lagged.loc[idx]

    if len(delta) < 10:
        return np.nan

    try:
        X = np.column_stack([np.ones(len(lagged)), lagged.values])
        beta = np.linalg.lstsq(X, delta.values, rcond=None)[0][1]
        if beta >= 0:
            return np.nan
        hl = -np.log(2) / beta
        return float(hl) if np.isfinite(hl) else np.nan
    except Exception:
        return np.nan


def _zscore_kalman(spread: pd.Series) -> pd.Series:
    """Simple scalar Kalman filter applied to the spread to estimate dynamic mean.

    State: mean estimate. Measurement noise R, process noise Q.
    Returns z-score of spread vs Kalman mean estimate.
    """
    arr = spread.values.astype(float)
    n = len(arr)

    # Initialise
    Q = 1e-5   # process noise
    R = 1e-3   # measurement noise
    x_hat = arr[0] if np.isfinite(arr[0]) else 0.0
    P = 1.0

    estimates = np.empty(n)
    estimates[0] = x_hat

    for i in range(1, n):
        # Predict
        x_hat_minus = x_hat
        P_minus = P + Q

        # Update
        if np.isfinite(arr[i]):
            K = P_minus / (P_minus + R)
            x_hat = x_hat_minus + K * (arr[i] - x_hat_minus)
            P = (1 - K) * P_minus
        else:
            x_hat = x_hat_minus
            P = P_minus

        estimates[i] = x_hat

    estimates_series = pd.Series(estimates, index=spread.index)
    residuals = spread - estimates_series
    std = residuals.rolling(20, min_periods=5).std()
    z = residuals / std.replace(0, np.nan)
    return z.fillna(0.0)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute(
    df: DataFrame,
    pair: str,
    cfg: dict,
    dp=None,
    all_pairs: list[str] | None = None,
    df_cache: dict[str, DataFrame] | None = None,
) -> DataFrame:
    """Compute 10 statistical %-features and append them to *df*.

    Parameters
    ----------
    df:        OHLCV DataFrame for this pair (must contain 'close').
    pair:      Pair symbol, e.g. 'BTC/USDT'.
    cfg:       ZAP config dict (reads cfg["scanner"]["zscore_window"]).
    dp:        DataProvider (unused here, kept for interface consistency).
    all_pairs: Full list of pairs in the basket.
    df_cache:  Dict mapping pair -> DataFrame, used for basket computation.

    Returns
    -------
    df with 10 new %-prefixed columns added in-place copy.
    """
    all_pairs = all_pairs or []
    df_cache = df_cache or {}

    scanner_cfg = cfg.get("scanner", {})
    window: int = int(scanner_cfg.get("zscore_window", 288))

    _COLS = [
        "%-zscore",
        "%-spread_velocity",
        "%-spread_accel",
        "%-half_life",
        "%-hurst",
        "%-coint_score",
        "%-zscore_ewm",
        "%-log_spread",
        "%-zscore_kalman",
        "%-zscore_cumret",
    ]

    # Ensure df is a copy so we don't mutate callers' frames
    df = df.copy()

    if "close" not in df.columns or df.empty:
        for col in _COLS:
            df[col] = 0.0
        return df

    # ------------------------------------------------------------------
    # Log price of this pair
    # ------------------------------------------------------------------
    log_price = np.log(df["close"].replace(0, np.nan).ffill())

    # ------------------------------------------------------------------
    # Basket average (needed for spread-based features)
    # ------------------------------------------------------------------
    # Include this pair in df_cache for basket computation
    if pair not in df_cache:
        df_cache = {**df_cache, pair: df}

    basket_avg = _compute_basket_avg(pair, all_pairs or [pair], df_cache)

    if basket_avg is None or basket_avg.empty:
        # Fallback: no basket — all features set to 0
        for col in _COLS:
            df[col] = 0.0
        return df

    # Align basket to this df's index
    basket_aligned = basket_avg.reindex(df.index).ffill().bfill()

    # Normalised log price (starts at 0 like basket)
    log_price_norm = log_price - log_price.iloc[0]

    # Raw log spread: pair log price (normalised) vs basket
    spread = log_price_norm - basket_aligned

    # ------------------------------------------------------------------
    # 1. %-zscore  (SMA-based)
    # ------------------------------------------------------------------
    sma = spread.rolling(window, min_periods=window // 4).mean()
    std = spread.rolling(window, min_periods=window // 4).std()
    zscore = ((spread - sma) / std.replace(0, np.nan)).fillna(0.0)
    df["%-zscore"] = zscore

    # ------------------------------------------------------------------
    # 2. %-spread_velocity  diff(5)
    # ------------------------------------------------------------------
    df["%-spread_velocity"] = spread.diff(5).fillna(0.0)

    # ------------------------------------------------------------------
    # 3. %-spread_accel  diff(5).diff(5)
    # ------------------------------------------------------------------
    df["%-spread_accel"] = spread.diff(5).diff(5).fillna(0.0)

    # ------------------------------------------------------------------
    # 4. %-half_life  (scalar, broadcast over all rows for this candle batch)
    # ------------------------------------------------------------------
    hl = _half_life(spread)
    df["%-half_life"] = hl if np.isfinite(hl) else 0.0

    # ------------------------------------------------------------------
    # 5. %-hurst
    # ------------------------------------------------------------------
    df["%-hurst"] = _hurst_exponent(spread)

    # ------------------------------------------------------------------
    # 6. %-coint_score  (correlation of log-price levels)
    # ------------------------------------------------------------------
    roll_corr = log_price_norm.rolling(window, min_periods=window // 4).corr(basket_aligned)
    df["%-coint_score"] = roll_corr.fillna(0.0)

    # ------------------------------------------------------------------
    # 7. %-zscore_ewm
    # ------------------------------------------------------------------
    ewm_mean = spread.ewm(span=window, min_periods=window // 8).mean()
    ewm_std = spread.ewm(span=window, min_periods=window // 8).std()
    df["%-zscore_ewm"] = ((spread - ewm_mean) / ewm_std.replace(0, np.nan)).fillna(0.0)

    # ------------------------------------------------------------------
    # 8. %-log_spread  (raw)
    # ------------------------------------------------------------------
    df["%-log_spread"] = spread.fillna(0.0)

    # ------------------------------------------------------------------
    # 9. %-zscore_kalman
    # ------------------------------------------------------------------
    df["%-zscore_kalman"] = _zscore_kalman(spread)

    # ------------------------------------------------------------------
    # 10. %-zscore_cumret  (cumulative returns z-score)
    # ------------------------------------------------------------------
    cum_ret = df["close"].pct_change().fillna(0.0).cumsum()
    basket_close_ret = (
        basket_aligned.diff().fillna(0.0).cumsum()
    )
    cum_spread = cum_ret - basket_close_ret.reindex(df.index).fillna(0.0)
    cum_sma = cum_spread.rolling(window, min_periods=window // 4).mean()
    cum_std = cum_spread.rolling(window, min_periods=window // 4).std()
    df["%-zscore_cumret"] = (
        (cum_spread - cum_sma) / cum_std.replace(0, np.nan)
    ).fillna(0.0)

    return df
