"""V10 variant — V8 with long breakout DISABLED.

V10 = V8 base (asym lev 4x/7x + 3 short plugs) + disable_long=true.

Hypothesis: V8 longs contributed -$16 (-1.64%) over 60d. If we remove
the breakout long side entirely, the strategy becomes a pure short
mean-rev system. Expected gain:
    +$16 from killing the long drag
    Possibly less if shorts use up position slots that longs were
    occupying (so fewer simultaneous short trades).

This is the cleanest test of "does the long side add or subtract alpha
in this period?". If V10 > V8, longs are net-negative drag and should
be removed. If V10 < V8, the long side actually provided diversification
or freed up margin/slots.

Trade-off in production: removing longs means no upside capture in
strong bull markets (where the basket z-score for "leading" pairs may
stay positive forever — i.e., shorts get destroyed). This is purely a
backtest exercise.
"""
import sys
from pathlib import Path

_STRATEGIES_DIR = str(Path(__file__).resolve().parent)
if _STRATEGIES_DIR not in sys.path:
    sys.path.insert(0, _STRATEGIES_DIR)

from twin_pennies_hybrid.strategy import TwinPenniesHybridStrategy as _Base


class TwinPenniesHybridV10Strategy(_Base):
    CONFIG_PATH = Path(__file__).parent / "twin_pennies_hybrid_v10_config.json"
