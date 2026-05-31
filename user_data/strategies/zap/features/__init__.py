"""Feature computation dispatcher with importance-based pruning."""
from __future__ import annotations

from pandas import DataFrame

# Features to KEEP based on feature importance analysis (April 2026 backtest).
# Everything else computed by sub-modules gets dropped to reduce noise/overfitting.
# Top features per category (consistently >2% importance across BTC/XRP/ADA/LINK):
KEEP_FEATURES = {
    # statistical — coint_score is #1 for all alts
    "%-coint_score", "%-coint_score_fast", "%-coint_score_slow", "%-log_spread",
    # momentum
    "%-adx", "%-macd_signal", "%-ema_slope_8", "%-ema_slope_21",
    # volatility
    "%-atr", "%-atr_pctile", "%-vol_weighted_vol", "%-bb_width", "%-vol_ratio_sl",
    # microstructure
    "%-cvd", "%-vwap_dev",
    # cross_pair
    "%-beta_btc", "%-beta_eth", "%-spread_vel_rank", "%-corr_rank", "%-rel_strength",
    # macro
    "%-btc_momentum", "%-btc_adx", "%-btc_dom_delta", "%-mkt_vol_index", "%-alt_corr_btc",
}


def compute_all_features(
    df: DataFrame,
    pair: str,
    cfg: dict,
    dp=None,
    all_pairs=None,
    btc_df=None,
    df_cache=None,
) -> DataFrame:
    """Compute all features for a single pair. Adds %-prefixed columns.

    After computation, prunes low-importance features to reduce overfitting.
    """
    df_cache = df_cache or {}
    all_pairs = all_pairs or []

    try:
        from zap.features.statistical import compute as compute_statistical
        df = compute_statistical(df, pair, cfg, dp, all_pairs, df_cache)
    except ImportError:
        pass

    try:
        from zap.features.momentum import compute as compute_momentum
        df = compute_momentum(df, cfg)
    except ImportError:
        pass

    try:
        from zap.features.microstructure import compute as compute_microstructure
        df = compute_microstructure(df, cfg)
    except ImportError:
        pass

    try:
        from zap.features.cross_pair import compute as compute_cross_pair
        df = compute_cross_pair(df, pair, cfg, dp, all_pairs, df_cache)
    except ImportError:
        pass

    try:
        from zap.features.volatility import compute as compute_volatility
        df = compute_volatility(df, cfg)
    except ImportError:
        pass

    try:
        from zap.features.macro import compute as compute_macro
        df = compute_macro(df, btc_df, cfg)
    except ImportError:
        pass

    return df
