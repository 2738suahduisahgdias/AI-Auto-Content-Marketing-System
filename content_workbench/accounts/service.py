from content_workbench.accounts.analytics import AccountAnalytics
from content_workbench.accounts.collection_knowledge import collection_bootstrap
from content_workbench.accounts.leads import LeadService
from content_workbench.accounts.snapshot_rules import snapshot_has_data
from content_workbench.publishing.knowledge import publish_knowledge
from content_workbench.storage.db import connect, dumps, immediate, loads, new_id, utcnow


class AccountService:
    def __init__(self, db_path, topics):
        self.db_path = str(db_path)
        self.topics = topics
        self.leads = LeadService(self.db_path)

    def conn(self, readonly=False):
        return connect(self.db_path, readonly=readonly)

    def ensure_tables(self):
        with self.conn() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS account_daily_snapshots(
                id TEXT PRIMARY KEY,platform TEXT NOT NULL,snapshot_json TEXT NOT NULL,captured_at TEXT NOT NULL)""")
        self.leads.ensure_tables()

    def save_snapshot(self, platform, profile, items):
        self.ensure_tables()
        snapshot_id = new_id("account")
        with self.conn() as conn, immediate(conn):
            initial = not conn.execute("SELECT 1 FROM account_daily_snapshots WHERE platform=? LIMIT 1", (platform,)).fetchone()
            profile = {**profile, "sync_mode": "initial" if initial else "incremental"}
            conn.execute("INSERT INTO account_daily_snapshots VALUES (?,?,?,?)", (snapshot_id, platform, dumps({"profile": profile, "items": items}), utcnow()))
        return snapshot_id

    def merge_profile(self, platform, metrics):
        self.ensure_tables()
        with self.conn(readonly=True) as conn:
            row = conn.execute("SELECT snapshot_json FROM account_daily_snapshots WHERE platform=? ORDER BY captured_at DESC LIMIT 1", (platform,)).fetchone()
        current = loads(row[0], {}) if row else {}
        profile = {**(current.get("profile") or {}), **metrics}
        return self.save_snapshot(platform, profile, current.get("items") or [])

    def bootstrap(self):
        self.ensure_tables()
        with self.conn(readonly=True) as conn:
            snapshots = [dict(row) for row in conn.execute("SELECT * FROM account_daily_snapshots ORDER BY captured_at DESC")]
            candidates = [dict(row) for row in conn.execute("SELECT * FROM wb_topic_candidates ORDER BY created_at DESC LIMIT 20")]
        latest = []
        seen = set()
        for row in snapshots:
            if row["platform"] in seen:
                continue
            value = loads(row["snapshot_json"], {})
            if not snapshot_has_data(value):
                continue
            seen.add(row["platform"])
            latest.append({"id": row["id"], "platform": row["platform"], "captured_at": row["captured_at"], **value})
        recommendations = []
        for row in candidates:
            payload = loads(row["payload_json"], {})
            if payload.get("agent") == "account_analysis":
                recommendations.append({**payload, "id": row["id"], "created_at": row["created_at"]})
        analytics = AccountAnalytics(self.db_path).bootstrap()
        return {"accounts": latest, "recommendations": recommendations, "analytics": analytics,
                "collection_knowledge": collection_bootstrap(),
                "publish_knowledge": publish_knowledge(),
                "competitor_analytics": analytics["competitor_analytics"],
                "jobs": [job for job in self.topics.jobs.list() if job["kind"].startswith("accounts.") or job["kind"] == "publish.douyin"][:20]}


def platform_names():
    return {"douyin": "抖音", "xiaohongshu": "小红书", "wechat_channels": "视频号", "wechat_official_account": "公众号"}
