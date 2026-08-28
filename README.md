<p align="center">
  <img src="docs/logo.webp" alt="OpenRouter Usage" width="120" />
</p>

# OpenRouter Usage

**Org spend at a glance — native to Agent Zero.**

A minimal sidebar widget and detailed dashboard powered by your OpenRouter **management key**. Read-only. No extra dependencies.

---

## What you see

| View | Shows |
|------|-------|
| **Widget** | 30-day spend, credit balance, top keys |
| **Detailed** | Daily spend, per-key bars, top models, token table |

Data path: `credits` + `keys` + per-key `activity` (when keys are watched).

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

1. **Fetch keys** → check keys to watch (empty = aggregate activity only)
2. Set aliases: `821713b8=luke,abc12345=helpdesk`
3. Adjust refresh interval (default 5 min)

---

## Design

- **Server-side only** — management key never reaches the browser
- **TTL cache** — one compact JSON blob per refresh cycle
- **Graceful degradation** — partial data if one key's activity fails
- **Non-blocking** — widget shows stale/error state; Agent Zero still starts

---

## Manual checklist

- [ ] Missing key → clear empty state
- [ ] With key → widget shows spend + balance
- [ ] Watched keys → per-key charts populate
- [ ] Detailed view tables and bars render

---

## License

MIT
