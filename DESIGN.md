# Design direction: Copper Gauge

Spend is a meter you read at a glance. Warm paper and ink, one copper accent for "the needle" (the number that moves), everything else quiet. Reads as an instrument panel, not a SaaS dashboard.

## Method note

The `refero-design` skill was not run (small plugin). References were chosen from first-hand knowledge: Agent Zero's own theme (the plugin must sit inside it), OpenRouter's Activity page, and Stripe-style tabular money layouts. Reference lock: tabular figures for every amount, one accent colour, no gradients except the existing KPI tint. Decision ledger below.

| Decision | Choice | Why |
|---|---|---|
| Inherit host theme | Keep `--color-*` Agent Zero vars first, fall back to tokens below | Plugin lives in A0 chrome; must follow its light/dark |
| Accent | Copper, not blue | Distinct from A0 blue; money/meter feel |
| Numbers | `font-variant-numeric: tabular-nums` everywhere | Columns of dollars must align |
| Status colour | Never colour alone; pill carries a text label | Accessibility |

## Tokens

Fallbacks used when the host does not define `--color-*`. Contrast measured (WCAG relative luminance).

| Token | Light | Dark |
|---|---|---|
| paper (bg) | `#FAF8F4` | `#14130F` |
| surface | `#F1EDE5` | `#1F1D17` |
| ink (text) | `#1C1B18` (16.2:1) | `#ECE8DF` (15.2:1) |
| ink-muted | `#5E5A50` (6.5:1) | `#A8A294` (7.3:1) |
| copper (accent) | `#9A4A0C` (5.9:1) | `#E8A063` (8.5:1) |
| good | `#1F6B43` (6.1:1) | `#6FCB92` (9.4:1) |
| warn | `#8F5A00` (5.5:1) | `#E9B949` (10.2:1) |
| bad | `#B3261E` (6.2:1) | `#FF8A80` (8.1:1) |

All text pairs are at or above AA (4.5:1) on paper.

## Type

Host font for UI text (inherits Agent Zero). Money, ids and model names use the host mono stack at 0.9em. KPI value `clamp(1.05rem, 4vw, 1.45rem)` weight 800; labels 0.68rem uppercase with 0.06em tracking.

## Icon and glyph style

Geometric, 6 px stroke on a 64 grid, round caps, two colours (ink + copper). Status dots are 8 px circles. No icon fonts, no emoji.

## Motion

Skeleton shimmer only (existing). 120 ms colour transitions on hover/focus. No bar-grow animation. `prefers-reduced-motion` disables the shimmer.

## Surfaces

- **Sidebar widget** (`extensions/webui/sidebar-quick-actions-main-end/usage-widget.html`): 18 px mark plus today's spend.
- **Dashboard modal** (`webui/usage-dashboard.html`): hero, KPI strip, Simple (sparkline, top lists) and Detailed (tabs, tables, ORI routing, confirm dialog).
- **Settings** (`webui/config.html`): form fields, workspace and key pickers.
- **README / docs**: logo, social card (`assets/brand/`).

States: empty (no management key) states the fix; loading uses skeleton KPIs; errors use the bad banner; stale uses a warn pill. Focus: 2 px copper ring, 2 px offset, on every button, tab and select.

## Audit (current UI, 2026-10-11)

- No visible focus ring on `.ui-btn`, `.ui-tab`: fixed in `ui: focus rings`.
- Accent was blue `#6cc4ff` fallback, which fails AA on light surfaces: replaced by the copper fallback.
- Chrome used `docs/logo.webp`: replaced with the new mark (proposal).
- Not verified: screenshots (UI needs a running Agent Zero and a live OpenRouter key; no paid calls were made).
