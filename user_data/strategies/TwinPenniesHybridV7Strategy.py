"""V7 variant — V2 knobs + asymmetric leverage (short=4x, long=7x).

V7 = V2 + short_leverage=4

Hypothesis: V2 shorts lose -$779 in `trailing_stop_loss` (safety stop firing)
because 7x leverage on a 1.14% adverse move = -8% on the position. Cutting
short leverage from 7x to 4x means the same 1.14% move only causes -4.56%
on the position — well under the -8% safety stop. The safety stop fires
much less often, and when it does, each loss is ~43% smaller.

Trade-off: short winners also yield ~43% less per trade. But since the
`mr_winner_revert` exit fires on z-reversion (not leverage-dependent),
the GROSS win remains; it's the leveraged amplification that shrinks.

Longs stay at 7x because:
    - Breakout edge depends on capturing trends with leverage
    - Long `trailing_stop_loss` was only -$22 in V2 (already tame)
    - Reducing long leverage would hurt the wins more than help the losses
"""
import sys
from pathlib import Path

_STRATEGIES_DIR = str(Path(__file__).resolve().parent)
if _STRATEGIES_DIR not in sys.path:
    sys.path.insert(0, _STRATEGIES_DIR)

from twin_pennies_hybrid.strategy import TwinPenniesHybridStrategy as _Base


class TwinPenniesHybridV7Strategy(_Base):
    CONFIG_PATH = Path(__file__).parent / "twin_pennies_hybrid_v7_config.json"
