"""V8 variant — V7 (asym leverage 4x/7x) + three short-side leak plugs.

V8 changes from V7 (config-only — no code-vs-base):

    1. stale_exit_after_candles = 15
       stale_z_threshold = 0.6
         -> If short aged >=15c AND z still > 0.6 (not reverting),
            exit at current profit. Targets mr_time_stop (-$252 in V7).

    2. z_worsen_mult = 1.4
         -> If short's z climbs to 1.4 * entry_z (basket dispersion
            keeps widening AGAINST the trade), exit immediately.
            Targets trailing_stop_loss shorts (-$441 in V7).

    3. cooldown_after_n_losses = 2
       cooldown_pair_minutes = 60
         -> After 2 consecutive losses on (pair, side), block that
            combo for 60min. Cuts the "ONDO/SOL keeps killing"
            concentration effect.

Long side untouched — V7 longs already broke even.
"""
import sys
from pathlib import Path

_STRATEGIES_DIR = str(Path(__file__).resolve().parent)
if _STRATEGIES_DIR not in sys.path:
    sys.path.insert(0, _STRATEGIES_DIR)

from twin_pennies_hybrid.strategy import TwinPenniesHybridStrategy as _Base


class TwinPenniesHybridV8Strategy(_Base):
    CONFIG_PATH = Path(__file__).parent / "twin_pennies_hybrid_v8_config.json"
