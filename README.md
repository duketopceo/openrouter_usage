<p align="center">
  <img src="docs/logo.webp" alt="OpenRouter Usage" width="120" />
</p>

# OpenRouter Usage

**Org spend, workspace-aware analytics, and routing recommendations — native to Agent Zero.**

A quick-view/detailed dashboard powered by your OpenRouter **management key**. Discovers workspaces, queries the OpenRouter Analytics API, caches history locally, and recommends per-workspace routing defaults. Read-only by default; routing changes require explicit confirmation.

---

## What you see

| View | Shows |
|------|-------|
| **Quick** | 30-day spend, credit balance, spend today, top model/key, active workspace |
| **Detailed** | Tabs for spend, models, providers, apps, keys, workspaces, activity, budgets, and the OpenRouter Routing harness (ORI) |

Data path: `workspaces` + `credits` + `keys` + `activity` + `analytics/query` (primary) with a local SQLite cache for historical data.

---

## Install

```bash
cp -r openrouter_usage /a0/usr/plugins/
```

Restart Agent Zero → **Plugins** → enable **OpenRouter Usage**.

### 1. Secret (required)

`/a0/usr/secrets.env`

```env
OPENROUTER_MANAGEMENT_KEY=sk-or-mgmt-...
```

> Use your org **management** key — not an inference key.

### 2. Settings → Developer

1. **Load workspaces** → pin a default workspace (optional)
2. **Fetch keys** → check keys to watch (empty = aggregate activity only)
3. Set aliases: `821713b8=luke,abc12345=helpdesk`
4. Adjust refresh interval, history days, burn window, and budget alert threshold

---

## Design

- **Server-side only** — management key never reaches the browser
- **Workspace-scoped** — discovers and selects workspaces; all usage queries respect the selection
- **Analytics-first** — uses OpenRouter `/analytics/query` with `credits`, `keys`, `activity`, and `budgets` as supplements
- **Local history** — SQLite cache at `~/.local/share/openrouter_usage/usage.db` extends the API window
- **Routing harness (ORI)** — recommends per-workspace defaults and applies only after explicit confirmation
- **Graceful degradation** — partial data and stale flags if a scoped query fails
- **Non-blocking** — widget shows stale/error state; Agent Zero still starts

---

## Manual checklist

- [ ] Missing key → clear empty state
- [ ] With key → quick view shows spend, balance, top model/key, and active workspace
- [ ] Detailed view → tabs load models, providers, apps, keys, workspaces, activity, budgets, and routing
- [ ] Workspace selector switches scope and refreshes data
- [ ] Routing harness shows current vs recommended defaults and requires confirmation to apply

---

## License

MIT
