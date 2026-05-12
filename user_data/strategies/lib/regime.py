"""Regime filter and spread volatility filter — pure functional extraction from V51."""

import numpy as np
from pandas import DataFrame


def _get_pair_df(pair: str, timeframe: str, dp, df_cache: dict) -> DataFrame | None:
    """Cached wrapper around dp.get_pair_dataframe."""
    key = f"{pair}__{timeframe}"
    if key in df_cache:
        return df_cache[key]
    if not dp:
        return None
    df = dp.get_pair_dataframe(pair=pair, timeframe=timeframe)
    if df is not None:
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
        return dataframe["log_return"]
    if not dp:
        return None
    other_df = _get_pair_df(target_pair, timeframe, dp, df_cache)
    if other_df is None or len(other_df) < 50:
        return None
    ret = np.log(other_df["close"] / other_df["close"].shift(1))
    return ret.iloc[-len(dataframe):].reset_index(drop=True)


def compute(
    dataframe: DataFrame,
    pair: str,
    cfg: dict,
    dp,
    df_cache: dict,
    timeframe: str,
    group_a: list[str],
    group_b: list[str],
) -> DataFrame:
    """Add regime filter columns: rolling_corr, regime_ok.

    Config keys used: regime.regime_window, regime_corr_min, use_ewm_corr, ewm_span
    """
    c = cfg["regime"]

    if not group_a or not group_b or not dp:
        dataframe["regime_ok"] = 1
        return dataframe

    ret_a = _get_returns(group_a[0], pair, dataframe, dp, df_cache, timeframe)
    ret_b = _get_returns(group_b[0], pair, dataframe, dp, df_cache, timeframe)

    if ret_a is not None and ret_b is not None:
        if c["use_ewm_corr"]:
            ewm_span = c["ewm_span"]
            ewm_cov = ret_a.ewm(span=ewm_span).cov(ret_b)
            ewm_std_a = ret_a.ewm(span=ewm_span).std()
            ewm_std_b = ret_b.ewm(span=ewm_span).std()
            rolling_corr = (ewm_cov / (ewm_std_a * ewm_std_b).replace(0, np.nan)).fillna(0.0)
        else:
            rolling_corr = ret_a.rolling(window=c["regime_window"]).corr(ret_b)
        dataframe["rolling_corr"] = rolling_corr.fillna(0.0)
        dataframe["regime_ok"] = (rolling_corr.abs() > c["regime_corr_min"]).astype(int).fillna(0)
    else:
        dataframe["rolling_corr"] = 0.0
        dataframe["regime_ok"] = 1

    return dataframe


def compute_spread_vol(dataframe: DataFrame, cfg: dict) -> DataFrame:
    """Add spread volatility filter columns: spread_vol_z, spread_vol_ok.

    Must be called after spread_zscore column exists in the dataframe.

    Config keys used: regime.spread_vol_filter, spread_vol_window, spread_vol_max_z
    """
    c = cfg["regime"]

    if c["spread_vol_filter"]:
        window = c["spread_vol_window"]
        spread_std = dataframe["spread_zscore"].rolling(window).std()
        spread_std_mean = spread_std.rolling(window).mean()
        spread_std_std = spread_std.rolling(window).std().replace(0, np.nan)
        dataframe["spread_vol_z"] = ((spread_std - spread_std_mean) / spread_std_std).fillna(0.0)
        dataframe["spread_vol_ok"] = (dataframe["spread_vol_z"] < c["spread_vol_max_z"]).astype(int)
    else:
        dataframe["spread_vol_ok"] = 1

    return dataframe
