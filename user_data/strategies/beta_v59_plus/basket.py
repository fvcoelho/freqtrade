"""Dynamic Basket Z-Score for V59Plus.

Improvements over V59:
    - Adaptive z-score window (shorter in consolidation via ATR)
    - Basket dispersion filter (blocks entries when basket is too tight)
    - RSI per pair for consolidation entry confirmation
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from pandas import DataFrame

logger = logging.getLogger(__name__)

_basket_cache: dict = {}


def _load_log_prices(all_pairs, n, timeframe, dp, df_cache, zscore_window):
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


def _get_basket_avg(all_pairs, n, timeframe, dp, df_cache, zscore_window):
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

    # Compute basket dispersion (std of normalized prices across pairs)
    dispersion = np.nanstd(np.column_stack(normalized), axis=1)

    _basket_cache = {"key": cache_key, "avg": basket_avg,
                     "log_prices": log_prices, "dispersion": dispersion}
    return basket_avg


def compute_basket_zscore(dataframe, pair, all_pairs, zscore_window,
                          timeframe, dp, df_cache, cfg=None):
    """Compute z-score with adaptive window and dispersion filter."""
    n = len(dataframe)
    basket_avg = _get_basket_avg(all_pairs, n, timeframe, dp, df_cache, zscore_window)
    if basket_avg is None:
        dataframe["basket_z"] = 0.0
        dataframe["basket_spread"] = 0.0
        dataframe["basket_dispersion"] = 0.0
        return dataframe

    cached = _basket_cache.get("log_prices", {})
    pair_lp = cached[pair] if pair in cached else np.log(dataframe["close"].values)

    first_valid = np.nan
    for v in pair_lp:
        if not np.isnan(v):
            first_valid = v
            break
    pair_norm = pair_lp - first_valid
    spread = pd.Series(pair_norm - basket_avg, index=dataframe.index)

    # Dispersion
    dispersion = _basket_cache.get("dispersion", np.zeros(n))
    if len(dispersion) == n:
        dataframe["basket_dispersion"] = dispersion
    else:
        dataframe["basket_dispersion"] = 0.0

    # Adaptive window: use shorter window in consolidation
    # Check if is_consolidation column exists (mapped from btc_trend)
    effective_window = zscore_window
    if "is_consolidation" in dataframe.columns:
        consol_pct = dataframe["is_consolidation"].tail(zscore_window).mean()
        if consol_pct > 0.5:
            # More than 50% of recent candles are consolidation → shorter window
            adaptive_factor = cfg.get("basket", {}).get("consol_window_factor", 0.6) if cfg else 0.6
            effective_window = max(50, int(zscore_window * adaptive_factor))

    method = cfg.get("basket", {}).get("zscore_method", "sma") if cfg else "sma"

    if method == "ewm":
        spread_mean = spread.ewm(span=effective_window).mean()
        spread_std = spread.ewm(span=effective_window).std()
    elif method == "kalman":
        kalman_gain = cfg.get("basket", {}).get("kalman_gain", 0.05) if cfg else 0.05
        # Adaptive kalman gain: higher in consolidation (more reactive)
        if "is_consolidation" in dataframe.columns:
            consol_pct = dataframe["is_consolidation"].tail(effective_window).mean()
            if consol_pct > 0.5:
                kalman_gain *= 1.5  # more reactive in consolidation

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
        spread_mean = spread.rolling(window=effective_window).mean()
        spread_std = spread.rolling(window=effective_window).std()

    basket_z = ((spread - spread_mean) / spread_std.replace(0, np.nan)).fillna(0.0)
    dataframe["basket_z"] = basket_z
    dataframe["basket_spread"] = spread

    # RSI for consolidation entry confirmation
    delta = dataframe["close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    dataframe["rsi"] = (100 - 100 / (1 + rs)).fillna(50)

    return dataframe


def generate_basket_entries(dataframe, pair, cfg):
    """Generate entry signals with regime-aware thresholds."""
    basket_cfg = cfg.get("basket", {})
    regime_params = cfg.get("regime_params", {})

    # Dynamic entry_z based on regime
    base_entry_z = basket_cfg.get("entry_z", 2.0)

    # Check regime — use vectorized columns
    is_consol = dataframe.get("is_consolidation", pd.Series(False, index=dataframe.index)).astype(bool)
    is_trend = dataframe.get("is_trending", pd.Series(False, index=dataframe.index)).astype(bool)

    consol_params = regime_params.get("consolidation", {})
    trend_params = regime_params.get("trending", {})

    consol_entry_z = consol_params.get("entry_z", base_entry_z + 0.5)
    trend_entry_z = trend_params.get("entry_z", base_entry_z - 0.3)

    # Per-candle entry_z
    entry_z = pd.Series(base_entry_z, index=dataframe.index)
    entry_z[is_consol] = consol_entry_z
    entry_z[is_trend] = trend_entry_z

    safe_long = ~dataframe.get("btc_dump", pd.Series(False, index=dataframe.index)).astype(bool)
    safe_short = ~dataframe.get("btc_pump", pd.Series(False, index=dataframe.index)).astype(bool)
    no_chaos = ~dataframe.get("btc_high_vol", pd.Series(False, index=dataframe.index)).astype(bool)
    vol = dataframe.get("vol_ok", pd.Series(1, index=dataframe.index)) == 1

    btc_mom = dataframe.get("btc_mom", pd.Series(0.0, index=dataframe.index))
    bear_threshold = basket_cfg.get("bear_mom_threshold", -1.0)
    bull_threshold = basket_cfg.get("bull_mom_threshold", 0.0)
    is_bear = btc_mom < bear_threshold
    is_bull = btc_mom > bull_threshold
    is_ranging = ~is_bull & ~is_bear

    no_long = dataframe["enter_long"] == 0
    no_short = dataframe["enter_short"] == 0

    # Dispersion filter: block weak entries when basket is too tight
    disp_min = basket_cfg.get("dispersion_min", 0.0)
    if disp_min > 0 and "basket_dispersion" in dataframe.columns:
        disp_ok = dataframe["basket_dispersion"] >= disp_min
    else:
        disp_ok = pd.Series(True, index=dataframe.index)

    # RSI filter for consolidation entries
    rsi_long_max = consol_params.get("rsi_long_max", 35)
    rsi_short_min = consol_params.get("rsi_short_min", 65)
    rsi = dataframe.get("rsi", pd.Series(50, index=dataframe.index))

    # In consolidation: require RSI confirmation
    rsi_ok_long = ~is_consol | (rsi < rsi_long_max)
    rsi_ok_short = ~is_consol | (rsi > rsi_short_min)

    # Z-crossing confirmation for consolidation
    # Require z was more extreme 3 candles ago (reverting, not diverging)
    bz = dataframe["basket_z"]
    bz_prev3 = bz.shift(3)
    z_reverting_long = ~is_consol | (bz > bz_prev3)   # z becoming less negative
    z_reverting_short = ~is_consol | (bz < bz_prev3)   # z becoming less positive

    # Bull: LONG lagging pair
    is_lagging = dataframe["basket_z"] < -entry_z
    mask_long = is_lagging & is_bull & safe_long & no_chaos & vol & no_long & disp_ok & rsi_ok_long & z_reverting_long
    dataframe.loc[mask_long, ["enter_long", "enter_tag"]] = (1, "basket_long")

    # Bear: SHORT leading pair
    is_leading = dataframe["basket_z"] > entry_z
    mask_short = is_leading & is_bear & safe_short & no_chaos & vol & no_short & disp_ok & rsi_ok_short & z_reverting_short
    dataframe.loc[mask_short, ["enter_short", "enter_tag"]] = (1, "basket_short")

    # Ranging: both (if enabled)
    no_long2 = dataframe["enter_long"] == 0
    no_short2 = dataframe["enter_short"] == 0
    ranging_long = cfg.get("queue", {}).get("ranging_long_enabled", False)
    ranging_short = cfg.get("queue", {}).get("ranging_short_enabled", False)
    if ranging_long:
        mask_long_r = is_lagging & is_ranging & safe_long & no_chaos & vol & no_long2 & disp_ok & rsi_ok_long & z_reverting_long
        dataframe.loc[mask_long_r, ["enter_long", "enter_tag"]] = (1, "basket_long")
    if ranging_short:
        mask_short_r = is_leading & is_ranging & safe_short & no_chaos & vol & no_short2 & disp_ok & rsi_ok_short & z_reverting_short
        dataframe.loc[mask_short_r, ["enter_short", "enter_tag"]] = (1, "basket_short")

    return dataframe


def check_basket_exit(pair, trade, current_profit, cfg, dp, df_cache,
                      timeframe, all_pairs):
    """Exit with regime-aware thresholds."""
    tag = trade.enter_tag or ""
    if not tag.startswith("basket_"):
        return None

    basket_cfg = cfg.get("basket", {})
    exit_z = basket_cfg.get("exit_z", 0.3)
    profit_lock = basket_cfg.get("profit_lock", 0.002)
    loss_exit_z = basket_cfg.get("loss_exit_z", -4.0)
    zscore_window = cfg["zscore"]["zscore_window"]

    pair_df = df_cache.get(f"{pair}__{timeframe}")
    if pair_df is None and dp:
        pair_df = dp.get_pair_dataframe(pair=pair, timeframe=timeframe)
    if pair_df is None or len(pair_df) < zscore_window:
        return None

    temp_df = pair_df.tail(zscore_window * 2).copy().reset_index(drop=True)
    compute_basket_zscore(temp_df, pair, all_pairs, zscore_window, timeframe, dp, df_cache)

    if "basket_z" not in temp_df.columns:
        return None
    current_z = temp_df["basket_z"].iloc[-1]

    # Dynamic exit_z: tighter in consolidation
    is_consol = False
    if "is_consolidation" in pair_df.columns and len(pair_df) > 0:
        is_consol = bool(pair_df["is_consolidation"].iloc[-1])

    if is_consol:
        consol_params = cfg.get("regime_params", {}).get("consolidation", {})
        exit_z = consol_params.get("exit_z", exit_z + 0.1)

    is_long = not trade.is_short
    max_loss = basket_cfg.get("max_loss_per_trade", -0.10)
    if current_profit < max_loss:
        return "basket_max_loss"

    if is_long:
        if current_z > -exit_z and current_profit > profit_lock:
            return "basket_revert_profit"
        if current_z > 0 and current_profit > 0:
            return "basket_revert_neutral"
        if current_z < loss_exit_z and current_profit < -0.02:
            return "basket_diverge_stop"
    else:
        if current_z < exit_z and current_profit > profit_lock:
            return "basket_revert_profit"
        if current_z < 0 and current_profit > 0:
            return "basket_revert_neutral"
        if current_z > -loss_exit_z and current_profit < -0.02:
            return "basket_diverge_stop"

    return None
