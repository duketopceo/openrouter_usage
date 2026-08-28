from helpers.extension import Extension
from helpers.secrets import get_secrets_manager


class OpenRouterFeatureCard(Extension):
    async def execute(self, banners: list | None = None, frontend_context: dict | None = None, **kwargs):
        if banners is None:
            return
        key = get_secrets_manager().load_secrets().get("OPENROUTER_MANAGEMENT_KEY", "").strip()
        if key:
            return
        banners.append(
            {
                "id": "openrouter_usage-setup",
                "type": "feature",
                "priority": 41,
                "title": "OpenRouter Usage",
                "description": "Track org spend, per-key usage, and top models with a lightweight sidebar widget.",
                "thumbnail": "/plugins/openrouter_usage/docs/logo.webp",
                "icon": "monitoring",
                "cta_text": "Add management key",
                "cta_action": "open-plugin-config:openrouter_usage",
                "dismissible": True,
            }
        )
