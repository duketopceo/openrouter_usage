"""Analytics aggregation helpers."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from usr.plugins.openrouter_usage.helpers.aliases import label_for_key, parse_aliases
from usr.plugins.openrouter_usage.helpers.format import chart_date_label, format_usd

from .models import Activity, AnalyticsRow, Key


_IMAGE_TOKENS = {
    "dall-e",
    "midjourney",
    "stable-diffusion",
    "sdxl",
    "flux",
    "ideogram",
    "kandinsky",
    "image",
    "vision",
    "imagen",
}


def is_image_model(model: str | None, variant: str | None = None, endpoint_id: str | None = None) -> bool:
    text = " ".join([x or "" for x in (model, variant, endpoint_id)]).lower()
    return any(token in text for token in _IMAGE_TOKENS)


def is_text_model(model: str | None, variant: str | None = None, endpoint_id: str | None = None) -> bool:
    return not is_image_model(model, variant, endpoint_id)


def _metric_value(row: AnalyticsRow, metric: str) -> float:
    return row.metric(metric)


def group_by_dimension(
    rows: list[AnalyticsRow],
    dimension: str,
    metrics: list[str] | None = None,
) -> dict[str, dict[str, float]]:
    grouped: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    metrics_to_sum = metrics or ["total_usage"]
    for row in rows:
        value = row.dimension(dimension)
        if value is None:
            value = "unknown"
        bucket = grouped[value]
        for metric in metrics_to_sum:
            if metric in row.metrics:
                bucket[metric] += row.metrics[metric]
    return {k: dict(v) for k, v in grouped.items()}


def top_by_dimension(
    rows: list[AnalyticsRow],
    dimension: str,
    sort_metric: str = "total_usage",
    top_n: int = 12,
    metrics: list[str] | None = None,
    label_key: str = "value",
) -> list[dict[str, Any]]:
    metrics_to_sum = metrics or [sort_metric]
    grouped = group_by_dimension(rows, dimension, metrics=metrics_to_sum)
    results: list[dict[str, Any]] = []
    for value, totals in grouped.items():
        item = {label_key: value}
        item.update(totals)
        results.append(item)
    results.sort(key=lambda item: item.get(sort_metric, 0.0), reverse=True)
    return results[:top_n]


def totals(rows: list[AnalyticsRow], metrics: list[str] | None = None) -> dict[str, float]:
    metrics_to_sum = metrics or [
        "total_usage",
        "request_count",
        "tokens_prompt",
        "tokens_completion",
        "reasoning_tokens",
    ]
    out: dict[str, float] = {m: 0.0 for m in metrics_to_sum}
    for row in rows:
        for metric in metrics_to_sum:
            if metric in row.metrics:
                out[metric] += row.metrics[metric]
    return out


def daily_series(
    rows: list[AnalyticsRow],
    metric: str = "total_usage",
    date_dimension: str = "date",
) -> list[dict[str, Any]]:
    grouped: dict[str, float] = defaultdict(float)
    for row in rows:
        day = row.dimension(date_dimension)
        if not day and row.start_time:
            try:
                dt = datetime.fromisoformat(row.start_time.replace("Z", "+00:00"))
                day = dt.strftime("%Y-%m-%d")
            except ValueError:
                day = row.start_time[:10]
        if not day:
            day = "unknown"
        grouped[day] += row.metric(metric)

    series: list[dict[str, Any]] = []
    for day in sorted(grouped):
        label = chart_date_label(day)
        series.append({"day": day, "label": label or day, "usd": grouped[day]})
    return series


def per_key_from_analytics(
    rows: list[AnalyticsRow],
    keys: list[Key] | None = None,
    aliases: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    aliases = aliases or {}
    key_lookup: dict[str, Key] = {}
    if keys:
        for k in keys:
            if k.hash:
                key_lookup[k.hash.lower()] = k
                key_lookup[k.hash[:8].lower()] = k

    grouped = group_by_dimension(
        rows,
        "api_key_id",
        metrics=["total_usage", "request_count", "tokens_prompt", "tokens_completion", "reasoning_tokens"],
    )
    results: list[dict[str, Any]] = []
    for api_key_id, totals in grouped.items():
        key_obj = key_lookup.get(str(api_key_id).lower())
        hash_value = key_obj.hash if key_obj else str(api_key_id)
        label = label_for_key(hash_value, key_obj.name if key_obj else "", key_obj.label if key_obj else "", aliases)
        results.append(
            {
                "label": label,
                "hash_prefix": hash_value[:8].lower() if hash_value else "",
                "hash": hash_value,
                "usd": totals.get("total_usage", 0.0),
                "prompt_tokens": int(totals.get("tokens_prompt", 0)),
                "completion_tokens": int(totals.get("tokens_completion", 0)),
                "reasoning_tokens": int(totals.get("reasoning_tokens", 0)),
                "requests": int(totals.get("request_count", 0)),
            }
        )
    results.sort(key=lambda item: item["usd"], reverse=True)
    return results


def per_key_from_activity(
    activity_rows: list[Activity],
    keys: list[Key] | None = None,
    aliases: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    aliases = aliases or {}
    key_lookup: dict[str, Key] = {}
    if keys:
        for k in keys:
            if k.hash:
                key_lookup[k.hash.lower()] = k
                key_lookup[k.hash[:8].lower()] = k

    per_key: dict[str, dict[str, Any]] = {}
    for record in activity_rows:
        label = record.key_label() or record.model or "unknown"
        prefix = record.extra.get("_key_prefix") or ""
        bucket = per_key.setdefault(
            label,
            {
                "label": label,
                "hash_prefix": prefix,
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


def daily_from_activity(activity_rows: list[Activity]) -> list[dict[str, Any]]:
    daily: dict[str, float] = defaultdict(float)
    for record in activity_rows:
        day = (record.date or "")[:10]
        if not day:
            continue
        daily[day] += record.usage
    return [
        {"day": day, "label": chart_date_label(day) or day, "usd": value}
        for day, value in sorted(daily.items())
    ]


def build_totals_from_analytics(rows: list[AnalyticsRow]) -> dict[str, Any]:
    totals_map = totals(rows)
    usd = totals_map.get("total_usage", 0.0)
    return {
        "usd": usd,
        "prompt_tokens": int(totals_map.get("tokens_prompt", 0)),
        "completion_tokens": int(totals_map.get("tokens_completion", 0)),
        "reasoning_tokens": int(totals_map.get("reasoning_tokens", 0)),
        "requests": int(totals_map.get("request_count", 0)),
        "usd_label": format_usd(usd),
    }


def build_totals_from_activity(activity_rows: list[Activity]) -> dict[str, Any]:
    usd = sum(r.usage for r in activity_rows)
    return {
        "usd": usd,
        "prompt_tokens": sum(r.prompt_tokens for r in activity_rows),
        "completion_tokens": sum(r.completion_tokens for r in activity_rows),
        "reasoning_tokens": sum(r.reasoning_tokens for r in activity_rows),
        "requests": sum(r.requests for r in activity_rows),
        "usd_label": format_usd(usd),
    }
