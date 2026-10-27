import re

from content_workbench.domain.errors import DomainError


class ReviewAPI:
    def __init__(self, app, service):
        self.app = app
        self.service = service

    def handle(self, handler, method, path, query, body):
        body = body or {}
        if method == "GET" and path == "/api/review/bootstrap":
            data = self.service.bootstrap(query.get("batch_id", [None])[0])
            data["csrf_token"] = self.app.csrf(self.app.cookie(handler))
            return self.app.response(handler, data)
        if method == "POST" and path == "/api/review/batches":
            if body.get("upload"):
                batch = self.service.create_upload_batch(body.get("rules") or {})
            else:
                batch = self.service.create_batch(body.get("folder"), body.get("rules") or {})
            return self.app.response(handler, batch, 201)
        if method == "POST" and path == "/api/review/uploads":
            filename = query.get("filename", [""])[0]
            batch_id = query.get("batch_id", [""])[0]
            length = int(handler.headers.get("Content-Length", "0"))
            if length <= 0 or length > 2 * 1024 ** 3:
                raise DomainError("REVIEW_FILE_TOO_LARGE", "视频为空或超过 2GB", 413, "file", "选择不超过 2GB 的视频")
            data = handler.rfile.read(length)
            if len(data) != length:
                raise DomainError("REVIEW_UPLOAD_INCOMPLETE", "视频上传不完整", 400, "file", "重新上传")
            return self.app.response(handler, self.service.add_upload(batch_id, filename, data), 201)
        match = re.fullmatch(r"/api/review/batches/([^/]+)/start", path)
        if method == "POST" and match:
            return self.app.response(handler, self.service.start(match.group(1)), 202)
        match = re.fullmatch(r"/api/review/items/([^/]+)/decide", path)
        if method == "POST" and match:
            output = self.service.decide(match.group(1), body.get("decision"))
            return self.app.response(handler, {"output_path": output, "decision": body.get("decision")})
        match = re.fullmatch(r"/api/review/items/([^/]+)/repair", path)
        if method == "POST" and match:
            return self.app.response(handler, self.service.repair(match.group(1)), 202)
        match = re.fullmatch(r"/api/review/items/([^/]+)/publish-source", path)
        if method == "GET" and match:
            return self.app.response(handler, self.service.source_for_publish(match.group(1)))
        raise DomainError("REVIEW_API_NOT_FOUND", "审核接口不存在", 404)
