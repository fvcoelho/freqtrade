"""V2 variant — same strategy code, tighter knobs via twin_pennies_hybrid_v2_config.json.

V2 changes from V1:
    SHORT (mean reversion):
        - entry_z: 1.2 -> 1.5  (only stronger divergences)
        - loser_max_candles: 3 -> 2  (kick losers faster)
        - max_candles: 30 -> 24  (don't sit on time-stops)
        - safety_stop: -0.1167 -> -0.08  (cut MR losses earlier)
    LONG (breakout):
        - min_breakout_atr_mult: 0.15 -> 0.30  (require clean break)
        - min_atr_z: NEW, 0.5  (volatility expanding, not contracting)
        - chandelier_atr_mult: 2.5 -> 1.5  (much faster trailing on retracement)
        - chandelier_min_profit: 0.005 -> 0.002  (start trailing sooner)
        - invalidation_atr_buffer: 0.5 -> 0.25  (faster exit on fake breakout)
        - max_scale_times: 1 -> 0  (no scaling losing/winning longs — flat sizing)
        - safety_stop: -0.10 -> -0.07
        - max_candles: 48 -> 36
"""
import sys
from pathlib import Path

_STRATEGIES_DIR = str(Path(__file__).resolve().parent)
if _STRATEGIES_DIR not in sys.path:
    sys.path.insert(0, _STRATEGIES_DIR)

from twin_pennies_hybrid.strategy import TwinPenniesHybridStrategy as _Base


class TwinPenniesHybridV2Strategy(_Base):
    CONFIG_PATH = Path(__file__).parent / "twin_pennies_hybrid_v2_config.json"
