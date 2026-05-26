"""V9 variant — V8 + faster stale exit and more aggressive winner scaling.

V9 changes from V8:

    1. stale_exit_after_candles: 15 -> 10
       stale_z_threshold:        0.6 -> 0.5
         -> Exit shorts even faster if z isn't reverting. V8 mr_stale
            was -$276 with avg duration 1:17 — try to catch them earlier
            with smaller losses per trade.

    2. scale_min_profit:        0.00117 -> 0.0007
       z_revert_min:             0.35   -> 0.30
         -> Scale up winners sooner (at 0.07% profit instead of 0.12%)
            and require less z-movement (0.30 instead of 0.35) to add
            size to clean reversions. V8 winners contributed +$597; goal
            is to amplify that by scaling earlier.

Long side untouched. Asym leverage (short=4x, long=7x) kept from V7.
"""
import sys
from pathlib import Path

_STRATEGIES_DIR = str(Path(__file__).resolve().parent)
if _STRATEGIES_DIR not in sys.path:
    sys.path.insert(0, _STRATEGIES_DIR)

from twin_pennies_hybrid.strategy import TwinPenniesHybridStrategy as _Base


class TwinPenniesHybridV9Strategy(_Base):
    CONFIG_PATH = Path(__file__).parent / "twin_pennies_hybrid_v9_config.json"
