---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
execution: code
title: "OpenRouter Usage Ultimate"
date: 2026-09-04
author: ce-plan
---

# OpenRouter Usage Ultimate

> Build the ultimate OpenRouter usage plugin for the `openrouter_usage` Agent Zero plugin. Add workspace discovery and dynamic workspace selection, surface all model/usage data via the management key and the analytics API, implement a quick-view/detailed-view toggle UI, and build an OpenRouter routing harness (ORI) that recommends and applies per-workspace default models and provider sort based on usage data.

## Problem frame

The current plugin is a lightweight sidebar widget backed by an in-memory TTL cache. It reads `/credits`, `/keys`, and per-key `/activity` to show 30-day spend, top keys, and a few top models. It has no workspace awareness, no access to the richer `/analytics/query` API, no persistent local cache for historical data, and no way to act on the data it surfaces. The `helpers/openrouter_client.py` module mixes transport, parsing, aggregation, and cache logic, making it hard to reuse outside Agent Zero.

This plan refactors the plugin into a reusable `engine/` package, adds workspace discovery and scoping, ingests the analytics API into a local SQLite cache, rebuilds the UI as a quick-view/detailed-dashboard pair, and adds an ORI routing harness that lets a human operator review and apply workspace routing defaults grounded in actual usage.

## Scope boundary

### In scope

- Refactor `helpers/openrouter_client.py` into a real `engine/` package (`engine/api.py`, `engine/cache.py`, `engine/db.py`, `engine/models.py`) plus an orchestrator/facade layer.
- Discover workspaces via `GET /api/v1/workspaces` and pass `workspace_id` to all scoped queries.
- Use `POST /api/v1/analytics/query` as the primary analytics source, with `GET /api/v1/keys`, `/api/v1/credits`, and `/api/v1/activity` as supplements.
- Maintain a local SQLite cache at `~/.local/share/openrouter_usage/usage.db` to retain analytics beyond the 30-day API window.
- Rebuild UI into a **QuickView** compact widget and a **DetailedDashboard** with tabs and a toggle.
- Add the ORI routing harness panel: show per-workspace `default_text_model`, `default_image_model`, `default_provider_sort`; recommend values from usage data; apply via `PATCH /api/v1/workspaces/{id}` after explicit confirmation.
- Add budgets read support and projected burn alerts as an optional unit.
- Keep existing Agent Zero plugin wiring working (`plugin.yaml`, `api/*.py`, `webui/*.html`).
- Make the engine reusable for future MCP/CLI/Omarchy harnesses by isolating Agent Zero-specific wiring from the core engine.

### Out of scope

- Modifying OpenRouter billing or credit balances (read-only on credits).
- User/role management, API key creation/deletion, or provider account configuration.
- Real-time streaming analytics; the plugin remains request/poll based.
- Non-OpenRouter inference providers.
- Building a separate CLI/MCP harness in this repo (the engine must be reusable, but no harness UI is implemented here).
- Advanced forecasting models; burn projection uses simple linear extrapolation from recent usage.

## Decisions

### D1 — Management key stays server-side
**Decision:** All OpenRouter calls use `OPENROUTER_MANAGEMENT_KEY` from Agent Zero Secrets. The key is loaded by the server and never serialized to the browser.  
**Rationale:** The management key grants org-level access. Exposing it in the front-end would break the security model.

### D2 — Workspace discovery and client-side selection
**Decision:** Workspaces are discovered via `GET /api/v1/workspaces`. Users can select/pin a workspace, and `workspace_id` is passed to all scoped queries. Selection is persisted in the front-end store and config.  
**Rationale:** Workspaces are the OpenRouter scoping boundary. Letting the user choose a workspace keeps queries fast and relevant while keeping the engine flexible for org-level views.

### D3 — Analytics API as primary source
**Decision:** `POST /api/v1/analytics/query` is the primary source for model/provider/key/app/user breakdowns. `GET /api/v1/keys`, `/api/v1/credits`, and `/api/v1/activity` supplement key metadata, credit balance, and raw daily activity.  
**Rationale:** The analytics API supports metrics (`total_usage`, `request_count`, `tokens_*`, `latency`, `cache_*`) and dimensions (`model`, `variant`, `provider`, `api_key_id`, `workspace`, `app`, `user`, etc.) in one query, reducing round trips and enabling richer aggregations.

### D4 — Local SQLite cache
**Decision:** Analytics rows are persisted to `~/.local/share/openrouter_usage/usage.db` so the plugin can answer queries beyond the 30-day API window. Cache metadata records `as_of` and a stale flag.  
**Rationale:** The OpenRouter analytics window is limited. A local cache gives historical trend and burn projection without increasing API load.

### D5 — Engine package decoupled from Agent Zero
**Decision:** Core logic lives in `engine/`. `helpers/openrouter_client.py` becomes a thin compatibility facade that loads Agent Zero config/secrets and delegates to the engine.  
**Rationale:** This keeps the engine reusable for MCP/CLI/Omarchy harnesses while preserving existing `api/*.py` imports and `webui` API paths.

### D6 — Quick view vs detailed dashboard
**Decision:** The UI has a persistent quick view (compact sidebar/card) and a detailed view (full scrollable dashboard with tabs). The default view is controlled by `default_config.yaml` and user preference.  
**Rationale:** At-a-glance usage belongs in the sidebar; deep exploration (models, providers, keys, workspaces, routing) belongs in a dedicated dashboard.

### D7 — ORI apply requires explicit confirmation
**Decision:** The routing harness recommends defaults but only applies them via `PATCH /api/v1/workspaces/{id}` when the user explicitly confirms a previewed diff.  
**Rationale:** Routing defaults affect production inference. A two-step confirm flow prevents accidental changes.

### D8 — Budget burn alerts are optional
**Decision:** Budget read and projected burn alerts are implemented as an optional unit controlled by settings `budget_alert_threshold` and `burn_window_days`.  
**Rationale:** Not all orgs use OpenRouter budgets, so the feature must gracefully degrade when budgets or credits are absent.

## Requirements traceability

| ID | Requirement | Satisfied by |
|----|-------------|--------------|
| R1 | Discover and select/pin workspaces | U3, U8, U10, U12, U13 |
| R2 | Pass `workspace_id` to all scoped usage queries | U3, U5, U8 |
| R3 | Use `POST /api/v1/analytics/query` as primary analytics source | U2, U3, U4, U5, U8 |
| R4 | Supplement analytics with keys, credits, and activity | U3, U5 |
| R5 | Persist historical analytics in a local SQLite cache | U4, U5 |
| R6 | Provide a compact QuickView widget | U10, U11 |
| R7 | Provide a full DetailedDashboard with tabs and a toggle | U11, U12 |
| R8 | Build an ORI routing harness that recommends and applies per-workspace defaults | U6, U8, U12 |
| R9 | Read workspace budgets | U7, U8 |
| R10 | Surface projected burn alerts | U7, U9, U13 |
| R11 | Make the engine reusable for future MCP/CLI/Omarchy harnesses | U1–U7 |

## Implementation units

> U-IDs are stable. Do not renumber, backfill, or reorder IDs if the plan is split or deepened.

---

### U1. Engine domain models
**Purpose:** Define typed domain objects for Workspaces, Keys, Credits, Activity, Analytics rows, Budgets, and Routing defaults so the rest of the codebase stops relying on untyped dictionaries.

**Files touched:**
- `engine/__init__.py`
- `engine/models.py`
- `helpers/openrouter_client.py` (remove inline dict building)

**Dependencies:** None.

**Test scenarios:**
- `[Happy]` Construct a `Workspace` from a `/api/v1/workspaces` item containing `id`, `slug`, `name`, `default_text_model`, `default_image_model`, `default_provider_sort`, and `is_observability_*_enabled` flags.
- `[Edge]` Construct a `Workspace` from an item missing `name` and default-model fields; missing values default safely without raising.
- `[Edge]` Construct an `AnalyticsRow` with float metrics and string dimension values; ensure no negative spend when API returns `0`.
- `[Error]` Pass a non-dict payload to a model constructor; the constructor rejects it cleanly without crashing the API handler.
- `[Integration]` Serialize an overview payload to JSON and confirm existing `webui/usage-store.js` properties (`overview.ok`, `overview.totals.usd_label`) remain present.

---

### U2. Shared HTTP transport
**Purpose:** Extend `helpers/fetch.py` to support GET, POST, and PATCH calls with JSON bodies and consistent `OpenRouterError` handling.

**Files touched:**
- `helpers/fetch.py`

**Dependencies:** U1 (models describe request/response shapes).

**Test scenarios:**
- `[Happy]` GET `/api/v1/keys` returns a parsed list.
- `[Happy]` POST `/api/v1/analytics/query` with a metrics/dimensions body returns tabular rows.
- `[Happy]` PATCH `/api/v1/workspaces/{id}` with a JSON body returns the updated workspace.
- `[Edge]` A 204 No Content response returns an empty dict or `None` without a JSON decode error.
- `[Error]` A 401 response raises `OpenRouterError` with the HTTP status and a message containing the response detail.
- `[Error]` A network timeout raises `OpenRouterError` indicating the service is unreachable.
- `[Integration]` Confirm the `Authorization` header is present and the management key is never included in response payloads sent to the browser.

---

### U3. Workspace discovery and scoped fetcher
**Purpose:** Build `engine/api.py` to list workspaces and fetch workspace-scoped keys, credits, activity, and analytics.

**Files touched:**
- `engine/api.py`
- `helpers/fetch.py`

**Dependencies:** U1, U2.

**Test scenarios:**
- `[Happy]` `list_workspaces()` returns objects with `id`, `slug`, `name`, `default_text_model`, `default_image_model`, `default_provider_sort`, and `include_byok_in_budgets`.
- `[Happy]` Fetching keys with a `workspace_id` returns only keys whose `workspace_id` matches the selected workspace.
- `[Happy]` Fetching activity with a `workspace_id` returns workspace-scoped activity rows.
- `[Happy]` Querying analytics with a `workspace_id` applies a workspace filter/dimension.
- `[Edge]` Omitting `workspace_id` returns org-level results where the API supports it.
- `[Error]` A 403 from `/api/v1/workspaces` raises a permission error that the UI can surface.
- `[Integration]` All methods load the management key server-side and never expose it.

---

### U4. SQLite cache and query builder
**Purpose:** Create `engine/db.py` for the local cache schema and `engine/cache.py` for a TTL-aware cache layer. Support querying analytics by time range, dimensions, and filters, and merging cached historical rows with fresh API rows.

**Files touched:**
- `engine/db.py`
- `engine/cache.py`
- `helpers/openrouter_client.py` (cache-invalidation hook)

**Dependencies:** U1.

**Test scenarios:**
- `[Happy]` On first call the cache creates the directory `~/.local/share/openrouter_usage/` and the `usage.db` file.
- `[Happy]` Upsert analytics rows and query by `workspace`, `model`, and time range returns aggregated totals.
- `[Happy]` A 90-day query merges rows older than 30 days from the cache with newer rows from the API.
- `[Edge]` A query with no matching rows returns an empty list, not an error.
- `[Edge]` Upserting the same dimensions/time overwrites the existing row rather than duplicating it.
- `[Error]` A database lock during write is retried or surfaces as a stale flag; the UI still receives partial data.
- `[Integration]` Cache `as_of` timestamps are recorded; stale flags propagate through to the front-end.

---

### U5. Overview and analytics orchestrator
**Purpose:** Build `engine/orchestrator.py` to combine credits, keys, activity, and analytics into a unified overview payload. Keep `helpers/openrouter_client.py` as a thin facade so existing `api/*.py` imports continue to work.

**Files touched:**
- `engine/orchestrator.py`
- `helpers/openrouter_client.py` (refactored to facade)
- `engine/api.py`
- `engine/db.py`
- `engine/cache.py`
- `engine/models.py`
- `helpers/format.py`
- `helpers/aliases.py`

**Dependencies:** U1, U2, U3, U4.

**Test scenarios:**
- `[Happy]` Missing management key returns `ok: false` with `empty_state: missing_management_key` and a clear message.
- `[Happy]` With a valid key and no workspace selected, the overview contains org-level totals, top keys, top models/providers, and a daily spend series.
- `[Happy]` With a `workspace_id` selected, totals and breakdowns are scoped to that workspace.
- `[Happy]` Analytics dimensions `model`, `provider`, and `api_key_id` produce separate breakdowns in the overview.
- `[Edge]` If the `/activity` call for one key fails, the overview still returns partial data with `last_error` set and `stale: true`.
- `[Edge]` If analytics returns no rows, totals are `$0` and the dashboard shows an empty state.
- `[Error]` An invalid management key invalidates the TTL cache and returns an error state.
- `[Integration]` `fetch_overview(force=True)` refreshes the cache and refetches; `api/overview.py` and `api/refresh.py` still return shapes the store expects.

---

### U6. Routing recommendation engine
**Purpose:** Add `engine/recommender.py` to derive per-workspace `default_text_model`, `default_image_model`, and `default_provider_sort` from usage analytics.

**Files touched:**
- `engine/recommender.py`
- `engine/models.py`
- `engine/db.py`

**Dependencies:** U4, U5.

**Test scenarios:**
- `[Happy]` When `openai/gpt-4o` is the top text model by `total_usage`, the recommendation returns it as `default_text_model`.
- `[Happy]` When usage contains image-related variants/endpoints, the top image model is recommended as `default_image_model`.
- `[Happy]` When `Anthropic` has the highest usage share with the lowest p95 latency, the provider sort recommends `Anthropic` first.
- `[Edge]` If there is no image usage, the recommendation preserves the existing `default_image_model` or returns `None` with a note.
- `[Edge]` Tied text models are broken by `request_count`, then by most recent usage.
- `[Error]` If the workspace has zero usage, the recommendation falls back to the current workspace values or a safe empty default.

---

### U7. Budgets and burn projection engine
**Purpose:** Add `engine/budgets.py` to read workspace budgets and compute a simple projected burn alert based on credits balance and recent usage rate.

**Files touched:**
- `engine/budgets.py`
- `engine/api.py`
- `engine/db.py`
- `engine/models.py`

**Dependencies:** U3, U4, U5.

**Test scenarios:**
- `[Happy]` `list_budgets(workspace_id)` returns budget objects with `limit`, `limit_remaining`, `limit_reset`, and usage fields.
- `[Happy]` When the 30-day burn rate exceeds the credit balance within `burn_window_days`, a burn alert is surfaced.
- `[Edge]` If `total_credits` is missing, budget list still returns and projection is skipped.
- `[Edge]` If no budgets exist for a workspace, the result is an empty list and `projected_burn` is `null`.
- `[Error]` If the budget endpoint returns 403, the error is attached to the overview/budget payload without breaking other sections.

---

### U8. Agent Zero API handlers
**Purpose:** Add/update `api/*.py` handlers for overview, keys, refresh, workspaces, analytics, routing, and budgets.

**Files touched:**
- `api/overview.py`
- `api/keys_list.py`
- `api/refresh.py`
- `api/workspaces.py` (new)
- `api/analytics.py` (new)
- `api/routing.py` (new)
- `api/budgets.py` (new)
- `engine/orchestrator.py`
- `engine/api.py`
- `engine/recommender.py`
- `engine/budgets.py`

**Dependencies:** U1, U2, U3, U5, U6, U7.

**Test scenarios:**
- `[Happy]` `GET /plugins/openrouter_usage/workspaces` returns a workspace list with a pinned/selected flag.
- `[Happy]` `POST /plugins/openrouter_usage/analytics` with metrics, dimensions, and time range returns tabular rows.
- `[Happy]` `GET /plugins/openrouter_usage/routing?workspace_id=...` returns current defaults and recommendations.
- `[Happy]` `POST /plugins/openrouter_usage/routing` with `workspace_id`, `defaults`, and `confirmed: true` calls `PATCH /api/v1/workspaces/{id}` and returns the updated workspace.
- `[Error]` `POST /plugins/openrouter_usage/routing` without `confirmed: true` returns a validation error and does not call PATCH.
- `[Error]` Missing management key returns `ok: false` from every endpoint.
- `[Integration]` `api/overview.py` accepts a `workspace_id` parameter and passes it to the orchestrator.

---

### U9. Front-end store and API wiring
**Purpose:** Update `webui/usage-store.js` to call the new endpoints and manage workspace selection, view mode, active tab, analytics state, routing recommendations, and budget alerts.

**Files touched:**
- `webui/usage-store.js`
- `webui/usage-dashboard.html`
- `extensions/webui/sidebar-quick-actions-main-end/usage-widget.html`
- `extensions/webui/initFw_end/bootstrap-usage.js`

**Dependencies:** U8.

**Test scenarios:**
- `[Happy]` The store loads the workspace list on initialization and restores the selected/pinned workspace from `localStorage`.
- `[Happy]` `fetchOverview` passes `workspace_id` when a workspace is selected and updates `overview`, `topModels`, `workspaces`, and `routingRecommendations`.
- `[Happy]` `setView` persists the quick/detailed mode in `localStorage` and updates the UI.
- `[Happy]` `applyRouting` calls the routing endpoint only after explicit confirmation and shows a success or error toast.
- `[Edge]` If the workspace list is empty, the selected workspace resets to null and the overview uses org-level data.
- `[Error]` If an API call returns 500, the store calls the error toast and leaves the UI in its previous state.

---

### U10. Quick view widget refresh
**Purpose:** Update the sidebar widget to show a compact summary with a workspace selector and the current spend/balance.

**Files touched:**
- `extensions/webui/sidebar-quick-actions-main-end/usage-widget.html`
- `extensions/webui/initFw_end/bootstrap-usage.js`
- `webui/usage-store.js`

**Dependencies:** U9.

**Test scenarios:**
- `[Happy]` With no workspace selected, the widget displays the org-level total spend and balance.
- `[Happy]` Selecting a workspace from the widget dropdown updates the displayed spend and label.
- `[Edge]` With a missing management key, the widget shows a compact "Add key" prompt consistent with the banner.
- `[Integration]` Clicking the widget opens the detailed dashboard with the selected workspace pre-selected.

---

### U11. Detailed dashboard with tabs and toggle
**Purpose:** Rebuild `webui/usage-dashboard.html` into a full scrollable dashboard with a Quick/Detailed toggle and tabbed sections.

**Files touched:**
- `webui/usage-dashboard.html`
- `webui/usage-store.js`

**Dependencies:** U9.

**Test scenarios:**
- `[Happy]` The default view mode follows `default_config.yaml` and the user can toggle between QuickView and DetailedDashboard.
- `[Happy]` DetailedDashboard shows tabs: Overview, Keys, Models/Providers, Workspaces, Routing.
- `[Happy]` Overview tab renders daily spend bars, top keys, top models, and totals.
- `[Edge]` When there is no data, each tab renders an appropriate empty state.
- `[Integration]` Active tab state is persisted in the store and restored on dashboard reopen.

---

### U12. ORI routing harness panel
**Purpose:** Add the "Routing" tab to DetailedDashboard. It displays current workspace defaults, usage-driven recommendations, and an explicit-confirm apply flow.

**Files touched:**
- `webui/usage-dashboard.html` (Routing tab)
- `webui/usage-store.js` (routing actions and state)
- `engine/recommender.py`
- `api/routing.py`

**Dependencies:** U6, U8, U9, U11.

**Test scenarios:**
- `[Happy]` The Routing tab loads the current `default_text_model`, `default_image_model`, and `default_provider_sort` for the selected workspace.
- `[Happy]` A "Recommend" action fetches recommendations and shows a diff preview against current defaults.
- `[Happy]` The "Apply" button is disabled until the user confirms; after confirmation, it calls the routing endpoint and shows the updated workspace values.
- `[Edge]` If the workspace has no current defaults, the recommendation fields pre-fill from usage or show "no data".
- `[Error]` If the PATCH call fails, the store shows an error toast and keeps the original values on screen.

---

### U13. Configuration page updates and plugin metadata
**Purpose:** Extend `webui/config.html` with workspace pinning, budget alert threshold, and analytics quick-picks. Bump `plugin.yaml` and `default_config.yaml` and update docs.

**Files touched:**
- `webui/config.html`
- `default_config.yaml`
- `plugin.yaml`
- `README.md`
- `extensions/python/banners/_10_openrouter_feature.py`

**Dependencies:** U9, U11.

**Test scenarios:**
- `[Happy]` The config page lists workspaces and lets the user pin one; the pinned workspace persists in config.
- `[Happy]` The budget alert threshold input validates as a number and saves successfully.
- `[Happy]` `plugin.yaml` version and description reflect workspace and routing features.
- `[Edge]` Without a management key, the workspace controls are disabled and the banner still prompts for a key.
- `[Integration]` Old config files missing new keys (`pinned_workspace_id`, `budget_alert_threshold`, `burn_window_days`) still load with sensible defaults.

---

## Risks & dependencies

| Risk | Impact | Mitigation |
|------|--------|------------|
| OpenRouter management API schemas differ from research data | High | Keep parsing permissive; log unknown fields rather than failing; validate with real responses during implementation. |
| Workspace-scoped `/activity` does not accept a `workspace_id` query parameter | Medium | If the parameter is ignored, filter aggregate activity rows by a `workspace` dimension/field client-side before aggregation. |
| SQLite concurrency from multi-process Agent Zero | Medium | Use connection-per-request with appropriate timeout/locking; consider WAL mode if needed. |
| Routing PATCH can alter production defaults | High | Require `confirmed: true`, show a diff preview, and consider showing the previous values for manual rollback. |
| 30-day analytics window vs local cache drift | Medium | Store `as_of` timestamps, mark stale data, and invalidate on refresh or force reload. |
| Reusability vs Agent Zero coupling | Medium | `engine/` must not import Agent Zero helpers; only `helpers/openrouter_client.py` and `api/*.py` may bridge config/secrets. |
| No existing test harness in the repo | Medium | The test scenarios in this plan serve as the acceptance criteria; the implementing agent should add `pytest` or manual checks. |
| Management key invalidation | Low | 401/403 responses invalidate the cache and surface an actionable error message. |

## Implementation-time choices

The following are intentionally left to the implementing agent to decide with code in front of them:

- Whether to use `dataclasses`, `Pydantic`, or plain dicts inside `engine/models.py`.
- Exact database schema and migration strategy for `engine/db.py`.
- Whether to keep `helpers/fetch.py` or move transport into `engine/http.py`.
- Specific front-end component structure (tabs, modals) within the existing Alpine.js framework.
- How to detect image vs text models from analytics dimensions (variant, endpoint_id, or model slug heuristics).
- Exact algorithm for projected burn (linear, weighted, or configurable).

These are not blockers; they are design choices that should respect the guardrails above.
