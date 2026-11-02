import re

from content_workbench.accounts.collection_ontology import collection_ontology
from content_workbench.accounts.setup import setup_status
from content_workbench.domain.errors import DomainError


class AccountAPI:
    def __init__(self, app, service):
        self.app = app
        self.service = service
        self.jobs = app.jobs

    def handle(self, handler, method, path, body):
        if method == "POST" and path in ("/api/accounts/sync", "/api/accounts/recommend"):
            raise DomainError("ACCOUNT_ANALYTICS_PAUSED", "账号经营数据采集已停用；选题采集和发布账号登录不受影响", 410)

        if path == "/api/accounts/browser/connection":
            from content_workbench.accounts.browser_connection import status, control
            if method == "GET":
                return self.app.response(handler, status())
            if method == "POST":
                return self.app.response(handler, control((body or {}).get("action"), self.service.db_path))

        if method == "GET" and path == "/api/accounts/setup":
            data = setup_status(self.service.db_path)
            from content_workbench.readiness import runtime_readiness
            data["readiness"] = runtime_readiness(self.app)
            data["activation"] = self.app.license.status()["status"]
            data["wechat_client"] = self.app.topic_api.wechat_client.status()
            data["csrf_token"] = self.app.csrf(self.app.cookie(handler))
            return self.app.response(handler, data)
        if method == "GET" and path == "/api/accounts/collection-knowledge":
            return self.app.response(handler, collection_ontology())
        match = re.fullmatch(r"/api/accounts/collection-knowledge/([^/]+)/([^/]+)", path)
        if method == "GET" and match:
            return self.app.response(handler, collection_ontology(platform=match.group(1), category=match.group(2)))
        match = re.fullmatch(r"/api/accounts/collection-knowledge/([^/]+)", path)
        if method == "GET" and match:
            return self.app.response(handler, collection_ontology(platform=match.group(1)))
        if method == "GET" and path == "/api/accounts/bootstrap":
            data = self.service.bootstrap()
            data["csrf_token"] = self.app.csrf(self.app.cookie(handler))
            return self.app.response(handler, data)
        if method == "GET" and path == "/api/accounts/leads":
            return self.app.response(handler, {"items": self.service.leads.list()})
        if method == "POST" and path == "/api/accounts/leads":
            return self.app.response(handler, self.service.leads.create(body), 201)
        if method == "POST" and path == "/api/accounts/leads/delete":
            return self.app.response(handler, self.service.leads.delete((body or {}).get("ids")))
        if method == "POST" and re.fullmatch(r"/api/accounts/leads/([^/]+)", path):
            lead_id = re.fullmatch(r"/api/accounts/leads/([^/]+)", path).group(1)
            return self.app.response(handler, self.service.leads.update(lead_id, body))
        if method == "POST" and path == "/api/accounts/sync":
            return self.app.response(handler, self.jobs.enqueue("accounts.sync", {}, "accounts", resource_key="browser"), 202)
        if method == "POST" and path == "/api/accounts/recommend":
            return self.app.response(handler, self.jobs.enqueue("accounts.recommend", {}, "accounts", resource_key="cloud_text"), 202)
        if method == "POST" and path == "/api/accounts/browser/open":
            platform = (body or {}).get("platform")
            if platform not in ("xiaohongshu", "douyin_publish", "wechat_channels", "wechat_official_account"):
                raise DomainError("ACCOUNT_BROWSER_PLATFORM_INVALID", "登录窗口仅支持抖音、小红书、视频号或公众号", 422, "platform", "使用页面提供的登录入口")
            return self.app.response(handler, self.jobs.enqueue("accounts.login", {"platform": platform}, "accounts", resource_key="browser"), 202)
        if method == "POST" and path == "/api/publish/douyin/preview":
            data = body or {}
            return self.app.response(handler, self.jobs.enqueue("publish.douyin", data, "publish", resource_key="browser"), 202)
        if method == "GET" and re.fullmatch(r"/api/accounts/jobs/([^/]+)", path):
            return self.app.response(handler, self.jobs.get(re.fullmatch(r"/api/accounts/jobs/([^/]+)", path).group(1)))
        raise DomainError("ACCOUNT_API_NOT_FOUND", "账号接口不存在", 404)
