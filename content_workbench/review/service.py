import shutil
from pathlib import Path

from content_workbench.domain.errors import DomainError
from content_workbench.jobs.store import JobStore
from content_workbench.storage.db import PROJECT_ROOT, connect, dumps, file_hash, immediate, loads, new_id, utcnow
from .schemas import DEFAULT_RULES, VIDEO_EXTENSIONS, validate_rules


class ReviewService:
    def __init__(self, db_path, root):
        self.db_path = str(db_path)
        self.root = Path(root).resolve()
        self.jobs = JobStore(db_path)
        self.ensure_schema()

    def conn(self, readonly=False):
        return connect(self.db_path, readonly=readonly)

    def ensure_schema(self):
        with self.conn() as conn:
            conn.executescript((PROJECT_ROOT / "migrations/004_review.sql").read_text())

    def get_batch(self, batch_id):
        with self.conn(readonly=True) as conn:
            row = conn.execute("SELECT * FROM review_batches WHERE id=?", (batch_id,)).fetchone()
            if not row:
                raise DomainError("REVIEW_BATCH_NOT_FOUND", "审核批次不存在", 404, "batch_id", "重新选择文件夹或上传视频", batch_id)
            batch = dict(row)
            items = [dict(item) for item in conn.execute("SELECT * FROM review_items WHERE batch_id=? ORDER BY source_path", (batch_id,))]
        batch["rules"] = loads(batch.pop("rules_json"), {})
        batch["items"] = []
        for item in items:
            item["report"] = loads(item.pop("report_json"), {})
            item["ai_risk"] = loads(item.pop("ai_risk_json"), {})
            item["error"] = loads(item.pop("error_json"), None)
            batch["items"].append(item)
        batch["counts"] = self.counts(items)
        return batch

    @staticmethod
    def counts(items):
        result = {"total": len(items), "queued": 0, "reviewing": 0, "needs_review": 0, "approved": 0, "rejected": 0, "failed": 0}
        for item in items:
            result[item["status"]] = result.get(item["status"], 0) + 1
        return result

    def latest(self, batch_id=None):
        if batch_id:
            return self.get_batch(batch_id)
        with self.conn(readonly=True) as conn:
            row = conn.execute("SELECT id FROM review_batches ORDER BY created_at DESC LIMIT 1").fetchone()
        return self.get_batch(row[0]) if row else None

    def bootstrap(self, batch_id=None):
        batch = self.latest(batch_id)
        return {"batch": batch, "default_rules": DEFAULT_RULES,
                "jobs": [job for job in self.jobs.list() if job["kind"].startswith("review.")][:30]}

    def create_batch(self, folder, rules, allow_empty=False):
        rules = validate_rules(rules)
        folder = Path(str(folder or "")).expanduser().resolve()
        if not folder.is_dir():
            raise DomainError("REVIEW_FOLDER_NOT_FOUND", "视频文件夹不存在", 404, "folder", "选择真实存在且可读取的文件夹 A")
        paths = sorted(path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS)
        if not paths and not allow_empty:
            raise DomainError("REVIEW_FOLDER_EMPTY", "文件夹中没有支持的视频", 422, "folder", "放入 MP4、MOV、WebM 或 MKV 后重试")
        if len(paths) > 50:
            raise DomainError("REVIEW_BATCH_TOO_LARGE", "每批最多审核 50 个视频", 422, "folder", "分批选择视频")
        batch_id = new_id("review")
        timestamp = utcnow()
        with self.conn() as conn, immediate(conn):
            conn.execute("INSERT INTO review_batches VALUES (?,?,?,?,?,?)", (batch_id, str(folder), dumps(rules), "queued", timestamp, timestamp))
            for path in paths:
                if path.stat().st_size > 2 * 1024 ** 3:
                    raise DomainError("REVIEW_FILE_TOO_LARGE", path.name + " 超过 2GB", 413, "folder", "先压缩过大的视频")
                conn.execute("INSERT INTO review_items VALUES (?,?,?,?,'queued','pending','{}','{}',NULL,NULL,NULL,?,?)",
                             (new_id("reviewitem"), batch_id, str(path), file_hash(path), timestamp, timestamp))
        return self.get_batch(batch_id)

    def create_upload_batch(self, rules):
        folder = self.root / "data/review-uploads" / new_id("review")
        folder.mkdir(parents=True, exist_ok=False)
        return self.create_batch(folder, rules, allow_empty=True)

    def add_upload(self, batch_id, filename, data):
        batch = self.get_batch(batch_id)
        expected = (self.root / "data/review-uploads").resolve()
        folder = Path(batch["source_folder"]).resolve()
        if expected not in folder.parents or folder == expected:
            raise DomainError("REVIEW_UPLOAD_BATCH_INVALID", "该批次不是上传批次", 409, "batch_id", "重新创建上传批次")
        name = Path(filename or "").name
        if not name or Path(name).suffix.lower() not in VIDEO_EXTENSIONS:
            raise DomainError("REVIEW_UPLOAD_TYPE_INVALID", "仅支持 MP4、MOV、WebM 或 MKV", 422, "filename", "选择有效视频文件")
        if not data or len(data) > 2 * 1024 ** 3:
            raise DomainError("REVIEW_FILE_TOO_LARGE", "视频为空或超过 2GB", 413, "file", "选择不超过 2GB 的视频")
        path = (folder / name).resolve()
        if folder not in path.parents:
            raise DomainError("REVIEW_UPLOAD_PATH_INVALID", "上传文件名无效", 422, "filename", "只提供文件名")
        path.write_bytes(data)
        timestamp = utcnow()
        with self.conn() as conn, immediate(conn):
            conn.execute("INSERT INTO review_items VALUES (?,?,?,?,'queued','pending','{}','{}',NULL,NULL,NULL,?,?)",
                         (new_id("reviewitem"), batch_id, str(path), file_hash(path), timestamp, timestamp))
        return self.get_batch(batch_id)

    def start(self, batch_id):
        batch = self.get_batch(batch_id)
        items = [item for item in batch["items"] if item["status"] in ("queued", "needs_review", "failed") and item["decision"] != "approved"]
        if not items:
            raise DomainError("REVIEW_NOTHING_TO_SCAN", "没有需要机器预审的视频", 409, "batch_id", "上传新视频或修改规则后重新审核")
        with self.conn() as conn, immediate(conn):
            conn.execute("UPDATE review_batches SET status='reviewing',updated_at=? WHERE id=?", (utcnow(), batch_id))
            conn.execute("UPDATE review_items SET status='reviewing',error_json=NULL,updated_at=? WHERE batch_id=? AND decision!='approved'", (utcnow(), batch_id))
        job = self.jobs.enqueue("review.scan", {"batch_id": batch_id}, batch_id, resource_key="media_review")
        if batch["rules"].get("ai_risk", True):
            self.jobs.enqueue("review.ai", {"batch_id": batch_id}, batch_id, resource_key="cloud_text")
        return job

    def decide(self, item_id, decision):
        if decision not in ("approved", "rejected"):
            raise DomainError("REVIEW_DECISION_INVALID", "人工决定仅支持通过或驳回", 422, "decision", "明确选择通过或驳回")
        with self.conn(readonly=True) as conn:
            item = conn.execute("SELECT * FROM review_items WHERE id=?", (item_id,)).fetchone()
        if not item:
            raise DomainError("REVIEW_ITEM_NOT_FOUND", "审核视频不存在", 404, "item_id", "刷新审核批次", item_id)
        report = loads(item["report_json"], {})
        if not report:
            raise DomainError("REVIEW_REQUIRED", "必须先完成机器预审", 409, "item_id", "先运行机器预审再人工终审", item_id)
        if decision == "approved" and any(issue.get("severity") == "error" for issue in report.get("issues", [])):
            raise DomainError("REVIEW_ERRORS_UNRESOLVED", "仍有阻断审核的问题，不能直接通过", 409, "item_id", "先修复错误项并重新审核；警告可由人工判断", item_id)
        status = decision
        output = item["output_path"]
        if decision == "approved":
            source = Path(item["candidate_path"] or item["source_path"]).resolve()
            if not source.is_file():
                raise DomainError("REVIEW_CANDIDATE_MISSING", "审核候选文件不存在", 409, "item_id", "重新上传或转码后终审")
            directory = Path(item["source_path"]).parent / "审核通过"
            directory.mkdir(exist_ok=True)
            output_path = (directory / Path(item["source_path"]).name).resolve()
            if output_path != source:
                shutil.copy2(source, output_path)
            output = str(output_path)
        timestamp = utcnow()
        with self.conn() as conn, immediate(conn):
            conn.execute("UPDATE review_items SET decision=?,status=?,output_path=?,updated_at=? WHERE id=?",
                         (decision, status, output, timestamp, item_id))
            conn.execute("UPDATE review_batches SET status='completed',updated_at=? WHERE id=(SELECT batch_id FROM review_items WHERE id=?)",
                         (timestamp, item_id))
        return output

    def repair(self, item_id):
        with self.conn(readonly=True) as conn:
            item = conn.execute("SELECT * FROM review_items WHERE id=?", (item_id,)).fetchone()
        if not item or not loads(item["report_json"], {}).get("safe_transcode_candidate", {}).get("eligible"):
            raise DomainError("REVIEW_TRANSCODE_UNAVAILABLE", "该视频不能安全转码", 409, "item_id", "先完成媒体解析；黑帧和静音需要人工剪辑")
        job = self.jobs.enqueue("review.repair", {"item_id": item_id}, item_id, resource_key="media_review")
        with self.conn() as conn, immediate(conn):
            conn.execute("UPDATE review_items SET status='reviewing',decision='pending',output_path=NULL,updated_at=? WHERE id=?",
                         (utcnow(), item_id))
        return job

    def source_for_publish(self, item_id):
        with self.conn(readonly=True) as conn:
            item = conn.execute("SELECT * FROM review_items WHERE id=?", (item_id,)).fetchone()
        if not item or item["decision"] != "approved" or not item["output_path"]:
            raise DomainError("REVIEW_APPROVAL_REQUIRED", "视频尚未人工审核通过", 409, "item_id", "先在审核中心完成人工终审", item_id)
        path = Path(item["output_path"]).resolve()
        if not path.is_file():
            raise DomainError("REVIEW_OUTPUT_MISSING", "审核通过文件不存在", 409, "item_id", "重新审核并生成输出文件")
        report = loads(item["report_json"], {})
        return {"kind": "video", "source_id": item_id, "source_hash": file_hash(path), "title": path.stem,
                "description": path.stem, "revision_id": item["source_sha256"], "video_path": str(path),
                "absolute_video_path": str(path), "review_report": report}
