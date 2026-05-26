"""V6 variant — V2 knobs + twin filter on shorts.

V6 = V2 + require_twin_for_short=true

Twin filter (mean-rev shorts only): before entering short on pair X,
require at least one OTHER basket pair to have z < -entry_z. This
confirms the basket is genuinely dispersed (one pair leading, one
lagging) rather than a single-pair anomaly. Hypothesis: tighter
short filter cuts the false `mr_time_stop` and `trailing_stop_loss`
losses seen in V1/V2 without sacrificing the `mr_winner_revert`
alpha (which only fires on real reversions).

Long breakout entries are NOT affected by the twin filter — they
use their own breakout signal (close > donchian_high + ATR mult).
"""
import sys
from pathlib import Path

_STRATEGIES_DIR = str(Path(__file__).resolve().parent)
if _STRATEGIES_DIR not in sys.path:
    sys.path.insert(0, _STRATEGIES_DIR)

from twin_pennies_hybrid.strategy import TwinPenniesHybridStrategy as _Base


class TwinPenniesHybridV6Strategy(_Base):
    CONFIG_PATH = Path(__file__).parent / "twin_pennies_hybrid_v6_config.json"
