"""Entry signal generation for ZScore V54.

Adapted from V52 entries.py for dual independent groups.
Each group call only sets signals where no previous group already triggered.
"""
from __future__ import annotations

from pandas import DataFrame


def generate(
    dataframe: DataFrame,
    pair: str,
    cfg: dict,
    btc_state: dict,
    group_sub1: list[str],
    group_sub2: list[str],
    group_name: str,
    spread_z_col: str,
) -> DataFrame:
    """Generate entry signals for one group. Adds: enter_long, enter_short, enter_tag.

    Does NOT overwrite signals already set by a previous group — only fills
    rows where enter_long == 0 and enter_short == 0.

    Entry tags: mr_long_a_{group}, mr_short_a_{group}, mr_short_b_{group},
                mr_long_b_{group}, duo_long_a_{group}, duo_short_a_{group},
                duo_short_b_{group}, duo_long_b_{group}, consol_long_a_{group}

    Parameters
    ----------
    dataframe : DataFrame
        Must already contain indicators: btc_mom, btc_atr_z, the spread z column,
        vol_ok, regime_ok, spread_vol_ok, btc_high_vol, btc_dump, btc_pump,
        btc_vol_ended, pair_zscore.
    pair : str
        Trading pair name.
    cfg : dict
        Full strategy config dict with sections: regime, zscore,
        consolidation, btc_trend, entry_modes.
    btc_state : dict
        Not used directly here (BTC columns already in dataframe).
    group_sub1 : list[str]
        Pairs in this group's sub1 (long side).
    group_sub2 : list[str]
        Pairs in this group's sub2 (short side).
    group_name : str
        Group identifier, e.g. "A" or "B".
    spread_z_col : str
        Column name for spread z-score, e.g. "spread_z_a".

    Returns
    -------
    DataFrame
        Same dataframe with enter_long, enter_short, enter_tag columns set.
    """
    # --- Config lookups ---
    regime_cfg = cfg["regime"]
    zscore_cfg = cfg["zscore"]
    consol_cfg = cfg["consolidation"]
    btc_cfg = cfg["btc_trend"]
    modes = cfg["entry_modes"]

    trending_btc_mom = regime_cfg["trending_btc_mom"]
    trending_atr_z = regime_cfg["trending_atr_z"]
    consolidation_atr_z = regime_cfg["consolidation_atr_z"]
    consolidation_spread_max = regime_cfg["consolidation_spread_max"]
    consolidation_btc_mom_max = regime_cfg["consolidation_btc_mom_max"]

    zscore_entry = zscore_cfg["zscore_entry"]
    pair_z_entry = zscore_cfg["pair_z_entry"]

    consol_zscore_entry = consol_cfg["consol_zscore_entry"]
    consol_pair_z_entry = consol_cfg["consol_pair_z_entry"]

    vol_bounce_spread_min = btc_cfg["vol_bounce_spread_min"]

    hedge_pairs = modes["hedge_pairs"]
    group_a_long = modes["group_a_long"]
    group_a_short = modes["group_a_short"]
    group_b_long = modes["group_b_long"]
    group_b_short = modes["group_b_short"]

    # --- Regime classification ---
    btc_mom = dataframe["btc_mom"]
    btc_atr_z = dataframe["btc_atr_z"]
    spread_z = dataframe[spread_z_col].abs()

    is_trending = (btc_mom.abs() > trending_btc_mom) | (btc_atr_z > trending_atr_z)
    is_consolidation = (
        (btc_atr_z < consolidation_atr_z)
        & (spread_z < consolidation_spread_max)
        & (btc_mom.abs() < consolidation_btc_mom_max)
    )
    is_ranging = ~is_trending & ~is_consolidation

    # Initialize columns only if they don't exist yet (first group call)
    if "enter_long" not in dataframe.columns:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe["enter_tag"] = ""

    is_a = pair in group_sub1
    is_b = pair in group_sub2

    if not is_a and not is_b:
        return dataframe

    # Guard: only set signals on rows not already claimed by another group
    no_long = dataframe["enter_long"] == 0
    no_short = dataframe["enter_short"] == 0

    # --- Safety filters ---
    vol = dataframe["vol_ok"] == 1
    # Volume required during trending, skip during ranging/consolidation
    vol_adaptive = vol | is_ranging | is_consolidation
    regime = (dataframe["regime_ok"] == 1) & (dataframe["spread_vol_ok"] == 1)
    no_chaos = ~dataframe["btc_high_vol"]
    safe_long = ~dataframe["btc_dump"] & no_chaos
    safe_short = ~dataframe["btc_pump"] & no_chaos

    # --- Spread divergence thresholds ---
    spread_low = dataframe[spread_z_col] < -zscore_entry
    spread_high = dataframe[spread_z_col] > zscore_entry

    # Vol bounce: enter on relaxed spread after volatility ends
    vol_bounce_low = dataframe["btc_vol_ended"] & (
        dataframe[spread_z_col] < -vol_bounce_spread_min
    )
    vol_bounce_high = dataframe["btc_vol_ended"] & (
        dataframe[spread_z_col] > vol_bounce_spread_min
    )
    spread_low = spread_low | vol_bounce_low
    spread_high = spread_high | vol_bounce_high

    # Per-pair z-score confirmation
    pair_z_long = dataframe["pair_zscore"] < -pair_z_entry
    pair_z_short = dataframe["pair_zscore"] > pair_z_entry

    # --- Tag suffix ---
    gn = group_name

    # --- RANGING ENTRIES ---
    if hedge_pairs:
        base = is_ranging & vol_adaptive & regime
        if is_a:
            mask = base & spread_low & safe_long & no_long
            dataframe.loc[mask, ["enter_long", "enter_tag"]] = (1, f"duo_long_a_{gn}")
            mask = base & spread_high & safe_short & no_short
            dataframe.loc[mask, ["enter_short", "enter_tag"]] = (1, f"duo_short_a_{gn}")
        elif is_b:
            mask = base & spread_low & safe_short & no_short
            dataframe.loc[mask, ["enter_short", "enter_tag"]] = (1, f"duo_short_b_{gn}")
            mask = base & spread_high & safe_long & no_long
            dataframe.loc[mask, ["enter_long", "enter_tag"]] = (1, f"duo_long_b_{gn}")
    else:
        if is_a:
            if group_a_long:
                mr_long = is_ranging & vol_adaptive & regime & spread_low & safe_long & pair_z_long & no_long
                dataframe.loc[mr_long, ["enter_long", "enter_tag"]] = (1, f"mr_long_a_{gn}")
            if group_a_short:
                mr_short = (
                    is_ranging & vol_adaptive & regime & spread_high & safe_short & pair_z_short & no_short
                )
                dataframe.loc[mr_short, ["enter_short", "enter_tag"]] = (1, f"mr_short_a_{gn}")
        elif is_b:
            if group_b_short:
                mr_short = (
                    is_ranging & vol_adaptive & regime & spread_low & safe_short & pair_z_short & no_short
                )
                dataframe.loc[mr_short, ["enter_short", "enter_tag"]] = (1, f"mr_short_b_{gn}")
            if group_b_long:
                mr_long = is_ranging & vol_adaptive & regime & spread_high & safe_long & pair_z_long & no_long
                dataframe.loc[mr_long, ["enter_long", "enter_tag"]] = (1, f"mr_long_b_{gn}")

    # --- CONSOLIDATION ENTRIES ---
    consol_spread_low = dataframe[spread_z_col] < -consol_zscore_entry
    consol_pair_z_long = dataframe["pair_zscore"] < -consol_pair_z_entry
    if is_a:
        consol_long = (
            is_consolidation & regime & consol_spread_low & safe_long & consol_pair_z_long
        )
        mask = consol_long & no_long
        dataframe.loc[mask, ["enter_long", "enter_tag"]] = (1, f"consol_long_a_{gn}")

    return dataframe
