---
title: "OpenRouter Usage v1.3.0 release cut - Plan"
type: feat
date: 2026-09-12
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-plan-bootstrap
execution: code
---

# OpenRouter Usage v1.3.0 Release Cut - Plan

## Goal Capsule

- **Objective:** The merged "ultimate" work (engine refactor, workspace awareness, ORI routing harness, SQLite cache) ships as a tagged, released v1.3.0 with CI keeping it green — the repo's public state finally matches what `plugin.yaml` already claims.
- **Authority:** This plan. `plugin.yaml` (version source of truth: 1.3.0), `docs/plans/2026-09-04---openrouter-usage-ultimate.md` (implemented scope, merged via PRs #1–#2), `README.md`.
- **Execution profile:** Changes land on `main` through a release branch + PR — the repo's dominant convention (all landed work came via PRs #1 and #2). Tag and release happen on `main` after the PR merges.
- **Stop conditions:** unittest suite green locally and in CI; `v1.3.0` annotated tag pushed to `main`; GitHub release published with notes; stale merged branches deleted.

---

## Product Contract

### Summary

The plugin reached feature-complete v1.3.0 through two merged PRs but was never released: no tag, no GitHub release, no CI, and two stale merged remote branches (`origin/feat/ultimate`, `origin/sync/ui-overhaul`) linger. This plan is release mechanics plus two hygiene gaps — a CI workflow so the suite runs without a human remembering it, and a one-line test fix so the suite stays green instead of silently rotting.

### Problem Frame

A plugin repo with `version: 1.3.0` in its manifest but no corresponding tag or release is undistributable in practice — nobody can install a pinned version, and future contributors have no signal for what shipped. The suite (26 unittest cases over fixtures, zero network) passes locally today — but `test_prune` hardcodes its "recent" fixture row at `2026-09-01` while `UsageDb.prune` deletes rows older than 90 days, so the suite goes red around 2026-11-30 with no code change. Releasing CI that rots in 11 weeks is not release-stage.

### Requirements

- R1. The test suite runs green via `python3 -m unittest tests.test_engine` from repo root (verified during planning: 26 tests, OK; unittest discovery via the `tests.` package so `tests/__init__.py` installs the `_site` shim mapping `usr.plugins.openrouter_usage` to the repo root).
- R2. `tests/test_engine.py::test_prune`'s hardcoded `2026-09-01` "recent" row is generated relative to `datetime.now(timezone.utc)` so the 90-day prune window can never age it out — the one permitted code change; everything else about the plugin stays untouched.
- R3. `.github/workflows/ci.yml` runs the suite on push to `main` and on `pull_request` (session-settled: CI in scope — chosen over tag-and-release only).
- R4. `CHANGELOG.md` is created documenting v1.3.0 (engine package, workspaces, analytics API primary source, SQLite cache, quick/detailed UI, ORI routing harness, budgets/projected burn) with a brief prior-history summary; the entry date tracks the actual release date.
- R5. Annotated tag `v1.3.0` is created on `main` after CI lands and **pushed** before `gh release create` runs (otherwise gh mints a lightweight remote tag and the DoD's annotated-tag requirement silently fails), and a GitHub release is published from it with notes drawn from the changelog.
- R6. Stale remote branches whose content is already in `main` are deleted via `git push origin --delete feat/ultimate sync/ui-overhaul` (removes remote branch and local remote-tracking ref in one step) — but only after a content-level check, not a commit-list check: `git diff origin/feat/ultimate f51e20d` must be empty (the branch's unique commit `ab21516` is the pre-squash twin of PR #1's squashed merge), and `git diff main origin/sync/ui-overhaul` must be empty (its merge style is unverified — the diff, not ancestry, is authoritative).

### Success Criteria

- `gh release view v1.3.0` resolves and its notes match the changelog section.
- The `ci.yml` workflow reports success on the tagged commit.
- `git branch -r` shows only `main` (+ `HEAD`).

### Scope Boundaries

- No plugin behavior changes — the only code touched is the `test_prune` fixture date (R2); everything else is fixed at what already merged.
- No new features, no fixture expansion, no pytest migration (suite is `unittest`-native; a port is not needed to release).
- No README CI badge — none exists today and the success criterion tracks the workflow run, not a badge.
- Not publishing to any plugin registry beyond the GitHub release.

---

## Planning Contract

### Key Technical Decisions

- KTD1. **CI added before the tag** (session-settled: user-approved — chosen over tag-only: releasing an untested-by-CI manifest version invites a broken "stable"). Governs R3, R5.
- KTD2. **unittest, not pytest.** The suite is `unittest.TestCase`-based and `pytest` isn't installed; the one canonical command is `python3 -m unittest tests.test_engine` — used identically in R1, the workflow, and the Verification Contract. The suite is stdlib-only (verified: test/engine/helper imports need no `pip install`; `helpers/openrouter_client.py`'s Agent-Zero imports are never reached by the suite).
- KTD3. **Version already declared.** `plugin.yaml` says `1.3.0`; no manifest edit needed — the tag names what the manifest already claims.
- KTD4. **Stale-branch deletion is gated on content, not topology.** `feat/ultimate` is expected to show its pre-squash commit `ab21516` in `git log main..` (non-empty is fine); `sync/ui-overhaul`'s merge style is unverified so its `git log` may also be non-empty. What must be empty is the tree diff against the merged content — `git diff` exit-clean is the check, ancestry claims are not.

### Assumptions

- `gh` has release-creation and branch-deletion rights on `duketopceo/openrouter_usage` (verified for PR listing during planning; deletion scope is the live check in U4).
- GitHub Actions is enabled on the repo (workflows exist in sibling repos on the same account; none exist here yet).

### Sequencing

U1 (test fix) → U2 (CI) → U3 (changelog) → U4 (tag + release + branch cleanup). U2 and U3 are order-free relative to each other; U4 must be last. All four land on one release PR.

---

## Implementation Units

### U1. Fix test_prune's rotting fixture

**Goal:** The suite stays green in December without human attention.

**Requirements:** R1, R2

**Files:** `tests/test_engine.py`

**Approach:**
- In `TestDatabase.test_prune` (around `tests/test_engine.py:228-234`), generate the "recent" `AnalyticsRow.start_time` relative to `datetime.now(timezone.utc)` (e.g., now minus a few days) instead of the hardcoded `2026-09-01T00:00:00Z`; leave the old row's date and the assertion shape alone.
- Execution note: one-line fixture change; keep the test's intent (recent row survives a 90-day prune) identical.

**Test scenarios:**
- `test_prune` passes today and is time-invariant (the "recent" row can never cross the 90-day cutoff).
- Full suite still 26 tests, 0 failures.

**Verification:** `python3 -m unittest tests.test_engine` exits 0.

### U2. CI workflow

**Goal:** Every push/PR runs the fixture suite.

**Requirements:** R1, R3

**Dependencies:** U1 (CI must not land on a rotting test)

**Files:** `.github/workflows/ci.yml` (new)

**Approach:**
- Single job: `ubuntu-latest`, `actions/setup-python` (3.x), run `python3 -m unittest tests.test_engine` from repo root.
- Triggers: push to `main`, `pull_request`.
- No dependency install step — the suite is stdlib-only (verified during planning); do not add `pip install`.

**Patterns to follow:** minimal workflow shape used in sibling repos (e.g. `vision-e2e`, `OmaSeal` CI files) — match naming/trigger conventions.

**Test scenarios:**
- Workflow file parses (actionlint if available).
- A scratch PR exercises the `pull_request` trigger — pushing to a scratch branch alone produces no runs under these triggers.

**Verification:** `gh run list` shows a green run for the release PR and for the landing commit.

### U3. CHANGELOG

**Goal:** v1.3.0's changes are recorded for the release notes and future readers.

**Requirements:** R4

**Files:** `CHANGELOG.md` (new)

**Approach:**
- Keep a Changelog-ish format, single `## [1.3.0] - <actual release date>` entry plus a short "Earlier" note for pre-1.3.0 (plugin existed before versioning discipline).
- Content sourced from merged PRs #1/#2 and the ultimate plan's scope list — workspace discovery, analytics API primary source, SQLite cache, quick/detailed UI, ORI routing harness, budgets/projected burn.

**Test expectation: none** — documentation only.

**Verification:** changelog's 1.3.0 items each trace to a merged commit; no invented features; entry date matches the real tag date.

### U4. Tag, release, branch cleanup

**Goal:** v1.3.0 is installable-by-tag and visible on the releases page; stale refs gone.

**Requirements:** R5, R6

**Dependencies:** U2 (CI green on the tagged commit), U3 (release notes source), release PR merged

**Files:** none (git refs + GitHub release only)

**Approach:**
1. On post-merge `main`: create annotated tag `v1.3.0` (message `v1.3.0`), then `git push origin v1.3.0` — the tag must exist on the remote before the release is created or `gh` mints a lightweight tag instead.
2. `gh release create v1.3.0` with notes from the changelog section.
3. Content-check then delete: `git diff origin/feat/ultimate f51e20d` empty AND `git diff main origin/sync/ui-overhaul` empty, then `git push origin --delete feat/ultimate sync/ui-overhaul`. A non-empty diff stops the deletion — surface it instead of forcing.
4. Delete local stale branches if present; `git fetch --prune` to settle remote-tracking refs.

**Test expectation: none** — release mechanics.

**Verification:** `gh release view v1.3.0` renders notes; remote tag is annotated (the local one); `git ls-remote --heads` and `git branch -r` show only `main`.

---

## Verification Contract

| Gate | Command / check |
|------|-----------------|
| Suite | `python3 -m unittest tests.test_engine` — 26 tests, OK |
| CI | `gh run list` — `ci.yml` green on the tagged commit |
| Release | `gh release view v1.3.0` — exists, notes match changelog |
| Refs | `git ls-remote --heads origin` and `git branch -r` — `main` only |
| Tag | `git cat-file -t v1.3.0` on the remote-pushed ref — `tag` (annotated), not `commit` |

## Definition of Done

- `main` carries the test fix, CI workflow, and CHANGELOG via the release PR; CI green on the tip commit.
- Annotated tag `v1.3.0` pushed before release creation; GitHub release published with notes.
- Stale remote branches deleted after content checks; local repo clean.
- No plugin source files modified except the `test_prune` fixture date; no abandoned-attempt artifacts.
