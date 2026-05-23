"""Configuration loader for MicroRevert strategy."""
from __future__ import annotations

import json
from pathlib import Path


def load(path: Path) -> dict:
    """Load and return JSON config dict."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path, "r") as f:
        return json.load(f)
