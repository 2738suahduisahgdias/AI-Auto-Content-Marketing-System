import re

from content_workbench.domain.errors import DomainError


class AccountAPI:
    def __init__(self, app, service):
        self.app = app
        self.service = service
        self.jobs = app.jobs

    def handle(self, handler, method, path, body):
        if method == "GET" and path == "/api/accounts/bootstrap":
            data = self.service.bootstrap()
            data["csrf_token"] = self.app.csrf(self.app.cookie(handler))
            return self.app.response(handler, data)
        if method == "POST" and path == "/api/accounts/sync":
            return self.app.response(handler, self.jobs.enqueue("accounts.sync", {}, "accounts", resource_key="browser"), 202)
        if method == "POST" and path == "/api/accounts/recommend":
            return self.app.response(handler, self.jobs.enqueue("accounts.recommend", {}, "accounts", resource_key="cloud_text"), 202)
        if method == "POST" and path == "/api/publish/douyin/preview":
            data = body or {}
            return self.app.response(handler, self.jobs.enqueue("publish.douyin", data, "publish", resource_key="browser"), 202)
        if method == "GET" and re.fullmatch(r"/api/accounts/jobs/([^/]+)", path):
            return self.app.response(handler, self.jobs.get(re.fullmatch(r"/api/accounts/jobs/([^/]+)", path).group(1)))
        raise DomainError("ACCOUNT_API_NOT_FOUND", "账号接口不存在", 404)
