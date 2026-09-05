"""Shared HTTP for OpenRouter (facade over engine.fetch)."""

from __future__ import annotations

from usr.plugins.openrouter_usage.engine.fetch import (
    OpenRouterError,
    get_json,
    patch_json,
    post_json,
    request_json,
    with_query,
)

__all__ = [
    "OpenRouterError",
    "get_json",
    "patch_json",
    "post_json",
    "request_json",
    "with_query",
]
