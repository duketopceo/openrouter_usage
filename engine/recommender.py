"""OpenRouter routing recommendation engine (ORI)."""

from __future__ import annotations

import math
from collections import defaultdict
from statistics import mean
from typing import Any

from .analytics import is_image_model, is_text_model
from .models import AnalyticsRow, Recommendation, RoutingDefaults


_SCORE_METRICS = [
    ("avg_latency", False),
    ("p90_latency", False),
    ("avg_throughput", True),
    ("p90_throughput", True),
    ("cache_hit_rate", True),
]


def _avg_metric(rows: list[AnalyticsRow], metric: str) -> float:
    values = [r.metric(metric) for r in rows if metric in r.metrics and r.metric(metric) is not None]
    return mean(values) if values else 0.0


def _model_rows(rows: list[AnalyticsRow], model: str | None) -> list[AnalyticsRow]:
    if not model:
        return []
    return [r for r in rows if r.dimension("model") == model]


def _provider_rows(rows: list[AnalyticsRow], provider: str | None) -> list[AnalyticsRow]:
    if not provider:
        return []
    return [r for r in rows if r.dimension("provider") == provider]


def _weighted_requests(rows: list[AnalyticsRow]) -> float:
    return sum(r.metric("request_count") for r in rows)


def _recommend_text_model(rows: list[AnalyticsRow]) -> tuple[str | None, float, dict[str, float]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"total_usage": 0.0, "request_count": 0.0, "latest_end": ""})
    for row in rows:
        model = row.dimension("model")
        if not model or not is_text_model(model, row.dimension("variant"), row.dimension("endpoint_id")):
            continue
        bucket = grouped[model]
        bucket["total_usage"] += row.metric("total_usage")
        bucket["request_count"] += row.metric("request_count")
        end = row.end_time or ""
        if end > bucket["latest_end"]:
            bucket["latest_end"] = end

    if not grouped:
        return None, 0.0, {}

    sorted_models = sorted(
        grouped.items(),
        key=lambda item: (item[1]["total_usage"], item[1]["request_count"], item[1]["latest_end"]),
        reverse=True,
    )
    top, stats = sorted_models[0]
    return top, float(stats["request_count"]), dict(stats)


def _recommend_image_model(rows: list[AnalyticsRow]) -> tuple[str | None, float, dict[str, float]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"total_usage": 0.0, "request_count": 0.0, "latest_end": ""})
    for row in rows:
        model = row.dimension("model")
        if not model or not is_image_model(model, row.dimension("variant"), row.dimension("endpoint_id")):
            continue
        bucket = grouped[model]
        bucket["total_usage"] += row.metric("total_usage")
        bucket["request_count"] += row.metric("request_count")
        end = row.end_time or ""
        if end > bucket["latest_end"]:
            bucket["latest_end"] = end

    if not grouped:
        return None, 0.0, {}

    sorted_models = sorted(
        grouped.items(),
        key=lambda item: (item[1]["total_usage"], item[1]["request_count"], item[1]["latest_end"]),
        reverse=True,
    )
    top, stats = sorted_models[0]
    return top, float(stats["request_count"]), dict(stats)


def _score_providers(rows: list[AnalyticsRow]) -> list[dict[str, Any]]:
    grouped: dict[str, list[AnalyticsRow]] = defaultdict(list)
    for row in rows:
        provider = row.dimension("provider")
        if provider:
            grouped[provider].append(row)

    if not grouped:
        return []

    providers: list[dict[str, Any]] = []
    for provider, provider_rows in grouped.items():
        entry = {
            "provider": provider,
            "request_count": _weighted_requests(provider_rows),
            "avg_latency": _avg_metric(provider_rows, "avg_latency"),
            "p90_latency": _avg_metric(provider_rows, "p90_latency"),
            "avg_throughput": _avg_metric(provider_rows, "avg_throughput"),
            "p90_throughput": _avg_metric(provider_rows, "p90_throughput"),
            "cache_hit_rate": _avg_metric(provider_rows, "cache_hit_rate"),
        }
        providers.append(entry)

    # normalize each metric and compute geometric mean
    scores: dict[str, list[float]] = defaultdict(list)
    for metric, higher_better in _SCORE_METRICS:
        values = [p[metric] for p in providers if p[metric] > 0]
        if not values:
            continue
        min_v, max_v = min(values), max(values)
        for p in providers:
            v = p[metric]
            if v <= 0 or max_v == min_v:
                score = 0.5
            elif higher_better:
                score = (v - min_v) / (max_v - min_v)
            else:
                score = (max_v - v) / (max_v - min_v)
            scores[p["provider"]].append(score)

    for p in providers:
        vals = scores.get(p["provider"], [0.5])
        p["score"] = math.exp(sum(math.log(max(v, 0.0001)) for v in vals) / len(vals))

    providers.sort(key=lambda p: (p["score"], p["request_count"]), reverse=True)
    return providers


def _project_tradeoffs(
    rows: list[AnalyticsRow],
    current: RoutingDefaults,
    recommended: RoutingDefaults,
) -> dict[str, Any]:
    current_text = current_rows = _model_rows(rows, current.default_text_model) or rows
    recommended_text = _model_rows(rows, recommended.default_text_model) or rows

    current_first_provider = (current.default_provider_sort or [None])[0]
    recommended_first_provider = (recommended.default_provider_sort or [None])[0]
    current_provider_rows = _provider_rows(rows, current_first_provider) or rows
    recommended_provider_rows = _provider_rows(rows, recommended_first_provider) or rows

    def _snapshot(model_rows: list[AnalyticsRow], provider_rows: list[AnalyticsRow]) -> dict[str, float]:
        return {
            "blended_cost_per_million_tokens": _avg_metric(model_rows, "blended_cost_per_million_tokens"),
            "avg_latency": _avg_metric(provider_rows, "avg_latency"),
            "avg_throughput": _avg_metric(provider_rows, "avg_throughput"),
            "cache_hit_rate": _avg_metric(provider_rows, "cache_hit_rate"),
        }

    current_metrics = _snapshot(current_text, current_provider_rows)
    recommended_metrics = _snapshot(recommended_text, recommended_provider_rows)

    def _pct_change(old: float, new: float) -> float:
        if old == 0:
            return 0.0
        return (new - old) / old * 100.0

    return {
        "current_cost_per_mtok": current_metrics["blended_cost_per_million_tokens"],
        "recommended_cost_per_mtok": recommended_metrics["blended_cost_per_million_tokens"],
        "cost_change_pct": _pct_change(
            current_metrics["blended_cost_per_million_tokens"],
            recommended_metrics["blended_cost_per_million_tokens"],
        ),
        "current_avg_latency_ms": current_metrics["avg_latency"],
        "recommended_avg_latency_ms": recommended_metrics["avg_latency"],
        "latency_change_pct": _pct_change(current_metrics["avg_latency"], recommended_metrics["avg_latency"]),
        "current_avg_throughput": current_metrics["avg_throughput"],
        "recommended_avg_throughput": recommended_metrics["avg_throughput"],
        "throughput_change_pct": _pct_change(current_metrics["avg_throughput"], recommended_metrics["avg_throughput"]),
        "current_cache_hit_rate": current_metrics["cache_hit_rate"],
        "recommended_cache_hit_rate": recommended_metrics["cache_hit_rate"],
        "cache_hit_change_pct": _pct_change(current_metrics["cache_hit_rate"], recommended_metrics["cache_hit_rate"]),
    }


def recommend(
    rows: list[AnalyticsRow],
    current: RoutingDefaults,
    min_requests: int = 5,
) -> Recommendation:
    if not rows:
        return Recommendation(
            current=current,
            recommended=RoutingDefaults(
                default_text_model=current.default_text_model,
                default_image_model=current.default_image_model,
                default_provider_sort=current.default_provider_sort,
            ),
            tradeoffs={},
            confidence="low",
            note="No analytics data available; preserving current defaults.",
        )

    text_model, text_reqs, _ = _recommend_text_model(rows)
    image_model, image_reqs, _ = _recommend_image_model(rows)

    provider_scores = _score_providers(rows)
    provider_sort = [p["provider"] for p in provider_scores[:6]] if provider_scores else current.default_provider_sort

    if not image_model:
        image_model = current.default_image_model
        note = "No image usage detected; preserving current image default."
    else:
        note = None

    recommended = RoutingDefaults(
        default_text_model=text_model or current.default_text_model,
        default_image_model=image_model,
        default_provider_sort=provider_sort,
    )

    requests = text_reqs + image_reqs + sum(p["request_count"] for p in provider_scores[:1])
    if requests >= 100:
        confidence = "high"
    elif requests >= 10:
        confidence = "medium"
    else:
        confidence = "low"

    tradeoffs = _project_tradeoffs(rows, current, recommended)

    return Recommendation(
        current=current,
        recommended=recommended,
        tradeoffs=tradeoffs,
        confidence=confidence,
        note=note,
    )
