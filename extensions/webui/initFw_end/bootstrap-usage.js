import { store } from "/plugins/openrouter_usage/webui/usage-store.js";

export default function bootstrapUsage() {
  store.fetchOverview().then(() => store.startPolling());
}
