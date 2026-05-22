"""Leverage sizing for V59Plus with consolidation cap."""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def compute(pair, cfg, dp, timeframe, entry_tag, side, max_leverage, is_consolidation=False):
    """Compute leverage with regime-aware caps.

    Returns (leverage, trade_type).
    """
    lev_cfg = cfg.get("leverage", {})
    type_cfg = lev_cfg.get("by_type", {})
    regime_params = cfg.get("regime_params", {})

    if not dp:
        base = lev_cfg.get("base_multiplier", 6.0)
        return float(max(1, min(int(base), int(max_leverage)))), "default"

    try:
        import pandas as pd
        import numpy as np
        df, _ = dp.get_analyzed_dataframe(pair, timeframe)
        if df is None or df.empty or "basket_z" not in df.columns:
            base = lev_cfg.get("base_multiplier", 6.0)
            return float(max(1, min(int(base), int(max_leverage)))), "default"

        last = df.iloc[-1]
        abs_z = abs(float(last.get("basket_z", 0)))
        vol_ratio = float(last.get("vol_ratio", 1.0))
        btc_mom = float(last.get("btc_mom", 0.0))
        btc_atr_z = float(last.get("btc_atr_z", 0.0))

        bz_prev = float(df["basket_z"].iloc[-4]) if len(df) >= 4 else abs_z
        velocity = abs(float(last.get("basket_z", 0)) - bz_prev)

        # Detect trade type
        if velocity >= 1.0 and vol_ratio >= 2.0:
            trade_type = "breakout"
        elif abs(btc_mom) >= 1.5 and btc_atr_z < 2.0:
            trade_type = "trending"
        else:
            trade_type = "mean_reversion"

        tc = type_cfg.get(trade_type, {})
        t_min = tc.get("min", lev_cfg.get("min", 2.0))
        t_max = tc.get("max", lev_cfg.get("max", 8.0))
        t_z_min = tc.get("z_min", lev_cfg.get("z_min", 0.3))
        t_z_max = tc.get("z_max", lev_cfg.get("z_max", 2.0))

        if abs_z <= t_z_min:
            lev = t_min
        elif abs_z >= t_z_max:
            lev = t_max
        else:
            t = (abs_z - t_z_min) / (t_z_max - t_z_min)
            lev = t_min + t * (t_max - t_min)

        # Ranging regime leverage cap
        ranging_cap = lev_cfg.get("ranging_leverage_cap", 0)
        if ranging_cap and btc_mom <= 0 and btc_mom > -1.0:
            lev = min(lev, ranging_cap)

        # ── CONSOLIDATION CAP ──
        # In consolidation: force lower leverage (less conviction)
        if is_consolidation:
            consol_max_lev = regime_params.get("consolidation", {}).get("max_lev", 4.0)
            if lev > consol_max_lev:
                logger.info("LEV_CAP %s consol: %.1f -> %.1f", pair, lev, consol_max_lev)
                lev = consol_max_lev

        final_lev = float(max(1, min(int(lev), int(max_leverage))))
        logger.info(
            "LEV %s %s | type=%s lev=%.0fx | abs_z=%.3f vol=%.2f vel=%.3f consol=%s",
            pair, side, trade_type, final_lev, abs_z, vol_ratio, velocity,
            "Y" if is_consolidation else "N",
        )
        return final_lev, trade_type

    except Exception:
        base = lev_cfg.get("base_multiplier", 6.0)
        return float(max(1, min(int(base), int(max_leverage)))), "default"
