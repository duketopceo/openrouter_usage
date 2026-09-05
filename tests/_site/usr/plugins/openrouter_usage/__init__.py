"""Test shim: point usr.plugins.openrouter_usage at the repo root."""

from __future__ import annotations

from pathlib import Path

__path__ = [str(Path(__file__).resolve().parents[5])]
