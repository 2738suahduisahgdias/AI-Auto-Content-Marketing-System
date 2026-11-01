import os
import re
import sqlite3

from content_workbench.domain.errors import DomainError
from content_workbench.storage.db import PROJECT_ROOT, connect, dumps, immediate, loads, new_id, utcnow

CATEGORIES = {"unclassified": "待分类", "featured": "精选", "competitor": "竞品", "high_praise": "高赞", "industry": "行业"}
MESSAGE_TYPES = {"text", "link", "image", "voice", "file", "video", "card", "unknown"}


def message_title(text, url):
    title = re.sub(r"https?://\S+", "", text or "").strip()
    title = re.sub(r"\s+", " ", title)
    if title:
        return title[:200]
    return "微信链接消息" if url else "微信随手记"


class WechatInboxService:
    def __init__(self, db_path, topics):
        self.db_path = str(db_path)
        self.topics = topics
        with self.conn() as conn:
            conn.executescript((PROJECT_ROOT / "migrations/006_wechat_inbox.sql").read_text())
            conn.executescript((PROJECT_ROOT / "migrations/007_wechat_snapshots.sql").read_text())
        self.backfill()

    def conn(self, readonly=False):
        return connect(self.db_path, readonly=readonly)

    def row_dict(self, row):
        metadata = loads(row["metadata_json"], {})
        return {"id": row["id"], "msgid": row["msgid"], "research_item_id": row["research_item_id"],
                "message_type": row["message_type"], "raw_text": row["raw_text"], "original_url": row["original_url"],
                "title": row["title_override"] or message_title(row["raw_text"], row["original_url"]),
                "note": row["note_override"] or row["raw_text"], "category": row["category"],
                "category_name": CATEGORIES[row["category"]], "ingest_status": row["ingest_status"],
                "received_at": row["received_at"], "created_at": row["created_at"], "updated_at": row["updated_at"],
                "archived": bool(metadata.get("archived_at")), "source_name": metadata.get("source_name") or "微信私聊",
                "snapshot_status": row["snapshot_status"] or "not_started", "snapshot": loads(row["snapshot_json"], {}),
                "snapshot_error": row["snapshot_error"]}

    def get(self, message_id):
        with self.conn(readonly=True) as conn:
            row = conn.execute("""SELECT m.*,r.metadata_json,s.status AS snapshot_status,
                s.snapshot_json,s.error AS snapshot_error FROM wechat_topic_messages m
                JOIN wb_research_items r ON r.id=m.research_item_id
                LEFT JOIN wechat_link_snapshots s ON s.message_id=m.id WHERE m.id=?""", (message_id,)).fetchone()
        if not row:
            raise DomainError("WECHAT_MESSAGE_NOT_FOUND", "微信消息不存在", 404, "id", "刷新消息列表后重新选择")
        return self.row_dict(row)

    def get_by_msgid(self, msgid):
        with self.conn(readonly=True) as conn:
            row = conn.execute("""SELECT m.*,r.metadata_json,s.status AS snapshot_status,
                s.snapshot_json,s.error AS snapshot_error FROM wechat_topic_messages m
                JOIN wb_research_items r ON r.id=m.research_item_id
                LEFT JOIN wechat_link_snapshots s ON s.message_id=m.id WHERE m.msgid=?""", (msgid,)).fetchone()
        return self.row_dict(row) if row else None

    def list(self):
        with self.conn(readonly=True) as conn:
            rows = conn.execute("""SELECT m.*,r.metadata_json,s.status AS snapshot_status,
                s.snapshot_json,s.error AS snapshot_error FROM wechat_topic_messages m
                JOIN wb_research_items r ON r.id=m.research_item_id
                LEFT JOIN wechat_link_snapshots s ON s.message_id=m.id ORDER BY m.received_at DESC LIMIT 500""").fetchall()
        return [self.row_dict(row) for row in rows]

    def update_snapshot(self, message_id, status, snapshot=None, error=None):
        self.get(message_id)
        timestamp = utcnow()
        with self.conn() as conn, immediate(conn):
            conn.execute("""INSERT INTO wechat_link_snapshots(message_id,status,snapshot_json,error,created_at,updated_at)
                VALUES (?,?,?,?,?,?) ON CONFLICT(message_id) DO UPDATE SET status=excluded.status,
                snapshot_json=excluded.snapshot_json,error=excluded.error,updated_at=excluded.updated_at""",
                         (message_id, status, dumps(snapshot or {}), error, timestamp, timestamp))
        return self.get(message_id)

    def ingest(self, data):
        text = str(data.get("text") or "").strip()[:12000]
        original_url = str(data.get("original_url") or data.get("url") or "").strip()
        if not original_url:
            found = re.search(r"https?://[^\s]+", text)
            original_url = found.group(0).rstrip("，。！？,.!?)]}") if found else ""
        if original_url and not original_url.startswith(("https://", "http://")):
            raise DomainError("WECHAT_URL_INVALID", "原始链接格式无效", 422, "original_url", "使用 http:// 或 https:// 开头的链接，或留空")
        raw_payload = data.get("raw_payload") if isinstance(data.get("raw_payload"), dict) else {}
        if not text and not original_url and not raw_payload:
            raise DomainError("WECHAT_MESSAGE_EMPTY", "消息内容不能为空", 422, "text", "发送链接、文本想法或支持的媒体消息")
        msgid = str(data.get("msgid") or new_id("manual")).strip()[:256]
        sender_id = str(data.get("sender_id") or "local_user").strip()[:256]
        if data.get("source") == "openclaw":
            allowed_sender = os.environ.get("CONTENT_AGENT_WECHAT_SENDER_ID", "")
            if not allowed_sender:
                raise DomainError("WECHAT_SENDER_NOT_CONFIGURED", "尚未配置本人微信发送者", 503, "sender_id", "扫码后设置 CONTENT_AGENT_WECHAT_SENDER_ID，不接收其他私聊消息")
            if sender_id != allowed_sender:
                raise DomainError("WECHAT_SENDER_FORBIDDEN", "该微信发送者没有选题入库权限", 403, "sender_id", "仅使用已授权的本人微信私聊")
        message_type = str(data.get("message_type") or ("link" if original_url else "text"))
        if message_type not in MESSAGE_TYPES:
            message_type = "unknown"
        existing = self.get_by_msgid(msgid)
        if existing:
            return existing, False
        title = message_title(text, original_url)
        timestamp = utcnow()
        message_id = new_id("wechat")
        canonical = "https://wechat.local/messages/" + message_id
        source_name = "微信私聊" if data.get("source") == "openclaw" else "本机手动"
        metadata = {"title": title, "raw_message": text, "original_url": original_url or None,
                    "source_name": source_name, "tag": "待分类", "message_id": message_id,
                    "message_type": message_type, "ingest": "wechat_manual"}
        research_item_id = self.topics.upsert_item({"title": title, "canonical_url": canonical, "metadata": metadata},
                                                   "wechat_inbox", platform="wechat_channels")
        try:
            with self.conn() as conn, immediate(conn):
                conn.execute("""INSERT INTO wechat_topic_messages(id,msgid,research_item_id,sender_id,message_type,raw_text,
                    original_url,raw_payload_json,title_override,note_override,category,ingest_status,received_at,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,'unclassified','saved',?,?,?)""",
                             (message_id, msgid, research_item_id, sender_id, message_type, text, original_url or None,
                              dumps(raw_payload), title, text, data.get("received_at") or timestamp, timestamp, timestamp))
        except sqlite3.IntegrityError:
            existing = self.get_by_msgid(msgid)
            if existing:
                return existing, False
            raise
        return self.get(message_id), True

    def update(self, message_id, data):
        current = self.get(message_id)
        if current["archived"]:
            raise DomainError("WECHAT_MESSAGE_ARCHIVED", "已归档消息不能直接编辑", 409, "id", "先在已归档中恢复，再修改")
        category = str(data.get("category") or current["category"])
        if category not in CATEGORIES:
            raise DomainError("WECHAT_CATEGORY_INVALID", "选题分类无效", 422, "category", "选择待分类、精选、竞品、高赞或行业")
        title = str(data.get("title") if "title" in data else current["title"]).strip()[:200]
        note = str(data.get("note") if "note" in data else current["note"]).strip()[:12000]
        original_url = str(data.get("original_url") if "original_url" in data else current["original_url"] or "").strip()
        if not title:
            raise DomainError("WECHAT_TITLE_EMPTY", "后台标题不能为空", 422, "title", "填写便于识别的标题")
        if original_url and not original_url.startswith(("https://", "http://")):
            raise DomainError("WECHAT_URL_INVALID", "原始链接格式无效", 422, "original_url", "使用有效链接或留空")
        with self.conn() as conn, immediate(conn):
            conn.execute("UPDATE wechat_topic_messages SET title_override=?,note_override=?,category=?,original_url=?,updated_at=? WHERE id=?",
                         (title, note, category, original_url or None, utcnow(), message_id))
        self.topics.update_metadata(current["research_item_id"], {"title": title, "raw_note": note,
            "tag": CATEGORIES[category], "original_url": original_url or None})
        return self.get(message_id)

    def connection(self):
        verified = any(item.get("source_name") == "微信私聊" and item.get("ingest_status") == "saved" for item in self.list())
        if verified:
            return {"status": "connected", "label": "微信已连接 · 私聊入库已验证",
                    "detail": "真实私聊消息已保存到待分类；原始链接可继续生成公开快照"}
        return {"status": "manual_ready", "label": "本机入库可用，OpenClaw 待接入",
                "detail": "当前可使用手动录入；微信插件完成真实消息验收后才显示已连接"}

    def backfill(self):
        with self.conn(readonly=True) as conn:
            rows = conn.execute("SELECT * FROM wb_research_items").fetchall()
        reverse = {value: key for key, value in CATEGORIES.items()}
        for row in rows:
            metadata = loads(row["metadata_json"], {})
            if metadata.get("source_key") != "wechat_inbox":
                continue
            msgid = "legacy_" + row["id"]
            with self.conn(readonly=True) as conn:
                exists = conn.execute("SELECT 1 FROM wechat_topic_messages WHERE msgid=?", (msgid,)).fetchone()
            if exists:
                continue
            original_url = metadata.get("original_url")
            if not original_url and not row["canonical_url"].startswith("https://wechat.local/"):
                original_url = row["canonical_url"]
            raw_text = metadata.get("raw_message") or metadata.get("title") or "历史微信消息"
            timestamp = row["first_seen_at"]
            with self.conn() as conn, immediate(conn):
                conn.execute("""INSERT INTO wechat_topic_messages(id,msgid,research_item_id,sender_id,message_type,raw_text,
                    original_url,raw_payload_json,title_override,note_override,category,ingest_status,received_at,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,'{}',?,?,?,'saved',?,?,?)""",
                             (new_id("wechat"), msgid, row["id"], "legacy", metadata.get("message_type") or "text", raw_text,
                              original_url, metadata.get("title") or message_title(raw_text, original_url), raw_text,
                              reverse.get(metadata.get("tag"), "unclassified"), timestamp, timestamp, timestamp))
