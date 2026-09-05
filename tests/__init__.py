"""Test package bootstrap."""

from __future__ import annotations

import sys
from pathlib import Path

_SITE = Path(__file__).resolve().parent / "_site"
if str(_SITE) not in sys.path:
    sys.path.insert(0, str(_SITE))
