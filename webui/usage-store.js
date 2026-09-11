import { createStore } from "/js/AlpineStore.js";
import { callJsonApi } from "/js/api.js";
import {
  toastFrontendError,
  toastFrontendSuccess,
} from "/components/notifications/notification-store.js";
import { fmtUsd, fmtNum, fmtMs, pctChange, barPct, maxOf, relTime, dayKey } from "/plugins/openrouter_usage/webui/ui.js";

const API_OVERVIEW = "/plugins/openrouter_usage/overview";
const API_REFRESH = "/plugins/openrouter_usage/refresh";
const API_KEYS = "/plugins/openrouter_usage/keys_list";
const API_WORKSPACES = "/plugins/openrouter_usage/workspaces";
const API_ANALYTICS = "/plugins/openrouter_usage/analytics";
const API_BUDGETS = "/plugins/openrouter_usage/budgets";
const API_ROUTING = "/plugins/openrouter_usage/routing";
const VIEW_KEY = "openrouter_usage_view";
const TAB_KEY = "openrouter_usage_tab";

function isoDaysAgo(days) {
  return new Date(Date.now() - days * 86400000).toISOString();
}

const ANALYTICS_TABS = {
  models: {
    label: "Models",
    dimensions: ["model"],
    metrics: ["total_usage", "request_count", "tokens_prompt", "tokens_completion"],
  },
  providers: {
    label: "Providers",
    dimensions: ["provider"],
    metrics: ["total_usage", "request_count", "avg_latency", "p90_latency", "avg_throughput"],
  },
  apps: {
    label: "Apps",
    dimensions: ["app"],
    metrics: ["total_usage", "request_count"],
  },
  keys: {
    label: "Keys",
    dimensions: ["api_key_id"],
    metrics: ["total_usage", "request_count"],
  },
  workspaces: {
    label: "Workspaces",
    dimensions: ["workspace"],
    metrics: ["total_usage", "request_count"],
  },
};

export const TABS = [
  { id: "overview", label: "Overview" },
  { id: "spend", label: "Spend" },
  { id: "models", label: "Models" },
  { id: "providers", label: "Providers" },
  { id: "apps", label: "Apps" },
  { id: "keys", label: "Keys" },
  { id: "workspaces", label: "Workspaces" },
  { id: "activity", label: "Activity" },
  { id: "budgets", label: "Budgets" },
  { id: "routing", label: "Routing" },
];

export const store = createStore("openrouterUsageStore", {
  tabs: TABS,
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
  budgets: [],
  confirmApply: false,
  applying: false,
  pollTimer: null,
  view: localStorage.getItem(VIEW_KEY) || "simple",
  _overviewSeq: 0,
  _tabSeq: 0,

  get emptyState() {
    return this.overview?.empty_state || null;
  },

  get hasData() {
    return !!this.overview?.ok;
  },

  get stale() {
    return !!this.overview?.stale;
  },

  get historyDays() {
    return this.overview?.settings?.history_days || 30;
  },

  get summaryLine() {
    const totals = this.overview?.totals;
    if (!totals) return "No data";
    return `${totals.usd_label || fmtUsd(totals.usd || 0)} · last ${this.historyDays}d`;
  },

  get widgetLabel() {
    const totals = this.overview?.totals;
    if (this.loading) return "…";
    if (!totals) return "OR";
    return totals.usd_label || fmtUsd(totals.usd || 0);
  },

  get creditLine() {
    const credits = this.overview?.credits;
    return credits?.balance_label ? `Balance ${credits.balance_label}` : "";
  },

  get asOfLabel() {
    return relTime(this.overview?.as_of);
  },

  get activeWorkspaceName() {
    const ws = this.workspaces.find((w) => w.id === this.selectedWorkspaceId);
    return ws?.name || ws?.id || this.selectedWorkspaceId || "—";
  },

  get topModel() {
    const row = this.overview?.top_models?.[0];
    if (!row) return null;
    const value = row.total_usage ?? row.usd ?? 0;
    return { model: row.model || "—", total_usage: value, total_usage_label: fmtUsd(value) };
  },

  get topKey() {
    const row = this.overview?.top_keys?.[0];
    if (!row) return null;
    const value = row.total_usage ?? row.usd ?? 0;
    return {
      label: row.label || row.hash_prefix || "—",
      total_usage: value,
      total_usage_label: fmtUsd(value),
    };
  },

  _dayOf(row) {
    if (row?.day && /^\d{4}-\d{2}-\d{2}/.test(row.day)) {
      const [y, m, d] = row.day.slice(0, 10).split("-").map(Number);
      return { y, m, d };
    }
    return dayKey(row?.label);
  },

  get spendToday() {
    const daily = this.overview?.daily;
    if (!Array.isArray(daily) || !daily.length) return "—";
    const now = new Date();
    const found = daily.find((row) => {
      const k = this._dayOf(row);
      return k && k.y === now.getUTCFullYear() && k.m === now.getUTCMonth() + 1 && k.d === now.getUTCDate();
    });
    return found ? fmtUsd(this.totalDaily(found)) : "—";
  },

  get spendThisMonth() {
    const daily = this.overview?.daily;
    if (!Array.isArray(daily) || !daily.length) return "—";
    const now = new Date();
    const y = now.getUTCFullYear();
    const m = now.getUTCMonth() + 1;
    const total = daily.reduce((sum, row) => {
      const k = this._dayOf(row);
      return k && k.y === y && k.m === m ? sum + this.totalDaily(row) : sum;
    }, 0);
    return total > 0 ? fmtUsd(total) : "—";
  },

  get dailyMax() {
    return maxOf(this.overview?.daily, "usd");
  },

  // ---- formatting delegates (kept for template brevity) ----
  fmtUsd, fmtNum, fmtMs, pctChange, barPct, maxOf, relTime,

  totalDaily(day) {
    if (!day) return 0;
    if (typeof day.usd === "number") return day.usd;
    if (day.by_key && typeof day.by_key === "object") {
      return Object.values(day.by_key).reduce((s, v) => s + (Number(v) || 0), 0);
    }
    return 0;
  },

  keyLabel(id) {
    if (!id) return "—";
    const hashMap = this.overview?.hash_to_label || {};
    if (hashMap[id]) return hashMap[id];
    const keys = this.overview?.keys || this.availableKeys || [];
    const key = keys.find(
      (k) => k.hash === id || k.hash_prefix === id || (k.hash_prefix && id.startsWith(k.hash_prefix)),
    );
    return key ? key.label || key.name || key.hash_prefix || id : id;
  },

  setView(mode) {
    this.view = mode === "detailed" ? "detailed" : "simple";
    localStorage.setItem(VIEW_KEY, this.view);
    if (this.view === "detailed") this._loadTabData();
  },

  setTab(tab) {
    this.activeTab = tab;
    localStorage.setItem(TAB_KEY, tab);
    this._loadTabData();
  },

  _loadTabData() {
    if (this.activeTab === "routing") this.fetchRouting();
    else if (this.activeTab === "budgets") this.fetchBudgets();
    else if (ANALYTICS_TABS[this.activeTab]) {
      const { dimensions, metrics } = ANALYTICS_TABS[this.activeTab];
      this.fetchAnalytics(dimensions, metrics);
    }
  },

  async selectWorkspace(id) {
    if (!id || id === this.selectedWorkspaceId) return;
    this.selectedWorkspaceId = id;
    this.analyticsRows = [];
    this.budgets = [];
    this.routing = null;
    await this.fetchOverview({ force: true, workspace_id: id });
    this._loadTabData();
  },

  async fetchWorkspaces() {
    try {
      const result = await callJsonApi(API_WORKSPACES, {});
      if (!result?.ok) {
        toastFrontendError(result?.error || "Could not load workspaces", "OpenRouter Usage");
        return;
      }
      this.workspaces = Array.isArray(result.workspaces) ? result.workspaces : [];
    } catch (error) {
      toastFrontendError(error?.message || "Could not load workspaces", "OpenRouter Usage");
    }
  },

  async fetchOverview({ force = false, workspace_id } = {}) {
    const seq = ++this._overviewSeq;
    this.loading = true;
    this.error = null;
    try {
      const payload = { workspace_id: workspace_id || this.selectedWorkspaceId || undefined };
      if (force) payload.force = true;
      const result = await callJsonApi(force ? API_REFRESH : API_OVERVIEW, payload);
      if (seq !== this._overviewSeq) return; // superseded by a newer request
      this.overview = result;
      if (this.overview?.workspace_id) this.selectedWorkspaceId = this.overview.workspace_id;
      if (this.overview?.routing?.current) this.routing = this.overview.routing;
    } catch (error) {
      if (seq !== this._overviewSeq) return;
      this.error = error?.message || "Failed to load OpenRouter usage";
      toastFrontendError(this.error, "OpenRouter Usage");
    } finally {
      if (seq === this._overviewSeq) this.loading = false;
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
    const seq = ++this._tabSeq;
    this.loadingTabs = true;
    try {
      const payload = {
        dimensions,
        metrics,
        time_granularity: "day",
        start_time: isoDaysAgo(this.historyDays),
        end_time: isoDaysAgo(0),
        limit: 1000,
      };
      if (this.selectedWorkspaceId && !dimensions.includes("workspace")) {
        payload.workspace_id = this.selectedWorkspaceId;
      }
      const result = await callJsonApi(API_ANALYTICS, payload);
      if (seq !== this._tabSeq) return;
      if (result?.ok === false) {
        toastFrontendError(result.error || "Analytics request failed", "OpenRouter Usage");
        this.analyticsRows = [];
        return;
      }
      this.analyticsRows = Array.isArray(result?.rows) ? result.rows : [];
    } catch (error) {
      if (seq !== this._tabSeq) return;
      toastFrontendError(error?.message || "Analytics request failed", "OpenRouter Usage");
      this.analyticsRows = [];
    } finally {
      if (seq === this._tabSeq) this.loadingTabs = false;
    }
  },

  async fetchBudgets() {
    if (!this.selectedWorkspaceId) return;
    const seq = ++this._tabSeq;
    this.loadingTabs = true;
    try {
      const result = await callJsonApi(API_BUDGETS, { workspace_id: this.selectedWorkspaceId });
      if (seq !== this._tabSeq) return;
      if (result?.ok === false) {
        toastFrontendError(result.error || "Could not load budgets", "OpenRouter Usage");
        this.budgets = [];
        return;
      }
      this.budgets = Array.isArray(result?.budgets) ? result.budgets : [];
    } catch (error) {
      if (seq !== this._tabSeq) return;
      toastFrontendError(error?.message || "Could not load budgets", "OpenRouter Usage");
      this.budgets = [];
    } finally {
      if (seq === this._tabSeq) this.loadingTabs = false;
    }
  },

  async fetchRouting() {
    if (!this.selectedWorkspaceId) return;
    const seq = ++this._tabSeq;
    this.loadingTabs = true;
    try {
      const result = await callJsonApi(API_ROUTING, { workspace_id: this.selectedWorkspaceId });
      if (seq !== this._tabSeq) return;
      if (!result?.ok) {
        toastFrontendError(result?.error || "Could not load routing", "OpenRouter Usage");
        this.routing = null;
        return;
      }
      this.routing = result;
    } catch (error) {
      if (seq !== this._tabSeq) return;
      toastFrontendError(error?.message || "Could not load routing", "OpenRouter Usage");
      this.routing = null;
    } finally {
      if (seq === this._tabSeq) this.loadingTabs = false;
    }
  },

  requestApply() {
    if (!this.routing?.recommended || !this.selectedWorkspaceId) return;
    this.confirmApply = true;
  },

  cancelApply() {
    this.confirmApply = false;
  },

  async applyRouting() {
    this.confirmApply = false;
    const defaults = this.routing?.recommended;
    if (!defaults || !this.selectedWorkspaceId) return;
    this.applying = true;
    try {
      const result = await callJsonApi(API_ROUTING, {
        workspace_id: this.selectedWorkspaceId,
        defaults,
        confirmed: true,
      });
      if (!result?.ok) throw new Error(result?.error || "Routing update failed");
      toastFrontendSuccess("Routing updated", "OpenRouter Usage");
      await this.fetchOverview({ force: true });
      await this.fetchRouting();
    } catch (error) {
      toastFrontendError(error?.message || "Failed to apply routing", "OpenRouter Usage");
    } finally {
      this.applying = false;
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
    this.pollTimer = window.setInterval(() => this.fetchOverview(), Math.max(1, minutes) * 60 * 1000);
  },

  stopPolling() {
    if (this.pollTimer) {
      window.clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
  },

  async onOpen() {
    await this.fetchWorkspaces();
    await this.fetchOverview({ force: true });
    if (this.view === "detailed") this._loadTabData();
    this.startPolling();
  },

  cleanup() {
    this.stopPolling();
  },
});

export default function bootstrapOpenRouterUsage() {
  store.onOpen();
}
