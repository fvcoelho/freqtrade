"""Entry signal generation for Consolidation Scalp.

Two modes:
  - "ob" (original): enter at order block support + confirmation
  - "grid": divide consolidation range into zones, buy in lower zones

BTC regime filter applied in both modes.
"""
from __future__ import annotations

import numpy as np
from pandas import DataFrame


def generate(dataframe: DataFrame, cfg: dict) -> DataFrame:
    """Generate entry signals. Mutates and returns dataframe."""
    entry_cfg = cfg["entries"]
    mode = entry_cfg.get("mode", "ob")

    if mode == "grid":
        return _grid_entries(dataframe, cfg)
    else:
        return _ob_entries(dataframe, cfg)


def _btc_safety(dataframe: DataFrame):
    """Return safe_long, safe_short masks from BTC regime."""
    no_chaos = ~dataframe["btc_high_vol"]
    safe_long = ~dataframe["btc_dump"] & no_chaos
    safe_short = ~dataframe["btc_pump"] & no_chaos
    return safe_long, safe_short


def _apply_cooldown(long_arr, short_arr, cooldown):
    """Suppress signals within cooldown candles of previous signal."""
    long_arr = long_arr.copy()
    short_arr = short_arr.copy()
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


def _ob_entries(dataframe: DataFrame, cfg: dict) -> DataFrame:
    """Original order block entries."""
    entry_cfg = cfg["entries"]
    cooldown = entry_cfg["cooldown_candles"]
    require_confirm = entry_cfg.get("require_confirmation", True)
    engine = cfg["level_engine"]

    consolidating = dataframe["is_consolidating"]
    at_sup = dataframe["at_support"]
    at_res = dataframe["at_resistance"]
    safe_long, safe_short = _btc_safety(dataframe)

    if require_confirm:
        bullish_confirm = dataframe["close"] > dataframe["open"]
        bearish_confirm = dataframe["close"] < dataframe["open"]
    else:
        bullish_confirm = True
        bearish_confirm = True

    long_signal = consolidating & at_sup & bullish_confirm & safe_long
    short_signal = consolidating & at_res & bearish_confirm & safe_short

    long_arr = long_signal.values.astype(bool)
    short_arr = short_signal.values.astype(bool)
    long_arr, short_arr = _apply_cooldown(long_arr, short_arr, cooldown)

    dataframe["enter_long"] = long_arr.astype(int)
    dataframe["enter_short"] = short_arr.astype(int)
    dataframe["enter_tag"] = ""
    dataframe.loc[dataframe["enter_long"] == 1, "enter_tag"] = f"{engine}_long_support"
    dataframe.loc[dataframe["enter_short"] == 1, "enter_tag"] = f"{engine}_short_resistance"
    return dataframe


def _grid_entries(dataframe: DataFrame, cfg: dict) -> DataFrame:
    """Grid-style entries using consolidation range position.

    Divides the rolling range into zones:
      - Bottom zone (0-30%): strong buy signal
      - Lower-mid zone (30-50%): buy on OB confirmation or bullish candle
      - Upper-mid zone (50-70%): no entry
      - Top zone (70-100%): no entry (long-only)

    Also enters at OB support regardless of zone (bonus).
    """
    entry_cfg = cfg["entries"]
    cooldown = entry_cfg.get("cooldown_candles", 6)
    grid_cfg = entry_cfg.get("grid", {})

    buy_zone_top = grid_cfg.get("buy_zone_top", 0.30)
    mid_zone_top = grid_cfg.get("mid_zone_top", 0.50)

    consolidating = dataframe["is_consolidating"]
    safe_long, _ = _btc_safety(dataframe)

    close = dataframe["close"]
    rolling_high = dataframe["rolling_high"]
    rolling_low = dataframe["rolling_low"]
    range_size = rolling_high - rolling_low

    # Position in range: 0 = at support, 1 = at resistance
    pos_in_range = (close - rolling_low) / range_size.replace(0, np.nan)
    pos_in_range = pos_in_range.fillna(0.5)
    dataframe["pos_in_range"] = pos_in_range

    # Grid levels: divide bottom half into N levels
    n_levels = grid_cfg.get("n_levels", 3)
    level_size = mid_zone_top / n_levels  # e.g. 0.50 / 3 = ~0.167

    # Detect when price CROSSES DOWN through a grid level (new touch)
    # This is the grid trigger — like a limit order being filled
    grid_cross = np.zeros(len(dataframe), dtype=bool)
    for lv in range(n_levels):
        level = (lv + 1) * level_size  # 0.167, 0.333, 0.500
        crossed_down = (pos_in_range.shift(1) > level) & (pos_in_range <= level)
        grid_cross = grid_cross | crossed_down.values

    # Confirmations
    bullish_candle = close > dataframe["open"]
    at_ob_support = dataframe.get("at_support", False)

    # Entry logic:
    # Grid level touch: price crossed down through a grid line + bullish candle
    grid_signal = consolidating & safe_long & grid_cross & bullish_candle

    # OB bonus: enter at OB support anywhere in bottom half (selective)
    ob_signal = consolidating & safe_long & (pos_in_range <= mid_zone_top) & at_ob_support & bullish_candle

    # grid_level optional
    use_grid_levels = grid_cfg.get("use_grid_levels", True)
    if use_grid_levels:
        long_signal = grid_signal | ob_signal
    else:
        long_signal = ob_signal

    long_arr = long_signal.values.astype(bool)
    short_arr = np.zeros(len(dataframe), dtype=bool)
    long_arr, short_arr = _apply_cooldown(long_arr, short_arr, cooldown)

    dataframe["enter_long"] = long_arr.astype(int)
    dataframe["enter_short"] = 0
    dataframe["enter_tag"] = ""

    # Tag by source
    dataframe.loc[
        (dataframe["enter_long"] == 1) & grid_cross,
        "enter_tag"
    ] = "grid_level"
    dataframe.loc[
        (dataframe["enter_long"] == 1) & (dataframe["enter_tag"] == ""),
        "enter_tag"
    ] = "grid_ob"

    return dataframe
