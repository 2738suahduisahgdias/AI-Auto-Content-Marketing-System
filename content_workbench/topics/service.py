import hashlib
import json
import urllib.request
from pathlib import Path

from content_workbench.jobs.store import JobStore
from content_workbench.storage.db import connect, dumps, immediate, loads, new_id, utcnow

DEFAULT_SETTINGS = {
    "industry_scope": "人工智能 企业应用 AI落地 企业转型",
    "industry_prompt": "关注企业AI落地、AI教学、AI营销获客。优先真实业务任务、流程改造、验收和可复用方法，不推荐泛娱乐或无法核实的案例。",
    "douyin_prompt": "综合今日热榜和收藏快照，选择与账号定位相关且能形成差异化表达的主题。热点只作场景，不硬蹭灾难、隐私或无关娱乐事件。",
    "xiaohongshu_prompt": "综合个人小红书收藏夹中的热点、精选、竞品和高赞笔记快照，选择与账号定位相关且能形成差异化表达的主题。收藏只代表个人研究样本，不代表平台全貌；没有明确指标时不得编造热度。",
    "daily_time": "09:00", "daily_enabled": False,
    "featured_collection": "选题", "competitor_collection": "企业AI落地竞对账号", "high_praise_collection": "低粉高赞文案",
    "xhs_hot_collection": "热点选题", "xhs_featured_collection": "精选选题", "xhs_competitor_collection": "竞对账号内容", "xhs_high_praise_collection": "高赞选题",
}
SOURCE_KEYS = ("industry", "hot", "featured", "competitor", "high_praise", "xhs_hot", "xhs_featured", "xhs_competitor", "xhs_high_praise", "xhs_notes", "wechat_inbox")


def stable_id(prefix, value):
    return prefix + "_" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]


def canonical_hash(url):
    return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()


class TopicService:
    def __init__(self, db_path, root):
        self.db_path = str(db_path)
        self.root = Path(root)
        self.jobs = JobStore(db_path)
        with self.conn() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY,value TEXT NOT NULL)")

    def conn(self, readonly=False):
        return connect(self.db_path, readonly=readonly)

    def settings(self):
        with self.conn(readonly=True) as conn:
            row = conn.execute("SELECT value FROM settings WHERE key='topics_settings'").fetchone()
        return {**DEFAULT_SETTINGS, **(loads(row[0], {}) if row else {})}

    def save_settings(self, values):
        current = self.settings()
        for key in ("industry_scope", "industry_prompt", "douyin_prompt", "xiaohongshu_prompt", "featured_collection", "competitor_collection", "high_praise_collection",
                    "xhs_hot_collection", "xhs_featured_collection", "xhs_competitor_collection", "xhs_high_praise_collection"):
            if key in values:
                current[key] = str(values[key]).strip()[:12000]
        if "daily_time" in values:
            value = str(values["daily_time"])
            if len(value) != 5 or value[2] != ":" or not value[:2].isdigit() or not value[3:].isdigit() or not 0 <= int(value[:2]) <= 23 or not 0 <= int(value[3:]) <= 59:
                raise ValueError("每日时间必须是 HH:MM")
            current["daily_time"] = value
        if "daily_enabled" in values:
            current["daily_enabled"] = bool(values["daily_enabled"])
        if not current["industry_scope"] or not current["industry_prompt"] or not current["douyin_prompt"] or not current["xiaohongshu_prompt"]:
            raise ValueError("行业范围、行业提示词、抖音提示词和小红书提示词不能为空")
        with self.conn() as conn, immediate(conn):
            conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES ('topics_settings',?)", (dumps(current),))
        from .scheduler import configure_schedule
        configure_schedule(self.db_path, current)
        return current

    def ensure_account(self, profile_ref="data/topic-browser-profile", platform="douyin"):
        account_id = "source_{}_main".format(platform)
        with self.conn() as conn, immediate(conn):
            conn.execute("INSERT OR IGNORE INTO wb_source_accounts VALUES (?,?,?,?,?,?)",
                         (account_id, platform, "main", profile_ref, "unknown", utcnow()))
        return account_id

    def collection(self, title, account_id=None):
        account_id = account_id or self.ensure_account()
        collection_id = stable_id("col", account_id + ":" + title)
        with self.conn() as conn, immediate(conn):
            conn.execute("INSERT OR IGNORE INTO wb_collections VALUES (?,?,?,?,1)", (collection_id, account_id, title, title))
        return collection_id

    def upsert_item(self, item, source_key, collection_title=None, run_id=None, platform="douyin"):
        url = item.get("canonical_url") or item.get("url")
        if not url or not url.startswith(("https://", "http://")):
            raise ValueError("作品缺少有效原链接")
        platform_item_id = str(item.get("platform_item_id") or "") or None
        url_hash = canonical_hash(url)
        item_id = stable_id("research", platform + ":" + (platform_item_id or url_hash))
        timestamp = utcnow()
        metadata = dict(item.get("metadata") or {})
        for key in ("title", "rank", "heat", "author", "published_at", "duration", "visible_metrics", "source_url"):
            if key in item:
                metadata[key] = item[key]
        metadata["source_key"] = source_key
        metadata["title"] = item.get("title") or metadata.get("title") or "未读取标题"
        collection_id = self.collection(collection_title, self.ensure_account(platform=platform)) if collection_title else None
        with self.conn() as conn, immediate(conn):
            existing = conn.execute("SELECT id FROM wb_research_items WHERE platform=? AND canonical_url_hash=?", (platform, url_hash)).fetchone()
            if existing:
                item_id = existing[0]
                previous = conn.execute("SELECT metadata_json FROM wb_research_items WHERE id=?", (item_id,)).fetchone()[0]
                merged = loads(previous, {})
                merged.update(metadata)
                metadata = merged
                conn.execute("""UPDATE wb_research_items SET platform_item_id=COALESCE(platform_item_id,?),canonical_url=?,metadata_json=?,last_seen_at=?,observed_at=? WHERE id=?""",
                             (platform_item_id, url, dumps(metadata), timestamp, timestamp, item_id))
            else:
                conn.execute("INSERT INTO wb_research_items VALUES (?,?,?,?,?,?,?,?,?)",
                             (item_id, platform, platform_item_id, url, url_hash, dumps(metadata), timestamp, timestamp, timestamp))
            if collection_id:
                conn.execute("""INSERT INTO wb_memberships VALUES (?,?, 'present',?,0)
                    ON CONFLICT(collection_id,item_id) DO UPDATE SET status='present',last_seen_run_id=excluded.last_seen_run_id,consecutive_full_scan_misses=0""",
                    (collection_id, item_id, run_id))
        return item_id

    def cache_cover(self, item_id):
        item = self.get_item(item_id)
        url = item["metadata"].get("cover_url")
        if not url:
            return False
        path = self.root / "covers" / "topic-research" / (item_id + ".jpg")
        path.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": item["url"]})
        with urllib.request.urlopen(request, timeout=20) as response:
            content_type = response.headers.get("Content-Type", "")
            if response.status != 200 or not content_type.startswith("image/"):
                return False
            body = response.read(10 * 1024 * 1024)
        if len(body) < 100:
            return False
        path.write_bytes(body)
        self.update_metadata(item_id, {"cover_cached": True})
        return True

    def update_metadata(self, item_id, values):
        with self.conn() as conn, immediate(conn):
            row = conn.execute("SELECT metadata_json FROM wb_research_items WHERE id=?", (item_id,)).fetchone()
            if not row:
                raise ValueError("研究条目不存在")
            metadata = loads(row[0], {})
            metadata.update(values)
            conn.execute("UPDATE wb_research_items SET metadata_json=?,observed_at=? WHERE id=?", (dumps(metadata), utcnow(), item_id))

    def reconcile_collection(self, title, item_ids, run_id, complete, account_id=None):
        if not complete:
            return
        collection_id = self.collection(title, account_id)
        with self.conn() as conn, immediate(conn):
            rows = conn.execute("SELECT item_id FROM wb_memberships WHERE collection_id=? AND status='present'", (collection_id,)).fetchall()
            missing = [row[0] for row in rows if row[0] not in set(item_ids)]
            for item_id in missing:
                conn.execute("""UPDATE wb_memberships SET consecutive_full_scan_misses=consecutive_full_scan_misses+1,
                    last_seen_run_id=? WHERE collection_id=? AND item_id=?""", (run_id, collection_id, item_id))
            conn.execute("UPDATE wb_memberships SET status='removed' WHERE collection_id=? AND consecutive_full_scan_misses>=2", (collection_id,))

    def start_sync(self, mode="incremental", scope=None, platform="douyin"):
        account_id = self.ensure_account(platform=platform)
        run_id = new_id("sync")
        with self.conn() as conn, immediate(conn):
            conn.execute("INSERT INTO wb_sync_runs VALUES (?,?,?,?,'running','{}','topics-v1',0,?,NULL,'{}',NULL)",
                         (run_id, account_id, mode, dumps(scope or {}), timestamp_now()))
        return run_id

    def finish_sync(self, run_id, status, stats, complete, error=None):
        with self.conn() as conn, immediate(conn):
            conn.execute("UPDATE wb_sync_runs SET status=?,complete=?,finished_at=?,stats_json=?,error_json=? WHERE id=?",
                         (status, int(complete), utcnow(), dumps(stats), dumps(error) if error else None, run_id))

    def save_candidates(self, agent, candidates):
        ids = []
        with self.conn() as conn, immediate(conn):
            for candidate in candidates:
                candidate_id = new_id("topic")
                payload = {**candidate, "agent": agent, "created_at": utcnow()}
                scores = candidate.get("scores") or {"evidence": candidate.get("evidence_score"), "relevance": candidate.get("relevance_score")}
                conn.execute("INSERT INTO wb_topic_candidates VALUES (?,?,?,?,?,?)",
                             (candidate_id, dumps(payload), dumps(scores), dumps(candidate.get("evidence_ids", [])), "new", utcnow()))
                ids.append(candidate_id)
        return ids

    def get_candidate(self, candidate_id):
        with self.conn(readonly=True) as conn:
            row = conn.execute("SELECT * FROM wb_topic_candidates WHERE id=?", (candidate_id,)).fetchone()
        if not row:
            from content_workbench.domain.errors import DomainError
            raise DomainError("TOPIC_CANDIDATE_NOT_FOUND", "推荐选题不存在", 404, "id", "刷新今日推荐后重新选择")
        return {**loads(row["payload_json"], {}), "id": row["id"], "status": row["status"], "created_at": row["created_at"]}

    def mark_candidate_converted(self, candidate_id, task_id):
        candidate = self.get_candidate(candidate_id)
        payload = {key: value for key, value in candidate.items() if key not in ("id", "status", "created_at")}
        payload["task_id"] = task_id
        with self.conn() as conn, immediate(conn):
            conn.execute("UPDATE wb_topic_candidates SET status='converted',payload_json=? WHERE id=?", (dumps(payload), candidate_id))

    def item_dict(self, row, analyses=None):
        metadata = loads(row["metadata_json"], {})
        analyses = analyses or []
        latest = analyses[0] if analyses else None
        return {"id": row["id"], "platform": row["platform"], "url": row["canonical_url"],
                "title": metadata.get("title") or "未读取标题", "metadata": metadata,
                "archived": bool(metadata.get("archived_at")),
                "source_key": metadata.get("source_key"), "first_seen_at": row["first_seen_at"],
                "last_seen_at": row["last_seen_at"], "analysis_status": latest["status"] if latest else "not_started",
                "analysis_id": latest["id"] if latest else None}

    def set_archived(self, item_id, archived):
        self.get_item(item_id)
        return self.update_metadata(item_id, {"archived_at": utcnow() if archived else None})

    def bootstrap(self):
        settings = self.settings()
        mapping = {"featured": settings["featured_collection"], "competitor": settings["competitor_collection"], "high_praise": settings["high_praise_collection"]}
        xhs_mapping = {"xhs_hot": settings["xhs_hot_collection"], "xhs_featured": settings["xhs_featured_collection"],
                       "xhs_competitor": settings["xhs_competitor_collection"], "xhs_high_praise": settings["xhs_high_praise_collection"]}
        with self.conn(readonly=True) as conn:
            rows = [dict(row) for row in conn.execute("SELECT * FROM wb_research_items ORDER BY last_seen_at DESC")]
            analysis_rows = [dict(row) for row in conn.execute("SELECT id,item_id,status,created_at FROM wb_analyses ORDER BY created_at DESC")]
            memberships = [dict(row) for row in conn.execute("""SELECT m.item_id,c.title,c.account_id FROM wb_memberships m JOIN wb_collections c ON c.id=m.collection_id WHERE m.status='present'""")]
            candidates = [dict(row) for row in conn.execute("SELECT * FROM wb_topic_candidates ORDER BY created_at DESC LIMIT 40")]
            sync = conn.execute("SELECT * FROM wb_sync_runs WHERE account_id='source_douyin_main' ORDER BY started_at DESC LIMIT 1").fetchone()
            xhs_sync = conn.execute("SELECT * FROM wb_sync_runs WHERE account_id='source_xiaohongshu_main' ORDER BY started_at DESC LIMIT 1").fetchone()
            account = conn.execute("SELECT * FROM wb_source_accounts WHERE id='source_douyin_main'").fetchone()
        by_item = {}
        for row in analysis_rows:
            by_item.setdefault(row["item_id"], []).append(row)
        grouped = {key: [] for key in SOURCE_KEYS}
        archived = []
        for row in rows:
            item = self.item_dict(row, by_item.get(row["id"]))
            item_memberships = [m for m in memberships if m["item_id"] == row["id"]]
            item["collections"] = [m["title"] for m in item_memberships]
            if item["archived"]:
                archived.append(item)
                continue
            source = item["source_key"]
            if source in ("hot", "industry", "xhs_notes", "wechat_inbox"):
                grouped[source].append(item)
            for key, title in mapping.items():
                if any(m["account_id"] == "source_douyin_main" and m["title"] == title for m in item_memberships) and item not in grouped[key]:
                    grouped[key].append(item)
            for key, title in xhs_mapping.items():
                if any(m["account_id"] == "source_xiaohongshu_main" and m["title"] == title for m in item_memberships) and item not in grouped[key]:
                    grouped[key].append(item)
        if grouped["hot"]:
            grouped["hot"] = sorted(grouped["hot"], key=lambda item: item["last_seen_at"], reverse=True)[:20]
            grouped["hot"].sort(key=lambda item: item["metadata"].get("rank") or 9999)
        recommendations = {"industry": [], "douyin": [], "xiaohongshu": []}
        for row in candidates:
            payload = loads(row["payload_json"], {})
            agent = payload.get("agent")
            if agent in recommendations and len(recommendations[agent]) < 10 and not any(c.get("title") == payload.get("title") for c in recommendations[agent]):
                recommendations[agent].append({**payload, "id": row["id"], "status": row["status"], "created_at": row["created_at"]})
        return {"settings": settings, "sources": grouped, "recommendations": recommendations,
                "archived": archived, "archived_count": len(archived),
                "hot_complete": len(grouped["hot"]) >= 20, "hot_count": len(grouped["hot"]),
                "last_sync": dict(sync) if sync else None, "xhs_last_sync": dict(xhs_sync) if xhs_sync else None,
                "connection": dict(account) if account else {"connection_status": "not_configured"},
                "jobs": [job for job in self.jobs.list() if job["kind"].startswith("topics.") or job["kind"] in ("research.analyze", "research.snapshot")][:20],
                "collection_mapping": mapping, "xhs_collection_mapping": xhs_mapping}

    def get_item(self, item_id):
        with self.conn(readonly=True) as conn:
            row = conn.execute("SELECT * FROM wb_research_items WHERE id=?", (item_id,)).fetchone()
            if not row:
                raise ValueError("研究条目不存在")
            item = self.item_dict(row)
            item["analyses"] = []
            for analysis in conn.execute("SELECT * FROM wb_analyses WHERE item_id=? ORDER BY created_at DESC", (item_id,)):
                value = dict(analysis)
                value["report"] = loads(value.pop("report_json"), {})
                value["evidence"] = [dict(evidence) for evidence in conn.execute("SELECT * FROM wb_evidence WHERE analysis_id=? ORDER BY start_ms", (analysis["id"],))]
                item["analyses"].append(value)
            item["assets"] = [dict(asset) for asset in conn.execute("""SELECT a.*,l.purpose FROM wb_assets a JOIN wb_asset_links l ON l.asset_id=a.id
                WHERE l.owner_type='research_item' AND l.owner_id=?""", (item_id,))]
        if item["analyses"]:
            item["analysis_status"] = item["analyses"][0]["status"]
            item["analysis_id"] = item["analyses"][0]["id"]
        return item


def timestamp_now():
    return utcnow()
