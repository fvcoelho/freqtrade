"""Grid trading module for ZScore V55 — consolidation regime.

Uses spread z-score levels as grid: buy when spread z crosses down
through a level, sell when it crosses up. Natural grid for mean-reversion
pairs — the z-score oscillates around 0 during consolidation.
"""
from __future__ import annotations

import numpy as np
from pandas import DataFrame


def compute_levels(dataframe: DataFrame, cfg: dict) -> DataFrame:
    """Add grid helper columns. Requires spread_z columns to exist."""
    grid_cfg = cfg["grid"]

    close = dataframe["close"]
    if "rsi" not in dataframe.columns:
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0).rolling(14).mean()
        loss_s = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
        rs = gain / loss_s.replace(0, np.nan)
        dataframe["rsi"] = (100 - (100 / (1 + rs))).fillna(50)

    return dataframe


def generate(
    dataframe: DataFrame,
    pair: str,
    cfg: dict,
    group_sub1: list[str],
    group_sub2: list[str],
    group_name: str,
) -> DataFrame:
    """Generate grid signals using spread z-score crossings during consolidation.

    Grid levels are at z-score intervals: ±0.5, ±1.0, ±1.5, etc.
    Long when z crosses DOWN through a negative level (spread cheapening).
    Short when z crosses UP through a positive level (spread richening).
    """
    grid_cfg = cfg["grid"]
    n_levels = grid_cfg["n_levels"]
    cooldown = grid_cfg["cooldown_candles"]
    require_confirm = grid_cfg["require_confirmation"]
    z_step = grid_cfg.get("z_step", 0.5)

    is_a = pair in group_sub1
    is_b = pair in group_sub2
    if not is_a and not is_b:
        return dataframe

    consolidating = dataframe["is_consolidating"]

    no_chaos = ~dataframe["btc_high_vol"]
    safe_long = ~dataframe["btc_dump"] & no_chaos
    safe_short = ~dataframe["btc_pump"] & no_chaos

    if require_confirm:
        bullish = dataframe["close"] > dataframe["open"]
        bearish = dataframe["close"] < dataframe["open"]
    else:
        bullish = True
        bearish = True

    no_long = dataframe["enter_long"] == 0
    no_short = dataframe["enter_short"] == 0

    # Use group-specific spread z-score
    spread_col = f"spread_z_{group_name.lower()}"
    if spread_col not in dataframe.columns:
        return dataframe

    z = dataframe[spread_col]
    z_prev = z.shift(1)

    long_cross = np.zeros(len(dataframe), dtype=bool)
    short_cross = np.zeros(len(dataframe), dtype=bool)
    cross_level = np.zeros(len(dataframe), dtype=int)

    for lv in range(1, n_levels + 1):
        neg_threshold = -lv * z_step  # -0.5, -1.0, -1.5, ...
        pos_threshold = lv * z_step   # +0.5, +1.0, +1.5, ...

        # Z crosses DOWN through negative level → long (spread is cheap)
        crossed_down = (z_prev > neg_threshold) & (z <= neg_threshold)
        # Z crosses UP through positive level → short (spread is rich)
        crossed_up = (z_prev < pos_threshold) & (z >= pos_threshold)

        down_mask = crossed_down.values.astype(bool)
        up_mask = crossed_up.values.astype(bool)

        long_cross = long_cross | down_mask
        short_cross = short_cross | up_mask
        cross_level[down_mask] = lv
        cross_level[up_mask] = lv

    gn = group_name

    long_signal = (
        consolidating & safe_long
        & long_cross & no_long
    )
    # Grid short disabled — consolidation long-only
    short_signal = np.zeros(len(dataframe), dtype=bool)

    long_arr = long_signal.values.astype(bool).copy()
    short_arr = np.asarray(short_signal).astype(bool).copy()
    long_arr, short_arr = _apply_cooldown(long_arr, short_arr, cooldown)

    dataframe.loc[long_arr, "enter_long"] = 1
    dataframe.loc[long_arr, "enter_tag"] = ""
    dataframe.loc[short_arr, "enter_short"] = 1
    dataframe.loc[short_arr, "enter_tag"] = ""

    for i in range(len(dataframe)):
        if long_arr[i]:
            dataframe.iat[i, dataframe.columns.get_loc("enter_tag")] = (
                f"grid_long_L{cross_level[i]}_{gn}"
            )
        elif short_arr[i]:
            dataframe.iat[i, dataframe.columns.get_loc("enter_tag")] = (
                f"grid_short_L{cross_level[i]}_{gn}"
            )

    return dataframe


def _apply_cooldown(long_arr, short_arr, cooldown):
    """Suppress signals within cooldown candles of previous signal."""
    last_long = -cooldown - 1
    last_short = -cooldown - 1
    for i in range(len(long_arr)):
        if long_arr[i]:
            if i - last_long <= cooldown:
                long_arr[i] = False
            else:
                last_long = i
        if short_arr[i]:
            if i - last_short <= cooldown:
                short_arr[i] = False
            else:
                last_short = i
    return long_arr, short_arr
