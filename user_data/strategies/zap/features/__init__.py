"""Feature computation dispatcher."""
from __future__ import annotations

from pandas import DataFrame


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

    Modules are imported lazily so missing future modules don't cause failures.
    """
    df_cache = df_cache or {}
    all_pairs = all_pairs or []

    try:
        from user_data.strategies.zap.features.statistical import compute as compute_statistical
        df = compute_statistical(df, pair, cfg, dp, all_pairs, df_cache)
    except ImportError:
        pass

    try:
        from user_data.strategies.zap.features.momentum import compute as compute_momentum
        df = compute_momentum(df, cfg)
    except ImportError:
        pass

    try:
        from user_data.strategies.zap.features.microstructure import compute as compute_microstructure
        df = compute_microstructure(df, cfg)
    except ImportError:
        pass

    try:
        from user_data.strategies.zap.features.cross_pair import compute as compute_cross_pair
        df = compute_cross_pair(df, pair, cfg, dp, all_pairs, df_cache)
    except ImportError:
        pass

    try:
        from user_data.strategies.zap.features.volatility import compute as compute_volatility
        df = compute_volatility(df, cfg)
    except ImportError:
        pass

    try:
        from user_data.strategies.zap.features.macro import compute as compute_macro
        df = compute_macro(df, btc_df, cfg)
    except ImportError:
        pass

    return df
