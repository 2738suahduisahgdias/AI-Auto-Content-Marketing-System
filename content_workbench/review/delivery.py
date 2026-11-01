"""Link Yingxu deliveries to existing review items; no separate review workflow."""
from pathlib import Path
from content_workbench.domain.errors import DomainError
from content_workbench.storage.db import dumps, loads, file_hash, immediate, new_id, utcnow
from .schemas import validate_rules

class DeliveryReviewMixin:
    def ensure_delivery_schema(self, conn):
        conn.execute("""CREATE TABLE IF NOT EXISTS review_deliveries (
            item_id TEXT PRIMARY KEY,content_id TEXT NOT NULL,file_id INTEGER NOT NULL,
            revision INTEGER NOT NULL,source_sha256 TEXT NOT NULL,output_sha256 TEXT,
            UNIQUE(content_id,file_id,revision,source_sha256))""")

    def delivery(self, item_id, conn=None):
        if conn is not None:
            row = conn.execute("SELECT * FROM review_deliveries WHERE item_id=?", (item_id,)).fetchone()
            return dict(row) if row else None
        with self.conn(readonly=True) as db:
            return self.delivery(item_id, db)

    def assert_delivery(self, binding, conn=None):
        if not binding:
            return None
        if conn is None:
            with self.conn(readonly=True) as db:
                return self.assert_delivery(binding, db)
        task = conn.execute("SELECT * FROM tasks WHERE content_id=?", (binding["content_id"],)).fetchone()
        source = loads(task["source_json"], {}) if task else {}
        handoff = source.get("yingxu_handoff", {})
        if handoff.get("stale") or any(handoff.get(key) != binding[other] for key, other in
                (("file_id", "file_id"), ("revision", "revision"), ("file_sha256", "source_sha256"))):
            raise DomainError("DELIVERY_STALE", "制作或交付版本已变化，请返回映序重新交付并审核", 409)
        file = conn.execute("SELECT * FROM files WHERE id=? AND content_id=? AND kind='video'", (binding["file_id"], binding["content_id"])).fetchone()
        path = (self.root / file["relative_path"]).resolve() if file else None
        if not path or self.root not in path.parents or not path.is_file() or file_hash(path) != binding["source_sha256"]:
            raise DomainError("DELIVERY_FILE_CHANGED", "交付成片缺失或已变更，请重新交付", 409)
        return dict(task)

    def receive_delivery(self, content_id):
        with self.conn() as conn, immediate(conn):
            task = conn.execute("SELECT * FROM tasks WHERE content_id=?", (content_id,)).fetchone()
            if not task:
                raise DomainError("DELIVERY_TASK_MISSING", "原视频任务不存在", 404)
            source = loads(task["source_json"], {})
            handoff = source.get("yingxu_handoff", {})
            if not handoff or handoff.get("stale"):
                raise DomainError("DELIVERY_REQUIRED", "请先从映序交付当前成片", 409)
            binding = {"content_id": content_id, "file_id": handoff["file_id"], "revision": handoff["revision"], "source_sha256": handoff["file_sha256"]}
            self.assert_delivery(binding, conn)
            existing = conn.execute("SELECT i.batch_id,d.item_id FROM review_deliveries d JOIN review_items i ON i.id=d.item_id WHERE d.content_id=? AND d.file_id=? AND d.revision=? AND d.source_sha256=?",
                (content_id, binding["file_id"], binding["revision"], binding["source_sha256"])).fetchone()
            if existing:
                batch_id, item_id = existing["batch_id"], existing["item_id"]
            else:
                file = conn.execute("SELECT * FROM files WHERE id=?", (binding["file_id"],)).fetchone()
                path = (self.root / file["relative_path"]).resolve()
                snapshot = source.get("yingxu", {}).get("snapshot", {})
                import re
                size = re.search(r"(\d+)\s*[×x]\s*(\d+)", str(snapshot.get("format", "")))
                rules = validate_rules({"target_width":int(size[1]) if size else 1080, "target_height":int(size[2]) if size else 1920,
                                        "check_ocr":False, "ai_risk":False})
                batch_id, item_id, timestamp = new_id("review"), new_id("reviewitem"), utcnow()
                conn.execute("INSERT INTO review_batches VALUES (?,?,?,?,?,?)", (batch_id,str(path.parent),dumps(rules),"queued",timestamp,timestamp))
                conn.execute("INSERT INTO review_items VALUES (?,?,?,?,'queued','pending','{}','{}',NULL,NULL,NULL,?,?)", (item_id,batch_id,str(path),binding["source_sha256"],timestamp,timestamp))
                conn.execute("INSERT INTO review_deliveries VALUES (?,?,?,?,?,NULL)", (item_id,content_id,binding["file_id"],binding["revision"],binding["source_sha256"]))
            handoff.update({"review_batch_id":batch_id,"review_item_id":item_id})
            conn.execute("UPDATE tasks SET source_json=? WHERE content_id=?", (dumps(source),content_id))
        return self.get_batch(batch_id)

    def delivery_state(self, item_id):
        binding = self.delivery(item_id)
        if not binding:
            return None
        try:
            task = self.assert_delivery(binding)
            return {**binding,"title":task["title"],"stale":False}
        except DomainError as exc:
            return {**binding,"stale":True,"reason":exc.message}

    def record_delivery_decision(self, conn, item_id, decision, output):
        binding = self.delivery(item_id, conn)
        if not binding:
            return
        task = self.assert_delivery(binding, conn)
        source = loads(task["source_json"], {})
        source["yingxu_handoff"]["status"] = "approved" if decision == "approved" else "rejected"
        conn.execute("UPDATE tasks SET source_json=? WHERE content_id=?", (dumps(source),binding["content_id"]))
        conn.execute("UPDATE review_deliveries SET output_sha256=? WHERE item_id=?", (file_hash(output) if decision == "approved" else None,item_id))

    def approved_sources(self):
        with self.conn(readonly=True) as conn:
            ids = [row[0] for row in conn.execute("SELECT id FROM review_items WHERE decision='approved' ORDER BY updated_at DESC")]
        result = []
        for item_id in ids:
            try:
                result.append(self.source_for_publish(item_id))
            except DomainError:
                continue
        return result
