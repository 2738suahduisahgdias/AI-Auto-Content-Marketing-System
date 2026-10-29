from pathlib import Path

from content_workbench.domain.errors import DomainError
from content_workbench.domain.services import Workbench
from content_workbench.jobs.store import JobStore
from content_workbench.storage.db import PROJECT_ROOT, connect, dumps, immediate, loads, new_id, payload_hash, utcnow
from .schemas import ARTICLE_PLATFORMS, PLATFORM_NAMES, VIDEO_PLATFORMS, prepare_supported, validate_payload


class PublishingService:
    def __init__(self, db_path, root):
        self.db_path = str(db_path)
        self.root = Path(root).resolve()
        self.workbench = Workbench(db_path, self.root)
        self.jobs = JobStore(db_path)
        self.ensure_schema()

    def conn(self, readonly=False):
        return connect(self.db_path, readonly=readonly)

    def ensure_schema(self):
        with self.conn() as conn:
            conn.executescript((PROJECT_ROOT / "migrations/003_publishing.sql").read_text())

    def source(self, kind, source_id):
        if kind == "article":
            item = self.workbench.get_item(source_id)
            if item["content_type"] != "article":
                raise DomainError("PUBLISH_SOURCE_KIND_MISMATCH", "该来源不是文章任务", 422, "source_id", "从文章任务选择已批准正文")
            revision_id = item["active_revisions"].get("draft")
            if not revision_id or item["state"] not in ("approved", "exported"):
                raise DomainError("PUBLISH_ARTICLE_NOT_APPROVED", "文章尚未完成人工审批", 409, "source_id", "先批准当前正文再创建发布批次", source_id)
            revision = self.workbench.get_revision(revision_id)
            return {"kind": kind, "source_id": source_id, "source_hash": item["manifest"]["hash"],
                    "title": item["campaign"]["title"], "body": revision["payload"].get("text", ""), "revision_id": revision_id}
        if kind != "video":
            raise DomainError("PUBLISH_KIND_INVALID", "发布类型仅支持文章或视频", 422, "content_kind", "选择文章或视频")
        if source_id.startswith("reviewitem_"):
            from content_workbench.review.service import ReviewService
            return ReviewService(self.db_path, self.root).source_for_publish(source_id)
        with self.conn(readonly=True) as conn:
            task = conn.execute("SELECT * FROM tasks WHERE content_id=?", (source_id,)).fetchone()
            file = conn.execute("SELECT * FROM files WHERE content_id=? AND kind='video' ORDER BY id DESC LIMIT 1", (source_id,)).fetchone()
        if not task or task["state"] != "approved" or not file:
            raise DomainError("PUBLISH_VIDEO_NOT_APPROVED", "视频任务没有已人工批准的成片", 409, "source_id", "先完成视频质检和人工最终审核", source_id)
        relative = file["relative_path"].replace("\\", "/")
        path = (self.root / relative).resolve()
        if self.root not in path.parents or path.suffix.lower() != ".mp4" or not path.is_file():
            raise DomainError("PUBLISH_VIDEO_MISSING", "已批准 MP4 不存在或路径无效", 409, "source_id", "重新上传并批准 MP4", source_id)
        scripts = loads(task["scripts_json"], {})
        return {"kind": kind, "source_id": source_id, "source_hash": payload_hash([task["updated_at"], relative, path.stat().st_size]),
                "title": task["title"], "description": scripts.get("douyin") or scripts.get("master") or task["title"],
                "revision_id": file["id"], "video_path": relative, "absolute_video_path": str(path)}

    def resolve_assets(self, payload):
        result = dict(payload)
        asset_id = result.get("cover_asset_id")
        if not asset_id:
            return result
        with self.conn(readonly=True) as conn:
            asset = conn.execute("SELECT * FROM wb_assets WHERE id=?", (asset_id,)).fetchone()
        if not asset or not str(asset["mime_type"]).startswith("image/"):
            raise DomainError("PUBLISH_COVER_INVALID", "封面不是有效图片资产", 422, "cover_asset_id", "上传 PNG、JPG 或 WebP 封面")
        path = (self.root / asset["storage_key"]).resolve()
        if self.root not in path.parents or not path.is_file():
            raise DomainError("PUBLISH_COVER_MISSING", "封面文件不存在", 409, "cover_asset_id", "重新上传封面")
        result["cover_path"] = str(path)
        return result

    def generate_fields(self, kind, source_id, platforms, prompt="", idempotency_key=None):
        self.source(kind, source_id)
        allowed = ARTICLE_PLATFORMS if kind == "article" else VIDEO_PLATFORMS if kind == "video" else ()
        if not isinstance(platforms, list) or not platforms:
            raise DomainError("PUBLISH_TARGETS_REQUIRED", "至少选择一个生成字段的平台", 422, "platforms", "勾选需要发布 Agent 填写的平台")
        if len(platforms) != len(set(platforms)) or any(platform not in allowed for platform in platforms):
            raise DomainError("PUBLISH_CONTENT_PLATFORM_MISMATCH", "生成字段的平台与内容类型不匹配或存在重复", 422, "platforms", "文章选择公众号或小红书；视频选择抖音、小红书或视频号")
        prompt = str(prompt or "").strip()
        if len(prompt) > 2000:
            raise DomainError("PUBLISH_PROMPT_TOO_LONG", "补充要求不能超过 2000 字", 422, "prompt", "精简补充要求后重试")
        return self.jobs.enqueue("publish.fields", {"content_kind": kind, "source_id": source_id, "platforms": platforms, "prompt": prompt},
                                 kind + ":" + source_id, idempotency_key, max_attempts=2, resource_key="cloud_text")

    def create_batch(self, kind, source_id, targets):
        source = self.source(kind, source_id)
        if not isinstance(targets, list) or not targets:
            raise DomainError("PUBLISH_TARGETS_REQUIRED", "至少选择一个发布平台", 422, "targets", "勾选目标平台")
        seen = set()
        for target in targets:
            platform = target.get("platform")
            if platform in seen:
                raise DomainError("PUBLISH_DUPLICATE_TARGET", "同一平台不能重复添加", 422, "platform", "每个平台只保留一个版本")
            seen.add(platform)
            payload = validate_payload(kind, platform, target.get("payload"))
            self.resolve_assets(payload)
        with self.conn(readonly=True) as conn:
            published = conn.execute("""SELECT t.platform FROM publish_targets t JOIN publish_batches b ON b.id=t.batch_id
                WHERE b.content_kind=? AND b.source_id=? AND t.status='published'""", (kind, source_id)).fetchall()
        duplicates = seen & {row[0] for row in published}
        if duplicates:
            raise DomainError("PUBLISH_ALREADY_RECORDED", "相同内容已有平台发布记录：" + "、".join(duplicates), 409, "targets", "先核对真实发布结果；不要重复发布")
        with self.conn(readonly=True) as conn:
            row = conn.execute("""SELECT id FROM publish_batches WHERE content_kind=? AND source_id=? AND source_hash=?
                ORDER BY created_at DESC LIMIT 1""", (kind, source_id, source["source_hash"])).fetchone()
        batch_id = row[0] if row else new_id("pubbatch")
        timestamp = utcnow()
        with self.conn() as conn, immediate(conn):
            if row:
                conn.execute("UPDATE publish_batches SET status='draft',confirmed_by=NULL,confirmed_at=NULL,updated_at=? WHERE id=?", (timestamp, batch_id))
            else:
                conn.execute("INSERT INTO publish_batches VALUES (?,?,?,?, 'draft',NULL,NULL,?,?)",
                             (batch_id, kind, source_id, source["source_hash"], timestamp, timestamp))
            for target in targets:
                platform = target["platform"]
                payload = validate_payload(kind, platform, target["payload"])
                encoded = dumps(payload)
                existing = conn.execute("SELECT * FROM publish_targets WHERE batch_id=? AND platform=?", (batch_id, platform)).fetchone()
                if existing and existing["status"] == "published":
                    raise DomainError("PUBLISH_ALREADY_RECORDED", PLATFORM_NAMES[platform] + "已有发布记录", 409, "platform", "不要重复发布")
                if existing and existing["payload_json"] == encoded and existing["status"] in ("ready", "published"):
                    continue
                target_id = existing["id"] if existing else new_id("pubtarget")
                conn.execute("""INSERT INTO publish_targets(id,batch_id,platform,payload_json,status,preview_json,error_json,job_id,external_url,created_at,updated_at)
                    VALUES (?,?,?,?,'draft','{}',NULL,NULL,NULL,?,?)
                    ON CONFLICT(batch_id,platform) DO UPDATE SET payload_json=excluded.payload_json,status='draft',preview_json='{}',
                    error_json=NULL,job_id=NULL,external_url=NULL,updated_at=excluded.updated_at""",
                    (target_id, batch_id, platform, encoded, timestamp, timestamp))
        self.update_batch_status(batch_id)
        return self.get_batch(batch_id)

    def get_batch(self, batch_id):
        with self.conn(readonly=True) as conn:
            row = conn.execute("SELECT * FROM publish_batches WHERE id=?", (batch_id,)).fetchone()
            if not row:
                raise DomainError("PUBLISH_BATCH_NOT_FOUND", "发布批次不存在", 404, "batch_id", "重新创建发布批次", batch_id)
            batch = dict(row)
            targets = [dict(value) for value in conn.execute("SELECT * FROM publish_targets WHERE batch_id=? ORDER BY created_at,platform", (batch_id,))]
        for target in targets:
            target["payload"] = loads(target.pop("payload_json"), {})
            target["preview"] = loads(target.pop("preview_json"), {})
            target["error"] = loads(target.pop("error_json"), None)
            target["platform_name"] = PLATFORM_NAMES[target["platform"]]
        batch["targets"] = targets
        return batch

    def retrospective(self):
        suggestions = {
            "douyin": "用内容管理中的标题和发布时间核验发布；短信验证完成后仍需核对作品列表。",
            "xiaohongshu": "长文控制篇幅与图片数量，公众号长文不要直接复用到小红书。",
            "wechat_channels": "保留人工选文件断点；上传后核对时长、短标题与描述再公开。",
            "wechat_official_account": "公众号保留完整深度文章，并为管理员微信验证预留确认步骤。",
        }
        result = {platform: {"platform_name": PLATFORM_NAMES[platform], "items": [],
                             "suggestion": suggestions[platform], "suggestion_kind": "流程建议，不是平台效果结论",
                             "data_boundary": "发布记录已核验；曝光、互动及分时间窗口指标未关联到本条内容，暂不能判断传播效果。"}
                for platform in PLATFORM_NAMES}
        with self.conn(readonly=True) as conn:
            rows = conn.execute("""SELECT t.id AS target_id,t.platform,t.payload_json,t.preview_json,t.external_url,t.updated_at,
                                       b.id AS batch_id,b.content_kind,b.source_id
                                FROM publish_targets t JOIN publish_batches b ON b.id=t.batch_id
                                WHERE t.status='published' ORDER BY t.updated_at DESC""").fetchall()
        for row in rows:
            payload = loads(row["payload_json"], {})
            preview = loads(row["preview_json"], {})
            result[row["platform"]]["items"].append({
                "target_id": row["target_id"], "batch_id": row["batch_id"], "source_id": row["source_id"],
                "content_kind": row["content_kind"], "title": payload.get("title") or row["source_id"],
                "verified_at": preview.get("reconciled_at") or row["updated_at"],
                "external_url": row["external_url"], "evidence": preview.get("published_evidence"),
            })
        return {"platforms": result, "total_published": len(rows),
                "note": "仅包含已核验发布记录；提升建议来自工作流证据，不代表内容效果已得到验证。"}

    def bootstrap(self, kind=None, source_id=None):
        batch = None
        field_jobs = []
        if kind and source_id:
            with self.conn(readonly=True) as conn:
                row = conn.execute("SELECT id FROM publish_batches WHERE content_kind=? AND source_id=? ORDER BY created_at DESC LIMIT 1", (kind, source_id)).fetchone()
            if row:
                batch = self.get_batch(row[0])
            aggregate_id = kind + ":" + source_id
            field_jobs = [job for job in self.jobs.list(200) if job["kind"] == "publish.fields" and job["aggregate_id"] == aggregate_id][:10]
        return {"batch": batch, "field_jobs": field_jobs, "article_platforms": ARTICLE_PLATFORMS, "video_platforms": VIDEO_PLATFORMS,
                "platform_names": PLATFORM_NAMES, "prepare_supported": {name: prepare_supported(name) for name in PLATFORM_NAMES}}

    def target(self, target_id):
        with self.conn(readonly=True) as conn:
            row = conn.execute("SELECT batch_id FROM publish_targets WHERE id=?", (target_id,)).fetchone()
        if not row:
            raise DomainError("PUBLISH_TARGET_NOT_FOUND", "平台发布目标不存在", 404, "target_id", "刷新发布批次", target_id)
        batch = self.get_batch(row[0])
        target = next(value for value in batch["targets"] if value["id"] == target_id)
        return batch, target

    def assert_current(self, batch):
        current = self.source(batch["content_kind"], batch["source_id"])
        if current["source_hash"] != batch["source_hash"]:
            raise DomainError("PUBLISH_SOURCE_CHANGED", "内容或审批版本已变化，旧预览不能发布", 409, "source_id", "重新创建批次并生成预览", batch["source_id"])
        return current

    def prepare(self, batch_id, platforms, idempotency_key=None):
        batch = self.get_batch(batch_id)
        self.assert_current(batch)
        selected = [target for target in batch["targets"] if not platforms or target["platform"] in platforms]
        if not selected:
            raise DomainError("PUBLISH_TARGETS_REQUIRED", "没有可预览的平台", 422, "platforms", "选择批次中的平台")
        jobs = []
        for target in selected:
            if target["status"] == "published":
                continue
            if not prepare_supported(target["platform"]):
                raise DomainError("PUBLISH_CONNECTOR_PENDING", PLATFORM_NAMES[target["platform"]] + "尚未完成发布字段验证", 409, "platform", "先登录并完成连接器验收；不要执行发布")
            job = self.jobs.enqueue("publish.prepare", {"target_id": target["id"]}, target["id"], idempotency_key,
                                    scope="prepare:" + target["id"], max_attempts=1, resource_key="browser")
            with self.conn() as conn, immediate(conn):
                conn.execute("UPDATE publish_targets SET status='preparing',error_json=NULL,job_id=?,updated_at=? WHERE id=?",
                             (job["id"], utcnow(), target["id"]))
            jobs.append(job)
        self.update_batch_status(batch_id)
        return jobs

    def confirm(self, batch_id, source_hash, platforms=None, actor="local_user", idempotency_key=None):
        batch = self.get_batch(batch_id)
        if not source_hash or source_hash != batch["source_hash"]:
            raise DomainError("PUBLISH_CONFIRMATION_STALE", "确认的内容版本已变化", 409, "source_hash", "刷新并重新确认当前版本")
        self.assert_current(batch)
        selected = [target for target in batch["targets"] if target["status"] == "ready" and (not platforms or target["platform"] in platforms)]
        if not selected:
            raise DomainError("PUBLISH_PREVIEW_REQUIRED", "没有已完成预览并等待确认的平台", 409, "targets", "先成功生成平台预览")
        timestamp = utcnow()
        with self.conn() as conn, immediate(conn):
            conn.execute("UPDATE publish_batches SET confirmed_by=?,confirmed_at=?,updated_at=? WHERE id=?", (actor, timestamp, timestamp, batch_id))
        jobs = []
        for target in selected:
            job = self.jobs.enqueue("publish.execute", {"target_id": target["id"]}, target["id"], idempotency_key,
                                    scope="execute:" + target["id"] + ":" + timestamp, max_attempts=1, resource_key="browser")
            with self.conn() as conn, immediate(conn):
                conn.execute("UPDATE publish_targets SET status='publishing',error_json=NULL,job_id=?,updated_at=? WHERE id=?",
                             (job["id"], utcnow(), target["id"]))
            jobs.append(job)
        self.update_batch_status(batch_id)
        return jobs

    def retry(self, target_id, idempotency_key=None):
        batch, target = self.target(target_id)
        if target["status"] not in ("failed", "draft"):
            raise DomainError("PUBLISH_RETRY_BLOCKED", "待人工核对或执行中的平台不能直接重试", 409, "status", "先核对平台后台，或重新生成预览")
        self.assert_current(batch)
        job = self.jobs.enqueue("publish.prepare", {"target_id": target_id}, target_id, idempotency_key,
                                scope="prepare:" + target_id, max_attempts=1, resource_key="browser")
        with self.conn() as conn, immediate(conn):
            conn.execute("UPDATE publish_targets SET status='preparing',error_json=NULL,job_id=?,updated_at=? WHERE id=?",
                         (job["id"], utcnow(), target_id))
        self.update_batch_status(batch["id"])
        return job

    def verify(self, target_id, idempotency_key=None):
        batch, target = self.target(target_id)
        if target["status"] != "unknown_remote":
            raise DomainError("PUBLISH_RECONCILE_NOT_REQUIRED", "只有待人工核对的目标需要后台结果核验", 409, "status", "先完成预览或核对当前状态")
        self.assert_current(batch)
        return self.jobs.enqueue("publish.verify", {"target_id": target_id}, target_id, idempotency_key,
                                 scope="verify:" + target_id, max_attempts=1, resource_key="browser")

    def reconcile(self, target_id, evidence, external_url=None):
        batch, target = self.target(target_id)
        if target["status"] != "unknown_remote":
            raise DomainError("PUBLISH_RECONCILE_NOT_REQUIRED", "只有待人工核对的目标可以确认发布结果", 409, "status", "先完成预览或核对当前状态")
        evidence = str(evidence or "").strip()
        if len(evidence) < 10:
            raise DomainError("PUBLISH_RECONCILE_EVIDENCE_REQUIRED", "请提供平台后台的实际发布证据", 422, "evidence", "填写后台时间、内容或真实链接，不要只写已发布")
        preview = dict(target.get("preview") or {})
        preview.update({"published_evidence": evidence, "reconciled_by": "local_user", "reconciled_at": utcnow()})
        self.set_target_result(target_id, "published", preview, external_url=external_url)
        return self.target(target_id)[1]

    def set_target_result(self, target_id, status, preview=None, error=None, job_id=None, external_url=None):
        with self.conn() as conn, immediate(conn):
            conn.execute("""UPDATE publish_targets SET status=?,preview_json=?,error_json=?,job_id=COALESCE(?,job_id),
                external_url=COALESCE(?,external_url),updated_at=? WHERE id=?""",
                (status, dumps(preview or {}), dumps(error) if error else None, job_id, external_url, utcnow(), target_id))
        with self.conn(readonly=True) as conn:
            row = conn.execute("SELECT batch_id FROM publish_targets WHERE id=?", (target_id,)).fetchone()
        if row:
            self.update_batch_status(row[0])

    def update_batch_status(self, batch_id):
        batch = self.get_batch(batch_id)
        statuses = [target["status"] for target in batch["targets"]]
        if any(value == "publishing" or value == "preparing" for value in statuses):
            status = "publishing"
        elif any(value == "unknown_remote" for value in statuses):
            status = "requires_action"
        elif statuses and all(value == "published" for value in statuses):
            status = "published"
        elif any(value == "published" for value in statuses):
            status = "partially_succeeded"
        elif any(value == "failed" for value in statuses):
            status = "failed"
        elif statuses and all(value == "ready" for value in statuses):
            status = "ready"
        else:
            status = "draft"
        with self.conn() as conn, immediate(conn):
            conn.execute("UPDATE publish_batches SET status=?,updated_at=? WHERE id=?", (status, utcnow(), batch_id))
        return status
