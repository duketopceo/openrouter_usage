"""Shared HTTP transport for OpenRouter."""

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


def request_json(
    method: str,
    url: str,
    api_key: str,
    json_body: Any | None = None,
    timeout: float = 20.0,
    extra_headers: dict[str, str] | None = None,
) -> Any:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)

    data: bytes | None = None
    if json_body is not None:
        data = json.dumps(json_body, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            if not raw.strip():
                return {} if method != "GET" else None
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise OpenRouterError(f"OpenRouter HTTP {exc.code}: {detail or exc.reason}", exc.code) from exc
    except urllib.error.URLError as exc:
        raise OpenRouterError(f"OpenRouter unreachable: {exc.reason}") from exc
    except TimeoutError as exc:
        raise OpenRouterError("OpenRouter unreachable: timeout") from exc
    except json.JSONDecodeError as exc:
        raise OpenRouterError("OpenRouter returned invalid JSON") from exc


def get_json(url: str, api_key: str, timeout: float = 20.0) -> Any:
    return request_json("GET", url, api_key, timeout=timeout)


def post_json(url: str, api_key: str, json_body: Any | None = None, timeout: float = 30.0) -> Any:
    return request_json("POST", url, api_key, json_body=json_body, timeout=timeout)


def patch_json(url: str, api_key: str, json_body: Any | None = None, timeout: float = 20.0) -> Any:
    return request_json("PATCH", url, api_key, json_body=json_body, timeout=timeout)


def with_query(base: str, params: dict[str, Any]) -> str:
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None and v != ""})
    return f"{base}?{query}" if query else base
