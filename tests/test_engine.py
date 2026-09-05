"""Engine unit tests using fixtures only (no real secrets or network)."""

from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

from usr.plugins.openrouter_usage.engine import analytics, fetch, models, recommender
from usr.plugins.openrouter_usage.engine.db import DbConfig, UsageDb
from usr.plugins.openrouter_usage.engine.budgets import project_burn


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load_fixture(name: str):
    with open(FIXTURES / name, "r", encoding="utf-8") as f:
        return json.load(f)


class TestModels(unittest.TestCase):
    def test_workspace_from_dict(self):
        data = load_fixture("workspaces.json")[0]
        ws = models.Workspace.from_dict(data)
        self.assertEqual(ws.id, "ws_1")
        self.assertEqual(ws.name, "Default Workspace")
        self.assertEqual(ws.default_text_model, "openai/gpt-4o")
        self.assertEqual(ws.default_provider_sort, ["OpenAI", "Anthropic"])
        self.assertTrue(ws.is_observability_io_logging_enabled)

    def test_workspace_missing_fields(self):
        ws = models.Workspace.from_dict({"id": "ws_x"})
        self.assertEqual(ws.id, "ws_x")
        self.assertIsNone(ws.name)
        self.assertIsNone(ws.default_text_model)
        self.assertIsNone(ws.default_provider_sort)

    def test_workspace_non_dict(self):
        ws = models.Workspace.from_dict(None)  # type: ignore[arg-type]
        self.assertEqual(ws.id, "")

    def test_key_from_dict(self):
        data = load_fixture("keys.json")[0]
        key = models.Key.from_dict(data)
        self.assertEqual(key.hash, "abc123def4567890")
        self.assertEqual(key.workspace_id, "ws_1")
        self.assertEqual(key.limit_remaining, 73.5)

    def test_analytics_row_from_dict(self):
        data = load_fixture("analytics.json")[0]
        row = models.AnalyticsRow.from_dict(data)
        self.assertEqual(row.dimension("model"), "openai/gpt-4o")
        self.assertEqual(row.metric("total_usage"), 1.23)
        self.assertEqual(row.metric("request_count"), 10)

    def test_analytics_row_no_negative_spend(self):
        row = models.AnalyticsRow.from_dict({"model": "x", "total_usage": 0})
        self.assertEqual(row.metric("total_usage"), 0.0)


class TestFetch(unittest.TestCase):
    def test_with_query(self):
        url = fetch.with_query("https://openrouter.ai/api/v1/keys", {"workspace_id": "ws_1", "empty": ""})
        self.assertEqual(url, "https://openrouter.ai/api/v1/keys?workspace_id=ws_1")

    def test_with_query_no_params(self):
        url = fetch.with_query("https://openrouter.ai/api/v1/keys", {})
        self.assertEqual(url, "https://openrouter.ai/api/v1/keys")

    @patch("urllib.request.urlopen")
    def test_get_json_success(self, mock_urlopen: MagicMock) -> None:
        response = MagicMock()
        response.read.return_value = json.dumps({"total_credits": 100}).encode("utf-8")
        mock_urlopen.return_value.__enter__ = lambda s, *a: response
        mock_urlopen.return_value.__exit__ = lambda *a, **k: None
        # context manager protocol on the urlopen return value
        mock_urlopen.return_value = response
        response.__enter__ = lambda *a: response
        response.__exit__ = lambda *a, **k: None

        result = fetch.get_json("https://openrouter.ai/api/v1/credits", "dummy_key")
        self.assertEqual(result, {"total_credits": 100})
        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.headers["Authorization"], "Bearer dummy_key")

    @patch("urllib.request.urlopen")
    def test_post_json_success(self, mock_urlopen: MagicMock) -> None:
        response = MagicMock()
        response.read.return_value = json.dumps([{"model": "x"}]).encode("utf-8")
        response.__enter__ = lambda *a: response
        response.__exit__ = lambda *a, **k: None
        mock_urlopen.return_value = response

        result = fetch.post_json("https://openrouter.ai/api/v1/analytics/query", "key", json_body={"metrics": []})
        self.assertEqual(result, [{"model": "x"}])
        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.headers["Content-type"], "application/json")

    def test_http_error_raises_openrouter_error(self):
        with patch("urllib.request.urlopen") as mock_urlopen:
            fp = io.BytesIO(b'{"detail":"unauthorized"}')
            mock_urlopen.side_effect = urllib.error.HTTPError(
                "https://openrouter.ai/api/v1/workspaces", 401, "Unauthorized", {}, fp
            )
            with self.assertRaises(fetch.OpenRouterError) as ctx:
                fetch.get_json("https://openrouter.ai/api/v1/workspaces", "key")
            self.assertEqual(ctx.exception.status, 401)
            self.assertIn("unauthorized", str(ctx.exception))


class TestAnalytics(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = [models.AnalyticsRow.from_dict(r) for r in load_fixture("analytics.json")]

    def test_top_models(self):
        top = analytics.top_by_dimension(self.rows, "model", "total_usage", top_n=2, label_key="model")
        self.assertEqual(len(top), 2)
        self.assertEqual(top[0]["model"], "anthropic/claude-3.5-sonnet")
        self.assertAlmostEqual(top[0]["total_usage"], 2.34)

    def test_top_providers(self):
        top = analytics.top_by_dimension(self.rows, "provider", "total_usage", top_n=2, label_key="provider")
        self.assertEqual(top[0]["provider"], "Anthropic")

    def test_totals(self):
        totals = analytics.totals(self.rows)
        self.assertAlmostEqual(totals["total_usage"], 1.23 + 2.34 + 0.5)
        self.assertEqual(totals["request_count"], 20)

    def test_per_key(self):
        keys = [models.Key.from_dict(k) for k in load_fixture("keys.json")]
        per_key = analytics.per_key_from_analytics(self.rows, keys, {})
        self.assertEqual(len(per_key), 1)
        self.assertEqual(per_key[0]["hash_prefix"], "abc123de")
        self.assertAlmostEqual(per_key[0]["usd"], 1.23 + 2.34 + 0.5)

    def test_image_detection(self):
        self.assertTrue(analytics.is_image_model("openai/dall-e-3"))
        self.assertFalse(analytics.is_image_model("openai/gpt-4o"))


class TestRecommender(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = [models.AnalyticsRow.from_dict(r) for r in load_fixture("analytics.json")]

    def test_recommend_text_model(self):
        current = models.RoutingDefaults(default_text_model="openai/gpt-4o")
        rec = recommender.recommend(self.rows, current)
        self.assertEqual(rec.recommended.default_text_model, "anthropic/claude-3.5-sonnet")

    def test_recommend_image_model(self):
        current = models.RoutingDefaults(default_image_model="openai/dall-e-3")
        rec = recommender.recommend(self.rows, current)
        self.assertEqual(rec.recommended.default_image_model, "openai/dall-e-3")

    def test_provider_sort(self):
        current = models.RoutingDefaults(default_provider_sort=["OpenAI"])
        rec = recommender.recommend(self.rows, current)
        self.assertIn("OpenAI", rec.recommended.default_provider_sort or [])
        self.assertIn("tradeoffs", rec.to_dict())

    def test_recommend_no_data(self):
        current = models.RoutingDefaults(default_text_model="x")
        rec = recommender.recommend([], current)
        self.assertEqual(rec.recommended.default_text_model, "x")
        self.assertEqual(rec.confidence, "low")


class TestDatabase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = UsageDb(DbConfig(path=self.tmp.name, history_days=90))

    def tearDown(self) -> None:
        self.db.close()
        Path(self.tmp.name).unlink(missing_ok=True)

    def test_upsert_and_query(self):
        rows = [models.AnalyticsRow.from_dict(r) for r in load_fixture("analytics.json")]
        self.db.upsert(rows)
        results = self.db.query(workspace_id="ws_1")
        # Each fixture row is flattened into one metric row per numeric metric present.
        self.assertGreaterEqual(len(results), 3)

    def test_merge_metrics(self):
        rows = [models.AnalyticsRow.from_dict(r) for r in load_fixture("analytics.json")]
        self.db.upsert(rows)
        raw = self.db.query(workspace_id="ws_1")
        merged = self.db.merge_metrics(raw)
        # 3 distinct dimension sets
        self.assertEqual(len(merged), 3)
        first = merged[0]
        self.assertIn("total_usage", first.metrics)
        self.assertIn("request_count", first.metrics)

    def test_upsert_overwrites(self):
        row = models.AnalyticsRow(
            dimensions={"model": "x"},
            metrics={"total_usage": 1.0},
            workspace_id="ws",
            start_time="2026-09-01T00:00:00Z",
            end_time="2026-09-01T23:59:59Z",
        )
        self.db.upsert([row])
        row.metrics["total_usage"] = 2.0
        self.db.upsert([row])
        results = self.db.merge_metrics(self.db.query(workspace_id="ws"))
        self.assertEqual(len(results), 1)
        self.assertAlmostEqual(results[0].metric("total_usage"), 2.0)

    def test_prune(self):
        old = models.AnalyticsRow(
            dimensions={"model": "old"},
            metrics={"total_usage": 1.0},
            workspace_id="ws",
            start_time="2025-01-01T00:00:00Z",
            end_time="2025-01-01T23:59:59Z",
        )
        recent = models.AnalyticsRow(
            dimensions={"model": "recent"},
            metrics={"total_usage": 2.0},
            workspace_id="ws",
            start_time="2026-09-01T00:00:00Z",
            end_time="2026-09-01T23:59:59Z",
        )
        self.db.upsert([old, recent])
        deleted = self.db.prune(history_days=90)
        self.assertGreaterEqual(deleted, 1)
        remaining = self.db.merge_metrics(self.db.query(workspace_id="ws"))
        self.assertEqual([r.dimension("model") for r in remaining], ["recent"])


class TestBudgets(unittest.TestCase):
    def test_project_burn_alert(self):
        credits = models.Credits(total_credits=100.0, total_usage=50.0)
        budgets = [models.Budget(interval="monthly", limit=100.0, limit_remaining=20.0, workspace_id="ws_1")]
        result = project_burn(credits, budgets, total_usage_30d=90.0, burn_window_days=30, threshold=0.8)
        self.assertEqual(result["daily_rate"], 3.0)
        self.assertEqual(result["projected_burn"], 90.0)
        self.assertTrue(any(a["type"] == "budget_burn" for a in result["alerts"]))

    def test_project_burn_no_credits(self):
        budgets = [models.Budget(interval="monthly", limit=1000.0, limit_remaining=900.0, workspace_id="ws_1")]
        result = project_burn(None, budgets, total_usage_30d=10.0)
        self.assertAlmostEqual(result["projected_burn"], 10.0)
        self.assertFalse(result["alerts"])


if __name__ == "__main__":
    unittest.main()
