import re

from content_workbench.domain.errors import DomainError
from content_workbench.storage.db import connect, dumps
from content_workbench.topics.wechat_inbox import WechatInboxService
from content_workbench.topics.wechat_client import WechatClient


class TopicAPI:
    def __init__(self, app, service, legacy_task_creator):
        self.app = app
        self.service = service
        self.jobs = app.jobs
        self.legacy_task_creator = legacy_task_creator
        self.wechat_inbox = WechatInboxService(service.db_path, service)
        self.wechat_client = WechatClient(service.root, self.wechat_inbox)

    def handle(self, handler, method, path, query, body):
        if path == "/api/topics/wechat/client" and method == "GET":
            return self.app.response(handler, self.wechat_client.status())
        if path in ("/api/topics/wechat/client/login", "/api/topics/wechat/client/poll", "/api/topics/wechat/client/disconnect") and method == "POST":
            try:
                result = self.wechat_client.disconnect() if path.endswith("/disconnect") else self.wechat_client.begin_login() if path.endswith('/login') else self.wechat_client.poll_login((body or {}).get('code',''))
                return self.app.response(handler, result)
            except Exception:
                raise DomainError("WECHAT_CONNECT_FAILED", "微信连接请求失败，请检查网络或重新获取二维码", 502, "wechat", "重试扫码连接")
        if method == "GET" and path == "/api/topics/bootstrap":
            data = self.service.bootstrap()
            data["wechat_messages"] = self.wechat_inbox.list()
            data["wechat_connection"] = self.wechat_inbox.connection()
            data["csrf_token"] = self.app.csrf(self.app.cookie(handler))
            return self.app.response(handler, data)
        if method == "GET" and path == "/api/topics/wechat/messages":
            return self.app.response(handler, {"items": self.wechat_inbox.list()})
        if method == "GET" and path == "/api/topics/wechat/connection":
            return self.app.response(handler, self.wechat_inbox.connection())
        match = re.fullmatch(r"/api/topics/wechat/snapshots/([A-Za-z0-9_-]+)/cover", path)
        if method == "GET" and match:
            cover = self.service.root / "data/publishing-evidence" / (match.group(1) + "-link-cover.png")
            if not cover.is_file():
                raise DomainError("COVER_NOT_FOUND", "视频截帧封面尚未生成", 404, "cover", "先完成一次动态链接解析")
            content = cover.read_bytes()
            handler.send_response(200)
            handler.send_header("Content-Type", "image/png")
            handler.send_header("Content-Length", str(len(content)))
            handler.send_header("Cache-Control", "private, max-age=86400")
            handler.end_headers()
            handler.wfile.write(content)
            return True
        if method == "POST" and path == "/api/topics/wechat/messages":
            message, created = self.wechat_inbox.ingest(body or {})
            if created and message.get("original_url"):
                self.wechat_inbox.update_snapshot(message["id"], "queued")
                self.jobs.enqueue("research.snapshot", {}, message["id"], resource_key="snapshot")
                message = self.wechat_inbox.get(message["id"])
            return self.app.response(handler, message, 201 if created else 200)
        match = re.fullmatch(r"/api/topics/wechat/messages/([^/]+)/snapshot", path)
        if method == "POST" and match:
            message = self.wechat_inbox.get(match.group(1))
            if not message.get("original_url"):
                raise DomainError("SNAPSHOT_URL_MISSING", "请先补充原始链接再生成快照", 422, "original_url", "编辑消息并填写公开链接")
            self.wechat_inbox.update_snapshot(message["id"], "queued")
            self.jobs.enqueue("research.snapshot", {}, message["id"], resource_key="snapshot")
            return self.app.response(handler, self.wechat_inbox.get(message["id"]), 202)
        match = re.fullmatch(r"/api/topics/wechat/messages/([^/]+)", path)
        if method == "PUT" and match:
            return self.app.response(handler, self.wechat_inbox.update(match.group(1), body or {}))
        if method == "POST" and path == "/api/topics/settings":
            return self.app.response(handler, self.service.save_settings(body or {}))
        if method == "POST" and path == "/api/topics/browser/open":
            return self.app.response(handler, self.jobs.enqueue("topics.login", {}, "source_douyin_main", resource_key="browser"), 202)
        if method == "POST" and path == "/api/topics/sync":
            return self.app.response(handler, self.jobs.enqueue_active_once("topics.sync", {}, "source_douyin_main", resource_key="browser"), 202)
        if method == "POST" and path == "/api/topics/xiaohongshu/browser/open":
            return self.app.response(handler, self.jobs.enqueue("topics.xhs_login", {}, "source_xiaohongshu_main", resource_key="browser"), 202)
        if method == "POST" and path == "/api/topics/xiaohongshu/sync":
            return self.app.response(handler, self.jobs.enqueue_active_once("topics.xhs_sync", {}, "source_xiaohongshu_main", resource_key="browser"), 202)
        if method == "POST" and path == "/api/topics/industry":
            return self.app.response(handler, self.jobs.enqueue("topics.industry", {"agent": "industry"}, "industry", resource_key="topics"), 202)
        if method == "POST" and path == "/api/topics/recommend":
            agent = (body or {}).get("agent", "douyin")
            return self.app.response(handler, self.jobs.enqueue_active_once("topics.recommend", {"agent": agent}, agent, resource_key="cloud_text"), 202)
        match = re.fullmatch(r"/api/topics/items/([^/]+)/cover/retry", path)
        if method == "POST" and match:
            item = self.service.get_item(match.group(1))
            return self.app.response(handler, self.jobs.enqueue_active_once("topics.cover", {}, item["id"], resource_key="browser"), 202)
        match = re.fullmatch(r"/api/topics/items/([^/]+)/cover", path)
        if method == "GET" and match:
            cover = self.service.root / "covers" / "topic-research" / (match.group(1) + ".jpg")
            if not cover.is_file():
                raise DomainError("COVER_NOT_FOUND", "封面尚未缓存", 404, "cover", "先同步该作品的封面元数据")
            body = cover.read_bytes()
            handler.send_response(200)
            handler.send_header("Content-Type", "image/jpeg")
            handler.send_header("Content-Length", str(len(body)))
            handler.send_header("Cache-Control", "private, max-age=86400")
            handler.end_headers()
            handler.wfile.write(body)
            return True
        match = re.fullmatch(r"/api/topics/items/([^/]+)", path)
        if method == "GET" and match:
            return self.app.response(handler, self.service.get_item(match.group(1)))
        match = re.fullmatch(r"/api/topics/items/([^/]+)/analyze", path)
        if method == "POST" and match:
            return self.app.response(handler, self.jobs.enqueue("research.analyze", {}, match.group(1), resource_key="download"), 202)
        match = re.fullmatch(r"/api/topics/items/([^/]+)/archive", path)
        if method == "POST" and match:
            item_id = match.group(1)
            self.service.set_archived(item_id, bool((body or {}).get("archived", True)))
            return self.app.response(handler, self.service.get_item(item_id))
        match = re.fullmatch(r"/api/topics/items/([^/]+)/create-task", path)
        if method == "POST" and match:
            item = self.service.get_item(match.group(1))
            if item.get("archived"):
                raise DomainError("TOPIC_ARCHIVED", "已归档选题不能创建生产任务", 409, "id", "先在已归档列表恢复该选题")
            payload = {"title": item["title"][:200], "pillar": "enterprise_ai", "audience": "business_owners",
                       "angle": "从真实热点或收藏结构切入，不复制原文；先核对来源与事实", "pain_point": ""}
            task = self.legacy_task_creator(payload)
            source = {"type": "topic_research", "research_item_id": item["id"], "url": item["url"],
                      "source_key": item["source_key"], "snapshot_at": item["last_seen_at"]}
            with connect(self.service.db_path) as conn:
                conn.execute("UPDATE tasks SET source_json=? WHERE content_id=?", (dumps(source), task["content_id"]))
            task["source"] = source
            return self.app.response(handler, task, 201)
        match = re.fullmatch(r"/api/topics/candidates/([^/]+)/create-task", path)
        if method == "POST" and match:
            candidate_id = match.group(1)
            candidate = self.service.get_candidate(candidate_id)
            if candidate.get("status") == "converted":
                raise DomainError("TOPIC_CANDIDATE_CONVERTED", "这条推荐已经转为选题", 409, "id", "从推荐卡片打开已创建的任务，不要重复创建")
            payload = {"title": candidate["title"][:200], "pillar": candidate.get("pillar") or "enterprise_ai",
                       "audience": candidate.get("audience") or "business_owners", "angle": candidate.get("angle") or "",
                       "pain_point": candidate.get("reason") or ""}
            task = self.legacy_task_creator(payload)
            source = {"type": "topic_candidate", "candidate_id": candidate_id, "agent": candidate.get("agent"),
                      "evidence_ids": candidate.get("evidence_ids") or [], "recommended_at": candidate.get("created_at")}
            with connect(self.service.db_path) as conn:
                conn.execute("UPDATE tasks SET source_json=? WHERE content_id=?", (dumps(source), task["content_id"]))
            self.service.mark_candidate_converted(candidate_id, task["content_id"])
            task["source"] = source
            return self.app.response(handler, task, 201)
        raise DomainError("TOPIC_API_NOT_FOUND", "选题接口不存在", 404)
