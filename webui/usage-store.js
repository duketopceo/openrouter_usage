import { createStore } from "/js/AlpineStore.js";
import { callJsonApi } from "/js/api.js";
import {
  toastFrontendError,
  toastFrontendSuccess,
} from "/components/notifications/notification-store.js";

const API_OVERVIEW = "/plugins/openrouter_usage/overview";
const API_KEYS = "/plugins/openrouter_usage/keys_list";
const API_REFRESH = "/plugins/openrouter_usage/refresh";
const VIEW_KEY = "openrouter_usage_view";

export const store = createStore("openrouterUsageStore", {
  loading: false,
  overview: null,
  availableKeys: [],
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
    return `${totals.usd_label || "$0"} · last 30d`;
  },

  get widgetLabel() {
    const totals = this.overview?.totals;
    if (this.loading) return "…";
    if (!totals) return "OR";
    return totals.usd_label || "$0";
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

  setView(mode) {
    this.view = mode === "detailed" ? "detailed" : "simple";
    localStorage.setItem(VIEW_KEY, this.view);
  },

  async fetchOverview({ force = false } = {}) {
    this.loading = true;
    try {
      this.overview = await callJsonApi(force ? API_REFRESH : API_OVERVIEW, force ? { force: true } : {});
    } catch (error) {
      toastFrontendError(error?.message || "Failed to load OpenRouter usage", "OpenRouter Usage");
    } finally {
      this.loading = false;
    }
  },

  async fetchKeys() {
    try {
      const result = await callJsonApi(API_KEYS, {});
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

  onOpen() {
    this.fetchOverview().then(() => this.startPolling());
  },

  cleanup() {
    this.stopPolling();
  },

  maxBar(values, field = "usd") {
    const nums = values.map((item) => Number(item[field]) || 0);
    return Math.max(...nums, 0.0001);
  },

  barWidth(value, max) {
    const pct = Math.min(100, (Number(value || 0) / max) * 100);
    return `${pct}%`;
  },
});

export default function bootstrapOpenRouterUsage() {
  store.fetchOverview().then(() => store.startPolling());
}
