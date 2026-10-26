import html
import json
import mimetypes
import os
import re
import shutil
import tempfile
import uuid
from pathlib import Path

from content_workbench.media.probe import probe
from content_workbench.storage.db import ROOT, connect, dumps, file_hash, immediate, loads, new_id, payload_hash, utcnow
from .errors import DomainError
from .workflow_registry import DOWNSTREAM, PLATFORM_PROFILES, REVISION_KINDS


class Workbench:
    def __init__(self, db_path=None, root=ROOT):
        self.db_path = str(db_path) if db_path else None
        self.root = Path(root).resolve()

    def conn(self, readonly=False):
        return connect(self.db_path, readonly=readonly)

    def create_campaign(self, title, brief=None):
        title = str(title or "").strip()
        if not title or len(title) > 200:
            raise DomainError("INVALID_TITLE", "标题需为 1～200 字", 422, "title", "填写一个具体内容主题")
        campaign_id = new_id("cmp")
        timestamp = utcnow()
        with self.conn() as conn, immediate(conn):
            conn.execute("INSERT INTO wb_campaigns(id,title,brief_json,version,created_at,updated_at) VALUES (?,?,?,1,?,?)",
                         (campaign_id, title, dumps(brief or {}), timestamp, timestamp))
            self.event(conn, "campaign", campaign_id, "campaign.created", {"title": title})
        return self.get_campaign(campaign_id)

    def create_item(self, content_type, platform, title, brief=None, campaign_id=None):
        profile = PLATFORM_PROFILES.get(platform)
        if not profile or profile["content_type"] != content_type:
            raise DomainError("PLATFORM_TYPE_MISMATCH", "该平台与内容类型不匹配或尚未开放", 422, "platform", "文章选择公众号；视频选择抖音")
        if not campaign_id:
            campaign = self.create_campaign(title, brief)
            campaign_id = campaign["id"]
        item_id = new_id("item")
        timestamp = utcnow()
        with self.conn() as conn, immediate(conn):
            if not conn.execute("SELECT 1 FROM wb_campaigns WHERE id=?", (campaign_id,)).fetchone():
                raise DomainError("CAMPAIGN_NOT_FOUND", "Campaign 不存在", 404)
            conn.execute("""INSERT INTO wb_content_items
                (id,campaign_id,content_type,platform,state,version,active_revisions_json,legacy_task_id,created_at,updated_at)
                VALUES (?,?,?,?,'brief_ready',1,'{}',NULL,?,?)""",
                (item_id, campaign_id, content_type, platform, timestamp, timestamp))
            self.event(conn, "content_item", item_id, "content.created", {"content_type": content_type, "platform": platform})
        text = str((brief or {}).get("text", "")).strip() if isinstance(brief, dict) else str(brief or "").strip()
        if text:
            self.save_revision(item_id, "brief", {"text": text, "title": title}, 1)
        return self.get_item(item_id)

    def get_campaign(self, campaign_id):
        with self.conn(readonly=True) as conn:
            row = conn.execute("SELECT * FROM wb_campaigns WHERE id=?", (campaign_id,)).fetchone()
            if not row:
                raise DomainError("CAMPAIGN_NOT_FOUND", "Campaign 不存在", 404)
            result = dict(row)
            result["brief"] = loads(result.pop("brief_json"), {})
            result["items"] = [item["id"] for item in conn.execute("SELECT id FROM wb_content_items WHERE campaign_id=?", (campaign_id,))]
            return result

    def list_items(self, content_type=None):
        query = "SELECT id FROM wb_content_items"
        values = []
        if content_type:
            query += " WHERE content_type=?"
            values.append(content_type)
        query += " ORDER BY updated_at DESC,id DESC"
        with self.conn(readonly=True) as conn:
            ids = [row[0] for row in conn.execute(query, values)]
        return [self.get_item(item_id) for item_id in ids]

    def get_item(self, item_id):
        with self.conn(readonly=True) as conn:
            row = conn.execute("SELECT * FROM wb_content_items WHERE id=?", (item_id,)).fetchone()
            if not row:
                raise DomainError("ITEM_NOT_FOUND", "内容实例不存在", 404, item=item_id)
            item = dict(row)
            item["active_revisions"] = loads(item.pop("active_revisions_json"), {})
            item["revisions"] = []
            for revision in conn.execute("SELECT * FROM wb_revisions WHERE item_id=? ORDER BY created_at,revision_no", (item_id,)):
                value = self.revision_dict(revision)
                value["dependencies"] = [dict(dep) for dep in conn.execute("SELECT * FROM wb_revision_dependencies WHERE revision_id=?", (value["id"],))]
                item["revisions"].append(value)
            item["assets"] = [dict(asset) for asset in conn.execute("""SELECT a.*,l.purpose FROM wb_assets a
                JOIN wb_asset_links l ON l.asset_id=a.id WHERE l.owner_type='content_item' AND l.owner_id=? ORDER BY a.created_at DESC""", (item_id,))]
            item["approvals"] = [dict(value) for value in conn.execute("SELECT * FROM wb_approvals WHERE item_id=? ORDER BY created_at DESC", (item_id,))]
            item["publications"] = [dict(value) for value in conn.execute("SELECT * FROM wb_publications WHERE item_id=? ORDER BY created_at DESC", (item_id,))]
            item["campaign"] = dict(conn.execute("SELECT id,title,brief_json FROM wb_campaigns WHERE id=?", (item["campaign_id"],)).fetchone())
            item["campaign"]["brief"] = loads(item["campaign"].pop("brief_json"), {})
        item["manifest"] = self.manifest(item_id)
        return item

    @staticmethod
    def revision_dict(row):
        value = dict(row)
        value["payload"] = loads(value.pop("payload_json"), {})
        return value

    def get_revision(self, revision_id):
        with self.conn(readonly=True) as conn:
            row = conn.execute("SELECT * FROM wb_revisions WHERE id=?", (revision_id,)).fetchone()
            if not row:
                raise DomainError("REVISION_NOT_FOUND", "版本不存在", 404, item=revision_id)
            return self.revision_dict(row)

    def manifest(self, item_id):
        with self.conn(readonly=True) as conn:
            item = conn.execute("SELECT id,content_type,platform,active_revisions_json FROM wb_content_items WHERE id=?", (item_id,)).fetchone()
            if not item:
                raise DomainError("ITEM_NOT_FOUND", "内容实例不存在", 404, item=item_id)
            active = loads(item["active_revisions_json"], {})
            revisions = {}
            for kind, revision_id in active.items():
                row = conn.execute("SELECT id,kind,payload_hash,payload_json,source_audio_asset_id FROM wb_revisions WHERE id=? AND item_id=?", (revision_id, item_id)).fetchone()
                if row:
                    revisions[kind] = {"id": row["id"], "hash": row["payload_hash"],
                                       "asset_id": loads(row["payload_json"], {}).get("asset_id"),
                                       "source_audio_asset_id": row["source_audio_asset_id"]}
            manifest = {"item_id": item_id, "content_type": item["content_type"], "platform": item["platform"], "revisions": revisions}
            if "audio" in revisions:
                manifest["audio_asset_id"] = revisions["audio"].get("asset_id")
            if "subtitle" in revisions:
                manifest["subtitle_asset_id"] = revisions["subtitle"].get("asset_id")
                manifest["subtitle_source_audio_asset_id"] = revisions["subtitle"].get("source_audio_asset_id")
            manifest["hash"] = payload_hash(manifest)
            return manifest

    def save_revision(self, item_id, kind, payload, expected_version=None, parent_id=None,
                      source_audio_asset_id=None, dependencies=None, activate=True, created_by="user"):
        if not isinstance(payload, dict):
            raise DomainError("INVALID_REVISION", "版本内容必须是对象", 422, "payload", "提交结构化文本或资产引用")
        with self.conn() as conn, immediate(conn):
            item = conn.execute("SELECT * FROM wb_content_items WHERE id=?", (item_id,)).fetchone()
            if not item:
                raise DomainError("ITEM_NOT_FOUND", "内容实例不存在", 404, item=item_id)
            if kind not in REVISION_KINDS[item["content_type"]]:
                raise DomainError("INVALID_REVISION_KIND", "该内容类型不支持此版本", 422, "kind", "选择页面提供的版本类型")
            if expected_version is not None and item["version"] != expected_version:
                raise DomainError("VERSION_CONFLICT", "内容已被其他窗口修改", 409, "expected_version",
                                  "刷新后比较版本，再基于最新版本保存；不要覆盖他人的修改", item_id)
            active = loads(item["active_revisions_json"], {})
            parent = parent_id or active.get(kind)
            number = conn.execute("SELECT COALESCE(MAX(revision_no),0)+1 FROM wb_revisions WHERE item_id=? AND kind=?", (item_id, kind)).fetchone()[0]
            revision_id = new_id("rev")
            timestamp = utcnow()
            conn.execute("""INSERT INTO wb_revisions
                (id,item_id,kind,revision_no,parent_id,payload_json,payload_hash,validity,source_audio_asset_id,created_by,created_at)
                VALUES (?,?,?,?,?,?,?,'valid',?,?,?)""",
                (revision_id, item_id, kind, number, parent, dumps(payload), payload_hash(payload), source_audio_asset_id, created_by, timestamp))
            for dependency in dependencies or []:
                revision_dep = dependency.get("revision_id")
                asset_dep = dependency.get("asset_id")
                if bool(revision_dep) == bool(asset_dep):
                    raise DomainError("INVALID_DEPENDENCY", "依赖必须且只能引用一个版本或资产", 422)
                conn.execute("INSERT INTO wb_revision_dependencies VALUES (?,?,?)", (revision_id, revision_dep, asset_dep))
            if payload.get("asset_id") and not any(dep.get("asset_id") == payload["asset_id"] for dep in dependencies or []):
                conn.execute("INSERT INTO wb_revision_dependencies VALUES (?,NULL,?)", (revision_id, payload["asset_id"]))
            if source_audio_asset_id:
                conn.execute("INSERT INTO wb_revision_dependencies VALUES (?,NULL,?)", (revision_id, source_audio_asset_id))
            if activate:
                invalidated = DOWNSTREAM.get(kind, set()) & set(active)
                for old_kind in invalidated:
                    old_id = active.pop(old_kind)
                    conn.execute("UPDATE wb_revisions SET validity='stale' WHERE id=?", (old_id,))
                    conn.execute("UPDATE wb_approvals SET revoked_at=? WHERE revision_id=? AND revoked_at IS NULL", (timestamp, old_id))
                if invalidated or kind in ("brief", "outline", "draft", "script", "audio", "subtitle", "storyboard", "render"):
                    conn.execute("""UPDATE wb_approvals SET revoked_at=? WHERE item_id=? AND revoked_at IS NULL
                        AND json_extract(check_results_json,'$.kind') IN ('final','article')""", (timestamp, item_id))
                active[kind] = revision_id
            state = self.recompute_state(conn, item_id, item["content_type"], active)
            conn.execute("UPDATE wb_content_items SET active_revisions_json=?,state=?,version=version+1,updated_at=? WHERE id=?",
                         (dumps(active), state, timestamp, item_id))
            self.event(conn, "content_item", item_id, "revision.created", {"revision_id": revision_id, "kind": kind, "active": activate})
            return revision_id

    def recompute_state(self, conn, item_id, content_type, active):
        row = conn.execute("SELECT state FROM wb_content_items WHERE id=?", (item_id,)).fetchone()
        if row["state"] == "needs_review" and not active:
            return "needs_review"
        if content_type == "article":
            if "export" in active:
                return "exported"
            if "draft" in active:
                approval = conn.execute("""SELECT 1 FROM wb_approvals WHERE item_id=? AND revision_id=? AND decision='approve'
                    AND revoked_at IS NULL AND json_extract(check_results_json,'$.kind')='article'""", (item_id, active["draft"])).fetchone()
                return "approved" if approval else "draft"
            return "outline_draft" if "outline" in active else "brief_ready"
        if "render" in active:
            approval = conn.execute("""SELECT 1 FROM wb_approvals WHERE item_id=? AND decision='approve' AND revoked_at IS NULL
                AND json_extract(check_results_json,'$.kind')='final'""", (item_id,)).fetchone()
            return "approved" if approval else "rendered"
        if "storyboard" in active:
            return "storyboard_ready"
        if "subtitle" in active:
            return "subtitles_ready"
        if "audio" in active:
            return "audio_ready"
        if "script" in active:
            approval = conn.execute("""SELECT 1 FROM wb_approvals WHERE item_id=? AND revision_id=? AND decision='approve'
                AND revoked_at IS NULL AND json_extract(check_results_json,'$.kind')='script'""", (item_id, active["script"])).fetchone()
            return "script_approved" if approval else "script_draft"
        return "brief_ready"

    def submit_review(self, item_id, expected_version):
        item = self.get_item(item_id)
        kind = "draft" if item["content_type"] == "article" else "script"
        if kind not in item["active_revisions"]:
            raise DomainError("MISSING_REVISION", "缺少可审核版本", 409, kind, "先保存并选择当前版本")
        with self.conn() as conn, immediate(conn):
            current = conn.execute("SELECT version FROM wb_content_items WHERE id=?", (item_id,)).fetchone()[0]
            if current != expected_version:
                raise DomainError("VERSION_CONFLICT", "提交前内容已变化", 409, "expected_version", "刷新后重试", item_id)
            state = "in_review" if item["content_type"] == "article" else "script_draft"
            conn.execute("UPDATE wb_content_items SET state=?,version=version+1,updated_at=? WHERE id=?", (state, utcnow(), item_id))
            self.event(conn, "content_item", item_id, "review.submitted", {"revision_id": item["active_revisions"][kind]})
        return self.get_item(item_id)

    def activate_revision(self, item_id, revision_id, expected_version):
        revision = self.get_revision(revision_id)
        if revision["item_id"] != item_id:
            raise DomainError("REVISION_ITEM_MISMATCH", "版本不属于当前内容", 409, "revision_id", "从当前内容的版本列表选择")
        dependencies = [{"asset_id": revision["payload"]["asset_id"]}] if revision["payload"].get("asset_id") else None
        new_revision = self.save_revision(item_id, revision["kind"], revision["payload"], expected_version,
                                          source_audio_asset_id=revision["source_audio_asset_id"], dependencies=dependencies,
                                          created_by="user_activate")
        return new_revision

    def approve(self, item_id, revision_id, manifest_hash, actor="local_user", decision="approve", kind=None):
        if not actor.strip():
            raise DomainError("ACTOR_REQUIRED", "审批人不能为空", 422, "actor", "填写本地审批人名称")
        item = self.get_item(item_id)
        kind = kind or ("article" if item["content_type"] == "article" else "final")
        active_kind = "draft" if kind == "article" else "script" if kind == "script" else "render"
        if item["active_revisions"].get(active_kind) != revision_id:
            raise DomainError("STALE_APPROVAL", "只能审批当前活动版本", 409, "revision_id", "刷新后选择当前版本", item_id)
        if item["manifest"]["hash"] != manifest_hash:
            raise DomainError("MANIFEST_CHANGED", "审批输入已经变化", 409, "manifest_hash", "重新检查当前输入后再审批", item_id)
        if decision not in ("approve", "reject"):
            raise DomainError("INVALID_DECISION", "审批决定无效", 422)
        approval_id = new_id("apr")
        timestamp = utcnow()
        with self.conn() as conn, immediate(conn):
            current = conn.execute("SELECT active_revisions_json FROM wb_content_items WHERE id=?", (item_id,)).fetchone()[0]
            if loads(current, {}).get(active_kind) != revision_id:
                raise DomainError("STALE_APPROVAL", "审批期间活动版本已改变", 409, item=item_id)
            checks = {"kind": kind, "automatic": False, "blockers": []}
            conn.execute("INSERT INTO wb_approvals VALUES (?,?,?,?,?,?,?,?,NULL)",
                         (approval_id, item_id, revision_id, manifest_hash, decision, dumps(checks), actor, timestamp))
            if decision == "approve":
                state = "approved" if kind in ("article", "final") else "script_approved"
            else:
                state = "draft" if kind == "article" else "script_draft" if kind == "script" else "rendered"
            conn.execute("UPDATE wb_content_items SET state=?,version=version+1,updated_at=? WHERE id=?", (state, timestamp, item_id))
            self.event(conn, "content_item", item_id, "review.decided", {"approval_id": approval_id, "decision": decision, "kind": kind})
        return self.get_item(item_id)

    def register_asset(self, source_path, source=None, rights_status="research_only", privacy_class="local_only", move=False):
        path = Path(source_path).resolve()
        if not path.is_file():
            raise DomainError("ASSET_NOT_FOUND", "素材文件不存在", 404, "file", "重新选择有效文件")
        media = probe(path)
        digest = file_hash(path)
        size = path.stat().st_size
        suffix = path.suffix.lower()[:12]
        storage_key = "assets/v2/{}/{}{}".format(digest[:2], digest, suffix)
        target = (self.root / storage_key).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            temporary = target.with_name("." + uuid.uuid4().hex + ".pending")
            shutil.copyfile(path, temporary)
            os.replace(temporary, target)
        if move:
            path.unlink(missing_ok=True)
        with self.conn() as conn, immediate(conn):
            row = conn.execute("SELECT id FROM wb_assets WHERE sha256=? AND byte_size=?", (digest, size)).fetchone()
            if row:
                return row[0]
            asset_id = new_id("asset")
            conn.execute("""INSERT INTO wb_assets
                (id,sha256,byte_size,storage_key,mime_type,media_info_json,source_json,privacy_class,rights_status,retention_class,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,'referenced',?)""",
                (asset_id, digest, size, storage_key, media["mime_type"], dumps(media), dumps(source or {}), privacy_class, rights_status, utcnow()))
            return asset_id

    def add_asset_revision(self, item_id, kind, asset_id, expected_version, source_audio_asset_id=None, metadata=None):
        if kind not in ("audio", "subtitle", "render"):
            raise DomainError("INVALID_ASSET_REVISION", "资产版本类型无效", 422, "kind", "选择音频、字幕或成片")
        item = self.get_item(item_id)
        if item["content_type"] != "video":
            raise DomainError("NOT_VIDEO", "文章不需要音频、字幕或视频资产", 409, item=item_id)
        with self.conn(readonly=True) as conn:
            asset = conn.execute("SELECT * FROM wb_assets WHERE id=?", (asset_id,)).fetchone()
            if not asset:
                raise DomainError("ASSET_NOT_FOUND", "资产不存在", 404, item=asset_id)
        payload = {"asset_id": asset_id, "metadata": metadata or {}}
        revision_id = self.save_revision(item_id, kind, payload, expected_version, source_audio_asset_id=source_audio_asset_id,
                                         dependencies=[{"asset_id": asset_id}], created_by="user")
        with self.conn() as conn, immediate(conn):
            link_id = new_id("assetlink")
            conn.execute("INSERT OR IGNORE INTO wb_asset_links VALUES (?,?, 'content_item',?,?,NULL,?)",
                         (link_id, asset_id, item_id, kind, utcnow()))
            self.event(conn, "content_item", item_id, "asset.linked", {"asset_id": asset_id, "kind": kind, "revision_id": revision_id})
        return self.get_item(item_id)

    def edit_subtitle(self, item_id, revision_id, text, expected_version):
        current = self.get_revision(revision_id)
        item = self.get_item(item_id)
        if current["kind"] != "subtitle" or current["item_id"] != item_id or item["active_revisions"].get("subtitle") != revision_id:
            raise DomainError("STALE_SUBTITLE", "只能编辑当前活动字幕", 409, "revision_id", "先选择要编辑的活动字幕版本", item_id)
        if not str(text or "").strip():
            raise DomainError("EMPTY_SUBTITLE", "字幕不能为空", 422, "text", "保留有效 SRT 时间轴与文本")
        with tempfile.TemporaryDirectory(prefix="v2-subtitle-edit-") as directory:
            path = Path(directory) / "edited.srt"
            path.write_text(text, encoding="utf-8")
            metadata = dict(current["payload"].get("metadata") or {})
            metadata.update({"edited": True, "edited_from_revision_id": revision_id})
            asset_id = self.register_asset(path, {"kind": "subtitle_edit", "source_audio_asset_id": current["source_audio_asset_id"],
                                                  "previous_revision_id": revision_id}, "owned")
        self.add_asset_revision(item_id, "subtitle", asset_id, expected_version, current["source_audio_asset_id"], metadata)
        return self.get_item(item_id)

    def validate_render(self, item_id, mode="remotion"):
        item = self.get_item(item_id)
        if item["content_type"] != "video" or item["platform"] != "douyin":
            raise DomainError("RENDER_PROFILE_UNAVAILABLE", "当前只开放抖音视频渲染", 409, "platform", "创建抖音视频实例")
        if mode != "remotion":
            raise DomainError("RENDER_MODE_PENDING", "upload/mixed 属于后续 P4 验收，当前仅开放 remotion", 409, "mode", "选择 remotion")
        active = item["active_revisions"]
        missing = [kind for kind in ("script", "audio", "subtitle") if kind not in active]
        if missing:
            raise DomainError("MISSING_RENDER_INPUT", "渲染输入不完整：" + "、".join(missing), 409, "manifest", "选择当前脚本、音频和匹配字幕", item_id)
        manifest = item["manifest"]
        if manifest.get("audio_asset_id") != manifest.get("subtitle_source_audio_asset_id"):
            raise DomainError("SUBTITLE_AUDIO_MISMATCH", "字幕来自另一版音频", 422, "subtitle_asset_id",
                              "选择与活动音频匹配的 subtitle revision，或重新转写当前音频", item_id)
        if not manifest.get("audio_asset_id") or not manifest.get("subtitle_asset_id"):
            raise DomainError("MISSING_MEDIA", "音频或字幕资产缺失", 422, "manifest", "重新关联真实文件", item_id)
        return manifest

    def export_article(self, item_id, revision_id, expected_version=None):
        item = self.get_item(item_id)
        if item["content_type"] != "article" or item["active_revisions"].get("draft") != revision_id:
            raise DomainError("STALE_EXPORT", "只能导出当前文章版本", 409, "revision_id", "刷新并选择当前正文", item_id)
        if item["state"] not in ("approved", "exported"):
            raise DomainError("ARTICLE_NOT_APPROVED", "文章尚未终审", 409, "state", "先批准当前正文版本", item_id)
        revision = self.get_revision(revision_id)
        text = str(revision["payload"].get("text", "")).strip()
        title = str(revision["payload"].get("title") or item["campaign"]["title"])
        if not text:
            raise DomainError("EMPTY_ARTICLE", "正文为空", 422, "text", "填写正文后重新审核")
        safe_html = "<!doctype html><html lang=\"zh-CN\"><meta charset=\"utf-8\"><title>{}</title><article><h1>{}</h1>{}</article></html>".format(
            html.escape(title), html.escape(title), "".join("<p>{}</p>".format(html.escape(line)) for line in text.splitlines() if line.strip()))
        directory = self.root / "renders" / "exports" / item_id
        directory.mkdir(parents=True, exist_ok=True)
        markdown_path = directory / (revision_id + ".md")
        html_path = directory / (revision_id + ".html")
        markdown_path.write_text("# {}\n\n{}".format(title, text), encoding="utf-8")
        html_path.write_text(safe_html, encoding="utf-8")
        markdown_asset = self.register_asset(markdown_path, {"kind": "article_markdown", "item_id": item_id}, "owned")
        html_asset = self.register_asset(html_path, {"kind": "article_html", "item_id": item_id}, "owned")
        version = expected_version if expected_version is not None else self.get_item(item_id)["version"]
        export_revision = self.save_revision(item_id, "export", {"markdown_asset_id": markdown_asset, "html_asset_id": html_asset,
                                                                  "source_revision_id": revision_id, "format": "markdown+safe_html"},
                                             version, dependencies=[{"revision_id": revision_id}, {"asset_id": markdown_asset}, {"asset_id": html_asset}], created_by="export")
        return self.get_item(item_id), export_revision

    def record_publication(self, item_id, revision_id, url, published_at=None, actor="local_user"):
        if not re.match(r"^https?://", str(url or "")):
            raise DomainError("INVALID_PUBLICATION_URL", "发布链接必须是真实 http(s) URL", 422, "url", "粘贴平台实际作品链接")
        item = self.get_item(item_id)
        if item["content_type"] == "article" and "export" not in item["active_revisions"]:
            raise DomainError("EXPORT_REQUIRED", "文章尚未导出", 409, "export", "先导出当前已批准文章")
        if item["content_type"] == "video" and "render" not in item["active_revisions"]:
            raise DomainError("RENDER_REQUIRED", "视频尚未生成成片", 409, "render", "先渲染并完成终审")
        with self.conn(readonly=True) as conn:
            approval = conn.execute("""SELECT * FROM wb_approvals WHERE item_id=? AND revision_id=? AND decision='approve'
                AND revoked_at IS NULL ORDER BY created_at DESC LIMIT 1""", (item_id, revision_id)).fetchone()
            if not approval:
                raise DomainError("APPROVAL_REQUIRED", "当前产物没有有效终审", 409, "revision_id", "批准当前版本后再记录发布", item_id)
        publication_id = new_id("pub")
        timestamp = utcnow()
        with self.conn() as conn, immediate(conn):
            conn.execute("INSERT INTO wb_publications VALUES (?,?,?,?,NULL,?,?,?,?,?,?)",
                         (publication_id, item_id, revision_id, approval["id"], dumps(item["manifest"]), item["platform"], url,
                          published_at or timestamp, actor, timestamp))
            conn.execute("UPDATE wb_content_items SET state='published',version=version+1,updated_at=? WHERE id=?", (timestamp, item_id))
            self.event(conn, "content_item", item_id, "publication.recorded", {"publication_id": publication_id, "url": url, "automatic": False})
        return self.get_item(item_id)

    def add_metric(self, publication_id, window_key, metric_key, value, missing_reason=None, source="manual", observed_at=None):
        if value is None and not missing_reason:
            raise DomainError("MISSING_REASON_REQUIRED", "缺失指标必须填写原因", 422, "missing_reason", "未到时间、平台未提供或读取失败")
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0):
            raise DomainError("INVALID_METRIC", "指标必须是非负数字或 null", 422, "value", "填写真实数字；缺失时填写原因")
        metric_id = new_id("metric")
        with self.conn() as conn, immediate(conn):
            if not conn.execute("SELECT 1 FROM wb_publications WHERE id=?", (publication_id,)).fetchone():
                raise DomainError("PUBLICATION_NOT_FOUND", "发布记录不存在", 404)
            conn.execute("INSERT INTO wb_metric_samples VALUES (?,?,?,?,?,?,?,?,NULL)",
                         (metric_id, publication_id, window_key, metric_key, value, missing_reason, source, observed_at or utcnow()))
            self.event(conn, "publication", publication_id, "metric.recorded", {"window": window_key, "metric": metric_key})
        return metric_id

    @staticmethod
    def event(conn, aggregate_type, aggregate_id, event_type, payload):
        conn.execute("""INSERT INTO wb_events
            (event_id,aggregate_type,aggregate_id,event_type,schema_version,actor,trace_id,payload_json,created_at)
            VALUES (?,?,?,?,1,'local_user',NULL,?,?)""",
            (new_id("evt"), aggregate_type, aggregate_id, event_type, dumps(payload), utcnow()))
