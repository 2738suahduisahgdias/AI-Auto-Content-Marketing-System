import re

from content_workbench.domain.errors import DomainError


class PublishingAPI:
    def __init__(self, app, service):
        self.app = app
        self.service = service

    def handle(self, handler, method, path, query, body):
        body = body or {}
        if method == "GET" and path == "/api/publishing/bootstrap":
            data = self.service.bootstrap(query.get("kind", [None])[0], query.get("source_id", [None])[0])
            data["csrf_token"] = self.app.csrf(self.app.cookie(handler))
            return self.app.response(handler, data)
        if method == "POST" and path == "/api/publishing/batches":
            batch = self.service.create_batch(body.get("content_kind"), body.get("source_id"), body.get("targets"))
            return self.app.response(handler, batch, 201)
        match = re.fullmatch(r"/api/publishing/batches/([^/]+)", path)
        if method == "GET" and match:
            return self.app.response(handler, self.service.get_batch(match.group(1)))
        match = re.fullmatch(r"/api/publishing/batches/([^/]+)/prepare", path)
        if method == "POST" and match:
            jobs = self.service.prepare(match.group(1), body.get("platforms"), handler.headers.get("Idempotency-Key"))
            return self.app.response(handler, {"jobs": jobs}, 202)
        match = re.fullmatch(r"/api/publishing/batches/([^/]+)/confirm", path)
        if method == "POST" and match:
            jobs = self.service.confirm(match.group(1), body.get("source_hash"), body.get("platforms"), "local_user",
                                        handler.headers.get("Idempotency-Key"))
            return self.app.response(handler, {"jobs": jobs, "final_confirmation": "recorded"}, 202)
        match = re.fullmatch(r"/api/publishing/targets/([^/]+)/retry", path)
        if method == "POST" and match:
            job = self.service.retry(match.group(1), handler.headers.get("Idempotency-Key"))
            return self.app.response(handler, job, 202)
        match = re.fullmatch(r"/api/publishing/connections/([^/]+)/login", path)
        if method == "POST" and match:
            from .schemas import PLATFORM_NAMES
            platform = match.group(1)
            if platform not in PLATFORM_NAMES:
                raise DomainError("PUBLISH_PLATFORM_INVALID", "发布平台无效", 422, "platform", "使用页面提供的平台登录入口")
            return self.app.response(handler, self.service.jobs.enqueue("publish.login", {"platform": platform}, "publishing:" + platform,
                                                                        handler.headers.get("Idempotency-Key"), max_attempts=1, resource_key="browser"), 202)
        raise DomainError("PUBLISHING_API_NOT_FOUND", "发布中心接口不存在", 404)
