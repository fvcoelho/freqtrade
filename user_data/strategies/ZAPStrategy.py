"""ZAP Strategy — top-level shim for freqtrade resolver.

The actual implementation lives in zap/strategy.py.
This file exists because freqtrade's resolver scans for
'class <Name>' in top-level .py files.
"""
import sys
from pathlib import Path

# Ensure zap package is importable
_strategies_dir = str(Path(__file__).resolve().parent)
if _strategies_dir not in sys.path:
    sys.path.insert(0, _strategies_dir)

from zap.agents.entry import EntryAgent  # noqa: E402
from zap.agents.manager import ManagerAgent  # noqa: E402
from zap.agents.regime import RegimeAgent  # noqa: E402
from zap.agents.scanner import ScannerAgent  # noqa: E402
from zap.config import load_config  # noqa: E402
from zap.queues import QueueManager  # noqa: E402

# Re-import the actual strategy base
from zap.strategy import ZAPStrategy as _ZAPBase  # noqa: E402


class ZAPStrategy(_ZAPBase):
    """ZScore Agent Pipeline Strategy with FreqAI."""
    pass
