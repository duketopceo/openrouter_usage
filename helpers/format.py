"""Format helpers."""

from __future__ import annotations

from datetime import datetime


def format_usd(value: float) -> str:
    amount = float(value or 0)
    if abs(amount) < 0.01:
        return f"${amount:.4f}"
    if abs(amount) < 1:
        return f"${amount:.3f}"
    return f"${amount:.2f}"


def chart_date_label(raw: str) -> str:
    if not raw:
        return ""
    try:
        if raw.endswith("Z"):
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(raw)
        return f"{dt.month}/{dt.day}"
    except ValueError:
        return raw[:10]
