import { createStore } from "/js/AlpineStore.js";
import { callJsonApi } from "/js/api.js";
import {
  toastFrontendError,
  toastFrontendSuccess,
} from "/components/notifications/notification-store.js";

const API_OVERVIEW = "/plugins/openrouter_usage/overview";
const API_REFRESH = "/plugins/openrouter_usage/refresh";
const API_KEYS = "/plugins/openrouter_usage/keys_list";
const API_WORKSPACES = "/plugins/openrouter_usage/workspaces";
const API_ANALYTICS = "/plugins/openrouter_usage/analytics";
const API_BUDGETS = "/plugins/openrouter_usage/budgets";
const API_ROUTING = "/plugins/openrouter_usage/routing";
const VIEW_KEY = "openrouter_usage_view";
const TAB_KEY = "openrouter_usage_tab";

function nowIso(daysAgo = 0) {
  const d = new Date(Date.now() - daysAgo * 24 * 60 * 60 * 1000);
  return d.toISOString();
}

const ANALYTICS_TABS = {
  models: {
    dimensions: ["model"],
    metrics: ["total_usage", "request_count", "tokens_prompt", "tokens_completion"],
  },
  providers: {
    dimensions: ["provider"],
    metrics: ["total_usage", "request_count", "avg_latency", "p90_latency", "avg_throughput"],
  },
  apps: {
    dimensions: ["app"],
    metrics: ["total_usage", "request_count"],
  },
  keys: {
    dimensions: ["api_key_id"],
    metrics: ["total_usage", "request_count"],
  },
  workspaces: {
    dimensions: ["workspace"],
    metrics: ["total_usage", "request_count"],
  },
};

export const store = createStore("openrouterUsageStore", {
  loading: false,
  loadingTabs: false,
  overview: null,
  error: null,
  availableKeys: [],
  workspaces: [],
  selectedWorkspaceId: "",
  activeTab: localStorage.getItem(TAB_KEY) || "overview",
  analyticsRows: [],
  routing: null,
  pendingRouting: null,
  budgets: [],
  pollTimer: null,
  view: localStorage.getItem(VIEW_KEY) || "simple",

  get emptyState() {
    return this.overview?.empty_state || null;
  },

  get hasData() {
    return !!this.overview?.ok;
  },

  get summaryLine() {
    const totals = this.overview?.totals;
    if (!totals) return "No data";
    const historyLabel =
      this.overview?.history_label ||
      (this.overview?.settings?.history_days
        ? `${this.overview.settings.history_days}d`
        : "30d");
    return `${totals.usd_label || this.formatUsd(totals.usd || 0)} · last ${historyLabel}`;
  },

  get widgetLabel() {
    const totals = this.overview?.totals;
    if (this.loading) return "…";
    if (!totals) return "OR";
    return totals.usd_label || this.formatUsd(totals.usd || 0);
  },

  get creditLine() {
    const credits = this.overview?.credits;
    if (!credits) return "";
    return credits.balance_label ? `Balance ${credits.balance_label}` : "";
  },

  get topKeys() {
    return Array.isArray(this.overview?.top_keys) ? this.overview.top_keys : [];
  },

  get asOfLabel() {
    if (!this.overview?.as_of) return "";
    try {
      return new Date(this.overview.as_of).toLocaleString();
    } catch {
      return this.overview.as_of;
    }
  },

  get activeWorkspaceName() {
    if (!this.selectedWorkspaceId) return "—";
    const ws = this.workspaces.find((w) => w.id === this.selectedWorkspaceId);
    return ws?.name || ws?.id || this.selectedWorkspaceId;
  },

  get topModel() {
    const row = this.overview?.top_models?.[0];
    if (!row) return null;
    const value = row.total_usage ?? row.usd ?? 0;
    return {
      model: row.model || "—",
      total_usage: value,
      total_usage_label: this.formatUsd(value),
    };
  },

  get topKey() {
    const row = this.overview?.top_keys?.[0];
    if (!row) return null;
    const value = row.total_usage ?? row.usd ?? 0;
    return {
      label: row.label || row.hash_prefix || "—",
      hash_prefix: row.hash_prefix || "",
      total_usage: value,
      total_usage_label: this.formatUsd(value),
    };
  },

  get spendToday() {
    const daily = this.overview?.daily;
    if (!Array.isArray(daily) || !daily.length) return "—";
    const now = new Date();
    const label = `${now.getUTCMonth() + 1}/${now.getUTCDate()}`;
    const found = daily.find((d) => d.label === label);
    if (!found) return "—";
    return this.formatUsd(this.totalDaily(found));
  },

  get spendThisMonth() {
    const daily = this.overview?.daily;
    if (!Array.isArray(daily) || !daily.length) return "—";
    const month = String(new Date().getUTCMonth() + 1);
    let total = 0;
    let matched = 0;
    for (const day of daily) {
      if (day.label && day.label.split("/")[0] === month) {
        matched += 1;
        total += this.totalDaily(day);
      }
    }
    return matched ? this.formatUsd(total) : "—";
  },

  formatUsd(value) {
    const amount = Number(value || 0);
    if (Math.abs(amount) < 0.01) return `$${amount.toFixed(4)}`;
    if (Math.abs(amount) < 1) return `$${amount.toFixed(3)}`;
    return `$${amount.toFixed(2)}`;
  },

  formatNumber(value, digits = 2) {
    const n = Number(value);
    if (Number.isNaN(n)) return "—";
    return n.toLocaleString(undefined, {
      minimumFractionDigits: 0,
      maximumFractionDigits: digits,
    });
  },

  totalDaily(day) {
    if (!day) return 0;
    if (typeof day.usd === "number") return day.usd;
    if (day.by_key && typeof day.by_key === "object") {
      return Object.values(day.by_key).reduce((sum, v) => sum + (Number(v) || 0), 0);
    }
    return 0;
  },

  keyLabel(id) {
    if (!id) return "—";
    const hashMap = this.overview?.hash_to_label || {};
    if (hashMap[id]) return hashMap[id];
    const keys = this.overview?.keys || this.availableKeys || [];
    const key = keys.find(
      (k) =>
        k.hash === id ||
        k.hash_prefix === id ||
        (k.hash_prefix && id.startsWith(k.hash_prefix))
    );
    if (key) return key.label || key.name || key.hash_prefix || id;
    return id;
  },

  setView(mode) {
    this.view = mode === "detailed" ? "detailed" : "simple";
    localStorage.setItem(VIEW_KEY, this.view);
  },

  setTab(tab) {
    this.activeTab = tab;
    localStorage.setItem(TAB_KEY, tab);
    if (tab === "routing") {
      this.fetchRouting();
    } else if (tab === "budgets") {
      this.fetchBudgets();
    } else if (ANALYTICS_TABS[tab]) {
      const { dimensions, metrics } = ANALYTICS_TABS[tab];
      this.fetchAnalytics(dimensions, metrics);
    }
  },

  async selectWorkspace(id) {
    if (!id) return;
    this.selectedWorkspaceId = id;
    await this.fetchOverview({ force: true, workspace_id: id });
  },

  async fetchWorkspaces() {
    try {
      const result = await callJsonApi(API_WORKSPACES, {});
      if (!result?.ok) {
        toastFrontendError(result?.error || "Could not load workspaces", "OpenRouter Usage");
        return;
      }
      this.workspaces = Array.isArray(result.workspaces) ? result.workspaces : [];
      // Let the backend (pinned_workspace_id or first workspace) choose the active one.
      // selection is updated after the first overview fetch.
    } catch (error) {
      toastFrontendError(error?.message || "Could not load workspaces", "OpenRouter Usage");
    }
  },

  async fetchOverview({ force = false, workspace_id } = {}) {
    this.loading = true;
    this.error = null;
    try {
      const payload = {
        workspace_id: workspace_id || this.selectedWorkspaceId || undefined,
      };
      if (force) payload.force = true;
      const endpoint = force ? API_REFRESH : API_OVERVIEW;
      this.overview = await callJsonApi(endpoint, payload);
      if (this.overview?.workspace_id) {
        this.selectedWorkspaceId = this.overview.workspace_id;
      }
      if (this.overview?.routing?.current) {
        this.routing = this.overview.routing;
      }
    } catch (error) {
      this.error = error?.message || "Failed to load OpenRouter usage";
      toastFrontendError(this.error, "OpenRouter Usage");
    } finally {
      this.loading = false;
    }
  },

  async fetchKeys(workspace_id) {
    try {
      const payload = {};
      const ws = workspace_id || this.selectedWorkspaceId;
      if (ws) payload.workspace_id = ws;
      const result = await callJsonApi(API_KEYS, payload);
      if (!result?.ok) {
        toastFrontendError(result?.error || "Could not list keys", "OpenRouter Usage");
        return;
      }
      this.availableKeys = Array.isArray(result.keys) ? result.keys : [];
      toastFrontendSuccess(`Loaded ${this.availableKeys.length} keys`, "OpenRouter Usage");
    } catch (error) {
      toastFrontendError(error?.message || "Could not list keys", "OpenRouter Usage");
    }
  },

  async fetchAnalytics(dimensions, metrics) {
    this.loadingTabs = true;
    try {
      const days = this.overview?.settings?.history_days || 30;
      const payload = {
        dimensions,
        metrics,
        time_granularity: "day",
        start_time: nowIso(days),
        end_time: nowIso(),
        limit: 1000,
      };
      // Comparing workspaces means no workspace filter; otherwise scope to the selected one.
      if (this.selectedWorkspaceId && !dimensions.includes("workspace")) {
        payload.workspace_id = this.selectedWorkspaceId;
      }
      const result = await callJsonApi(API_ANALYTICS, payload);
      this.analyticsRows = Array.isArray(result?.rows) ? result.rows : [];
    } catch (error) {
      toastFrontendError(error?.message || "Analytics request failed", "OpenRouter Usage");
      this.analyticsRows = [];
    } finally {
      this.loadingTabs = false;
    }
  },

  async fetchBudgets() {
    if (!this.selectedWorkspaceId) return;
    this.loadingTabs = true;
    try {
      const result = await callJsonApi(API_BUDGETS, { workspace_id: this.selectedWorkspaceId });
      this.budgets = Array.isArray(result?.budgets) ? result.budgets : [];
    } catch (error) {
      toastFrontendError(error?.message || "Could not load budgets", "OpenRouter Usage");
      this.budgets = [];
    } finally {
      this.loadingTabs = false;
    }
  },

  async fetchRouting() {
    if (!this.selectedWorkspaceId) return;
    this.loadingTabs = true;
    try {
      const result = await callJsonApi(API_ROUTING, { workspace_id: this.selectedWorkspaceId });
      if (!result?.ok) {
        toastFrontendError(result?.error || "Could not load routing", "OpenRouter Usage");
        this.routing = null;
        return;
      }
      this.routing = result;
    } catch (error) {
      toastFrontendError(error?.message || "Could not load routing", "OpenRouter Usage");
      this.routing = null;
    } finally {
      this.loadingTabs = false;
    }
  },

  async applyRouting(defaults, confirmed = false) {
    if (!confirmed) {
      this.pendingRouting = defaults || this.routing?.recommended || null;
      await this.fetchRouting();
      return;
    }
    const toApply = defaults || this.pendingRouting || this.routing?.recommended || {};
    if (!this.selectedWorkspaceId) {
      toastFrontendError("Select a workspace before applying routing", "OpenRouter Usage");
      return;
    }
    this.loading = true;
    try {
      const result = await callJsonApi(API_ROUTING, {
        workspace_id: this.selectedWorkspaceId,
        defaults: toApply,
        confirmed: true,
      });
      if (!result?.ok) {
        throw new Error(result?.error || "Routing update failed");
      }
      toastFrontendSuccess("Routing updated", "OpenRouter Usage");
      this.pendingRouting = null;
      await this.fetchOverview({ force: true });
      await this.fetchRouting();
    } catch (error) {
      toastFrontendError(error?.message || "Failed to apply routing", "OpenRouter Usage");
    } finally {
      this.loading = false;
    }
  },

  toggleWatch(hashPrefix, config) {
    if (!config || !hashPrefix) return;
    const list = Array.isArray(config.watched_key_hashes) ? [...config.watched_key_hashes] : [];
    const index = list.indexOf(hashPrefix);
    if (index >= 0) list.splice(index, 1);
    else list.push(hashPrefix);
    config.watched_key_hashes = list;
  },

  isWatched(hashPrefix, config) {
    const list = config?.watched_key_hashes;
    return Array.isArray(list) && list.includes(hashPrefix);
  },

  startPolling() {
    this.stopPolling();
    const minutes = Number(this.overview?.settings?.refresh_interval_minutes || 5);
    const ms = Math.max(1, minutes) * 60 * 1000;
    this.pollTimer = window.setInterval(() => this.fetchOverview(), ms);
  },

  stopPolling() {
    if (this.pollTimer) {
      window.clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
  },

  async onOpen() {
    await this.fetchWorkspaces();
    // The backend resolves pinned_workspace_id or the first workspace.
    await this.fetchOverview({ force: true });
    this.startPolling();
  },

  cleanup() {
    this.stopPolling();
  },

  maxBar(values, field = "usd") {
    const nums = values.map((item) =>
      typeof item === "number"
        ? item
        : Number(item?.[field] ?? item?.total_usage ?? item?.usd ?? 0) || 0
    );
    return Math.max(...nums, 0.0001);
  },

  barWidth(value, max) {
    const pct = Math.min(100, (Number(value || 0) / (max || 0.0001)) * 100);
    return `${pct}%`;
  },
});

export default function bootstrapOpenRouterUsage() {
  store.onOpen();
}
