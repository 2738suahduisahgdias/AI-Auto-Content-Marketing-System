from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from content_workbench.domain.errors import DomainError
from content_workbench.jobs.store import JobStore
from content_workbench.publishing.schemas import prepare_supported
from content_workbench.publishing.service import PublishingService
from content_workbench.storage.db import connect, immediate, new_id, payload_hash, utcnow


class ScheduleService:
    def __init__(self, db_path, root, publishing=None):
        self.db_path = str(db_path)
        self.root = Path(root).resolve()
        self.publishing = publishing or PublishingService(db_path, self.root)
        self.jobs = self.publishing.jobs if publishing else JobStore(db_path)
        self.ensure_schema()

    def conn(self, readonly=False):
        return connect(self.db_path, readonly=readonly)

    def ensure_schema(self):
        migration = Path(__file__).resolve().parent / "migrations/005_publish_schedule.sql"
        with self.conn() as conn:
            conn.executescript(migration.read_text(encoding="utf-8"))

    @staticmethod
    def _datetime(value, field="first_run_at"):
        if isinstance(value, datetime):
            parsed = value
        else:
            try:
                parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except (TypeError, ValueError):
                raise DomainError("SCHEDULE_TIME_INVALID", "排期时间不是有效的 ISO 时间", 422, field, "提供带时区的 ISO 时间")
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @classmethod
    def _time(cls, value, field="first_run_at"):
        return cls._datetime(value, field).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    @staticmethod
    def _positive(value, field):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise DomainError("SCHEDULE_SETTING_INVALID", field + " 必须是正整数", 422, field, "填写大于零的整数")
        return value

    @staticmethod
    def _requests(value):
        if not isinstance(value, list) or not value:
            raise DomainError("SCHEDULE_BATCHES_REQUIRED", "至少选择一个已预览视频批次", 422, "batches", "选择需要定时发布的视频和平台")
        result = []
        for item in value:
            if not isinstance(item, dict) or not item.get("batch_id") or not item.get("source_hash"):
                raise DomainError("SCHEDULE_CONFIRMATION_REQUIRED", "每个视频批次都需要内容版本确认", 422, "batches", "刷新预览并确认当前 source_hash")
            target_ids = item.get("target_ids")
            if target_ids is not None and (not isinstance(target_ids, list) or not target_ids or
                                           any(not isinstance(target_id, str) or not target_id for target_id in target_ids)):
                raise DomainError("SCHEDULE_TARGETS_INVALID", "target_ids 必须是非空字符串数组", 422, "target_ids", "选择批次中的平台")
            result.append({"batch_id": item["batch_id"], "source_hash": item["source_hash"],
                           "target_ids": list(target_ids) if target_ids is not None else None})
        return result

    @staticmethod
    def _slots(first_run_at, interval_minutes, daily_limit, count):
        first = ScheduleService._datetime(first_run_at)
        interval = timedelta(minutes=interval_minutes)
        first_time = time(first.hour, first.minute, first.second, first.microsecond, tzinfo=timezone.utc)
        candidate = first
        previous = None
        per_day = {}
        result = []
        for _ in range(count):
            if previous is not None:
                candidate = max(candidate, previous + interval)
            while per_day.get(candidate.date(), 0) >= daily_limit:
                next_day = candidate.date() + timedelta(days=1)
                candidate = datetime.combine(next_day, first_time)
                if previous is not None:
                    candidate = max(candidate, previous + interval)
            per_day[candidate.date()] = per_day.get(candidate.date(), 0) + 1
            result.append(candidate.isoformat(timespec="milliseconds").replace("+00:00", "Z"))
            previous = candidate
            candidate = candidate + interval
        return result

    def create_schedule(self, batches, first_run_at, interval_minutes=30, daily_limit=20,
                        actor="local_user", idempotency_key=None):
        requests = self._requests(batches)
        first_run_at = self._time(first_run_at)
        interval_minutes = self._positive(interval_minutes, "interval_minutes")
        daily_limit = self._positive(daily_limit, "daily_limit")
        key = idempotency_key or new_id("request")
        request_hash = payload_hash({"batches": requests, "first_run_at": first_run_at,
                                     "interval_minutes": interval_minutes, "daily_limit": daily_limit})
        with self.conn(readonly=True) as conn:
            existing = conn.execute("SELECT * FROM publish_schedules WHERE idempotency_key=?", (key,)).fetchone()
        if existing:
            if existing["request_hash"] != request_hash:
                raise DomainError("IDEMPOTENCY_CONFLICT", "同一幂等键对应了不同排期", 409, "Idempotency-Key", "使用新的请求键")
            return self.get_schedule(existing["id"])

        planned = []
        seen_targets = set()
        seen_platforms = set()
        for request in requests:
            batch = self.publishing.get_batch(request["batch_id"])
            if batch["content_kind"] != "video":
                raise DomainError("SCHEDULE_KIND_INVALID", "定时发布目前仅支持视频", 422, "batch_id", "选择已批准的视频批次")
            if request["source_hash"] != batch["source_hash"]:
                raise DomainError("PUBLISH_CONFIRMATION_STALE", "确认的内容版本已变化", 409, "source_hash", "刷新并重新确认当前版本")
            self.publishing.assert_current(batch)
            by_id = {target["id"]: target for target in batch["targets"]}
            if request["target_ids"] is None:
                selected = batch["targets"]
            else:
                missing = [target_id for target_id in request["target_ids"] if target_id not in by_id]
                if missing:
                    raise DomainError("PUBLISH_TARGET_NOT_FOUND", "平台发布目标不存在或不属于该批次", 404, "target_ids", "刷新发布批次", missing[0])
                selected = [by_id[target_id] for target_id in request["target_ids"]]
            if not selected:
                raise DomainError("PUBLISH_TARGETS_REQUIRED", "没有可定时发布的平台", 422, "target_ids", "选择批次中的平台")
            for target in selected:
                pair = (batch["source_id"], target["platform"])
                if target["id"] in seen_targets or pair in seen_platforms:
                    raise DomainError("SCHEDULE_DUPLICATE_TARGET", "同一视频和平台不能重复排期", 409, "target_ids", "每个视频平台只保留一个队列项")
                if target["status"] != "ready":
                    raise DomainError("PUBLISH_PREVIEW_REQUIRED", "只有完成机器预审并等待确认的平台可以排期", 409, "target_ids", "先成功生成平台预览", target["id"])
                if not prepare_supported(target["platform"]):
                    raise DomainError("PUBLISH_CONNECTOR_PENDING", "该平台尚未完成发布字段验证", 409, "platform", "不要为未验证平台创建发布任务")
                seen_targets.add(target["id"])
                seen_platforms.add(pair)
                planned.append({"batch_id": batch["id"], "video_id": batch["source_id"],
                                "target_id": target["id"], "platform": target["platform"]})

        schedule_id = new_id("schedule")
        timestamp = utcnow()
        slots = self._slots(first_run_at, interval_minutes, daily_limit, len(planned))
        existing_id = None
        with self.conn() as conn, immediate(conn):
            existing = conn.execute("SELECT * FROM publish_schedules WHERE idempotency_key=?", (key,)).fetchone()
            if existing:
                if existing["request_hash"] != request_hash:
                    raise DomainError("IDEMPOTENCY_CONFLICT", "同一幂等键对应了不同排期", 409, "Idempotency-Key", "使用新的请求键")
                existing_id = existing["id"]
            else:
                for item in planned:
                    duplicate = conn.execute("""SELECT 1 FROM publish_queue WHERE target_id=?
                        AND status IN ('queued','running','unknown_remote')""", (item["target_id"],)).fetchone()
                    target = conn.execute("SELECT status FROM publish_targets WHERE id=?", (item["target_id"],)).fetchone()
                    if duplicate:
                        raise DomainError("SCHEDULE_DUPLICATE_TARGET", "该平台已有有效排期，不能重复创建", 409, "target_ids", "修改或取消原排期", item["target_id"])
                    if not target or target["status"] != "ready":
                        raise DomainError("PUBLISH_PREVIEW_REQUIRED", "平台预览状态已变化，请重新确认", 409, "target_ids", "刷新预览后重试", item["target_id"])
                conn.execute("""INSERT INTO publish_schedules
                    (id,first_run_at,interval_minutes,daily_limit,status,next_run_at,idempotency_key,request_hash,created_at,updated_at)
                    VALUES (?,?,?,?,'active',?,?,?,?,?)""",
                    (schedule_id, first_run_at, interval_minutes, daily_limit, slots[0], key, request_hash, timestamp, timestamp))
                for position, (item, scheduled_for) in enumerate(zip(planned, slots)):
                    conn.execute("""INSERT INTO publish_queue
                        (id,schedule_id,batch_id,target_id,video_id,platform,position,scheduled_for,status,job_id,dispatched_at,dispatch_day,created_at,updated_at)
                        VALUES (?,?,?,?,?,?,?,?,'queued',NULL,NULL,NULL,?,?)""",
                        (new_id("pubqueue"), schedule_id, item["batch_id"], item["target_id"], item["video_id"],
                         item["platform"], position, scheduled_for, timestamp, timestamp))
                for batch_id in dict.fromkeys(item["batch_id"] for item in planned):
                    conn.execute("UPDATE publish_batches SET confirmed_by=?,confirmed_at=?,updated_at=? WHERE id=?",
                                 (actor, timestamp, timestamp, batch_id))
                for item in planned:
                    changed = conn.execute("""UPDATE publish_targets SET status='publishing',error_json=NULL,updated_at=?
                        WHERE id=? AND status='ready'""", (timestamp, item["target_id"]))
                    if changed.rowcount != 1:
                        raise DomainError("PUBLISH_PREVIEW_REQUIRED", "平台预览状态已变化，请重新确认", 409, "target_ids", "刷新预览后重试", item["target_id"])
        if existing_id:
            return self.get_schedule(existing_id)
        for batch_id in dict.fromkeys(item["batch_id"] for item in planned):
            self.publishing.update_batch_status(batch_id)
        return self.get_schedule(schedule_id)

    def _get_schedule(self, conn, schedule_id):
        row = conn.execute("SELECT * FROM publish_schedules WHERE id=?", (schedule_id,)).fetchone()
        if not row:
            raise DomainError("SCHEDULE_NOT_FOUND", "发布排期不存在", 404, "schedule_id", "刷新排期列表", schedule_id)
        result = dict(row)
        result["queue"] = [dict(item) for item in conn.execute(
            "SELECT * FROM publish_queue WHERE schedule_id=? ORDER BY position", (schedule_id,))]
        return result

    def get_schedule(self, schedule_id):
        self._sync_jobs(schedule_id)
        with self.conn(readonly=True) as conn:
            return self._get_schedule(conn, schedule_id)

    def list_schedules(self):
        with self.conn(readonly=True) as conn:
            ids = [row[0] for row in conn.execute("SELECT id FROM publish_schedules ORDER BY created_at DESC")]
        for schedule_id in ids:
            self._sync_jobs(schedule_id)
        with self.conn(readonly=True) as conn:
            return [self._get_schedule(conn, schedule_id) for schedule_id in ids]

    @staticmethod
    def _queue_status(job_status):
        if job_status in ("leased", "running", "cancel_requested"):
            return "running"
        if job_status == "succeeded":
            return "published"
        if job_status == "unknown_remote":
            return "unknown_remote"
        if job_status == "failed":
            return "failed"
        if job_status == "cancelled":
            return "cancelled"
        return "queued"

    def _refresh(self, conn, schedule_id, timestamp=None):
        row = conn.execute("SELECT status FROM publish_schedules WHERE id=?", (schedule_id,)).fetchone()
        if not row:
            return
        status = row["status"]
        next_run = None
        if status == "active":
            next_row = conn.execute("""SELECT MIN(scheduled_for) FROM publish_queue
                WHERE schedule_id=? AND status='queued'""", (schedule_id,)).fetchone()
            next_run = next_row[0]
            counts = conn.execute("""SELECT
                SUM(status='queued') AS queued,
                SUM(status IN ('running','unknown_remote')) AS unfinished,
                COUNT(*) AS total FROM publish_queue WHERE schedule_id=?""", (schedule_id,)).fetchone()
            if counts["total"] and not counts["queued"] and not counts["unfinished"]:
                status = "completed"
        conn.execute("UPDATE publish_schedules SET status=?,next_run_at=?,updated_at=? WHERE id=?",
                     (status, next_run, timestamp or utcnow(), schedule_id))

    def _sync_jobs(self, schedule_id=None):
        query = "SELECT id,schedule_id,job_id,status FROM publish_queue WHERE job_id IS NOT NULL"
        values = []
        if schedule_id:
            query += " AND schedule_id=?"
            values.append(schedule_id)
        with self.conn(readonly=True) as conn:
            rows = [dict(row) for row in conn.execute(query, values)]
        if not rows:
            if schedule_id:
                with self.conn(readonly=True) as conn:
                    exists = conn.execute("SELECT 1 FROM publish_schedules WHERE id=?", (schedule_id,)).fetchone()
                if not exists:
                    raise DomainError("SCHEDULE_NOT_FOUND", "发布排期不存在", 404, "schedule_id", "刷新排期列表", schedule_id)
            return
        by_job = {row["job_id"]: row for row in rows}
        with self.conn() as conn, immediate(conn):
            jobs = conn.execute("SELECT id,status FROM wb_jobs WHERE id IN ({})".format(",".join("?" * len(by_job))),
                                tuple(by_job)).fetchall()
            timestamp = utcnow()
            affected = set()
            for job in jobs:
                item = by_job[job["id"]]
                status = self._queue_status(job["status"])
                if item["status"] != status:
                    conn.execute("UPDATE publish_queue SET status=?,updated_at=? WHERE id=?",
                                 (status, timestamp, item["id"]))
                    affected.add(item["schedule_id"])
            for item_schedule in affected:
                self._refresh(conn, item_schedule, timestamp)

    def update_schedule(self, schedule_id, first_run_at=None, interval_minutes=None, daily_limit=None, status=None):
        if status not in (None, "active", "paused"):
            raise DomainError("SCHEDULE_STATUS_INVALID", "排期只能手动设为 active 或 paused", 422, "status", "使用取消接口终止待执行项")
        self._sync_jobs(schedule_id)
        with self.conn() as conn, immediate(conn):
            current = conn.execute("SELECT * FROM publish_schedules WHERE id=?", (schedule_id,)).fetchone()
            if not current:
                raise DomainError("SCHEDULE_NOT_FOUND", "发布排期不存在", 404, "schedule_id", "刷新排期列表", schedule_id)
            if current["status"] in ("completed", "cancelled"):
                raise DomainError("SCHEDULE_NOT_MODIFIABLE", "已完成或已取消的排期不能修改", 409, "status", "创建新的排期", schedule_id)
            first = self._time(first_run_at) if first_run_at is not None else current["first_run_at"]
            interval = self._positive(interval_minutes, "interval_minutes") if interval_minutes is not None else current["interval_minutes"]
            limit = self._positive(daily_limit, "daily_limit") if daily_limit is not None else current["daily_limit"]
            new_status = status or current["status"]
            queued = conn.execute("SELECT id,position,job_id FROM publish_queue WHERE schedule_id=? AND status='queued'", (schedule_id,)).fetchall()
            count = conn.execute("SELECT COUNT(*) FROM publish_queue WHERE schedule_id=?", (schedule_id,)).fetchone()[0]
            slots = self._slots(first, interval, limit, count)
            timestamp = utcnow()
            for item in queued:
                available_at = slots[item["position"]]
                changed = conn.execute("""UPDATE publish_queue SET scheduled_for=?,updated_at=?
                    WHERE id=? AND status='queued'""", (available_at, timestamp, item["id"]))
                if changed.rowcount == 1 and item["job_id"]:
                    job_available_at = "9999-12-31T23:59:59.000Z" if new_status == "paused" else available_at
                    conn.execute("""UPDATE wb_jobs SET available_at=?,updated_at=?
                        WHERE id=? AND status IN ('queued','retry_wait')""", (job_available_at, timestamp, item["job_id"]))
            conn.execute("""UPDATE publish_schedules SET first_run_at=?,interval_minutes=?,daily_limit=?,status=?,updated_at=?
                WHERE id=?""", (first, interval, limit, new_status, timestamp, schedule_id))
            self._refresh(conn, schedule_id, timestamp)
        return self.get_schedule(schedule_id)

    def cancel_schedule(self, schedule_id):
        self._sync_jobs(schedule_id)
        cancelled = 0
        with self.conn() as conn, immediate(conn):
            schedule = conn.execute("SELECT status FROM publish_schedules WHERE id=?", (schedule_id,)).fetchone()
            if not schedule:
                raise DomainError("SCHEDULE_NOT_FOUND", "发布排期不存在", 404, "schedule_id", "刷新排期列表", schedule_id)
            rows = conn.execute("SELECT * FROM publish_queue WHERE schedule_id=? AND status='queued' ORDER BY position", (schedule_id,)).fetchall()
            timestamp = utcnow()
            for item in rows:
                if item["job_id"]:
                    changed = conn.execute("""UPDATE wb_jobs SET status='cancelled',stage='cancelled',
                        error_json=?,cancel_requested_at=?,lease_owner=NULL,lease_expires_at=NULL,updated_at=?
                        WHERE id=? AND status IN ('queued','retry_wait')""",
                        ('{"code":"JOB_CANCELLED","message":"任务已取消"}', timestamp, timestamp, item["job_id"]))
                    if changed.rowcount != 1:
                        continue
                changed = conn.execute("""UPDATE publish_queue SET status='cancelled',updated_at=?
                    WHERE id=? AND status='queued'""", (timestamp, item["id"]))
                if changed.rowcount == 1:
                    cancelled += 1
                    conn.execute("UPDATE publish_targets SET status='ready',updated_at=? WHERE id=? AND status='publishing'",
                                 (timestamp, item["target_id"]))
            if not cancelled:
                raise DomainError("SCHEDULE_NOTHING_CANCELLABLE", "只有待执行队列项可以取消", 409, "status", "运行中、已完成或结果未知的项目保持不变", schedule_id)
            conn.execute("UPDATE publish_schedules SET status='cancelled',next_run_at=NULL,updated_at=? WHERE id=?",
                         (timestamp, schedule_id))
        with self.conn(readonly=True) as conn:
            batch_ids = [row[0] for row in conn.execute("SELECT DISTINCT batch_id FROM publish_queue WHERE schedule_id=?", (schedule_id,))]
        for batch_id in batch_ids:
            self.publishing.update_batch_status(batch_id)
        return self.get_schedule(schedule_id)

    def due_jobs(self, now=None, schedule_id=None, limit=None):
        timestamp = self._time(now or utcnow(), "now")
        day = timestamp[:10]
        if limit is not None:
            self._positive(limit, "limit")
        self._sync_jobs(schedule_id)
        query = """SELECT q.*,s.daily_limit FROM publish_queue q
            JOIN publish_schedules s ON s.id=q.schedule_id
            WHERE s.status='active' AND q.status='queued' AND q.scheduled_for<=?"""
        values = [timestamp]
        if schedule_id:
            query += " AND q.schedule_id=?"
            values.append(schedule_id)
        query += " ORDER BY q.scheduled_for,q.schedule_id,q.position"
        with self.conn(readonly=True) as conn:
            candidates = [dict(row) for row in conn.execute(query, values)]
        result = []
        for item in candidates:
            if limit is not None and len(result) >= limit:
                break
            if item["job_id"]:
                job = self.jobs.get(item["job_id"])
                if job["status"] in ("queued", "retry_wait"):
                    result.append(job)
                continue
            with self.conn(readonly=True) as conn:
                dispatched = conn.execute("SELECT COUNT(*) FROM publish_queue WHERE schedule_id=? AND dispatch_day=?",
                                          (item["schedule_id"], day)).fetchone()[0]
            if dispatched >= item["daily_limit"]:
                continue
            job = self.jobs.enqueue("publish.execute", {"target_id": item["target_id"]}, item["target_id"],
                                    "dispatch", scope="publish.schedule:" + item["id"], max_attempts=1,
                                    resource_key="browser", available_at=item["scheduled_for"])
            linked = False
            with self.conn() as conn, immediate(conn):
                current = conn.execute("""SELECT q.job_id FROM publish_queue q JOIN publish_schedules s ON s.id=q.schedule_id
                    WHERE q.id=? AND q.status='queued' AND q.scheduled_for<=? AND s.status='active'""",
                    (item["id"], timestamp)).fetchone()
                if current and current["job_id"] in (None, job["id"]):
                    dispatched = conn.execute("SELECT COUNT(*) FROM publish_queue WHERE schedule_id=? AND dispatch_day=?",
                                              (item["schedule_id"], day)).fetchone()[0]
                    if dispatched < item["daily_limit"]:
                        changed = conn.execute("""UPDATE publish_queue SET job_id=?,dispatched_at=?,dispatch_day=?,updated_at=?
                            WHERE id=? AND status='queued' AND job_id IS NULL""",
                            (job["id"], timestamp, day, utcnow(), item["id"]))
                        linked = changed.rowcount == 1 or current["job_id"] == job["id"]
            if not linked:
                with self.conn() as conn, immediate(conn):
                    conn.execute("""UPDATE wb_jobs SET status='cancelled',stage='cancelled',updated_at=?
                        WHERE id=? AND idempotency_scope=? AND status IN ('queued','retry_wait')""",
                        (utcnow(), job["id"], "publish.schedule:" + item["id"]))
                continue
            current_job = self.jobs.get(job["id"])
            if current_job["status"] in ("queued", "retry_wait"):
                result.append(current_job)
        self._sync_jobs(schedule_id)
        return result

    create = create_schedule
    get = get_schedule
    list = list_schedules
    update = update_schedule
    cancel = cancel_schedule
