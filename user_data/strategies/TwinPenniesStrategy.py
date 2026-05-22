"""Top-level shim for freqtrade strategy resolver.

Freqtrade's resolver does a text search for 'class TwinPenniesStrategy'
in the file, so a bare re-export doesn't work. This thin subclass satisfies
the resolver while delegating all logic to the package.
"""
import sys
from pathlib import Path

_STRATEGIES_DIR = str(Path(__file__).resolve().parent)
if _STRATEGIES_DIR not in sys.path:
    sys.path.insert(0, _STRATEGIES_DIR)

from twin_pennies.strategy import TwinPenniesStrategy as _Base


class TwinPenniesStrategy(_Base):
    pass
