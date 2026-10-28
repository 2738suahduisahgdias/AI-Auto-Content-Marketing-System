from content_workbench.accounts.analytics import parse_time
from content_workbench.domain.errors import DomainError
from content_workbench.storage.db import connect, immediate, new_id, utcnow

PLATFORMS = ("douyin", "wechat_channels", "xiaohongshu", "wechat_official_account")
STAGES = ("inquiry", "qualified", "high_intent", "meeting", "deal", "not_qualified")


class LeadService:
    def __init__(self, db_path):
        self.db_path = str(db_path)

    def conn(self, readonly=False):
        return connect(self.db_path, readonly=readonly)

    def ensure_tables(self):
        with self.conn() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS account_leads(
                id TEXT PRIMARY KEY,platform TEXT NOT NULL,author_alias TEXT NOT NULL,profile_text TEXT NOT NULL DEFAULT '',
                message_text TEXT NOT NULL,need_text TEXT NOT NULL DEFAULT '',source_content_id TEXT,source_url TEXT,
                occurred_at TEXT NOT NULL,stage TEXT NOT NULL,notes TEXT NOT NULL DEFAULT '',revenue REAL,deal_at TEXT,
                created_at TEXT NOT NULL,updated_at TEXT NOT NULL)""")
            columns = {row[1] for row in conn.execute("PRAGMA table_info(account_leads)")}
            if "deal_at" not in columns:
                conn.execute("ALTER TABLE account_leads ADD COLUMN deal_at TEXT")
            conn.execute("CREATE INDEX IF NOT EXISTS account_leads_platform_time ON account_leads(platform,occurred_at)")

    def list(self, platform=None):
        self.ensure_tables()
        with self.conn(readonly=True) as conn:
            if platform:
                rows = conn.execute("SELECT * FROM account_leads WHERE platform=? ORDER BY occurred_at DESC", (platform,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM account_leads ORDER BY occurred_at DESC").fetchall()
        return [dict(row) for row in rows]

    def values(self, body, existing=None):
        body = body or {}
        current = existing or {}
        value = lambda key, default="": body[key] if key in body else current.get(key, default)
        platform = value("platform")
        if platform not in PLATFORMS:
            raise DomainError("LEAD_PLATFORM_INVALID", "线索平台无效", 422, "platform", "选择抖音、视频号、小红书或公众号")
        alias = str(value("author_alias")).strip()
        message = str(value("message_text")).strip()
        if not alias or len(alias) > 80:
            raise DomainError("LEAD_ALIAS_INVALID", "用户别名不能为空且不能超过 80 字", 422, "author_alias", "填写便于识别的别名，不必填写真实姓名")
        if not message or len(message) > 12000:
            raise DomainError("LEAD_MESSAGE_INVALID", "私信详情不能为空且不能超过 12000 字", 422, "message_text", "粘贴需要本地保存的私信内容")
        stage = value("stage", "inquiry")
        if stage not in STAGES:
            raise DomainError("LEAD_STAGE_INVALID", "线索阶段无效", 422, "stage", "重新选择有效线索阶段")
        occurred_at = str(value("occurred_at") or utcnow())
        if not parse_time(occurred_at):
            raise DomainError("LEAD_TIME_INVALID", "私信发生时间格式无效", 422, "occurred_at", "使用有效的 ISO 日期时间")
        source_url = str(value("source_url") or "").strip()
        if source_url and not source_url.startswith(("https://", "http://")):
            raise DomainError("LEAD_SOURCE_URL_INVALID", "来源链接必须是 HTTP(S) 地址", 422, "source_url", "填写平台内容原链接或留空")
        revenue = value("revenue", None)
        if revenue in ("", None):
            revenue = None
        else:
            try:
                revenue = float(revenue)
            except (TypeError, ValueError):
                raise DomainError("LEAD_REVENUE_INVALID", "成交金额必须是数字", 422, "revenue", "填写人工确认金额或留空")
            if revenue < 0 or revenue > 1_000_000_000_000:
                raise DomainError("LEAD_REVENUE_INVALID", "成交金额超出允许范围", 422, "revenue", "检查金额后重试")
        deal_at = str(value("deal_at") or "").strip() or None
        if deal_at and not parse_time(deal_at):
            raise DomainError("LEAD_DEAL_TIME_INVALID", "实际成交时间格式无效", 422, "deal_at", "使用有效日期时间或留空")
        return {"platform": platform, "author_alias": alias, "profile_text": str(value("profile_text")).strip()[:2000],
                "message_text": message, "need_text": str(value("need_text")).strip()[:12000],
                "source_content_id": str(value("source_content_id") or "").strip()[:200] or None,
                "source_url": source_url or None, "occurred_at": occurred_at, "stage": stage,
                "notes": str(value("notes")).strip()[:12000], "revenue": revenue, "deal_at": deal_at}

    def create(self, body):
        self.ensure_tables()
        values = self.values(body)
        lead_id = new_id("lead")
        timestamp = utcnow()
        with self.conn() as conn, immediate(conn):
            conn.execute("""INSERT INTO account_leads(id,platform,author_alias,profile_text,message_text,need_text,
                source_content_id,source_url,occurred_at,stage,notes,revenue,deal_at,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (lead_id, *values.values(), timestamp, timestamp))
        return self.get(lead_id)

    def get(self, lead_id):
        with self.conn(readonly=True) as conn:
            row = conn.execute("SELECT * FROM account_leads WHERE id=?", (lead_id,)).fetchone()
        if not row:
            raise DomainError("LEAD_NOT_FOUND", "私信线索不存在", 404, "id", "刷新线索列表后重试", lead_id)
        return dict(row)

    def update(self, lead_id, body):
        self.ensure_tables()
        current = self.get(lead_id)
        expected = str((body or {}).get("expected_updated_at") or "")
        if not expected or expected != current["updated_at"]:
            raise DomainError("LEAD_EDIT_CONFLICT", "这条线索已被更新，不能覆盖最新记录", 409, "expected_updated_at", "刷新详情后重新标注", lead_id)
        values = self.values(body, current)
        timestamp = utcnow()
        with self.conn() as conn, immediate(conn):
            changed = conn.execute("""UPDATE account_leads SET platform=?,author_alias=?,profile_text=?,message_text=?,need_text=?,
                source_content_id=?,source_url=?,occurred_at=?,stage=?,notes=?,revenue=?,deal_at=?,updated_at=?
                WHERE id=? AND updated_at=?""", (*values.values(), timestamp, lead_id, expected)).rowcount
        if not changed:
            raise DomainError("LEAD_EDIT_CONFLICT", "这条线索已被更新，不能覆盖最新记录", 409, "expected_updated_at", "刷新详情后重新标注", lead_id)
        return self.get(lead_id)

    def delete(self, ids):
        if not isinstance(ids, list) or not ids or len(ids) > 100 or any(not isinstance(value, str) or not value for value in ids):
            raise DomainError("LEAD_DELETE_IDS_INVALID", "请选择要删除的本地线索", 422, "ids", "勾选至少一条且每次不超过 100 条")
        self.ensure_tables()
        unique_ids = list(dict.fromkeys(ids))
        with self.conn() as conn, immediate(conn):
            deleted = conn.execute("DELETE FROM account_leads WHERE id IN ({})".format(",".join("?" * len(unique_ids))), unique_ids).rowcount
        return {"deleted": deleted}
