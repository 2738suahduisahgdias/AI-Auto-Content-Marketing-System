import hashlib
import hmac
import json
import mimetypes
import re
import secrets
import tempfile
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs, quote

from content_workbench.domain.errors import DomainError
from content_workbench.domain.services import Workbench
from content_workbench.domain.workflow_registry import PLATFORM_PROFILES, workflow_bootstrap
from content_workbench.jobs.store import JobStore
from content_workbench.jobs.worker import Worker
from content_workbench.providers.local import LocalExecutors
from content_workbench.storage.db import expand_schema, loads


class V2Application:
    def __init__(self, db_path, root, legacy_task_creator=None):
        from content_workbench.accounts.api import AccountAPI
        from content_workbench.accounts.executors import AccountExecutors
        from content_workbench.accounts.scheduler import AccountScheduler, configure_account_schedule
        from content_workbench.accounts.service import AccountService
        from content_workbench.agents.api import AgentAPI
        from content_workbench.articles.api import ArticleAPI
        from content_workbench.knowledge.api import KnowledgeAPI
        from content_workbench.knowledge.service import KnowledgeService
        from content_workbench.publishing.api import PublishingAPI
        from content_workbench.publishing.executors import PublishingExecutors
        from content_workbench.publishing.service import PublishingService
        from content_workbench.topics.api import TopicAPI
        from content_workbench.topics.executors import TopicExecutors
        from content_workbench.topics.scheduler import TopicScheduler, configure_schedule
        from content_workbench.topics.service import TopicService
        self.root = Path(root).resolve()
        self.workbench = Workbench(db_path, self.root)
        self.jobs = JobStore(db_path)
        self.topics = TopicService(db_path, self.root)
        self.accounts = AccountService(db_path, self.topics)
        self.publishing = PublishingService(db_path, self.root)
        executors = LocalExecutors(self.workbench).mapping()
        executors.update(TopicExecutors(self.topics).mapping())
        executors.update(AccountExecutors(self.accounts).mapping())
        executors.update(PublishingExecutors(self.publishing).mapping())
        self.worker = Worker(db_path, executors, self.root)
        self.topic_scheduler = TopicScheduler(db_path)
        self.account_scheduler = AccountScheduler(db_path)
        self.topic_api = TopicAPI(self, self.topics, legacy_task_creator)
        self.account_api = AccountAPI(self, self.accounts)
        self.article_api = ArticleAPI(self)
        self.knowledge = KnowledgeService(db_path, self.root)
        self.knowledge_api = KnowledgeAPI(self, self.knowledge)
        self.publishing_api = PublishingAPI(self, self.publishing)
        self.agent_api = AgentAPI(self, db_path)
        self.secret = secrets.token_bytes(32)
        self.sessions = set()
        with self.workbench.conn() as conn:
            expand_schema(conn)
        configure_schedule(db_path, self.topics.settings())
        configure_account_schedule(db_path)

    def start(self):
        self.worker.start()
        self.topic_scheduler.start()
        self.account_scheduler.start()

    def stop(self):
        self.topic_scheduler.stop()
        self.account_scheduler.stop()
        self.worker.stop()

    @staticmethod
    def matches(path):
        return path == "/api/articles" or path.startswith(("/api/v2/", "/api/topics/", "/api/agents/", "/api/accounts/", "/api/publish/", "/api/publishing/", "/api/articles/", "/api/knowledge/"))

    def cookie(self, handler):
        parsed = SimpleCookie(handler.headers.get("Cookie", ""))
        morsel = parsed.get("wb_session")
        return morsel.value if morsel and morsel.value in self.sessions else None

    def session_header(self, handler):
        if self.cookie(handler):
            return None
        value = secrets.token_urlsafe(32)
        self.sessions.add(value)
        return "wb_session={}; HttpOnly; SameSite=Strict; Path=/".format(value)

    def csrf(self, session):
        return hmac.new(self.secret, session.encode("ascii"), hashlib.sha256).hexdigest()

    def authenticate(self, handler, write=False):
        host = handler.headers.get("Host", "")
        if not re.fullmatch(r"(127\.0\.0\.1|localhost):\d{1,5}", host):
            raise DomainError("INVALID_HOST", "仅允许本机工作台地址", 403)
        origin = handler.headers.get("Origin")
        if origin and not re.fullmatch(r"http://(127\.0\.0\.1|localhost):\d{1,5}", origin):
            raise DomainError("INVALID_ORIGIN", "拒绝其他来源的写请求", 403)
        session = self.cookie(handler)
        if not session:
            raise DomainError("SESSION_REQUIRED", "本地会话已失效", 401, action="刷新首页建立新会话后重试")
        if write and not hmac.compare_digest(handler.headers.get("X-CSRF-Token", ""), self.csrf(session)):
            raise DomainError("CSRF_REQUIRED", "请求校验已失效", 403, action="刷新页面后重试")
        return session

    def response(self, handler, data, status=200):
        handler.json_response(data, status)

    def handle(self, handler, method, path, query):
        try:
            self.authenticate(handler, method in ("POST", "PUT", "PATCH", "DELETE"))
            body = handler.read_json() if method in ("POST", "PUT", "PATCH") and not path == "/api/v2/assets" else None
            if path.startswith("/api/topics/"):
                return self.topic_api.handle(handler, method, path, query, body)
            if path.startswith("/api/agents/"):
                return self.agent_api.handle(handler, method, path, body)
            if path.startswith("/api/accounts/") or path.startswith("/api/publish/"):
                return self.account_api.handle(handler, method, path, body)
            if path == "/api/articles" or path.startswith("/api/articles/"):
                return self.article_api.handle(handler, method, path, body)
            if path.startswith("/api/publishing/"):
                return self.publishing_api.handle(handler, method, path, query, body)
            if path.startswith("/api/knowledge/"):
                return self.knowledge_api.handle(handler, method, path, query, body)
            if method == "GET" and path == "/api/v2/bootstrap":
                session = self.cookie(handler)
                with self.workbench.conn(readonly=True) as conn:
                    voices = [dict(row) for row in conn.execute("SELECT id,kind,name,authorized,use_count FROM voice_profiles ORDER BY kind,created_at")]
                    assets = [dict(row) for row in conn.execute("SELECT id,storage_key,mime_type,media_info_json,source_json,rights_status FROM wb_assets ORDER BY created_at DESC")]
                    migration = conn.execute("SELECT report_json FROM wb_migrations ORDER BY applied_at DESC LIMIT 1").fetchone()
                for asset in assets:
                    asset["media_info"] = loads(asset.pop("media_info_json"), {})
                    asset["source"] = loads(asset.pop("source_json"), {})
                return self.response(handler, {"items": self.workbench.list_items(), "workflows": workflow_bootstrap(),
                                               "platform_profiles": PLATFORM_PROFILES, "jobs": self.jobs.list(),
                                               "voices": voices, "assets": assets, "migration": loads(migration[0], {}) if migration else {},
                                               "csrf_token": self.csrf(session), "capabilities": {"browser_collection": "not_implemented",
                                               "cloud_providers": "not_configured", "render_modes": ["remotion"]}})
            if method == "GET" and path == "/api/v2/content-items":
                kind = query.get("type", [None])[0]
                return self.response(handler, {"items": self.workbench.list_items(kind)})
            match = re.fullmatch(r"/api/v2/content-items/([^/]+)", path)
            if method == "GET" and match:
                return self.response(handler, self.workbench.get_item(match.group(1)))
            if method == "POST" and path == "/api/v2/campaigns":
                return self.response(handler, self.workbench.create_campaign(body.get("title"), body.get("brief")), 201)
            if method == "POST" and path == "/api/v2/content-items":
                return self.response(handler, self.workbench.create_item(body.get("content_type"), body.get("platform"), body.get("title"),
                                                                          body.get("brief"), body.get("campaign_id")), 201)
            match = re.fullmatch(r"/api/v2/content-items/([^/]+)/revisions", path)
            if method == "POST" and match:
                item_id = match.group(1)
                revision = self.workbench.save_revision(item_id, body.get("kind"), body.get("payload"), body.get("expected_version"),
                                                        source_audio_asset_id=body.get("source_audio_asset_id"), dependencies=body.get("dependencies"))
                return self.response(handler, {"revision_id": revision, "item": self.workbench.get_item(item_id)}, 201)
            match = re.fullmatch(r"/api/v2/content-items/([^/]+)/asset-revisions", path)
            if method == "POST" and match:
                return self.response(handler, self.workbench.add_asset_revision(match.group(1), body.get("kind"), body.get("asset_id"),
                                                                                 body.get("expected_version"), body.get("source_audio_asset_id"),
                                                                                 body.get("metadata")), 201)
            match = re.fullmatch(r"/api/v2/content-items/([^/]+)/subtitle", path)
            if method == "POST" and match:
                return self.response(handler, self.workbench.edit_subtitle(match.group(1), body.get("revision_id"), body.get("text"),
                                                                            body.get("expected_version")), 201)
            match = re.fullmatch(r"/api/v2/content-items/([^/]+)/actions", path)
            if method == "POST" and match:
                item_id, action = match.group(1), body.get("action")
                if action == "submit_review":
                    return self.response(handler, self.workbench.submit_review(item_id, body.get("expected_version")))
                if action in ("approve", "reject"):
                    return self.response(handler, self.workbench.approve(item_id, body.get("revision_id"), body.get("manifest_hash"),
                                                                          body.get("actor", "local_user"), action, body.get("kind")))
                if action == "activate_revision":
                    revision = self.workbench.activate_revision(item_id, body.get("revision_id"), body.get("expected_version"))
                    return self.response(handler, {"revision_id": revision, "item": self.workbench.get_item(item_id)})
                raise DomainError("UNKNOWN_ACTION", "未知内容操作", 400, "action", "使用页面提供的操作")
            match = re.fullmatch(r"/api/v2/content-items/([^/]+)/generate", path)
            if method == "POST" and match:
                item = self.workbench.get_item(match.group(1))
                operation = body.get("operation")
                allowed = {"article": ("article.outline", "article.draft"), "video": ("video.script", "audio.synthesize", "voice.clone", "audio.transcribe")}
                if operation not in allowed[item["content_type"]]:
                    raise DomainError("INVALID_GENERATION", "该内容类型不支持此生成操作", 422, "operation", "使用页面提供的生成操作")
                input_data = dict(body)
                input_data.pop("operation", None)
                job = self.jobs.enqueue(operation, input_data, item["id"], handler.headers.get("Idempotency-Key"), resource_key="local_asr" if operation == "audio.transcribe" else "voice_conversion" if operation in ("audio.synthesize", "voice.clone") else "cloud_text")
                return self.response(handler, job, 202)
            match = re.fullmatch(r"/api/v2/content-items/([^/]+)/render", path)
            if method == "POST" and match:
                item_id = match.group(1)
                manifest = self.workbench.validate_render(item_id, body.get("mode", "remotion"))
                input_data = {"manifest": manifest, "expected_version": body.get("expected_version"), "mode": "remotion"}
                return self.response(handler, self.jobs.enqueue("video.render", input_data, item_id, handler.headers.get("Idempotency-Key"), resource_key="render"), 202)
            match = re.fullmatch(r"/api/v2/content-items/([^/]+)/export", path)
            if method == "POST" and match:
                item = self.workbench.get_item(match.group(1))
                revision = body.get("revision_id") or item["active_revisions"].get("draft")
                if item["state"] not in ("approved", "exported"):
                    raise DomainError("ARTICLE_NOT_APPROVED", "文章尚未终审", 409, "state", "先批准当前正文")
                job = self.jobs.enqueue("article.export", {"revision_id": revision, "expected_version": body.get("expected_version")},
                                        item["id"], handler.headers.get("Idempotency-Key"), resource_key="export")
                return self.response(handler, job, 202)
            if method == "POST" and path == "/api/v2/assets":
                filename = query.get("filename", ["asset.bin"])[0]
                if "/" in filename or "\\" in filename or "\x00" in filename:
                    raise DomainError("INVALID_FILENAME", "文件名不能包含路径", 422, "filename", "只提供文件名")
                length = int(handler.headers.get("Content-Length", "0"))
                if length <= 0 or length > 500 * 1024 * 1024:
                    raise DomainError("INVALID_UPLOAD_SIZE", "文件为空或超过 500MB", 413, "file", "选择非空且小于 500MB 的文件")
                data = handler.rfile.read(length)
                if len(data) != length:
                    raise DomainError("INCOMPLETE_UPLOAD", "文件上传不完整", 400)
                with tempfile.TemporaryDirectory(prefix="v2-upload-") as directory:
                    path_value = Path(directory) / filename
                    path_value.write_bytes(data)
                    asset_id = self.workbench.register_asset(path_value, {"filename": filename, "purpose": query.get("purpose", ["research"])[0]},
                                                              query.get("rights", ["research_only"])[0])
                with self.workbench.conn(readonly=True) as conn:
                    asset = dict(conn.execute("SELECT * FROM wb_assets WHERE id=?", (asset_id,)).fetchone())
                return self.response(handler, asset, 201)
            if method == "GET" and path == "/api/v2/jobs":
                return self.response(handler, {"jobs": self.jobs.list()})
            match = re.fullmatch(r"/api/v2/jobs/([^/]+)", path)
            if method == "GET" and match:
                return self.response(handler, self.jobs.get(match.group(1)))
            match = re.fullmatch(r"/api/v2/jobs/([^/]+)/(cancel|retry)", path)
            if method == "POST" and match:
                result = self.jobs.cancel(match.group(1)) if match.group(2) == "cancel" else self.jobs.retry(match.group(1))
                return self.response(handler, result, 202)
            if method == "GET" and path == "/api/v2/events":
                return self.response(handler, {"events": self.jobs.events(int(query.get("after", [0])[0]), query.get("aggregate_id", [None])[0])})
            if method == "POST" and path == "/api/v2/publications":
                return self.response(handler, self.workbench.record_publication(body.get("item_id"), body.get("revision_id"), body.get("url"),
                                                                                 body.get("published_at"), body.get("actor", "local_user")), 201)
            match = re.fullmatch(r"/api/v2/publications/([^/]+)/metrics", path)
            if method == "POST" and match:
                metric = self.workbench.add_metric(match.group(1), body.get("window_key"), body.get("metric_key"), body.get("value"),
                                                   body.get("missing_reason"), body.get("source", "manual"), body.get("observed_at"))
                return self.response(handler, {"id": metric}, 201)
            match = re.fullmatch(r"/api/v2/assets/([^/]+)/content", path)
            if method == "GET" and match:
                return self.serve_asset(handler, match.group(1), "download" in query)
            raise DomainError("API_NOT_FOUND", "v2 接口不存在", 404)
        except DomainError as error:
            self.response(handler, error.as_dict(), error.status)
        except Exception as error:
            print("v2 error:", repr(error), flush=True)
            failure = DomainError("INTERNAL_ERROR", "服务未完成此操作", 500, action="查看 data/server.log 中的 v2 error 和 trace 信息")
            self.response(handler, failure.as_dict(), failure.status)
        return True

    def serve_asset(self, handler, asset_id, download=False):
        with self.workbench.conn(readonly=True) as conn:
            row = conn.execute("SELECT * FROM wb_assets WHERE id=?", (asset_id,)).fetchone()
        if not row:
            raise DomainError("ASSET_NOT_FOUND", "资产不存在", 404)
        path = (self.root / row["storage_key"]).resolve()
        if self.root not in path.parents or not path.is_file():
            raise DomainError("ASSET_FILE_MISSING", "资产文件不存在", 404, action="恢复文件或重新上传，不要把缺失当删除")
        size = path.stat().st_size
        start, end = 0, size - 1
        status = 200
        range_header = handler.headers.get("Range")
        if range_header:
            match = re.fullmatch(r"bytes=(\d+)-(\d*)", range_header)
            if not match:
                raise DomainError("INVALID_RANGE", "媒体范围无效", 416)
            start = int(match.group(1))
            end = min(int(match.group(2)) if match.group(2) else end, end)
            if start > end or start >= size:
                raise DomainError("INVALID_RANGE", "媒体范围无效", 416)
            status = 206
        content_type = row["mime_type"] if row["mime_type"] and row["mime_type"].isascii() else None
        content_type = content_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        handler.send_response(status)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Accept-Ranges", "bytes")
        handler.send_header("Content-Length", str(end - start + 1))
        if download:
            handler.send_header("Content-Disposition", "attachment; filename*=UTF-8''{}".format(quote(path.name)))
        if status == 206:
            handler.send_header("Content-Range", "bytes {}-{}/{}".format(start, end, size))
        handler.end_headers()
        with path.open("rb") as source:
            source.seek(start)
            remaining = end - start + 1
            while remaining:
                chunk = source.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                handler.wfile.write(chunk)
                remaining -= len(chunk)
