"""Dynamic Basket Z-Score for V57.

All pairs in a single basket. Each candle, compute how far each pair
diverged from the basket average. Pairs with extreme z-scores are
candidates for mean-reversion trades.

Concept:
    basket_avg = mean(normalized log prices of all pairs)
    pair_z = z-score(pair - basket_avg)

    pair_z << 0 → pair lagging behind basket → LONG (catch-up)
    pair_z ≈ 0  → pair at basket mean → close position

Performance: basket_avg is computed ONCE per cycle and cached.
Each pair only computes its own spread vs the cached average.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from pandas import DataFrame

logger = logging.getLogger(__name__)

# Module-level cache for basket average (shared across all pairs in a cycle)
_basket_cache: dict = {}


def _load_log_prices(
    all_pairs: list[str],
    n: int,
    timeframe: str,
    dp,
    df_cache: dict,
    zscore_window: int,
) -> dict[str, np.ndarray]:
    """Load and cache log prices for all pairs. Returns {pair: log_price_array}."""
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
    """Get cached basket average, or compute and cache it.

    Cache key is (n, tuple(all_pairs)) — invalidated when dataframe
    length changes (new cycle).
    """
    global _basket_cache
    cache_key = (n, id(dp))  # dp changes each backtest cycle

    if "key" in _basket_cache and _basket_cache["key"] == cache_key:
        return _basket_cache["avg"]

    # Compute fresh
    log_prices = _load_log_prices(all_pairs, n, timeframe, dp, df_cache, zscore_window)

    if len(log_prices) < 3:
        return None

    # Normalize: subtract first valid value so all start at 0
    normalized = []
    for lp in log_prices.values():
        first_valid = np.nan
        for v in lp:
            if not np.isnan(v):
                first_valid = v
                break
        normalized.append(lp - first_valid)

    basket_avg = np.nanmean(np.column_stack(normalized), axis=1)

    # Cache it
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

    Adds columns:
        basket_z      — z-score of this pair vs basket (negative = lagging)
        basket_spread — raw spread (pair normalized log price - basket avg)

    Z-score method controlled by basket.zscore_method:
        "sma" (default) — Simple Moving Average, equal weight
        "ewm"           — Exponential Weighted Mean, recent candles weigh more

    Uses cached basket average — fast for 20+ pairs.
    """
    n = len(dataframe)

    basket_avg = _get_basket_avg(all_pairs, n, timeframe, dp, df_cache, zscore_window)
    if basket_avg is None:
        dataframe["basket_z"] = 0.0
        dataframe["basket_spread"] = 0.0
        return dataframe

    # This pair's log price (from cache or dataframe)
    cached = _basket_cache.get("log_prices", {})
    if pair in cached:
        pair_lp = cached[pair]
    else:
        pair_lp = np.log(dataframe["close"].values)

    # Normalize same as basket
    first_valid = np.nan
    for v in pair_lp:
        if not np.isnan(v):
            first_valid = v
            break
    pair_norm = pair_lp - first_valid

    # Spread vs basket
    spread = pd.Series(pair_norm - basket_avg, index=dataframe.index)

    # Z-score method: configurable via basket.zscore_method
    # "sma"      — Simple Moving Average (default, stable, more signals)
    # "ewm"      — Exponential Weighted Mean (reactive, fewer signals)
    # "vwap"     — Volume Weighted (ignores low-volume noise)
    # "kalman"   — Kalman Filter (adaptive window, self-tuning)
    # "halflife" — Half-Life adaptive window (window = speed of mean reversion)
    method = cfg.get("basket", {}).get("zscore_method", "sma") if cfg else "sma"

    if method == "ewm":
        spread_mean = spread.ewm(span=zscore_window).mean()
        spread_std = spread.ewm(span=zscore_window).std()

    elif method == "vwap":
        vol = dataframe["volume"].values
        close = dataframe["close"].values
        cum_vol = pd.Series(vol).rolling(zscore_window).sum()
        cum_pv = pd.Series(close * vol).rolling(zscore_window).sum()
        vwap = cum_pv / cum_vol.replace(0, np.nan)
        vwap_spread = pd.Series(close, index=dataframe.index) / vwap.values - 1.0
        spread_for_z = vwap_spread.fillna(0.0)
        spread_mean = spread_for_z.rolling(window=zscore_window).mean()
        spread_std = spread_for_z.rolling(window=zscore_window).std()
        spread = spread_for_z

    elif method == "kalman":
        # Kalman Filter: adaptive mean estimation
        # State = [mean, velocity], observation = spread value
        # The filter adapts its estimate based on prediction error
        kalman_gain = cfg.get("basket", {}).get("kalman_gain", 0.05)
        estimated_mean = spread.copy()
        estimated_var = spread.copy()

        km = spread.iloc[0] if not np.isnan(spread.iloc[0]) else 0.0
        kv = 1.0  # initial variance estimate

        means = np.zeros(len(spread))
        variances = np.zeros(len(spread))

        for i in range(len(spread)):
            val = spread.iloc[i]
            if np.isnan(val):
                means[i] = km
                variances[i] = kv
                continue
            # Prediction error
            err = val - km
            # Update mean estimate (Kalman gain controls reactivity)
            km = km + kalman_gain * err
            # Update variance estimate (exponential smoothing)
            kv = (1 - kalman_gain) * kv + kalman_gain * err * err
            means[i] = km
            variances[i] = kv

        spread_mean = pd.Series(means, index=spread.index)
        spread_std = pd.Series(np.sqrt(variances), index=spread.index)

    elif method == "halflife":
        # Half-Life: compute mean-reversion speed, use as adaptive window
        # Regression: spread(t) = alpha + beta * spread(t-1) + epsilon
        # half_life = -log(2) / log(beta)
        min_hl = 12   # minimum 1 hour
        max_hl = 576  # maximum 2 days
        hl_calc_window = zscore_window

        spread_lag = spread.shift(1)
        valid = ~(spread.isna() | spread_lag.isna())

        # Rolling OLS to get beta
        xy = (spread * spread_lag).rolling(hl_calc_window).mean()
        x_mean = spread_lag.rolling(hl_calc_window).mean()
        y_mean = spread.rolling(hl_calc_window).mean()
        x2 = (spread_lag ** 2).rolling(hl_calc_window).mean()
        beta = (xy - x_mean * y_mean) / (x2 - x_mean ** 2).replace(0, np.nan)
        beta = beta.clip(0.001, 0.999)  # avoid log(0) or log(negative)

        half_life = (-np.log(2) / np.log(beta)).clip(min_hl, max_hl).fillna(zscore_window)

        # Use half_life as adaptive rolling window
        # Approximation: use median half_life for the rolling window
        adaptive_window = int(half_life.median())
        adaptive_window = max(min_hl, min(max_hl, adaptive_window))

        spread_mean = spread.rolling(window=adaptive_window).mean()
        spread_std = spread.rolling(window=adaptive_window).std()

    else:  # sma (default)
        spread_mean = spread.rolling(window=zscore_window).mean()
        spread_std = spread.rolling(window=zscore_window).std()

    basket_z = ((spread - spread_mean) / spread_std.replace(0, np.nan)).fillna(0.0)

    dataframe["basket_z"] = basket_z
    dataframe["basket_spread"] = spread
    return dataframe


def generate_basket_entries(
    dataframe: DataFrame,
    pair: str,
    cfg: dict,
) -> DataFrame:
    """Generate entry signals based on basket z-score + BTC regime.

    Bear market (btc_mom < 0): SHORT the pair AHEAD of basket (z > +entry)
    Bull/ranging market:       LONG the pair BEHIND basket (z < -entry)

    The regime adapts automatically each candle — no manual switching.
    """
    basket_cfg = cfg.get("basket", {})
    entry_z = basket_cfg.get("entry_z", 2.0)

    safe_long = ~dataframe.get("btc_dump", pd.Series(False, index=dataframe.index)).astype(bool)
    safe_short = ~dataframe.get("btc_pump", pd.Series(False, index=dataframe.index)).astype(bool)
    no_chaos = ~dataframe.get("btc_high_vol", pd.Series(False, index=dataframe.index)).astype(bool)
    vol = dataframe.get("vol_ok", pd.Series(1, index=dataframe.index)) == 1

    # Regime: use BTC momentum to decide direction
    btc_mom = dataframe.get("btc_mom", pd.Series(0.0, index=dataframe.index))
    bear_threshold = basket_cfg.get("bear_mom_threshold", -1.0)
    bull_threshold = basket_cfg.get("bull_mom_threshold", 0.0)
    is_bear = btc_mom < bear_threshold
    is_bull = btc_mom > bull_threshold

    no_long = dataframe["enter_long"] == 0
    no_short = dataframe["enter_short"] == 0

    # Bull only: LONG the lagging pair (z << 0, behind basket)
    is_lagging = dataframe["basket_z"] < -entry_z
    mask_long = is_lagging & is_bull & safe_long & no_chaos & vol & no_long
    dataframe.loc[mask_long, ["enter_long", "enter_tag"]] = (1, "basket_long")

    # Bear: SHORT the leading pair (z >> 0, ahead of basket)
    is_leading = dataframe["basket_z"] > entry_z
    mask_short = is_leading & is_bear & safe_short & no_chaos & vol & no_short
    dataframe.loc[mask_short, ["enter_short", "enter_tag"]] = (1, "basket_short")

    return dataframe


def check_basket_exit(
    pair: str,
    trade,
    current_profit: float,
    cfg: dict,
    dp,
    df_cache: dict,
    timeframe: str,
    all_pairs: list[str],
) -> str | None:
    """Exit when pair's basket z-score reverts toward zero."""
    tag = trade.enter_tag or ""
    if not tag.startswith("basket_"):
        return None

    basket_cfg = cfg.get("basket", {})
    exit_z = basket_cfg.get("exit_z", 0.3)
    profit_lock = basket_cfg.get("profit_lock", 0.002)
    loss_exit_z = basket_cfg.get("loss_exit_z", -4.0)
    zscore_window = cfg["zscore"]["zscore_window"]

    # Get current pair data
    pair_df = df_cache.get(f"{pair}__{timeframe}")
    if pair_df is None and dp:
        pair_df = dp.get_pair_dataframe(pair=pair, timeframe=timeframe)
    if pair_df is None or len(pair_df) < zscore_window:
        return None

    # Compute current basket z (uses cached basket_avg)
    temp_df = pair_df.tail(zscore_window * 2).copy().reset_index(drop=True)
    compute_basket_zscore(temp_df, pair, all_pairs, zscore_window, timeframe, dp, df_cache)

    if "basket_z" not in temp_df.columns:
        return None
    current_z = temp_df["basket_z"].iloc[-1]

    is_long = not trade.is_short

    # 0. Safety net: max loss per trade (catastrophe protection)
    max_loss = basket_cfg.get("max_loss_per_trade", -0.10)
    if current_profit < max_loss:
        return "basket_max_loss"

    if is_long:
        # Long: z reverted up toward 0
        if current_z > -exit_z and current_profit > profit_lock:
            return "basket_revert_profit"
        if current_z > 0 and current_profit > 0:
            return "basket_revert_neutral"
        if current_z < loss_exit_z and current_profit < -0.02:
            return "basket_diverge_stop"
    else:
        # Short: z reverted down toward 0
        if current_z < exit_z and current_profit > profit_lock:
            return "basket_revert_profit"
        if current_z < 0 and current_profit > 0:
            return "basket_revert_neutral"
        if current_z > -loss_exit_z and current_profit < -0.02:
            return "basket_diverge_stop"

    return None
