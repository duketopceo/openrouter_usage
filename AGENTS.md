# openrouter_usage — agent notes

An [Agent Zero](https://github.com/agent0ai/agent-zero) plugin that tracks
OpenRouter org spend, per-key usage, models, providers, workspaces, budgets,
and routing recommendations. `README.md` is the user doc.

## Commands

```bash
# Tests — 28 tests, standard library only, no network and no secrets
python3 -m unittest discover -s tests -t . -v

# Exactly what CI runs (.github/workflows/ci.yml, push/PR on main):
python3 -m unittest discover -s tests -t . -v
```

`-t .` is **required**. It sets the top-level directory to the repo root so
`tests` is importable as a package; without it the run collects nothing.

CI also greps its own output for `Ran [1-9][0-9]* tests` and fails if it does
not match, so a suite that silently collects zero tests is a red build rather
than a false green. Keep that assertion honest when you add or rename test
modules.

## Layout

| Path | What it is |
|---|---|
| `plugin.yaml` | Manifest — `name: openrouter_usage`, `settings_sections: [developer]`. The id is also the install directory name. |
| `engine/` | All logic: `api.py`, `analytics.py`, `budgets.py`, `cache.py`, `db.py`, `fetch.py`, `models.py`, `recommender.py`. |
| `api/` | One module per Agent Zero API surface (`overview`, `keys_list`, `workspaces`, `routing`, `budgets`, `refresh`, `analytics`). |
| `helpers/` | `openrouter_client.py`, `fetch.py`, `format.py`, `cache.py`, `aliases.py`. |
| `webui/` | Static dashboard: `usage-dashboard.html`, `ui.js`, `usage-store.js`, `config.html`, `ui-kit.css`. |
| `extensions/` | Agent Zero injection points: a Python banner hook and two WebUI slots (`initFw_end`, `sidebar-quick-actions-main-end`). |
| `tests/_site/` | Path shim — see below. |
| `tests/fixtures/*.json` | Recorded API payloads. The only data source the tests use. |

## Conventions that will bite you

- **Tests import through the A0 install path.** `tests/__init__.py` puts
  `tests/_site` on `sys.path`, and
  `tests/_site/usr/plugins/openrouter_usage/` mirrors the directory A0 creates
  at install time. Tests then import
  `usr.plugins.openrouter_usage.engine.<module>` — the same path the runtime
  uses. A new engine module must be reachable under that mirrored tree or the
  tests break; do not "simplify" the imports to plain relative ones.
- **Fixtures only.** No network, no management key, no real SQLite file
  outside a `tempfile` directory. Extend `tests/fixtures/` instead.
- **No build step and no bundler.** `webui/` and `extensions/` are served as
  plain files. Introducing a bundler is a new architecture decision, not a
  refactor.

## Invariants

- **The management key never reaches the browser.** It is read server-side by
  `engine/` and `helpers/` code only — `webui/ui.js` and the `extensions/webui/`
  injection points talk to the A0 API, never to OpenRouter directly. Keep any
  new key handling on that side of the line.
- **The routing harness only applies after explicit confirmation.** It
  recommends per-workspace defaults; it must never auto-apply.
- **Every path degrades gracefully.** A failed or partial scoped query yields
  partial data plus a stale flag, never a thrown error that blocks Agent Zero
  from starting. Preserve that when adding a data source.
- `default_config.yaml` holds setting values only, never credentials.


## Code graph index (optional accelerator)

This repo may be indexed by `codebase-memory-mcp` (CBM) on an agent's local
machine — `.codebase-memory/` is gitignored. If your harness exposes CBM
tools (`search_graph`, `trace_path`, `get_architecture`, `detect_changes`),
prefer them for structural questions — symbol lookup, caller/callee traces,
impact analysis — instead of grep/read loops. Reindex after large refactors
(`index_repository`); treat `.codebase-memory/graph.db.zst` as a local cache
artifact, never commit it.
