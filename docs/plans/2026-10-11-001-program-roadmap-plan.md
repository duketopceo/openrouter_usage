---
title: "OpenRouter Usage program roadmap"
type: program
date: 2026-10-11
artifact_contract: ce-unified-plan/v1
execution: docs
---

# OpenRouter Usage: program roadmap

Written directly in the ce-plan unit format (the ce-plan skill was not run; repo is small). Status of v1.3.0: shipped (tag `v1.3.0`, CI in `.github/workflows/ci.yml`, 28 unittest cases pass).

## Goal capsule

Keep the plugin a read-mostly, org-level spend view inside Agent Zero. Close the trust gaps (tests of the HTTP/API layer, alerts, export) without becoming a gateway.

## Now

### U1. Delete dead duplicate and fix the social card
- **Status:** planned. **Evidence:** `helpers/cache.py` duplicates `engine/cache.py::TtlCache`; `grep` finds no importer of `helpers.cache`. `docs/social.png` describes an "Omarchy bar" product and shows a broken glyph.
- **Depends on:** none. **Verification:** unittest suite still passes; README shows `assets/brand/social-card.png`.
- **Difficulty:** easy. One file removal and an image swap.
- **Feasibility:** none blocking; confirm no external plugin imports `helpers.cache`.
- **Simpler alternative:** this is the simplification. Also fold `helpers/fetch.py` (a pure re-export facade of `engine.fetch`) into direct `engine.fetch` imports in `helpers/openrouter_client.py`, and drop `helpers/format.py` if `engine/` already formats.

### U2. Contract tests for the API handlers and client
- **Status:** planned. **Evidence:** `tests/test_engine.py` covers `engine/`; `api/*.py` (7 thin handlers) and `helpers/openrouter_client.py` (551 lines, owns overview assembly) have no tests.
- **Depends on:** none. **Verification:** new tests run in CI with fixtures in `tests/fixtures/`, zero network.
- **Difficulty:** medium. The client imports Agent Zero modules, so it needs stubs.
- **Feasibility:** needs a stub for Agent Zero `helpers`; no OpenRouter calls (use fixtures only, they cost money).
- **Simpler alternative:** test only `fetch_overview` and `apply_routing` (the confirm-gated write) first.

## Next

### U3. Budget-burn alerts as Agent Zero notifications
- **Status:** planned. **Evidence:** `engine/budgets.py` already computes projected burn and a threshold setting exists; alerts only show in the UI.
- **Depends on:** U2. **Verification:** unit test crossing the threshold fires once per window.
- **Difficulty:** medium. Needs a scheduler hook and de-duplication state in SQLite (`engine/db.py`).
- **Feasibility:** depends on Agent Zero offering a notification API to plugins; check before starting.
- **Simpler alternative:** extend `extensions/python/banners/_10_openrouter_feature.py` to show a banner at threshold; no scheduler.

### U4. Export current view as CSV/JSON
- **Status:** planned. **Evidence:** research shows export is expected (OpenRouter's own dashboard has it).
- **Depends on:** none. **Verification:** download matches table rows.
- **Difficulty:** easy. Client-side serialisation of data already in `usage-store.js`.
- **Feasibility:** none.
- **Simpler alternative:** a "copy as TSV" button on tables; no files.

## Later

### U5. Per-request drill-down
- **Status:** planned. **Evidence:** observability tools lead here (Langfuse, Helicone).
- **Depends on:** U2. **Verification:** row opens request metadata for a key/day.
- **Difficulty:** hard. Volume grows the SQLite cache; API pagination and rate limits.
- **Feasibility:** requires an OpenRouter endpoint exposing per-request data to management keys; unverified. Calls cost money to test, so fixtures first.
- **Simpler alternative:** link out to OpenRouter's Activity page filtered by key and date.

### U6. Split `helpers/openrouter_client.py`
- **Status:** planned. **Evidence:** 551 lines mixing settings, key/workspace mapping, overview, routing and budgets.
- **Depends on:** U2 (tests first). **Verification:** suite green, API responses unchanged.
- **Difficulty:** medium. Mechanical but wide.
- **Feasibility:** none.
- **Simpler alternative:** move only the `_*_to_dict` mappers to `engine/models.py` and stop there.
