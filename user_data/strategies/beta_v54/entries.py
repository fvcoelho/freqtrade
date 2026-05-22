"""Entry signal generation for V54.

V54 improvements over V53:
    - ADX-based regime classification (replaces btc_mom heuristic)
    - Dynamic z-score entry threshold (adapts to spread volatility)
    - Half-life gate (blocks entries when spread not mean-reverting)
    - Drawdown mode z-boost (stricter during equity drawdown)
"""
from __future__ import annotations

import pandas as pd
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
    strategy_state=None,
) -> DataFrame:
    """Generate entry signals for one group."""
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

    btc_mom = dataframe["btc_mom"]
    btc_atr_z = dataframe["btc_atr_z"]
    spread_z = dataframe[spread_z_col].abs()

    # ── REGIME CLASSIFICATION (Step 1: ADX-based) ──
    adx_cfg = cfg.get("adx_regime", {})
    if adx_cfg.get("enabled", False) and "adx_ranging" in dataframe.columns:
        is_ranging = dataframe["adx_ranging"].astype(bool)
        is_trending = dataframe["adx_trending"].astype(bool)
        is_consolidation = ~is_ranging & ~is_trending & (
            (btc_atr_z < consolidation_atr_z)
            & (spread_z < consolidation_spread_max)
            & (btc_mom.abs() < consolidation_btc_mom_max)
        )
    else:
        # Fallback: V53 logic
        is_trending = (btc_mom.abs() > trending_btc_mom) | (btc_atr_z > trending_atr_z)
        is_consolidation = (
            (btc_atr_z < consolidation_atr_z)
            & (spread_z < consolidation_spread_max)
            & (btc_mom.abs() < consolidation_btc_mom_max)
        )
        is_ranging = ~is_trending & ~is_consolidation

    # ── HALF-LIFE GATE (Step 3) ──
    hl_cfg = cfg.get("half_life", {})
    if hl_cfg.get("enabled", False) and "spread_half_life" in dataframe.columns:
        hl_max = hl_cfg.get("max_entry_candles", 50)
        hl_gate = dataframe["spread_half_life"] <= hl_max
        is_ranging = is_ranging & hl_gate

    if "enter_long" not in dataframe.columns:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe["enter_tag"] = ""

    is_a = pair in group_sub1
    is_b = pair in group_sub2
    if not is_a and not is_b:
        return dataframe

    no_long = dataframe["enter_long"] == 0
    no_short = dataframe["enter_short"] == 0

    vol = dataframe["vol_ok"] == 1
    regime = (dataframe["regime_ok"] == 1) & (dataframe["spread_vol_ok"] == 1)
    no_chaos = ~dataframe["btc_high_vol"]
    safe_long = ~dataframe["btc_dump"] & no_chaos
    safe_short = ~dataframe["btc_pump"] & no_chaos

    spread_low = dataframe[spread_z_col] < -zscore_entry
    spread_high = dataframe[spread_z_col] > zscore_entry

    vol_bounce_low = dataframe["btc_vol_ended"] & (dataframe[spread_z_col] < -vol_bounce_spread_min)
    vol_bounce_high = dataframe["btc_vol_ended"] & (dataframe[spread_z_col] > vol_bounce_spread_min)
    spread_low = spread_low | vol_bounce_low
    spread_high = spread_high | vol_bounce_high

    pair_z_long = dataframe["pair_zscore"] < -pair_z_entry
    pair_z_short = dataframe["pair_zscore"] > pair_z_entry

    gn = group_name

    # ── DYNAMIC Z-SCORE ENTRY (Step 2) ──
    ranging_cfg = cfg.get("ranging", {})
    dynamic_z = ranging_cfg.get("dynamic_z_entry", {})
    if dynamic_z.get("enabled", False):
        spread_vol = dataframe[spread_z_col].rolling(
            dynamic_z.get("vol_window", 144)
        ).std().fillna(1.0)
        base_mult = dynamic_z.get("base_multiplier", 1.4)
        vol_sens = dynamic_z.get("vol_sensitivity", 0.4)
        min_mult = dynamic_z.get("min_multiplier", 1.2)
        max_mult = dynamic_z.get("max_multiplier", 2.5)
        ranging_z_mult = (base_mult + (spread_vol - 1.0) * vol_sens).clip(min_mult, max_mult)
    else:
        ranging_z_mult = ranging_cfg.get("z_entry_multiplier", 1.5)

    # ── DRAWDOWN Z-BOOST (Step 5) ──
    dd_cfg = cfg.get("leverage", {}).get("drawdown_mode", {})
    if dd_cfg.get("enabled", False) and strategy_state:
        peak_bal = max(
            strategy_state.initial_balance,
            max((e["balance"] for e in strategy_state.equity_curve),
                default=strategy_state.initial_balance),
        )
        current_dd = (peak_bal - strategy_state.balance) / peak_bal if peak_bal > 0 else 0
        if current_dd > dd_cfg.get("dd_threshold", 0.08):
            z_boost = dd_cfg.get("z_threshold_boost", 1.2)
            ranging_z_mult = ranging_z_mult * z_boost

    ranging_spread_low = dataframe[spread_z_col] < -zscore_entry * ranging_z_mult
    ranging_spread_high = dataframe[spread_z_col] > zscore_entry * ranging_z_mult

    # ── RANGING ENTRIES ──
    if hedge_pairs:
        base = is_ranging & vol & regime
        if is_a:
            mask = base & ranging_spread_low & safe_long & no_long
            dataframe.loc[mask, ["enter_long", "enter_tag"]] = (1, f"duo_long_a_{gn}")
            mask = base & ranging_spread_high & safe_short & no_short
            dataframe.loc[mask, ["enter_short", "enter_tag"]] = (1, f"duo_short_a_{gn}")
        elif is_b:
            mask = base & ranging_spread_low & safe_short & no_short
            dataframe.loc[mask, ["enter_short", "enter_tag"]] = (1, f"duo_short_b_{gn}")
            mask = base & ranging_spread_high & safe_long & no_long
            dataframe.loc[mask, ["enter_long", "enter_tag"]] = (1, f"duo_long_b_{gn}")
    else:
        if is_a:
            if group_a_long:
                mr_long = is_ranging & vol & regime & ranging_spread_low & safe_long & pair_z_long & no_long
                dataframe.loc[mr_long, ["enter_long", "enter_tag"]] = (1, f"mr_long_a_{gn}")
            if group_a_short:
                mr_short = is_ranging & vol & regime & ranging_spread_high & safe_short & pair_z_short & no_short
                dataframe.loc[mr_short, ["enter_short", "enter_tag"]] = (1, f"mr_short_a_{gn}")
        elif is_b:
            if group_b_short:
                mr_short = is_ranging & vol & regime & ranging_spread_low & safe_short & pair_z_short & no_short
                dataframe.loc[mr_short, ["enter_short", "enter_tag"]] = (1, f"mr_short_b_{gn}")
            if group_b_long:
                mr_long = is_ranging & vol & regime & ranging_spread_high & safe_long & pair_z_long & no_long
                dataframe.loc[mr_long, ["enter_long", "enter_tag"]] = (1, f"mr_long_b_{gn}")

    # ── CONSOLIDATION ENTRIES ──
    consol_spread_low = dataframe[spread_z_col] < -consol_zscore_entry
    consol_pair_z_long = dataframe["pair_zscore"] < -consol_pair_z_entry
    if is_a:
        consol_long = is_consolidation & vol & regime & consol_spread_low & safe_long & consol_pair_z_long
        mask = consol_long & no_long
        dataframe.loc[mask, ["enter_long", "enter_tag"]] = (1, f"consol_long_a_{gn}")

    return dataframe
