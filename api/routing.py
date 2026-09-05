from helpers.api import ApiHandler, Input, Output, Request
from usr.plugins.openrouter_usage.helpers.openrouter_client import apply_routing, fetch_routing


class Routing(ApiHandler):
    async def process(self, input: Input, request: Request) -> Output:
        workspace_id = input.get("workspace_id") or None
        try:
            context = self.use_context(str(input.get("context") or ""), create_if_not_exists=False)
            agent = context.agent0 if context else None
        except Exception:
            agent = None

        # callJsonApi uses POST for all plugin API calls, so we distinguish by payload.
        wants_apply = bool(input.get("confirmed")) or input.get("defaults") is not None
        if wants_apply:
            if not input.get("confirmed"):
                return {"ok": False, "error": "confirmed: true is required to apply routing changes"}
            return apply_routing(
                agent,
                workspace_id=workspace_id,
                defaults=input.get("defaults") or {},
                confirmed=bool(input.get("confirmed")),
            )

        return fetch_routing(agent, workspace_id=workspace_id)
