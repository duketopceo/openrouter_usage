"""Typed domain models for OpenRouter usage data."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _s(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _f(value: Any) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def _i(value: Any) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _b(value: Any) -> bool:
    return bool(value)


def _ls(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Workspace:
    id: str
    slug: str | None = None
    name: str | None = None
    default_text_model: str | None = None
    default_image_model: str | None = None
    default_provider_sort: list[str] | None = None
    default_guardrail_id: str | None = None
    is_observability_io_logging_enabled: bool = False
    is_observability_broadcast_enabled: bool = False
    is_data_discount_logging_enabled: bool = False
    include_byok_in_budgets: bool = False
    created_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def from_dict(cls, payload: Any) -> Workspace:
        if not isinstance(payload, dict):
            return cls(id="")
        sort = payload.get("default_provider_sort")
        return cls(
            id=_s(payload.get("id")) or "",
            slug=_s(payload.get("slug")),
            name=_s(payload.get("name")),
            default_text_model=_s(payload.get("default_text_model")),
            default_image_model=_s(payload.get("default_image_model")),
            default_provider_sort=_ls(sort) if sort is not None else None,
            default_guardrail_id=_s(payload.get("default_guardrail_id")),
            is_observability_io_logging_enabled=_b(payload.get("is_observability_io_logging_enabled")),
            is_observability_broadcast_enabled=_b(payload.get("is_observability_broadcast_enabled")),
            is_data_discount_logging_enabled=_b(payload.get("is_data_discount_logging_enabled")),
            include_byok_in_budgets=_b(payload.get("include_byok_in_budgets")),
            created_at=_s(payload.get("created_at")),
            updated_at=_s(payload.get("updated_at")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "slug": self.slug,
            "name": self.name,
            "default_text_model": self.default_text_model,
            "default_image_model": self.default_image_model,
            "default_provider_sort": self.default_provider_sort,
            "default_guardrail_id": self.default_guardrail_id,
            "is_observability_io_logging_enabled": self.is_observability_io_logging_enabled,
            "is_observability_broadcast_enabled": self.is_observability_broadcast_enabled,
            "is_data_discount_logging_enabled": self.is_data_discount_logging_enabled,
            "include_byok_in_budgets": self.include_byok_in_budgets,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class Key:
    hash: str
    name: str | None = None
    label: str | None = None
    disabled: bool = False
    limit: float | None = None
    limit_remaining: float | None = None
    limit_reset: str | None = None
    usage: float = 0.0
    usage_daily: float = 0.0
    usage_weekly: float = 0.0
    usage_monthly: float = 0.0
    byok_usage: float = 0.0
    byok_usage_daily: float = 0.0
    byok_usage_weekly: float = 0.0
    byok_usage_monthly: float = 0.0
    workspace_id: str | None = None

    @classmethod
    def from_dict(cls, payload: Any) -> Key:
        if not isinstance(payload, dict):
            return cls(hash="")
        return cls(
            hash=_s(payload.get("hash") or payload.get("api_key_hash")) or "",
            name=_s(payload.get("name")),
            label=_s(payload.get("label")),
            disabled=_b(payload.get("disabled")),
            limit=_f(payload.get("limit")) or None,
            limit_remaining=_f(payload.get("limit_remaining")) or None,
            limit_reset=_s(payload.get("limit_reset")),
            usage=_f(payload.get("usage")),
            usage_daily=_f(payload.get("usage_daily")),
            usage_weekly=_f(payload.get("usage_weekly")),
            usage_monthly=_f(payload.get("usage_monthly")),
            byok_usage=_f(payload.get("byok_usage")),
            byok_usage_daily=_f(payload.get("byok_usage_daily")),
            byok_usage_weekly=_f(payload.get("byok_usage_weekly")),
            byok_usage_monthly=_f(payload.get("byok_usage_monthly")),
            workspace_id=_s(payload.get("workspace_id")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "hash": self.hash,
            "name": self.name,
            "label": self.label,
            "disabled": self.disabled,
            "limit": self.limit,
            "limit_remaining": self.limit_remaining,
            "limit_reset": self.limit_reset,
            "usage": self.usage,
            "usage_daily": self.usage_daily,
            "usage_weekly": self.usage_weekly,
            "usage_monthly": self.usage_monthly,
            "byok_usage": self.byok_usage,
            "byok_usage_daily": self.byok_usage_daily,
            "byok_usage_weekly": self.byok_usage_weekly,
            "byok_usage_monthly": self.byok_usage_monthly,
            "workspace_id": self.workspace_id,
        }


@dataclass
class Credits:
    total_credits: float | None = None
    total_usage: float | None = None

    @classmethod
    def from_dict(cls, payload: Any) -> Credits:
        if not isinstance(payload, dict):
            return cls()
        return cls(total_credits=_f(payload.get("total_credits")) or None, total_usage=_f(payload.get("total_usage")) or None)

    def to_dict(self) -> dict[str, Any]:
        return {"total_credits": self.total_credits, "total_usage": self.total_usage}


@dataclass
class Activity:
    date: str | None = None
    model_permaslug: str | None = None
    model: str | None = None
    endpoint_id: str | None = None
    usage: float = 0.0
    byok_usage_inference: float = 0.0
    requests: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    byok_requests: int = 0
    provider_name: str | None = None
    workspace_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Any) -> Activity:
        if not isinstance(payload, dict):
            return cls()
        known = {
            "date",
            "model_permaslug",
            "model",
            "endpoint_id",
            "usage",
            "byok_usage_inference",
            "requests",
            "prompt_tokens",
            "completion_tokens",
            "reasoning_tokens",
            "byok_requests",
            "provider_name",
            "workspace_id",
        }
        extra = {k: v for k, v in payload.items() if k not in known}
        return cls(
            date=_s(payload.get("date")),
            model_permaslug=_s(payload.get("model_permaslug")),
            model=_s(payload.get("model")),
            endpoint_id=_s(payload.get("endpoint_id")),
            usage=_f(payload.get("usage")),
            byok_usage_inference=_f(payload.get("byok_usage_inference")),
            requests=_i(payload.get("requests")),
            prompt_tokens=_i(payload.get("prompt_tokens")),
            completion_tokens=_i(payload.get("completion_tokens")),
            reasoning_tokens=_i(payload.get("reasoning_tokens")),
            byok_requests=_i(payload.get("byok_requests")),
            provider_name=_s(payload.get("provider_name")),
            workspace_id=_s(payload.get("workspace_id")),
            extra=extra,
        )

    def key_label(self) -> str | None:
        return self.extra.get("_key_label") or self.extra.get("_key_prefix")

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "model_permaslug": self.model_permaslug,
            "model": self.model,
            "endpoint_id": self.endpoint_id,
            "usage": self.usage,
            "byok_usage_inference": self.byok_usage_inference,
            "requests": self.requests,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "byok_requests": self.byok_requests,
            "provider_name": self.provider_name,
            "workspace_id": self.workspace_id,
            **self.extra,
        }


@dataclass
class AnalyticsRow:
    dimensions: dict[str, str | None] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)
    start_time: str | None = None
    end_time: str | None = None
    as_of: str | None = None
    workspace_id: str | None = None

    def dimension(self, name: str) -> str | None:
        return self.dimensions.get(name)

    def metric(self, name: str, default: float = 0.0) -> float:
        return self.metrics.get(name, default)

    @classmethod
    def from_dict(
        cls,
        payload: Any,
        dimensions: list[str] | None = None,
        metrics: list[str] | None = None,
        as_of: str | None = None,
    ) -> AnalyticsRow:
        if not isinstance(payload, dict):
            return cls()
        row_dim: dict[str, str | None] = {}
        row_metrics: dict[str, float] = {}

        if dimensions and metrics:
            for dim in dimensions:
                row_dim[dim] = _s(payload.get(dim))
            for met in metrics:
                row_metrics[met] = _f(payload.get(met))
        else:
            for key, value in payload.items():
                if key in ("start_time", "end_time", "as_of", "workspace_id"):
                    continue
                if isinstance(value, bool):
                    row_dim[key] = str(value)
                elif isinstance(value, (int, float)):
                    row_metrics[key] = float(value)
                elif isinstance(value, str):
                    row_dim[key] = value

        workspace_id = _s(payload.get("workspace_id") or payload.get("workspace") or row_dim.get("workspace"))
        return cls(
            dimensions=row_dim,
            metrics=row_metrics,
            start_time=_s(payload.get("start_time")),
            end_time=_s(payload.get("end_time")),
            as_of=as_of or _s(payload.get("as_of")),
            workspace_id=workspace_id,
        )

    def dimension_json(self) -> str:
        return json.dumps(self.dimensions, sort_keys=True, separators=(",", ":"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimensions": self.dimensions,
            "metrics": self.metrics,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "as_of": self.as_of,
            "workspace_id": self.workspace_id,
        }


@dataclass
class Budget:
    interval: str
    workspace_id: str | None = None
    limit: float | None = None
    limit_remaining: float | None = None
    limit_reset: str | None = None
    usage: float = 0.0
    usage_daily: float = 0.0
    usage_weekly: float = 0.0
    usage_monthly: float = 0.0
    lifetime: float = 0.0

    @classmethod
    def from_dict(cls, payload: Any, interval: str = "", workspace_id: str | None = None) -> Budget:
        if not isinstance(payload, dict):
            return cls(interval=interval or "", workspace_id=workspace_id)
        return cls(
            interval=interval or _s(payload.get("interval")) or "",
            workspace_id=workspace_id or _s(payload.get("workspace_id")),
            limit=_f(payload.get("limit")) or None,
            limit_remaining=_f(payload.get("limit_remaining")) or None,
            limit_reset=_s(payload.get("limit_reset")),
            usage=_f(payload.get("usage")),
            usage_daily=_f(payload.get("usage_daily")),
            usage_weekly=_f(payload.get("usage_weekly")),
            usage_monthly=_f(payload.get("usage_monthly")),
            lifetime=_f(payload.get("lifetime")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "interval": self.interval,
            "workspace_id": self.workspace_id,
            "limit": self.limit,
            "limit_remaining": self.limit_remaining,
            "limit_reset": self.limit_reset,
            "usage": self.usage,
            "usage_daily": self.usage_daily,
            "usage_weekly": self.usage_weekly,
            "usage_monthly": self.usage_monthly,
            "lifetime": self.lifetime,
        }


@dataclass
class RoutingDefaults:
    default_text_model: str | None = None
    default_image_model: str | None = None
    default_provider_sort: list[str] | None = None

    @classmethod
    def from_dict(cls, payload: Any) -> RoutingDefaults:
        if not isinstance(payload, dict):
            return cls()
        sort = payload.get("default_provider_sort")
        return cls(
            default_text_model=_s(payload.get("default_text_model")),
            default_image_model=_s(payload.get("default_image_model")),
            default_provider_sort=_ls(sort) if sort is not None else None,
        )

    @classmethod
    def from_workspace(cls, workspace: Workspace | None) -> RoutingDefaults:
        if not workspace:
            return cls()
        return cls(
            default_text_model=workspace.default_text_model,
            default_image_model=workspace.default_image_model,
            default_provider_sort=workspace.default_provider_sort,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "default_text_model": self.default_text_model,
            "default_image_model": self.default_image_model,
            "default_provider_sort": self.default_provider_sort,
        }


@dataclass
class Recommendation:
    current: RoutingDefaults = field(default_factory=RoutingDefaults)
    recommended: RoutingDefaults = field(default_factory=RoutingDefaults)
    tradeoffs: dict[str, Any] = field(default_factory=dict)
    confidence: str = "low"
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "current": self.current.to_dict(),
            "recommended": self.recommended.to_dict(),
            "tradeoffs": self.tradeoffs,
            "confidence": self.confidence,
            "note": self.note,
        }


@dataclass
class Overview:
    ok: bool = True
    empty_state: str | None = None
    credits: dict[str, Any] | None = None
    keys: list[dict[str, Any]] = field(default_factory=list)
    totals: dict[str, Any] = field(default_factory=dict)
    daily: list[dict[str, Any]] = field(default_factory=list)
    top_models: list[dict[str, Any]] = field(default_factory=list)
    per_key: list[dict[str, Any]] = field(default_factory=list)
    top_keys: list[dict[str, Any]] = field(default_factory=list)
    top_providers: list[dict[str, Any]] = field(default_factory=list)
    top_apps: list[dict[str, Any]] = field(default_factory=list)
    workspaces: list[dict[str, Any]] = field(default_factory=list)
    workspace_id: str | None = None
    activity: list[dict[str, Any]] = field(default_factory=list)
    routing: dict[str, Any] = field(default_factory=dict)
    budgets: list[dict[str, Any]] = field(default_factory=list)
    alerts: list[dict[str, Any]] = field(default_factory=list)
    settings: dict[str, Any] = field(default_factory=dict)
    as_of: str | None = None
    last_error: str | None = None
    errors: list[str] = field(default_factory=list)
    stale: bool = False
    hash_to_label: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "empty_state": self.empty_state,
            "credits": self.credits,
            "keys": self.keys,
            "totals": self.totals,
            "daily": self.daily,
            "top_models": self.top_models,
            "per_key": self.per_key,
            "top_keys": self.top_keys,
            "top_providers": self.top_providers,
            "top_apps": self.top_apps,
            "workspaces": self.workspaces,
            "workspace_id": self.workspace_id,
            "activity": self.activity,
            "routing": self.routing,
            "budgets": self.budgets,
            "alerts": self.alerts,
            "settings": self.settings,
            "as_of": self.as_of,
            "last_error": self.last_error,
            "errors": self.errors,
            "stale": self.stale,
            "hash_to_label": self.hash_to_label,
        }


@dataclass
class AnalyticsQuery:
    metrics: list[str] = field(default_factory=lambda: ["total_usage"])
    dimensions: list[str] = field(default_factory=list)
    time_granularity: str = "day"
    start_time: str | None = None
    end_time: str | None = None
    limit: int = 1000
    filters: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "metrics": self.metrics,
            "dimensions": self.dimensions,
            "time_granularity": self.time_granularity,
            "limit": self.limit,
        }
        if self.start_time:
            body["start_time"] = self.start_time
        if self.end_time:
            body["end_time"] = self.end_time
        if self.filters:
            body["filters"] = self.filters
        return body
