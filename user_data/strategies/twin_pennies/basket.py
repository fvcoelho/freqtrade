"""Dynamic Basket Z-Score for TwinPennies.

All pairs in a single basket. Each candle, compute how far each pair
diverged from the basket average. Pairs with extreme z-scores are
candidates for mean-reversion trades.

    basket_avg = mean(normalized log prices of all pairs)
    pair_z = z-score(pair - basket_avg)

    pair_z << 0 -> pair lagging behind basket -> LONG (catch-up)
    pair_z >> 0 -> pair ahead of basket -> SHORT (revert)
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from pandas import DataFrame

logger = logging.getLogger(__name__)

_basket_cache: dict = {}


def _load_log_prices(
    all_pairs: list[str],
    n: int,
    timeframe: str,
    dp,
    df_cache: dict,
    zscore_window: int,
) -> dict[str, np.ndarray]:
    log_prices = {}
    for p in all_pairs:
        key = f"{p}__{timeframe}"
        if key in df_cache:
            other_df = df_cache[key]
        elif dp is not None:
            other_df = dp.get_pair_dataframe(pair=p, timeframe=timeframe)
            if other_df is not None:
                df_cache[key] = other_df
        else:
            continue

        if other_df is None or len(other_df) < zscore_window:
            continue

        lp = np.log(other_df["close"].values)
        lp = lp[-n:] if len(lp) > n else lp
        if len(lp) < n:
            lp = np.concatenate([np.full(n - len(lp), np.nan), lp])
        log_prices[p] = lp

    return log_prices


def _get_basket_avg(
    all_pairs: list[str],
    n: int,
    timeframe: str,
    dp,
    df_cache: dict,
    zscore_window: int,
) -> np.ndarray | None:
    global _basket_cache
    cache_key = (n, id(dp))

    if "key" in _basket_cache and _basket_cache["key"] == cache_key:
        return _basket_cache["avg"]

    log_prices = _load_log_prices(all_pairs, n, timeframe, dp, df_cache, zscore_window)

    if len(log_prices) < 3:
        return None

    normalized = []
    for lp in log_prices.values():
        first_valid = np.nan
        for v in lp:
            if not np.isnan(v):
                first_valid = v
                break
        normalized.append(lp - first_valid)

    basket_avg = np.nanmean(np.column_stack(normalized), axis=1)

    _basket_cache = {"key": cache_key, "avg": basket_avg, "log_prices": log_prices}
    return basket_avg


def compute_basket_zscore(
    dataframe: DataFrame,
    pair: str,
    all_pairs: list[str],
    zscore_window: int,
    timeframe: str,
    dp,
    df_cache: dict,
    cfg: dict | None = None,
) -> DataFrame:
    """Compute this pair's z-score relative to the basket average.

    Adds columns: basket_z, basket_spread

    Z-score method controlled by basket.zscore_method:
        "sma" (default), "ewm", "kalman"
    """
    n = len(dataframe)

    basket_avg = _get_basket_avg(all_pairs, n, timeframe, dp, df_cache, zscore_window)
    if basket_avg is None:
        dataframe["basket_z"] = 0.0
        dataframe["basket_spread"] = 0.0
        return dataframe

    cached = _basket_cache.get("log_prices", {})
    if pair in cached:
        pair_lp = cached[pair]
    else:
        pair_lp = np.log(dataframe["close"].values)

    first_valid = np.nan
    for v in pair_lp:
        if not np.isnan(v):
            first_valid = v
            break
    pair_norm = pair_lp - first_valid

    spread = pd.Series(pair_norm - basket_avg, index=dataframe.index)

    method = cfg.get("basket", {}).get("zscore_method", "sma") if cfg else "sma"

    if method == "ewm":
        spread_mean = spread.ewm(span=zscore_window).mean()
        spread_std = spread.ewm(span=zscore_window).std()

    elif method == "kalman":
        kalman_gain = cfg.get("basket", {}).get("kalman_gain", 0.05)
        km = spread.iloc[0] if not np.isnan(spread.iloc[0]) else 0.0
        kv = 1.0

        means = np.zeros(len(spread))
        variances = np.zeros(len(spread))

        for i in range(len(spread)):
            val = spread.iloc[i]
            if np.isnan(val):
                means[i] = km
                variances[i] = kv
                continue
            err = val - km
            km = km + kalman_gain * err
            kv = (1 - kalman_gain) * kv + kalman_gain * err * err
            means[i] = km
            variances[i] = kv

        spread_mean = pd.Series(means, index=spread.index)
        spread_std = pd.Series(np.sqrt(variances), index=spread.index)

    else:  # sma
        spread_mean = spread.rolling(window=zscore_window).mean()
        spread_std = spread.rolling(window=zscore_window).std()

    basket_z = ((spread - spread_mean) / spread_std.replace(0, np.nan)).fillna(0.0)

    dataframe["basket_z"] = basket_z
    dataframe["basket_spread"] = spread
    return dataframe
