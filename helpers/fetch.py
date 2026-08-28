"""Shared HTTP for OpenRouter."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class OpenRouterError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def get_json(url: str, api_key: str, timeout: float = 20.0) -> Any:
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise OpenRouterError(f"OpenRouter HTTP {exc.code}: {detail or exc.reason}", exc.code) from exc
    except urllib.error.URLError as exc:
        raise OpenRouterError(f"OpenRouter unreachable: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise OpenRouterError("OpenRouter returned invalid JSON") from exc


def with_query(base: str, params: dict[str, Any]) -> str:
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None and v != ""})
    return f"{base}?{query}" if query else base
