"""In-memory TTL cache utilities."""

from __future__ import annotations

import time
from typing import Any, Generic, TypeVar

T = TypeVar("T")
K = TypeVar("K")


class TtlCache(Generic[T]):
    """Simple single-value TTL cache."""

    def __init__(self) -> None:
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


class KeyedTtlCache(Generic[K, T]):
    """TTL cache keyed by an arbitrary hashable."""

    def __init__(self) -> None:
        self._store: dict[K, tuple[T, float]] = {}

    def get(self, key: K) -> T | None:
        entry = self._store.get(key)
        if entry is None or time.monotonic() >= entry[1]:
            return None
        return entry[0]

    def set(self, key: K, value: T, ttl_seconds: float) -> None:
        self._store[key] = (value, time.monotonic() + max(1.0, ttl_seconds))

    def clear(self, key: K | None = None) -> None:
        if key is None:
            self._store.clear()
        else:
            self._store.pop(key, None)
