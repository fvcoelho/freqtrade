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

    # Other feature modules will be added by subsequent tasks.

    return df
