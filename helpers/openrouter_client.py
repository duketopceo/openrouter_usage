"""Agent Zero compatibility facade over the OpenRouter usage engine."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from helpers.plugins import get_plugin_config
from helpers.secrets import get_secrets_manager
from usr.plugins.openrouter_usage.engine import analytics, budgets as engine_budgets, cache, db, models
from usr.plugins.openrouter_usage.engine.api import (
    API_BASE,
    get_activity,
    get_credits,
    get_keys,
    list_budgets,
    list_workspaces,
    query_analytics,
    update_workspace,
)
from usr.plugins.openrouter_usage.engine.models import (
    AnalyticsQuery,
    Credits,
    Key,
    RoutingDefaults,
    Workspace,
)
from usr.plugins.openrouter_usage.engine.recommender import recommend as recommend_routing
from usr.plugins.openrouter_usage.helpers.aliases import label_for_key, parse_aliases
from usr.plugins.openrouter_usage.helpers.fetch import OpenRouterError, get_json, with_query
from usr.plugins.openrouter_usage.helpers.format import chart_date_label, format_usd

_OVERVIEW_CACHE: cache.KeyedTtlCache[str, dict[str, Any]] = cache.KeyedTtlCache()


def load_settings(agent: Any = None) -> dict[str, Any]:
    config = get_plugin_config("openrouter_usage", agent=agent) or {}
    watched = config.get("watched_key_hashes") or []
    if not isinstance(watched, list):
        watched = []
    return {
        "watched_key_hashes": [str(item).strip().lower() for item in watched if str(item).strip()],
        "key_aliases": str(config.get("key_aliases") or ""),
        "refresh_interval_minutes": max(1, int(config.get("refresh_interval_minutes") or 5)),
        "default_view": str(config.get("default_view") or "simple"),
        "show_token_counts": bool(config.get("show_token_counts", True)),
        "history_days": max(1, int(config.get("history_days") or 90)),
        "budget_alert_threshold": float(config.get("budget_alert_threshold") or 0.8),
        "burn_window_days": max(1, int(config.get("burn_window_days") or 30)),
        "pinned_workspace_id": str(config.get("pinned_workspace_id") or ""),
    }


def management_key() -> str:
    return get_secrets_manager().load_secrets().get("OPENROUTER_MANAGEMENT_KEY", "").strip()


def _key_to_dict(key: Key, aliases: dict[str, str]) -> dict[str, Any]:
    prefix = key.hash[:8].lower() if key.hash else ""
    label = label_for_key(key.hash, key.name or "", key.label or "", aliases)
    return {
        "hash_prefix": prefix,
        "hash": key.hash,
        "label": label,
        "name": key.name,
        "disabled": key.disabled,
        "limit": key.limit,
        "limit_remaining": key.limit_remaining,
        "limit_reset": key.limit_reset,
        "usage": key.usage,
        "usage_daily": key.usage_daily,
        "usage_weekly": key.usage_weekly,
        "usage_monthly": key.usage_monthly,
        "byok_usage": key.byok_usage,
        "byok_usage_daily": key.byok_usage_daily,
        "byok_usage_weekly": key.byok_usage_weekly,
        "byok_usage_monthly": key.byok_usage_monthly,
        "workspace_id": key.workspace_id,
    }


def _workspace_to_dict(workspace: Workspace, selected_id: str | None) -> dict[str, Any]:
    data = workspace.to_dict()
    data["selected"] = workspace.id == selected_id if selected_id else False
    return data


def _daily_from_activity(activity_rows: list[models.Activity]) -> list[dict[str, Any]]:
    daily: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for record in activity_rows:
        day = chart_date_label(record.date or "")
        if not day:
            continue
        label = record.key_label() or "all"
        daily[day][label] += record.usage
    return [{"label": day, "by_key": dict(values)} for day, values in sorted(daily.items())]


def _per_key_from_activity(activity_rows: list[models.Activity]) -> list[dict[str, Any]]:
    per_key: dict[str, dict[str, Any]] = {}
    for record in activity_rows:
        label = record.key_label() or record.provider_name or record.model or "unknown"
        bucket = per_key.setdefault(
            label,
            {
                "label": label,
                "hash_prefix": "",
                "hash": "",
                "usd": 0.0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "reasoning_tokens": 0,
                "requests": 0,
            },
        )
        bucket["usd"] += record.usage
        bucket["prompt_tokens"] += record.prompt_tokens
        bucket["completion_tokens"] += record.completion_tokens
        bucket["reasoning_tokens"] += record.reasoning_tokens
        bucket["requests"] += record.requests
    results = list(per_key.values())
    results.sort(key=lambda item: item["usd"], reverse=True)
    return results


def _top_models_from_activity(activity_rows: list[models.Activity]) -> list[dict[str, Any]]:
    per_model: dict[str, float] = defaultdict(float)
    for record in activity_rows:
        model = record.model or record.model_permaslug or "unknown"
        per_model[model] += record.usage
    return sorted(
        [{"model": model, "usd": value} for model, value in per_model.items()],
        key=lambda item: item["usd"],
        reverse=True,
    )[:12]


def _fetch_tagged_activity(
    api_key: str,
    keys: list[Key],
    aliases: dict[str, str],
    watched: list[str],
) -> list[models.Activity]:
    """Fetch aggregate or per-key activity and tag rows with key labels."""
    rows: list[models.Activity] = []

    def _tag(raw_rows: list[Any], meta: dict[str, Any]) -> None:
        prefix = meta.get("hash_prefix") or ""
        label = meta.get("label") or prefix
        for record in raw_rows:
            if not isinstance(record, dict):
                continue
            record["_key_prefix"] = prefix
            record["_key_label"] = label
            rows.append(models.Activity.from_dict(record))

    keys_for_activity = [k for k in keys if not watched or any(k.hash.lower().startswith(w) or k.hash[:8].lower().startswith(w[:8]) for w in watched)] if watched else []

    if not watched:
        try:
            payload = get_json(f"{API_BASE}/activity", api_key)
            raw = payload if isinstance(payload, list) else (payload.get("data") if isinstance(payload, dict) else [])
            if not isinstance(raw, list):
                raw = []
            _tag(raw, {"hash_prefix": "all", "label": "all"})
        except OpenRouterError:
            pass
    else:
        for key in keys_for_activity:
            try:
                payload = get_json(
                    with_query(f"{API_BASE}/activity", {"api_key_hash": key.hash}),
                    api_key,
                )
                raw = payload if isinstance(payload, list) else (payload.get("data") if isinstance(payload, dict) else [])
                if not isinstance(raw, list):
                    raw = []
                label = label_for_key(key.hash, key.name or "", key.label or "", aliases)
                _tag(raw, {"hash_prefix": key.hash[:8].lower(), "label": label})
            except OpenRouterError:
                pass

    return rows


def _empty_overview(empty_state: str, message: str, settings: dict[str, Any] | None = None) -> dict[str, Any]:
    return models.Overview(
        ok=False,
        empty_state=empty_state,
        credits=None,
        keys=[],
        totals={"usd": 0.0, "usd_label": "$0.0000"},
        daily=[],
        top_models=[],
        per_key=[],
        top_keys=[],
        top_providers=[],
        top_apps=[],
        workspaces=[],
        workspace_id=None,
        activity=[],
        routing={},
        budgets=[],
        alerts=[],
        settings=settings or {},
        as_of=None,
        last_error=message,
        errors=[message],
    ).to_dict()


def fetch_overview(agent: Any = None, *, force: bool = False, workspace_id: str | None = None) -> dict[str, Any]:
    settings = load_settings(agent)
    ttl = settings["refresh_interval_minutes"] * 60
    selected = workspace_id or settings.get("pinned_workspace_id") or None
    cache_key = selected or "__org__"

    if not force:
        cached = _OVERVIEW_CACHE.get(cache_key)
        if cached is not None:
            return cached

    key = management_key()
    if not key:
        payload = _empty_overview("missing_management_key", "Add OPENROUTER_MANAGEMENT_KEY to Agent Zero Secrets.", settings)
        _OVERVIEW_CACHE.set(cache_key, payload, ttl)
        return payload

    aliases = parse_aliases(settings["key_aliases"])
    watched = settings["watched_key_hashes"]
    errors: list[str] = []

    try:
        workspaces = list_workspaces(key)
    except OpenRouterError as exc:
        workspaces = []
        errors.append(str(exc))

    # Resolve the effective workspace before any scoped queries.
    current_ws = next((w for w in workspaces if w.id == selected), None)
    if not current_ws and workspaces:
        current_ws = workspaces[0]
    if current_ws:
        selected = current_ws.id
    cache_key = selected or "__org__"

    if not force:
        cached = _OVERVIEW_CACHE.get(cache_key)
        if cached is not None:
            return cached

    try:
        credits_obj = get_credits(key)
    except OpenRouterError as exc:
        credits_obj = Credits()
        errors.append(str(exc))

    try:
        keys = get_keys(key, selected)
    except OpenRouterError as exc:
        keys = []
        errors.append(str(exc))

    try:
        activity = _fetch_tagged_activity(key, keys, aliases, watched)
    except Exception as exc:
        activity = []
        errors.append(str(exc))

    analytics_rows: list[models.AnalyticsRow] = []
    now = datetime.now(timezone.utc)
    start_time = (now - timedelta(days=settings["history_days"])).isoformat()
    end_time = now.isoformat()

    query = AnalyticsQuery(
        metrics=[
            "total_usage",
            "request_count",
            "tokens_prompt",
            "tokens_completion",
            "reasoning_tokens",
            "avg_latency",
            "p90_latency",
            "avg_throughput",
            "p90_throughput",
            "cache_hit_rate",
            "blended_cost_per_million_tokens",
        ],
        dimensions=[
            "model",
            "variant",
            "provider",
            "api_key_id",
            "app",
            "workspace",
            "date",
            "endpoint_id",
        ],
        time_granularity="day",
        start_time=start_time,
        end_time=end_time,
        limit=2000,
    )

    try:
        fresh_rows = query_analytics(key, query, selected)
        usage_db = db.UsageDb()
        usage_db.upsert(fresh_rows)
        analytics_rows = usage_db.merge_metrics(
            usage_db.query(workspace_id=selected, start_time=start_time, end_time=end_time)
        )
        usage_db.prune(settings["history_days"])
        usage_db.close()
    except OpenRouterError as exc:
        errors.append(str(exc))
        try:
            usage_db = db.UsageDb()
            analytics_rows = usage_db.merge_metrics(
                usage_db.query(workspace_id=selected, start_time=start_time, end_time=end_time)
            )
            usage_db.close()
        except Exception:
            pass
    except Exception as exc:
        errors.append(str(exc))

    normalized_keys = [_key_to_dict(k, aliases) for k in keys]
    hash_to_label = {k["hash_prefix"]: k["label"] for k in normalized_keys if k.get("hash_prefix")}

    if analytics_rows:
        totals = analytics.build_totals_from_analytics(analytics_rows)
        top_models = analytics.top_by_dimension(analytics_rows, "model", "total_usage", top_n=12, label_key="model")
        top_providers = analytics.top_by_dimension(analytics_rows, "provider", "total_usage", top_n=12, label_key="provider")
        top_apps = analytics.top_by_dimension(analytics_rows, "app", "total_usage", top_n=12, label_key="app")
        per_key = analytics.per_key_from_analytics(analytics_rows, keys, aliases) or _per_key_from_activity(activity)
        activity_list: list[dict[str, Any]] = [a.to_dict() for a in activity]
    else:
        totals = analytics.build_totals_from_activity(activity)
        top_models = _top_models_from_activity(activity)
        top_providers = []
        top_apps = []
        per_key = _per_key_from_activity(activity)
        activity_list = [a.to_dict() for a in activity]

    daily = analytics.daily_series(analytics_rows) if analytics_rows else _daily_from_activity(activity)
    top_keys = per_key[:3]

    current_routing = RoutingDefaults.from_workspace(current_ws)
    recommendation = recommend_routing(analytics_rows, current_routing) if analytics_rows else models.Recommendation(current=current_routing, recommended=current_routing)

    budgets: list[models.Budget] = []
    burn: dict[str, Any] = {"projected_burn": None, "daily_rate": 0.0, "alerts": []}
    if selected:
        try:
            budgets = list_budgets(key, selected)
        except OpenRouterError as exc:
            errors.append(str(exc))
    if credits_obj:
        burn = engine_budgets.project_burn(
            credits_obj,
            budgets,
            totals.get("usd", 0.0),
            settings["burn_window_days"],
            settings["budget_alert_threshold"],
        )

    credits_dict = {
        "balance": credits_obj.total_credits,
        "total_usage": credits_obj.total_usage,
        "balance_label": format_usd(credits_obj.total_credits or 0) if credits_obj.total_credits is not None else "—",
        "usage_label": format_usd(credits_obj.total_usage or 0) if credits_obj.total_usage is not None else format_usd(totals["usd"]),
    }

    workspace_dicts = [_workspace_to_dict(w, selected) for w in workspaces]
    as_of = datetime.now(timezone.utc).isoformat()

    overview = models.Overview(
        ok=True,
        empty_state=None,
        credits=credits_dict,
        keys=normalized_keys,
        totals=totals,
        daily=daily,
        top_models=top_models,
        per_key=per_key,
        top_keys=top_keys,
        top_providers=top_providers,
        top_apps=top_apps,
        workspaces=workspace_dicts,
        workspace_id=selected,
        activity=activity_list,
        routing=recommendation.to_dict(),
        budgets=[b.to_dict() for b in budgets],
        alerts=burn["alerts"],
        settings={
            "default_view": settings["default_view"],
            "show_token_counts": settings["show_token_counts"],
            "refresh_interval_minutes": settings["refresh_interval_minutes"],
            "history_days": settings["history_days"],
            "budget_alert_threshold": settings["budget_alert_threshold"],
            "burn_window_days": settings["burn_window_days"],
            "pinned_workspace_id": settings["pinned_workspace_id"],
        },
        as_of=as_of,
        last_error="; ".join(errors) if errors else None,
        errors=errors,
        stale=bool(errors),
        hash_to_label=hash_to_label,
    )
    payload = overview.to_dict()
    _OVERVIEW_CACHE.set(cache_key, payload, ttl)
    return payload


def fetch_keys(agent: Any = None, workspace_id: str | None = None) -> dict[str, Any]:
    key = management_key()
    if not key:
        return {"ok": False, "keys": [], "error": "Missing OPENROUTER_MANAGEMENT_KEY"}
    settings = load_settings(agent)
    aliases = parse_aliases(settings["key_aliases"])
    try:
        keys = get_keys(key, workspace_id)
    except OpenRouterError as exc:
        return {"ok": False, "keys": [], "error": str(exc)}
    return {"ok": True, "keys": [_key_to_dict(k, aliases) for k in keys]}


def fetch_workspaces(agent: Any = None) -> dict[str, Any]:
    key = management_key()
    if not key:
        return {"ok": False, "workspaces": [], "error": "Missing OPENROUTER_MANAGEMENT_KEY"}
    try:
        workspaces = list_workspaces(key)
    except OpenRouterError as exc:
        return {"ok": False, "workspaces": [], "error": str(exc)}
    return {"ok": True, "workspaces": [w.to_dict() for w in workspaces]}


def fetch_analytics(agent: Any = None, request: dict[str, Any] | None = None) -> dict[str, Any]:
    key = management_key()
    if not key:
        return {"ok": False, "rows": [], "error": "Missing OPENROUTER_MANAGEMENT_KEY"}
    req = request or {}
    workspace_id = req.get("workspace_id") or load_settings(agent).get("pinned_workspace_id") or None
    query = AnalyticsQuery(
        metrics=req.get("metrics") or ["total_usage"],
        dimensions=req.get("dimensions") or [],
        time_granularity=req.get("time_granularity") or "day",
        start_time=req.get("start_time"),
        end_time=req.get("end_time"),
        limit=int(req.get("limit") or 1000),
    )
    try:
        rows = query_analytics(key, query, workspace_id)
    except OpenRouterError as exc:
        return {"ok": False, "rows": [], "error": str(exc)}
    return {"ok": True, "rows": [r.to_dict() for r in rows]}


def fetch_routing(agent: Any = None, workspace_id: str | None = None) -> dict[str, Any]:
    key = management_key()
    if not key:
        return {"ok": False, "error": "Missing OPENROUTER_MANAGEMENT_KEY"}
    try:
        workspaces = list_workspaces(key)
    except OpenRouterError as exc:
        return {"ok": False, "error": str(exc)}

    selected = workspace_id or load_settings(agent).get("pinned_workspace_id")
    workspace = next((w for w in workspaces if w.id == selected), workspaces[0] if workspaces else None)
    if not workspace:
        return {"ok": False, "error": "No workspace available"}

    current = RoutingDefaults.from_workspace(workspace)
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=30)).isoformat()
    end = now.isoformat()
    query = AnalyticsQuery(
        metrics=[
            "total_usage",
            "request_count",
            "avg_latency",
            "p90_latency",
            "avg_throughput",
            "p90_throughput",
            "cache_hit_rate",
            "blended_cost_per_million_tokens",
        ],
        dimensions=["model", "variant", "provider", "endpoint_id"],
        time_granularity="day",
        start_time=start,
        end_time=end,
        limit=1000,
    )
    try:
        rows = query_analytics(key, query, workspace.id)
    except OpenRouterError as exc:
        rows = []

    recommendation = recommend_routing(rows, current)
    return {
        "ok": True,
        "workspace_id": workspace.id,
        "current": recommendation.current.to_dict(),
        "recommended": recommendation.recommended.to_dict(),
        "tradeoffs": recommendation.tradeoffs,
        "confidence": recommendation.confidence,
        "note": recommendation.note,
    }


def apply_routing(
    agent: Any = None,
    workspace_id: str | None = None,
    defaults: dict[str, Any] | None = None,
    confirmed: bool = False,
) -> dict[str, Any]:
    if not confirmed:
        return {"ok": False, "error": "confirmed: true is required to apply routing changes"}
    if not workspace_id:
        return {"ok": False, "error": "workspace_id is required"}
    key = management_key()
    if not key:
        return {"ok": False, "error": "Missing OPENROUTER_MANAGEMENT_KEY"}
    try:
        updated = update_workspace(key, workspace_id, RoutingDefaults.from_dict(defaults or {}))
    except OpenRouterError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "workspace": updated.to_dict()}


def fetch_budgets(agent: Any = None, workspace_id: str | None = None, interval: str | None = None) -> dict[str, Any]:
    key = management_key()
    if not key:
        return {"ok": False, "budgets": [], "error": "Missing OPENROUTER_MANAGEMENT_KEY"}
    selected = workspace_id or load_settings(agent).get("pinned_workspace_id")
    if not selected:
        return {"ok": False, "budgets": [], "error": "workspace_id is required"}
    try:
        budgets = list_budgets(key, selected, interval)
    except OpenRouterError as exc:
        return {"ok": False, "budgets": [], "error": str(exc)}
    return {"ok": True, "budgets": [b.to_dict() for b in budgets]}


def invalidate_cache() -> None:
    _OVERVIEW_CACHE.clear()
