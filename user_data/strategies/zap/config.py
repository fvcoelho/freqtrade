"""ZAP Strategy configuration."""
from __future__ import annotations

import json
from pathlib import Path

ZAP_CONFIG = {
    "pairs_count": 20,
    "max_open_trades": 6,
    "leverage": {"min": 2, "max": 8},

    "scanner": {
        "zscore_window": 288,
        "half_life_max": 100,
        "correlation_window": 144,
        "hurst_window": 100,
    },

    "regime": {
        "adx_ranging": 18,
        "adx_trending": 25,
        "btc_momentum_window": 48,
        "btc_dump_threshold": -1.0,
        "btc_pump_threshold": 1.0,
    },

    "entry": {
        "top_k": 3,
        "min_predicted_return": 0.005,
        "cooldown_candles": 36,
        "regime_multipliers": {
            "bull_long": 1.0, "bull_short": 0.3,
            "bear_long": 0.3, "bear_short": 1.0,
            "ranging_long": 0.5, "ranging_short": 0.5,
        },
    },

    "manager": {
        "stoploss": -0.05,
        "trailing_activate": 0.015,
        "trailing_offset": 0.005,
        "time_stop_candles": 24,
        "dca_threshold": -0.03,
        "dca_min_predicted": 0.008,
        "dca_multipliers": [1.5, 2.5],
    },
}


def load_config(path: Path | None = None) -> dict:
    """Load ZAP config from JSON, falling back to defaults."""
    cfg = ZAP_CONFIG.copy()
    if path and path.exists():
        with open(path) as f:
            overrides = json.load(f).get("zap", {})
        for section, values in overrides.items():
            if isinstance(values, dict) and section in cfg:
                cfg[section].update(values)
            else:
                cfg[section] = values
    return cfg
