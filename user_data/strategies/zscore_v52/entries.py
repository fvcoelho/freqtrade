"""Entry signal generation for ZScore V52.

Pure-function extraction of V51 populate_entry_trend.
Identical logic — no behavioral changes.
"""
from __future__ import annotations

from pandas import DataFrame


def generate(
    dataframe: DataFrame,
    pair: str,
    cfg: dict,
    btc_state: dict,
    group_a: list[str],
    group_b: list[str],
) -> DataFrame:
    """Generate entry signals. Adds: enter_long, enter_short, enter_tag.

    Entry tags: mr_long_a, mr_short_a, mr_short_b, mr_long_b,
                duo_long_a, duo_short_a, duo_short_b, duo_long_b,
                consol_long_a

    Parameters
    ----------
    dataframe : DataFrame
        Must already contain indicators: btc_mom, btc_atr_z, spread_zscore,
        vol_ok, regime_ok, spread_vol_ok, btc_high_vol, btc_dump, btc_pump,
        btc_vol_ended, pair_zscore.
    pair : str
        Trading pair name.
    cfg : dict
        Full strategy config dict with sections: regime, zscore,
        consolidation, btc_trend, entry_modes.
    btc_state : dict
        Not used directly here (BTC columns already in dataframe).
    group_a : list[str]
        Pairs in group A.
    group_b : list[str]
        Pairs in group B.

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
    spread_z = dataframe["spread_zscore"].abs()

    is_trending = (btc_mom.abs() > trending_btc_mom) | (btc_atr_z > trending_atr_z)
    is_consolidation = (
        (btc_atr_z < consolidation_atr_z)
        & (spread_z < consolidation_spread_max)
        & (btc_mom.abs() < consolidation_btc_mom_max)
    )
    is_ranging = ~is_trending & ~is_consolidation

    dataframe["enter_long"] = 0
    dataframe["enter_short"] = 0
    dataframe["enter_tag"] = ""

    is_a = pair in group_a
    is_b = pair in group_b

    # --- Safety filters ---
    vol = dataframe["vol_ok"] == 1
    regime = (dataframe["regime_ok"] == 1) & (dataframe["spread_vol_ok"] == 1)
    no_chaos = ~dataframe["btc_high_vol"]
    safe_long = ~dataframe["btc_dump"] & no_chaos
    safe_short = ~dataframe["btc_pump"] & no_chaos

    # --- Spread divergence thresholds ---
    spread_low = dataframe["spread_zscore"] < -zscore_entry
    spread_high = dataframe["spread_zscore"] > zscore_entry

    # Vol bounce: enter on relaxed spread after volatility ends
    vol_bounce_low = dataframe["btc_vol_ended"] & (
        dataframe["spread_zscore"] < -vol_bounce_spread_min
    )
    vol_bounce_high = dataframe["btc_vol_ended"] & (
        dataframe["spread_zscore"] > vol_bounce_spread_min
    )
    spread_low = spread_low | vol_bounce_low
    spread_high = spread_high | vol_bounce_high

    # Per-pair z-score confirmation
    pair_z_long = dataframe["pair_zscore"] < -pair_z_entry
    pair_z_short = dataframe["pair_zscore"] > pair_z_entry

    # --- RANGING ENTRIES ---
    if hedge_pairs:
        base = is_ranging & vol & regime
        if is_a:
            dataframe.loc[
                base & spread_low & safe_long, ["enter_long", "enter_tag"]
            ] = (1, "duo_long_a")
            dataframe.loc[
                base & spread_high & safe_short, ["enter_short", "enter_tag"]
            ] = (1, "duo_short_a")
        elif is_b:
            dataframe.loc[
                base & spread_low & safe_short, ["enter_short", "enter_tag"]
            ] = (1, "duo_short_b")
            dataframe.loc[
                base & spread_high & safe_long, ["enter_long", "enter_tag"]
            ] = (1, "duo_long_b")
    else:
        if is_a:
            if group_a_long:
                mr_long = is_ranging & vol & regime & spread_low & safe_long & pair_z_long
                dataframe.loc[mr_long, ["enter_long", "enter_tag"]] = (1, "mr_long_a")
            if group_a_short:
                mr_short = (
                    is_ranging & vol & regime & spread_high & safe_short & pair_z_short
                )
                dataframe.loc[mr_short, ["enter_short", "enter_tag"]] = (
                    1,
                    "mr_short_a",
                )
        elif is_b:
            if group_b_short:
                mr_short = (
                    is_ranging & vol & regime & spread_low & safe_short & pair_z_short
                )
                dataframe.loc[mr_short, ["enter_short", "enter_tag"]] = (
                    1,
                    "mr_short_b",
                )
            if group_b_long:
                mr_long = is_ranging & vol & regime & spread_high & safe_long & pair_z_long
                dataframe.loc[mr_long, ["enter_long", "enter_tag"]] = (1, "mr_long_b")

    # --- CONSOLIDATION ENTRIES ---
    consol_spread_low = dataframe["spread_zscore"] < -consol_zscore_entry
    consol_pair_z_long = dataframe["pair_zscore"] < -consol_pair_z_entry
    if is_a:
        consol_long = (
            is_consolidation & vol & regime & consol_spread_low & safe_long & consol_pair_z_long
        )
        mask = consol_long & (dataframe["enter_long"] == 0)
        dataframe.loc[mask, ["enter_long", "enter_tag"]] = (1, "consol_long_a")

    return dataframe
