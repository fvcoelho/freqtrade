"""Top-level shim for freqtrade strategy resolver."""
import sys
from pathlib import Path

_STRATEGIES_DIR = str(Path(__file__).resolve().parent)
if _STRATEGIES_DIR not in sys.path:
    sys.path.insert(0, _STRATEGIES_DIR)

from twin_pennies_allin.strategy import TwinPenniesAllInStrategy as _Base


class TwinPenniesAllInStrategy(_Base):
    pass
