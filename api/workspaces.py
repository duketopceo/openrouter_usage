from helpers.api import ApiHandler, Input, Output, Request
from usr.plugins.openrouter_usage.helpers.openrouter_client import fetch_workspaces


class Workspaces(ApiHandler):
    async def process(self, input: Input, request: Request) -> Output:
        try:
            context = self.use_context(str(input.get("context") or ""), create_if_not_exists=False)
            agent = context.agent0 if context else None
        except Exception:
            agent = None
        return fetch_workspaces(agent)
