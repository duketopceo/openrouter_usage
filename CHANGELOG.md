# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] - 2026-09-12

### Added

- `engine/` package — models, analytics, fetch, recommender, budgets, and a SQLite-backed history store
- Workspace discovery and workspace-scoped usage queries with persisted selection
- Quick-view and detailed dashboard: spend, models, providers, apps, keys, workspaces, activity, budgets tabs
- ORI routing harness — recommends per-workspace routing defaults, applied only after explicit confirmation
- Budgets and projected-burn support in the detailed view
- CI workflow running the engine unittest suite on push and pull requests

### Changed

- Analytics API (`/analytics/query`) is now the primary usage source; `credits`, `keys`, `activity`, and `budgets` endpoints are supplements
- Usage history caches to a local SQLite database at `~/.local/share/openrouter_usage/usage.db`

## Earlier

The plugin shipped informally before versioning discipline: a standalone
Agent Zero usage panel reading the management key, later synced with the
monorepo UI kit and refactored into the `engine/` + `api/` + `webui/` layout.
