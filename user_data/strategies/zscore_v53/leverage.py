"""Leverage sizing and stake amount for ZScore V53.

Modes:
    - warmup:  Volume base + streak-based cap (3→5x over consecutive wins)
    - volume:  Sweet-spot volume ratio → max leverage, extremes → min
    - inverse: High z-score = low leverage (conservative on extreme signals)
    - exp:     Exponential (original V52, signal_strength drives leverage up)

Safety modifiers (applied after all modes):
    - Consolidation entries capped at consol_max
    - BTC high volatility capped at btc_high_vol_max
    - BTC pump/dump reduces by btc_pump_dump_multiplier
    - Final clamp to [floor, max_leverage]
"""
from __future__ import annotations

import math
import logging
from datetime import datetime
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


def _snapshot_features(last) -> list[float]:
    """Extract feature snapshot from the last candle row.

    Returns: [spread_z, rolling_corr, vol_ratio, btc_mom, btc_atr_z]
    Uses spread_z_a as primary spread indicator (V53 group-specific).
    Falls back to spread_zscore (V52 compat) then 0.0.
    """
    # V53 uses per-group spread columns; pick whichever is available
    spread_z = abs(float(
        last.get("spread_z_a", last.get("spread_z_b", last.get("spread_zscore", 0.0)))
    ))
    return [
        spread_z,
        float(last.get("rolling_corr", 0.0)),
        float(last.get("vol_ratio", 1.0)),
        float(last.get("btc_mom", 0.0)),
        float(last.get("btc_atr_z", 0.0)),
    ]


def _compute_volume_leverage(vol_ratio: float, lev_min: float, lev_max: float,
                              vol_sweet_min: float, vol_sweet_max: float,
                              vol_cap: float) -> float:
    """Volume-based leverage: sweet spot → max, extremes → min.

    Below sweet_min: scale linearly from min to max
    In sweet spot [sweet_min, sweet_max]: max leverage (market has conviction)
    Above sweet_max: decay back to min (may be panic spike)
    """
    if vol_ratio < vol_sweet_min:
        t = vol_ratio / vol_sweet_min
        return lev_min + t * (lev_max - lev_min)
    elif vol_ratio <= vol_sweet_max:
        return lev_max
    else:
        t = min(1.0, (vol_ratio - vol_sweet_max) / (vol_cap - vol_sweet_max))
        return lev_max - t * (lev_max - lev_min)


def compute(
    pair: str,
    cfg: dict,
    dp,
    timeframe: str,
    entry_tag: Optional[str],
    side: str,
    max_leverage: float,
    pending_features: dict,
) -> tuple[float, list[float]]:
    """Compute leverage and snapshot features.

    Returns (leverage_value, features_list).
    Features: [spread_z, rolling_corr, vol_ratio, btc_mom, btc_atr_z]

    The leverage mode is determined by cfg["leverage"]["mode"]:
        warmup  — volume base + win-streak cap from StrategyState
        volume  — pure volume-ratio curve
        inverse — high signal = low leverage
        exp     — exponential (V52 original)
    """
    lv = cfg["leverage"]
    lev_base = lv["base_multiplier"]

    # Get latest analyzed candle
    dataframe, _ = dp.get_analyzed_dataframe(pair, timeframe)
    if dataframe is None or dataframe.empty:
        return min(lev_base, max_leverage), []

    last = dataframe.iloc[-1]
    features = _snapshot_features(last)
    pending_features[pair] = features

    # Signal strength from per-group spread z-score (V53) or global (V52)
    spread_z = abs(float(
        last.get("spread_z_a", last.get("spread_z_b", last.get("spread_zscore", 0.0)))
    ))
    pair_z = abs(float(last.get("pair_zscore", 0.0)))
    signal_strength = max(spread_z, pair_z)

    # Config values
    lev_min = lv["min"]
    lev_max = lv["max"]
    lev_consol_max = lv["consol_max"]
    lev_btc_hv_max = lv["btc_high_vol_max"]
    lev_btc_pd_mult = lv["btc_pump_dump_multiplier"]
    lev_floor = lv["floor"]
    lev_mode = lv.get("mode", "exp")

    # Volume params (shared by warmup and volume modes)
    vol_ratio = float(last.get("vol_ratio", 1.0))
    vol_sweet_min = lv.get("vol_sweet_min", 2.0)
    vol_sweet_max = lv.get("vol_sweet_max", 10.0)
    vol_cap = lv.get("vol_cap", 20.0)

    # ── MODE: WARMUP ──
    # Volume base leverage + win-streak cap from persistent state.
    # Cold (streak=0) → lev_min, builds up per consecutive win.
    # Gap > N hours → reset to cold. Streak > cap → decay.
    if lev_mode == "warmup":
        vol_lev = _compute_volume_leverage(
            vol_ratio, lev_min, lev_max,
            vol_sweet_min, vol_sweet_max, vol_cap,
        )

        # Apply warmup cap from strategy state
        strategy_state = pending_features.get("_strategy_state")
        warmup_cfg = lv.get("warmup", {})

        if strategy_state and warmup_cfg:
            try:
                current_time = pd.Timestamp(
                    last.get("date", datetime.utcnow())
                ).to_pydatetime().replace(tzinfo=None)
            except Exception:
                current_time = datetime.utcnow()
            lev = strategy_state.compute_warmup_leverage(
                pair, current_time, vol_lev, warmup_cfg,
            )
        else:
            # FIX: If state unavailable, use minimum (cold start) not uncapped volume
            lev = min(vol_lev, lev_min)
            logger.debug(
                "WARMUP: %s — state unavailable, using cold leverage %.1fx",
                pair, lev,
            )

    # ── MODE: VOLUME ──
    # Pure volume-ratio curve, no streak modifier.
    elif lev_mode == "volume":
        lev = _compute_volume_leverage(
            vol_ratio, lev_min, lev_max,
            vol_sweet_min, vol_sweet_max, vol_cap,
        )

    # ── MODE: INVERSE ──
    # High z-score = low leverage (conservative on extreme signals).
    # Rationale: extreme z doesn't guarantee quick reversion.
    elif lev_mode == "inverse":
        entry_z = cfg.get("zscore", {}).get("zscore_entry", 2.1)
        z_range = lv.get("inverse_z_range", 3.0)
        t = min(1.0, max(0.0, (signal_strength - entry_z) / z_range))
        lev = lev_max - t * (lev_max - lev_min)

    # ── MODE: EXP (V52 original) ──
    # Exponential: higher signal → higher leverage.
    else:
        lev_aggression = lv["signal_aggression"]
        lev_divisor = lv["signal_divisor"]
        lev = lev_base * math.exp(signal_strength * lev_aggression / lev_divisor)

    # ── ATR-BASED LEVERAGE CAP ──
    if lv.get("atr_cap_enabled", False):
        atr_period = lv.get("atr_cap_period", 12)
        atr_mult = lv.get("atr_cap_multiplier", 2.0)
        if len(dataframe) >= atr_period:
            recent = dataframe.iloc[-atr_period:]
            atr_pct = ((recent["high"] - recent["low"]) / recent["open"]).mean()
            if atr_pct > 0:
                stoploss_abs = abs(cfg.get("risk", {}).get("stoploss", -0.07))
                atr_max_lev = stoploss_abs / (atr_mult * atr_pct)
                if atr_max_lev < lev:
                    logger.info(
                        "ATR_CAP: %s lev %.1f→%.1f (ATR=%.3f%%)",
                        pair, lev, atr_max_lev, atr_pct * 100,
                    )
                    lev = atr_max_lev

    # ── SAFETY MODIFIERS ──
    # Clamp to configured range
    lev = max(lev_min, min(lev, lev_max, max_leverage))

    # Consolidation entries: cap leverage (low conviction regime)
    if entry_tag and entry_tag.startswith("consol_"):
        lev = min(lev, lev_consol_max)

    # BTC regime modifiers
    if last.get("btc_high_vol", False):
        lev = min(lev, lev_btc_hv_max)
    elif last.get("btc_pump", False) or last.get("btc_dump", False):
        lev *= lev_btc_pd_mult

    # Final floor and round
    lev = round(max(lev_floor, min(lev, max_leverage)), 1)
    return lev, features


def stake_amount(cfg: dict, max_stake: float) -> float:
    """Return fixed stake per position."""
    return min(cfg["stake_per_position"], max_stake)
