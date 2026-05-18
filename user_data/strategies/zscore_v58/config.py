"""Configuration loader for ZScore V57 strategy."""
from __future__ import annotations

import json
from pathlib import Path


def load(path: Path) -> dict:
    """Load and return JSON config dict.

    Raises:
        FileNotFoundError: if *path* does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path, "r") as f:
        return json.load(f)
