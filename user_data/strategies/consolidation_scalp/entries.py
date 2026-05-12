"""Entry signal generation for Consolidation Scalp.

Generates enter_long / enter_short signals when:
1. Market is consolidating (is_consolidating == True)
2. Price is at a support or resistance level (at_support / at_resistance)
3. Optional confirmation: reversal candle detected

Adds cooldown tracking to avoid re-entering the same level repeatedly.
"""
from __future__ import annotations

import numpy as np
from pandas import DataFrame


def generate(dataframe: DataFrame, cfg: dict) -> DataFrame:
    """Generate entry signals. Mutates and returns dataframe."""
    entry_cfg = cfg["entries"]
    cooldown = entry_cfg["cooldown_candles"]
    require_confirm = entry_cfg["require_confirmation"]
    engine = cfg["level_engine"]

    consolidating = dataframe["is_consolidating"]
    at_sup = dataframe["at_support"]
    at_res = dataframe["at_resistance"]

    # Confirmation: close reversal (close > open for long, close < open for short)
    if require_confirm:
        bullish_confirm = dataframe["close"] > dataframe["open"]
        bearish_confirm = dataframe["close"] < dataframe["open"]
    else:
        bullish_confirm = True
        bearish_confirm = True

    # Long at support
    long_signal = consolidating & at_sup & bullish_confirm

    # Short at resistance
    short_signal = consolidating & at_res & bearish_confirm

    # Apply cooldown: suppress signals within N candles of previous signal
    long_arr = long_signal.values.copy().astype(bool)
    short_arr = short_signal.values.copy().astype(bool)

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

    dataframe["enter_long"] = long_arr.astype(int)
    dataframe["enter_short"] = short_arr.astype(int)
    dataframe["enter_tag"] = ""

    tag = engine
    dataframe.loc[dataframe["enter_long"] == 1, "enter_tag"] = f"{tag}_long_support"
    dataframe.loc[dataframe["enter_short"] == 1, "enter_tag"] = f"{tag}_short_resistance"

    return dataframe
