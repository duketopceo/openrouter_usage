"""In-memory TTL cache."""

from __future__ import annotations

import time
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class TtlCache(Generic[T]):
    def __init__(self):
        self._value: T | None = None
        self._expires_at = 0.0

    def get(self) -> T | None:
        if self._value is None or time.monotonic() >= self._expires_at:
            return None
        return self._value

    def set(self, value: T, ttl_seconds: float) -> None:
        self._value = value
        self._expires_at = time.monotonic() + max(1.0, ttl_seconds)

    def clear(self) -> None:
        self._value = None
        self._expires_at = 0.0
