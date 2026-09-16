"""Local SQLite cache for OpenRouter analytics rows."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from .models import AnalyticsRow


SCHEMA_VERSION = 2
DEFAULT_DB_DIR = Path.home() / ".local" / "share" / "openrouter_usage"
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "usage.db"


def _canon_ts(value: str | None) -> str | None:
    """Normalize an ISO-8601 timestamp to UTC `+00:00` with microseconds.

    Stored rows mix API-style `Z` suffixes with local `+00:00` values, and
    fraction width varies; SQLite compares these columns lexically, so a `Z`
    row inside a cutoff's second sorts above every `+00:00` boundary value
    and leaks through range/prune comparisons. Unparseable values pass
    through unchanged rather than breaking the row.
    """
    if value is None:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="microseconds")


@dataclass
class DbConfig:
    path: Path = field(default_factory=lambda: DEFAULT_DB_PATH)
    history_days: int = 90


class UsageDb:
    """Thin SQLite cache for analytics rows with upsert and time-range queries."""

    def __init__(self, config: DbConfig | None = None):
        self.config = config or DbConfig()
        self.path = Path(self.config.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.path), timeout=10.0)
            self._conn.row_factory = sqlite3.Row
            self._init_schema()
        return self._conn

    def _init_schema(self) -> None:
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS _version (
                version INTEGER PRIMARY KEY
            )
            """
        )
        cur.execute("INSERT OR IGNORE INTO _version (version) VALUES (?)", (SCHEMA_VERSION,))
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS analytics_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                as_of TEXT NOT NULL,
                workspace_id TEXT,
                metric TEXT NOT NULL,
                dimension_json TEXT NOT NULL,
                value REAL NOT NULL,
                start_time TEXT,
                end_time TEXT,
                UNIQUE(workspace_id, metric, dimension_json, start_time, end_time)
            )
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_analytics_workspace ON analytics_cache(workspace_id)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_analytics_as_of ON analytics_cache(as_of)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_analytics_time ON analytics_cache(start_time, end_time)"
        )
        # v1 -> v2: rewrite `Z`-suffixed timestamps to `+00:00` so lexical
        # comparisons against local cutoffs are chronologically correct.
        cur.execute("SELECT version FROM _version")
        if cur.fetchone()[0] < 2:
            for col in ("start_time", "end_time", "as_of"):
                cur.execute(
                    f"UPDATE analytics_cache SET {col} = REPLACE({col}, 'Z', '+00:00') WHERE {col} LIKE '%Z'"
                )
            cur.execute("DELETE FROM _version")
            cur.execute("INSERT INTO _version (version) VALUES (2)")
        conn.commit()

    def upsert(self, rows: Iterable[AnalyticsRow]) -> None:
        conn = self._connect()
        cur = conn.cursor()
        now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        for row in rows:
            as_of = _canon_ts(row.as_of) or now
            dim_json = row.dimension_json()
            ws = row.workspace_id
            st = _canon_ts(row.start_time)
            et = _canon_ts(row.end_time)
            for metric, value in row.metrics.items():
                cur.execute(
                    """
                    INSERT OR REPLACE INTO analytics_cache
                    (as_of, workspace_id, metric, dimension_json, value, start_time, end_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (as_of, ws, metric, dim_json, float(value), st, et),
                )
        conn.commit()

    def query(
        self,
        workspace_id: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        metric: str | None = None,
        dimension: str | None = None,
        dimension_value: str | None = None,
    ) -> list[AnalyticsRow]:
        conn = self._connect()
        cur = conn.cursor()
        clauses: list[str] = []
        params: list[Any] = []

        if workspace_id:
            clauses.append("workspace_id = ?")
            params.append(workspace_id)

        if start_time is not None:
            clauses.append("(start_time >= ? OR start_time IS NULL)")
            params.append(_canon_ts(start_time))
        if end_time is not None:
            clauses.append("(end_time <= ? OR end_time IS NULL)")
            params.append(_canon_ts(end_time))
        if metric is not None:
            clauses.append("metric = ?")
            params.append(metric)

        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        cur.execute(
            f"SELECT as_of, workspace_id, metric, dimension_json, value, start_time, end_time FROM analytics_cache{where}",
            params,
        )

        rows: list[AnalyticsRow] = []
        for row in cur.fetchall():
            dimensions = json.loads(row["dimension_json"])
            analytics = AnalyticsRow(
                dimensions=dimensions,
                metrics={row["metric"]: float(row["value"])},
                start_time=row["start_time"],
                end_time=row["end_time"],
                as_of=row["as_of"],
                workspace_id=row["workspace_id"],
            )
            rows.append(analytics)

        if dimension is not None and dimension_value is not None:
            rows = [r for r in rows if r.dimension(dimension) == dimension_value]

        return rows

    def merge_metrics(self, rows: list[AnalyticsRow]) -> list[AnalyticsRow]:
        """Collapse rows with the same dimensions/time into one row with all metrics."""
        grouped: dict[tuple[str, str | None, str | None, str | None], AnalyticsRow] = {}
        for row in rows:
            key = (row.dimension_json(), row.start_time, row.end_time, row.workspace_id)
            if key in grouped:
                grouped[key].metrics.update(row.metrics)
            else:
                grouped[key] = AnalyticsRow(
                    dimensions=dict(row.dimensions),
                    metrics=dict(row.metrics),
                    start_time=row.start_time,
                    end_time=row.end_time,
                    as_of=row.as_of,
                    workspace_id=row.workspace_id,
                )
        return list(grouped.values())

    def prune(self, history_days: int | None = None) -> int:
        days = history_days if history_days is not None else self.config.history_days
        cutoff = _canon_ts(
            (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="microseconds")
        )
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM analytics_cache WHERE start_time < ? OR (start_time IS NULL AND as_of < ?)",
            (cutoff, cutoff),
        )
        conn.commit()
        return cur.rowcount

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> UsageDb:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
