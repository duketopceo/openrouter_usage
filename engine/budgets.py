"""Budget read and projected burn alerts."""

from __future__ import annotations

from typing import Any

from . import api
from .models import Budget, Credits


def read_budgets(
    api_key: str,
    workspace_id: str,
    interval: str | None = None,
) -> list[Budget]:
    return api.list_budgets(api_key, workspace_id, interval)


def project_burn(
    credits: Credits | None,
    budgets: list[Budget],
    total_usage_30d: float,
    burn_window_days: int = 30,
    threshold: float = 0.8,
) -> dict[str, Any]:
    daily_rate = total_usage_30d / 30.0 if total_usage_30d else 0.0
    projected = daily_rate * burn_window_days
    alerts: list[dict[str, Any]] = []

    for budget in budgets:
        limit = budget.limit
        remaining = budget.limit_remaining
        if remaining is not None and projected > remaining * threshold:
            alerts.append(
                {
                    "type": "budget_burn",
                    "interval": budget.interval,
                    "workspace_id": budget.workspace_id,
                    "message": (
                        f"Projected {burn_window_days}d spend ({projected:.2f}) exceeds "
                        f"{threshold:.0%} of {budget.interval} budget remaining ({remaining:.2f})."
                    ),
                }
            )
        elif limit is not None and projected > limit * threshold:
            alerts.append(
                {
                    "type": "budget_burn",
                    "interval": budget.interval,
                    "workspace_id": budget.workspace_id,
                    "message": (
                        f"Projected {burn_window_days}d spend ({projected:.2f}) exceeds "
                        f"{threshold:.0%} of {budget.interval} budget limit ({limit:.2f})."
                    ),
                }
            )

    if credits and credits.total_credits is not None:
        if projected > credits.total_credits * threshold:
            alerts.append(
                {
                    "type": "credit_burn",
                    "message": (
                        f"Projected {burn_window_days}d spend ({projected:.2f}) exceeds "
                        f"{threshold:.0%} of credit balance ({credits.total_credits:.2f})."
                    ),
                }
            )

    return {
        "projected_burn": projected,
        "daily_rate": daily_rate,
        "burn_window_days": burn_window_days,
        "threshold": threshold,
        "alerts": alerts,
    }
