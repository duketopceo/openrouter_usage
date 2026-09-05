"""OpenRouter management API wrapper."""

from __future__ import annotations

from typing import Any

from .fetch import OpenRouterError, get_json, patch_json, post_json, with_query
from .models import (
    Activity,
    AnalyticsQuery,
    AnalyticsRow,
    Budget,
    Credits,
    Key,
    RoutingDefaults,
    Workspace,
)

API_BASE = "https://openrouter.ai/api/v1"


def _unwrap_list(payload: Any, *keys: str) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def _unwrap_dict(payload: Any, *keys: str) -> dict[str, Any]:
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, dict):
                return value
        return payload
    return {}


def list_workspaces(api_key: str) -> list[Workspace]:
    payload = get_json(f"{API_BASE}/workspaces", api_key)
    rows = _unwrap_list(payload, "data", "workspaces")
    return [Workspace.from_dict(row) for row in rows]


def get_keys(api_key: str, workspace_id: str | None = None) -> list[Key]:
    url = with_query(f"{API_BASE}/keys", {"workspace_id": workspace_id})
    payload = get_json(url, api_key)
    rows = _unwrap_list(payload, "data", "keys")
    keys = [Key.from_dict(row) for row in rows]
    if workspace_id:
        keys = [k for k in keys if k.workspace_id == workspace_id]
    return keys


def get_credits(api_key: str) -> Credits:
    payload = get_json(f"{API_BASE}/credits", api_key)
    data = _unwrap_dict(payload, "data")
    return Credits.from_dict(data)


def get_activity(api_key: str, workspace_id: str | None = None) -> list[Activity]:
    url = with_query(f"{API_BASE}/activity", {"workspace_id": workspace_id})
    payload = get_json(url, api_key)
    rows = _unwrap_list(payload, "data", "activity")
    activities = [Activity.from_dict(row) for row in rows]
    if workspace_id:
        activities = [a for a in activities if (a.workspace_id or workspace_id) == workspace_id]
    return activities


def _filter_workspace_rows(rows: list[AnalyticsRow], workspace_id: str | None) -> list[AnalyticsRow]:
    if not workspace_id:
        return rows
    return [r for r in rows if (r.workspace_id or workspace_id) == workspace_id]


def query_analytics(
    api_key: str,
    query: AnalyticsQuery | dict[str, Any],
    workspace_id: str | None = None,
) -> list[AnalyticsRow]:
    if isinstance(query, AnalyticsQuery):
        body = query.to_dict()
        dimensions = query.dimensions
        metrics = query.metrics
    else:
        body = dict(query)
        dimensions = body.get("dimensions") or []
        metrics = body.get("metrics") or []

    if workspace_id and "workspace" not in dimensions and not body.get("filters"):
        body["filters"] = body.get("filters") or []
        body["filters"].append({"dimension": "workspace", "operator": "eq", "value": workspace_id})

    payload = post_json(f"{API_BASE}/analytics/query", api_key, json_body=body)
    rows = _unwrap_list(payload, "data", "results", "rows")
    as_of = _s(payload.get("as_of")) if isinstance(payload, dict) else None

    analytics = [AnalyticsRow.from_dict(row, dimensions=dimensions, metrics=metrics, as_of=as_of) for row in rows]
    for row in analytics:
        if workspace_id and not row.workspace_id:
            row.workspace_id = workspace_id
    return _filter_workspace_rows(analytics, workspace_id)


def update_workspace(api_key: str, workspace_id: str, defaults: RoutingDefaults) -> Workspace:
    body: dict[str, Any] = {}
    if defaults.default_text_model is not None:
        body["default_text_model"] = defaults.default_text_model
    if defaults.default_image_model is not None:
        body["default_image_model"] = defaults.default_image_model
    if defaults.default_provider_sort is not None:
        body["default_provider_sort"] = defaults.default_provider_sort
    payload = patch_json(f"{API_BASE}/workspaces/{workspace_id}", api_key, json_body=body)
    return Workspace.from_dict(_unwrap_dict(payload, "data"))


def _budget_from_interval(payload: Any, interval: str, workspace_id: str | None) -> Budget:
    data = _unwrap_dict(payload, "data")
    return Budget.from_dict(data, interval=interval, workspace_id=workspace_id)


def list_budgets(
    api_key: str,
    workspace_id: str,
    interval: str | None = None,
) -> list[Budget]:
    if interval:
        payload = get_json(f"{API_BASE}/workspaces/{workspace_id}/budgets/{interval}", api_key)
        return [_budget_from_interval(payload, interval, workspace_id)]

    payload = get_json(f"{API_BASE}/workspaces/{workspace_id}/budgets", api_key)
    data = _unwrap_dict(payload, "data")
    if isinstance(data, dict):
        budgets: list[Budget] = []
        for key in ("daily", "weekly", "monthly", "lifetime"):
            value = data.get(key)
            if value is not None:
                budgets.append(Budget.from_dict(value, interval=key, workspace_id=workspace_id))
        return budgets
    rows = _unwrap_list(payload, "data", "budgets")
    return [Budget.from_dict(row, interval=str(i), workspace_id=workspace_id) for i, row in enumerate(rows)]


def _s(value: Any) -> str | None:
    return str(value) if value not in (None, "") else None
