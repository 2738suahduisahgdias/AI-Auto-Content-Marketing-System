import re

from content_workbench.agents.registry import AGENTS, all_agent_configs, save_agent_config
from content_workbench.domain.errors import DomainError


class AgentAPI:
    def __init__(self, app, db_path):
        self.app = app
        self.db_path = db_path

    def handle(self, handler, method, path, body):
        if method == "GET" and path == "/api/agents/config":
            return self.app.response(handler, {"agents": AGENTS, "configs": all_agent_configs(self.db_path),
                                               "csrf_token": self.app.csrf(self.app.cookie(handler))})
        match = re.fullmatch(r"/api/agents/config/([a-z_]+)", path)
        if method == "PUT" and match:
            return self.app.response(handler, save_agent_config(self.db_path, match.group(1), body or {}))
        raise DomainError("AGENT_API_NOT_FOUND", "Agent 配置接口不存在", 404)
