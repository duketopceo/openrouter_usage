from helpers.api import ApiHandler, Input, Output, Request
from usr.plugins.openrouter_usage.helpers.openrouter_client import fetch_overview, invalidate_cache


class Refresh(ApiHandler):
    async def process(self, input: Input, request: Request) -> Output:
        workspace_id = input.get("workspace_id") or None
        invalidate_cache(workspace_id)
        try:
            context = self.use_context(str(input.get("context") or ""), create_if_not_exists=False)
            agent = context.agent0 if context else None
        except Exception:
            agent = None
        return fetch_overview(agent, force=True, workspace_id=workspace_id)
