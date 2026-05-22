"""DCA + Partial Stop for ZScore V54.

DCA: add to winning positions progressively.
Partial Stop: sell a portion of the position at a loss threshold
before the full stoploss hits, reducing total loss.

Example (Partial Stop at -4%, sell 75%, final stop -7%):
    Without: -7% full → -7% loss
    With:    -4% sell 75% → -3% on 75% = -2.25%
             -7% stop 25% → -7% on 25% = -1.75%
             Total: -4.0% (vs -7% without)
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def adjust_position(
    trade,
    current_profit: float,
    cfg: dict,
    min_stake: Optional[float],
    max_stake: float,
    dp=None,
    timeframe: str = "5m",
) -> Optional[float]:
    """DCA (add) + Partial Stop (reduce) position adjustments.

    Returns:
        Positive float → add stake (DCA)
        Negative float → reduce stake (Partial Stop)
        None → no adjustment
    """
    # ── Partial Stop: sell portion at loss threshold ──
    ps = cfg.get("partial_stop", {})
    if ps.get("enabled", False):
        result = _partial_stop(trade, current_profit, ps, min_stake)
        if result is not None:
            logger.info("PARTIAL STOP RETURNING: %s profit=%.2f%% result=$%.2f",
                        trade.pair, current_profit * 100, result)
            return result

    # ── DCA: add to winners ──
    dca = cfg["dca"]
    thresholds = dca["thresholds"]
    multipliers = dca["multipliers"]

    adds = trade.nr_of_successful_entries - 1
    if adds >= len(thresholds):
        return None

    if current_profit <= 0:
        return None

    if current_profit >= thresholds[adds]:
        # V54: Smart DCA — validate z-score still favorable
        smart = dca.get("smart_dca", {})
        if smart.get("enabled", False) and dp:
            dataframe, _ = dp.get_analyzed_dataframe(trade.pair, timeframe)
            if dataframe is not None and not dataframe.empty:
                pair_z = float(dataframe.iloc[-1].get("pair_zscore", 0.0))
                min_z = smart.get("min_z_favorable", 0.5)
                is_long = trade.is_short is False
                z_ok = (pair_z < -min_z) if is_long else (pair_z > min_z)
                if not z_ok:
                    return None  # z no longer favorable

        min_profit_dca = dca.get("smart_min_profit", 0.0)
        if min_profit_dca > 0 and current_profit < min_profit_dca:
            return None

        add_stake = trade.stake_amount * multipliers[adds]
        if min_stake and add_stake < min_stake:
            add_stake = min_stake
        return min(add_stake, max_stake)

    return None


def _partial_stop(
    trade,
    current_profit: float,
    ps_cfg: dict,
    min_stake: Optional[float],
) -> Optional[float]:
    """Sell a portion of the position when loss reaches threshold.

    Config:
        trigger: loss % to trigger partial exit (e.g., -0.04 = -4%)
        sell_ratio: portion to sell (e.g., 0.75 = 75%)

    Only triggers once per trade (checks nr_of_successful_exits).
    """
    trigger = ps_cfg.get("trigger", -0.04)
    sell_ratio = ps_cfg.get("sell_ratio", 0.75)

    # Only trigger once (first partial exit)
    if trade.nr_of_successful_exits > 0:
        return None

    if current_profit <= trigger:
        sell_amount = trade.stake_amount * sell_ratio
        if min_stake and sell_amount < min_stake:
            sell_amount = min_stake
        logger.info(
            "PARTIAL STOP: %s %.1f%% — selling %.0f%% ($%.2f)",
            trade.pair, current_profit * 100, sell_ratio * 100, sell_amount,
        )
        return -sell_amount  # Negative = reduce position

    return None
