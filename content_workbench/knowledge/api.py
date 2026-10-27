from content_workbench.domain.errors import DomainError


class KnowledgeAPI:
    def __init__(self, app, service):
        self.app = app
        self.service = service

    def handle(self, handler, method, path, query, body):
        if method == "GET" and path == "/api/knowledge/bootstrap":
            data = self.service.bootstrap(query.get("q", [""])[0], query.get("type", [""])[0])
            data["csrf_token"] = self.app.csrf(self.app.cookie(handler))
            return self.app.response(handler, data)
        if method == "POST" and path == "/api/knowledge/backfill":
            return self.app.response(handler, self.service.backfill())
        if method == "POST" and path == "/api/knowledge/relations":
            data = body or {}
            relation = self.service.add_relation(data.get("source_type"), data.get("source_id"), data.get("predicate"),
                                                 data.get("target_type"), data.get("target_id"), data.get("evidence"))
            return self.app.response(handler, {"id": relation}, 201)
        raise DomainError("KNOWLEDGE_API_NOT_FOUND", "知识库接口不存在", 404)
