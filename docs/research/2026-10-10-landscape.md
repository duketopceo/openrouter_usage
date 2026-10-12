# Landscape: OpenRouter spend tracking (2026-10-11)

Method: two web searches (no paid calls) plus a read of this repo. Search snippets are secondary sources; licences and activity were not verified except where noted.

## Who else does this

| Project / product | What it does | Source |
|---|---|---|
| OpenRouter Activity dashboard | Built in. Total spend over a period, per-request table, export. | https://aireiter.com/blog/openrouter-activity-dashboard-guide |
| Hermes `openrouter-spend` plugin | Per-key spend in USD, local request ledger, desktop status-bar popup. Described as MIT. | https://hermes-agent.nousresearch.com/docs/plugins/openrouter-spend |
| `openrouter-usage` / `cost-tracker` agent skills | Balance, per-model cost and tokens from local session logs; SQLite history and budget alerts in the cost-tracker one. | https://getclawkit.com/skills/official-lcajigasm-openrouter-usage-info , https://getclawkit.com/skills/official-aiwithabidi-cost-tracker |
| Open WebUI cost-tracker filters | In-chat stats and cost for OpenRouter connections. | https://openwebui.com/f/kkoolldd/cost_tracker_openrouter |
| SigNoz OpenRouter dashboard | OpenTelemetry-based cost and usage template; needs an OTel pipeline. | https://signoz.io/docs/dashboards/dashboard-templates/openrouter-dashboard/ |
| Metabase | No native connector; you sync the activity API yourself. | https://www.metabase.com/integrations/openrouter |
| LiteLLM (gateway) | Per-key, user, team budgets with enforcement via virtual keys. | https://www.getmaxim.ai/articles/best-llm-cost-tracking-tools-in-2026/ |
| Langfuse / Helicone | Observability with cost breakdowns; sources do not show per-key budget enforcement. | same |

## Better and worse than this repo

- Others are better at: per-request tracing (Langfuse, Helicone, SigNoz), and hard budget enforcement (LiteLLM). This plugin only reads and alerts.
- Others are worse at: org scope. Most tools see only traffic through their own proxy or logs. This plugin reads the management-key APIs (workspaces, keys, analytics), so it sees usage from every app on the org.
- Users expect: spend today / this month, per-model and per-key splits, a balance, history longer than the API window, and alerts before a limit.

## What is unique here

1. It lives inside Agent Zero (sidebar widget, settings panel, banner), so spend sits next to the agents causing it.
2. Workspace-aware, org-level view from the management key, with the key kept server-side.
3. The ORI routing harness: recommends per-workspace default models from latency, throughput and cache-hit metrics, and applies only after confirmation.

## Gaps worth closing

No export, no alerts outside the UI, no per-request drill-down, no enforcement. Enforcement belongs to a gateway; this repo should not grow into one.
