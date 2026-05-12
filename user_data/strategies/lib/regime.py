"""Regime filter and spread volatility filter — pure functional extraction from V51."""

import numpy as np
from pandas import DataFrame


def _get_pair_df(pair: str, timeframe: str, dp, df_cache: dict) -> DataFrame:
    """Cached wrapper around dp.get_pair_dataframe."""
    key = f"{pair}__{timeframe}"
    if key in df_cache:
        return df_cache[key]
    df = dp.get_pair_dataframe(pair, timeframe)
    df_cache[key] = df
    return df


def _get_returns(
    target_pair: str,
    current_pair: str,
    dataframe: DataFrame,
    dp,
    df_cache: dict,
    timeframe: str,
) -> "pd.Series | None":
    """Get log returns for a pair, aligned to the current dataframe length."""
    if target_pair == current_pair:
        other_df = dataframe
    else:
        other_df = _get_pair_df(target_pair, timeframe, dp, df_cache)

    if len(other_df) == 0:
        return None

    ret = np.log(other_df["close"] / other_df["close"].shift(1))
    ret = ret.iloc[-len(dataframe):]
    ret = ret.reset_index(drop=True)
    return ret


def compute(
    dataframe: DataFrame,
    pair: str,
    cfg: dict,
    dp,
    df_cache: dict,
    timeframe: str,
    group_a: list,
    group_b: list,
) -> DataFrame:
    """Add regime filter columns: rolling_corr, regime_ok.

    Config keys used: regime.regime_window, regime_corr_min, use_ewm_corr, ewm_span
    """
    c = cfg["regime"]

    if "regime_ok" in dataframe:
        return dataframe

    # Collect returns for group_a
    returns_a = []
    for p in group_a:
        r = _get_returns(p, pair, dataframe, dp, df_cache, timeframe)
        if r is not None:
            returns_a.append(r)

    # Collect returns for group_b
    returns_b = []
    for p in group_b:
        r = _get_returns(p, pair, dataframe, dp, df_cache, timeframe)
        if r is not None:
            returns_b.append(r)

    # Average returns for each group
    ret_a = sum(returns_a) / len(returns_a)
    ret_b = sum(returns_b) / len(returns_b)

    if c.get("use_ewm_corr", False):
        ewm_span = c["ewm_span"]
        ewm_cov = ret_a.ewm(span=ewm_span).cov(ret_b)
        ewm_std_a = ret_a.ewm(span=ewm_span).std()
        ewm_std_b = ret_b.ewm(span=ewm_span).std()
        rolling_corr = (ewm_cov / (ewm_std_a * ewm_std_b)).replace(np.nan, 0).fillna(0)
    else:
        rolling_corr = (
            ret_a.rolling(c["regime_window"])
            .corr(ret_b)
            .replace(np.nan, 0)
            .fillna(0)
        )

    dataframe["rolling_corr"] = rolling_corr
    dataframe["regime_ok"] = (abs(rolling_corr) >= c["regime_corr_min"]).astype(int)

    return dataframe


def compute_spread_vol(dataframe: DataFrame, cfg: dict) -> DataFrame:
    """Add spread volatility filter columns: spread_vol_z, spread_vol_ok.

    Must be called after spread_zscore column exists in the dataframe.

    Config keys used: regime.spread_vol_filter, spread_vol_window, spread_vol_max_z
    """
    c = cfg["regime"]

    if not c.get("spread_vol_filter", False):
        dataframe["spread_vol_z"] = 0
        dataframe["spread_vol_ok"] = 1
        return dataframe

    window = c["spread_vol_window"]
    spread_std = dataframe["spread_zscore"].rolling(window).std()
    spread_std_mean = spread_std.rolling(window).mean()
    spread_std_std = spread_std.rolling(window).std()

    dataframe["spread_vol_z"] = (
        (spread_std - spread_std_mean) / spread_std_std
    ).replace(np.nan, 0).fillna(0)

    dataframe["spread_vol_ok"] = (
        dataframe["spread_vol_z"] <= c["spread_vol_max_z"]
    ).astype(int)

    return dataframe
