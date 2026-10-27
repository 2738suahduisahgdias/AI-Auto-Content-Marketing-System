from content_workbench.storage.db import connect, dumps, immediate, loads, new_id, utcnow


class AccountService:
    def __init__(self, db_path, topics):
        self.db_path = str(db_path)
        self.topics = topics

    def conn(self, readonly=False):
        return connect(self.db_path, readonly=readonly)

    def ensure_tables(self):
        with self.conn() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS account_daily_snapshots(
                id TEXT PRIMARY KEY,platform TEXT NOT NULL,snapshot_json TEXT NOT NULL,captured_at TEXT NOT NULL)""")

    def save_snapshot(self, platform, profile, items):
        self.ensure_tables()
        snapshot_id = new_id("account")
        with self.conn() as conn, immediate(conn):
            conn.execute("INSERT INTO account_daily_snapshots VALUES (?,?,?,?)", (snapshot_id, platform, dumps({"profile": profile, "items": items}), utcnow()))
        return snapshot_id

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
            seen.add(row["platform"])
            value = loads(row["snapshot_json"], {})
            latest.append({"id": row["id"], "platform": row["platform"], "captured_at": row["captured_at"], **value})
        recommendations = []
        for row in candidates:
            payload = loads(row["payload_json"], {})
            if payload.get("agent") == "account_analysis":
                recommendations.append({**payload, "id": row["id"], "created_at": row["created_at"]})
        return {"accounts": latest, "recommendations": recommendations,
                "jobs": [job for job in self.topics.jobs.list() if job["kind"].startswith("accounts.") or job["kind"] == "publish.douyin"][:20]}


def platform_names():
    return {"douyin": "抖音", "xiaohongshu": "小红书", "wechat_channels": "视频号", "wechat_official_account": "公众号"}
