"""Z-score computation for ZScore V53 strategy.

Extends V52 z-score module with per-group spread computation:
- Per-pair z-score (log-price based)
- Spread z-score (Log Spread method: mean(log A) - mean(log B))
- Z-score zero-cross signals
- Caching helpers for cross-pair lookups
- NEW: compute_group_spread_z() for independent group spread z-scores
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from pandas import DataFrame


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_pair_df(
    target_pair: str,
    timeframe: str,
    dp,
    df_cache: dict,
) -> DataFrame | None:
    """Cached wrapper around dp.get_pair_dataframe.

    Mirrors V51 ``_get_pair_df``.  The caller is responsible for clearing
    *df_cache* at the start of each indicator cycle.
    """
    key = f"{target_pair}__{timeframe}"
    if key in df_cache:
        return df_cache[key]
    if dp is None:
        return None
    df = dp.get_pair_dataframe(pair=target_pair, timeframe=timeframe)
    if df is not None:
        df_cache[key] = df
    return df


def _compute_pair_zscore_for(
    target_pair: str,
    n: int,
    zscore_window: int,
    cum_return_window: int,
    timeframe: str,
    dp,
    df_cache: dict,
) -> np.ndarray | None:
    """Compute z-score for a pair not yet cached (cache-miss path).

    Mirrors V51 ``_compute_pair_zscore``.
    """
    if dp is None:
        return None
    other_df = _get_pair_df(target_pair, timeframe, dp, df_cache)
    if other_df is None or len(other_df) < zscore_window + cum_return_window:
        return None

    close = other_df["close"].values
    # log_ret computed but not stored (V51 compat — kept for identical flow)
    log_ret = np.log(close[1:] / close[:-1])  # noqa: F841
    log_ret = np.concatenate([[0.0], log_ret])  # noqa: F841

    close_s = pd.Series(other_df["close"].values)
    log_price = np.log(close_s)
    lp_mean = log_price.rolling(window=zscore_window).mean()
    lp_std = log_price.rolling(window=zscore_window).std()
    z = ((log_price - lp_mean) / lp_std.replace(0, np.nan)).fillna(0.0).values
    return z[-n:] if len(z) > n else z


def _get_cached_zscore(
    target_pair: str,
    current_pair: str,
    dataframe: DataFrame,
    n: int,
    pair_zscores_cache: dict,
    zscore_window: int,
    cum_return_window: int,
    timeframe: str,
    dp,
    df_cache: dict,
) -> np.ndarray | None:
    """Get z-score from cache (fast path) or compute on cache miss.

    Mirrors V51 ``_get_cached_zscore``.
    """
    # Fast path: current pair already has z-score in dataframe
    if target_pair == current_pair:
        return dataframe["pair_zscore"].values

    # Cache hit: use pre-computed z-score
    if target_pair in pair_zscores_cache:
        cached = pair_zscores_cache[target_pair]["pair_zscore"].values
        return cached[-n:] if len(cached) > n else cached

    # Cache miss: compute and cache
    return _compute_pair_zscore_for(
        target_pair, n, zscore_window, cum_return_window,
        timeframe, dp, df_cache,
    )


def _compute_log_spread(
    pair: str,
    dataframe: DataFrame,
    zscore_window: int,
    timeframe: str,
    dp,
    df_cache: dict,
    group_a: list[str],
    group_b: list[str],
) -> float | pd.Series:
    """Log Spread Z-Score: spread = mean(log(A)) - mean(log(B)), then z-scored.

    Mirrors V51 ``_compute_log_spread`` exactly.
    """
    if not group_a or not group_b or dp is None:
        return 0.0

    n = len(dataframe)

    def _get_log_price(target_pair: str) -> np.ndarray | None:
        if target_pair == pair:
            return np.log(dataframe["close"].values)
        other_df = _get_pair_df(target_pair, timeframe, dp, df_cache)
        if other_df is None or len(other_df) < 50:
            return None
        lp = np.log(other_df["close"].values)
        return lp[-n:] if len(lp) > n else lp

    group_a_lp: list[np.ndarray] = []
    group_b_lp: list[np.ndarray] = []
    for p in group_a:
        lp = _get_log_price(p)
        if lp is not None:
            group_a_lp.append(lp)
    for p in group_b:
        lp = _get_log_price(p)
        if lp is not None:
            group_b_lp.append(lp)

    if not group_a_lp or not group_b_lp:
        return 0.0

    min_len = min(
        min(len(x) for x in group_a_lp),
        min(len(x) for x in group_b_lp),
    )
    group_a_lp = [x[-min_len:] for x in group_a_lp]
    group_b_lp = [x[-min_len:] for x in group_b_lp]

    mean_a = (
        np.column_stack(group_a_lp).mean(axis=1)
        if len(group_a_lp) > 1
        else group_a_lp[0]
    )
    mean_b = (
        np.column_stack(group_b_lp).mean(axis=1)
        if len(group_b_lp) > 1
        else group_b_lp[0]
    )

    if len(mean_a) < n:
        pad = n - len(mean_a)
        mean_a = np.concatenate([np.full(pad, np.nan), mean_a])
        mean_b = np.concatenate([np.full(pad, np.nan), mean_b])

    spread = pd.Series(mean_a - mean_b, index=dataframe.index)
    spread_mean = spread.rolling(window=zscore_window).mean()
    spread_std = spread.rolling(window=zscore_window).std()
    return ((spread - spread_mean) / spread_std.replace(0, np.nan)).fillna(0.0)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_group_spread_z(
    dataframe: DataFrame,
    pair: str,
    cfg: dict,
    dp,
    df_cache: dict,
    sub1: list[str],
    sub2: list[str],
) -> pd.Series:
    """Compute spread z-score for a specific group. Returns Series, does not modify dataframe."""
    zscore_window = cfg["zscore"]["zscore_window"]
    timeframe = cfg["timeframe"]
    return _compute_log_spread(pair, dataframe, zscore_window, timeframe, dp, df_cache, sub1, sub2)


def compute(
    dataframe: DataFrame,
    pair: str,
    cfg: dict,
    dp,
    pair_zscores_cache: dict,
    df_cache: dict,
    group_a: list[str],
    group_b: list[str],
) -> DataFrame:
    """Compute per-pair z-score and spread z-score.

    Adds columns:
        log_return, pair_zscore, spread_zscore,
        pair_z_cross_up, pair_z_cross_down

    Updates *pair_zscores_cache* with this pair's z-score for spread
    calculation by other pairs.

    Config keys used:
        cfg["zscore"]["zscore_window"]
        cfg["zscore"]["cum_return_window"]
        cfg["timeframe"]
    """
    zscore_window: int = cfg["zscore"]["zscore_window"]
    cum_return_window: int = cfg["zscore"]["cum_return_window"]
    timeframe: str = cfg["timeframe"]

    # --- Per-pair z-score (Log Spread method) ---
    dataframe["log_return"] = np.log(
        dataframe["close"] / dataframe["close"].shift(1)
    )
    log_price = np.log(dataframe["close"])
    lp_mean = log_price.rolling(window=zscore_window).mean()
    lp_std = log_price.rolling(window=zscore_window).std()
    dataframe["pair_zscore"] = (
        (log_price - lp_mean) / lp_std.replace(0, np.nan)
    ).fillna(0.0)

    # Store in cache for cross-pair spread calculation
    pair_zscores_cache[pair] = dataframe[["pair_zscore"]].copy()

    # --- Spread z-score (Log Spread: log(A) - log(B), then z-scored) ---
    dataframe["spread_zscore"] = _compute_log_spread(
        pair, dataframe, zscore_window, timeframe, dp, df_cache,
        group_a, group_b,
    )

    # --- Z-score zero-cross signals (used by scalp exit) ---
    dataframe["pair_z_cross_up"] = (
        (dataframe["pair_zscore"] > 0)
        & (dataframe["pair_zscore"].shift(1) <= 0)
    ).astype(int)
    dataframe["pair_z_cross_down"] = (
        (dataframe["pair_zscore"] < 0)
        & (dataframe["pair_zscore"].shift(1) >= 0)
    ).astype(int)

    return dataframe
