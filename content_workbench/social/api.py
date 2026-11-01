import re

from content_workbench.domain.errors import DomainError
from content_workbench.social.catalog import catalog, get_operation


class SocialAPI:
    def __init__(self, app, service):
        self.app = app
        self.service = service
        self.jobs = app.jobs

    def handle(self, handler, method, path, query, body):
        if method == "GET" and path == "/api/social/bootstrap":
            data = self.service.bootstrap()
            data["csrf_token"] = self.app.csrf(self.app.cookie(handler))
            return self.app.response(handler, data)
        if method == "GET" and path == "/api/social/catalog":
            return self.app.response(handler, catalog())
        if method == "GET" and path == "/api/social/providers":
            return self.app.response(handler, self.service.providers.status())
        if method == "GET" and path == "/api/social/runs":
            return self.app.response(handler, {"items": self.service.list_runs()})
        match = re.fullmatch(r"/api/social/runs/([A-Za-z0-9_-]+)", path)
        if method == "GET" and match:
            return self.app.response(handler, self.service.get_run(match.group(1)))
        if method == "POST" and path == "/api/social/execute":
            data = body or {}
            operation_id = str(data.get("operation_id") or "")
            operation = get_operation(operation_id)
            input_data = data.get("input") or {}
            if not isinstance(input_data, dict):
                raise DomainError("SOCIAL_INPUT_INVALID", "社媒能力输入必须是 JSON 对象", 422, "input", "按能力目录提交参数")
            provider = str(data.get("provider") or "kimi_cli")
            run = self.service.create_run(operation_id, input_data, provider)
            resource = "local_asr" if operation["executor"] == "local_transcript" else "download" if operation["executor"] == "local_download" else "browser"
            job = self.jobs.enqueue("social.execute", {}, run["id"], handler.headers.get("Idempotency-Key"), resource_key=resource)
            return self.app.response(handler, {"run": run, "job": job}, 202)
        raise DomainError("SOCIAL_API_NOT_FOUND", "社媒数据接口不存在", 404)
