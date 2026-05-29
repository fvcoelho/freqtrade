"""Cross-pair features: beta, lead-lag, relative strength, correlation, spread metrics."""
from __future__ import annotations

import numpy as np
import pandas as pd
from pandas import DataFrame


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _rolling_beta(pair_ret: pd.Series, ref_ret: pd.Series, window: int) -> pd.Series:
    """Rolling beta of pair_ret vs ref_ret via covariance / variance.

    :param pair_ret: Per-candle returns for the pair being featurised.
    :param ref_ret: Per-candle returns for the reference asset (BTC or ETH).
    :param window: Rolling window size in candles.
    :return: Series of rolling beta values, aligned to pair_ret index.
    """
    cov = pair_ret.rolling(window).cov(ref_ret)
    var = ref_ret.rolling(window).var()
    beta = cov / var.replace(0, np.nan)
    return beta.fillna(0.0)


def _lead_lag_score(pair_ret: pd.Series, ref_ret: pd.Series, max_lag: int = 6) -> float:
    """Scalar lead-lag score: signed lag at which cross-correlation is maximised.

    Positive value → pair leads ref; negative → pair lags ref.

    :param pair_ret: Per-candle return series for the pair.
    :param ref_ret: Per-candle return series for the reference asset.
    :param max_lag: Maximum lag to test in each direction.
    :return: Signed lag integer cast to float.
    """
    # Require enough data
    min_len = max_lag * 4
    p = pair_ret.dropna()
    r = ref_ret.dropna()
    common = p.index.intersection(r.index)
    if len(common) < min_len:
        return 0.0

    p = p.loc[common].values
    r = r.loc[common].values

    best_corr = -np.inf
    best_lag = 0
    for lag in range(-max_lag, max_lag + 1):
        if lag == 0:
            c = np.corrcoef(p, r)[0, 1]
        elif lag > 0:
            # pair leads ref by `lag` candles
            c = np.corrcoef(p[lag:], r[:-lag])[0, 1]
        else:
            # pair lags ref by `|lag|` candles
            ab = abs(lag)
            c = np.corrcoef(p[:-ab], r[ab:])[0, 1]
        if np.isfinite(c) and c > best_corr:
            best_corr = c
            best_lag = lag

    return float(best_lag)


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
    """Add 8 cross-pair %-features to *df* in-place and return it.

    Features added:
        %-beta_btc        Rolling beta vs BTC
        %-beta_eth        Rolling beta vs ETH
        %-lead_lag_btc    Lead-lag score vs BTC (scalar broadcast)
        %-rel_strength    Relative strength vs basket (cum-return diff)
        %-corr_rank       Average Pearson correlation with all other pairs
        %-spread_vel_rank Rolling mean of spread velocity (first diff of log-price)
        %-spread_div      Spread divergence z-score
        %-pair_momentum   12-candle rolling return sum

    When BTC/ETH/basket data is unavailable (no dp, empty df_cache) all
    features default to 0.0.

    :param df: OHLCV dataframe for the pair being featurised.
    :param pair: Pair symbol, e.g. ``"BTC/USDC:USDC"``.
    :param cfg: Config dict (uses ``cfg["scanner"]["correlation_window"]``).
    :param dp: DataProvider instance (optional); used to pull BTC/ETH candles.
    :param all_pairs: All pairs in the universe (optional).
    :param df_cache: Pre-fetched {pair: DataFrame} cache (optional).
    :return: Same dataframe with 8 new ``%-`` columns.
    """
    window: int = cfg.get("scanner", {}).get("correlation_window", 144)
    n = len(df)

    # ------------------------------------------------------------------
    # Pair returns
    # ------------------------------------------------------------------
    pair_ret = df["close"].pct_change()

    # ------------------------------------------------------------------
    # Helpers: resolve reference dataframes
    # ------------------------------------------------------------------
    def _get_ref_df(ref_pair: str) -> DataFrame | None:
        if df_cache and ref_pair in df_cache:
            rdf = df_cache[ref_pair]
            if rdf is not None and not rdf.empty:
                return rdf
        if dp is not None:
            try:
                # DataProvider.get_pair_dataframe returns an empty df, not None
                rdf = dp.get_pair_dataframe(ref_pair, df.attrs.get("timeframe", "5m"))
                if rdf is not None and not rdf.empty:
                    return rdf
            except Exception:
                pass
        return None

    BTC = "BTC/USDC:USDC"
    ETH = "ETH/USDC:USDC"

    btc_df = _get_ref_df(BTC)
    eth_df = _get_ref_df(ETH)

    def _align_ret(ref_df: DataFrame | None) -> pd.Series | None:
        """Return a return series aligned to df's index, or None."""
        if ref_df is None or ref_df.empty:
            return None
        ref_ret = ref_df.set_index("date")["close"].pct_change() if "date" in ref_df.columns else ref_df["close"].pct_change()
        # align by positional length if indexes differ
        if len(ref_ret) >= n:
            ref_ret = ref_ret.iloc[-n:]
            ref_ret.index = df.index
        elif len(ref_ret) < n:
            # pad front with zeros
            pad = pd.Series(0.0, index=df.index[: n - len(ref_ret)])
            ref_ret = pd.concat([pad, ref_ret.reset_index(drop=True).set_axis(df.index[n - len(ref_ret):])])
        return ref_ret

    btc_ret = _align_ret(btc_df)
    eth_ret = _align_ret(eth_df)

    # ------------------------------------------------------------------
    # 1. %-beta_btc
    # ------------------------------------------------------------------
    if btc_ret is not None:
        df["%-beta_btc"] = _rolling_beta(pair_ret, btc_ret, window)
    else:
        df["%-beta_btc"] = 0.0

    # ------------------------------------------------------------------
    # 2. %-beta_eth
    # ------------------------------------------------------------------
    if eth_ret is not None:
        df["%-beta_eth"] = _rolling_beta(pair_ret, eth_ret, window)
    else:
        df["%-beta_eth"] = 0.0

    # ------------------------------------------------------------------
    # 3. %-lead_lag_btc  (scalar broadcast over entire df)
    # ------------------------------------------------------------------
    if btc_ret is not None:
        score = _lead_lag_score(pair_ret, btc_ret, max_lag=6)
    else:
        score = 0.0
    df["%-lead_lag_btc"] = score

    # ------------------------------------------------------------------
    # 4. %-rel_strength  — cumulative return of pair minus basket mean
    # ------------------------------------------------------------------
    basket_rets: list[pd.Series] = []
    if df_cache:
        for p, pdf in df_cache.items():
            if p == pair or pdf is None or pdf.empty:
                continue
            r = _align_ret(pdf)
            if r is not None:
                basket_rets.append(r)

    if basket_rets:
        basket_mean = pd.concat(basket_rets, axis=1).mean(axis=1)
        pair_cum = (1 + pair_ret).cumprod() - 1
        basket_cum = (1 + basket_mean).cumprod() - 1
        df["%-rel_strength"] = (pair_cum - basket_cum).fillna(0.0)
    else:
        df["%-rel_strength"] = 0.0

    # ------------------------------------------------------------------
    # 5. %-corr_rank  — average |Pearson corr| with other pairs (rolling)
    # ------------------------------------------------------------------
    if basket_rets:
        corr_vals = pd.concat(
            [pair_ret.rolling(window).corr(r) for r in basket_rets], axis=1
        ).mean(axis=1)
        df["%-corr_rank"] = corr_vals.fillna(0.0)
    else:
        df["%-corr_rank"] = 0.0

    # ------------------------------------------------------------------
    # 6. %-spread_vel_rank  — rolling mean of first diff of log close
    # ------------------------------------------------------------------
    log_close = np.log(df["close"].replace(0, np.nan))
    spread_vel = log_close.diff()
    df["%-spread_vel_rank"] = spread_vel.rolling(window).mean().fillna(0.0)

    # ------------------------------------------------------------------
    # 7. %-spread_div  — spread divergence z-score of log close diff
    # ------------------------------------------------------------------
    sv_mean = spread_vel.rolling(window).mean()
    sv_std = spread_vel.rolling(window).std()
    df["%-spread_div"] = ((spread_vel - sv_mean) / sv_std.replace(0, np.nan)).fillna(0.0)

    # ------------------------------------------------------------------
    # 8. %-pair_momentum  — 12-candle rolling return sum
    # ------------------------------------------------------------------
    df["%-pair_momentum"] = pair_ret.rolling(12).sum().fillna(0.0)

    return df
