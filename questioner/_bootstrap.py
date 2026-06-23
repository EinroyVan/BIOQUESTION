"""Ensure the project root is on sys.path before package imports."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ROOT_TEXT = str(PROJECT_ROOT)
if _ROOT_TEXT not in sys.path:
    sys.path.insert(0, _ROOT_TEXT)
