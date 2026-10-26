import re

from content_workbench.domain.errors import DomainError
from content_workbench.storage.db import connect, dumps


class TopicAPI:
    def __init__(self, app, service, legacy_task_creator):
        self.app = app
        self.service = service
        self.jobs = app.jobs
        self.legacy_task_creator = legacy_task_creator

    def handle(self, handler, method, path, query, body):
        if method == "GET" and path == "/api/topics/bootstrap":
            data = self.service.bootstrap()
            data["csrf_token"] = self.app.csrf(self.app.cookie(handler))
            return self.app.response(handler, data)
        if method == "POST" and path == "/api/topics/settings":
            return self.app.response(handler, self.service.save_settings(body or {}))
        if method == "POST" and path == "/api/topics/browser/open":
            return self.app.response(handler, self.jobs.enqueue("topics.login", {}, "source_douyin_main", resource_key="browser"), 202)
        if method == "POST" and path == "/api/topics/sync":
            return self.app.response(handler, self.jobs.enqueue("topics.sync", {}, "source_douyin_main", resource_key="browser"), 202)
        if method == "POST" and path == "/api/topics/industry":
            return self.app.response(handler, self.jobs.enqueue("topics.industry", {"agent": "industry"}, "industry", resource_key="topics"), 202)
        if method == "POST" and path == "/api/topics/recommend":
            agent = (body or {}).get("agent", "douyin")
            return self.app.response(handler, self.jobs.enqueue("topics.recommend", {"agent": agent}, agent, resource_key="cloud_text"), 202)
        match = re.fullmatch(r"/api/topics/items/([^/]+)", path)
        if method == "GET" and match:
            return self.app.response(handler, self.service.get_item(match.group(1)))
        match = re.fullmatch(r"/api/topics/items/([^/]+)/analyze", path)
        if method == "POST" and match:
            return self.app.response(handler, self.jobs.enqueue("research.analyze", {}, match.group(1), resource_key="download"), 202)
        match = re.fullmatch(r"/api/topics/items/([^/]+)/create-task", path)
        if method == "POST" and match:
            item = self.service.get_item(match.group(1))
            payload = {"title": item["title"][:200], "pillar": "enterprise_ai", "audience": "business_owners",
                       "angle": "从真实热点或收藏结构切入，不复制原文；先核对来源与事实", "pain_point": ""}
            task = self.legacy_task_creator(payload)
            source = {"type": "topic_research", "research_item_id": item["id"], "url": item["url"],
                      "source_key": item["source_key"], "snapshot_at": item["last_seen_at"]}
            with connect(self.service.db_path) as conn:
                conn.execute("UPDATE tasks SET source_json=? WHERE content_id=?", (dumps(source), task["content_id"]))
            task["source"] = source
            return self.app.response(handler, task, 201)
        raise DomainError("TOPIC_API_NOT_FOUND", "选题接口不存在", 404)
