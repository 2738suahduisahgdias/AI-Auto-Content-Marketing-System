from datetime import datetime, timedelta, timezone

from content_workbench.domain.errors import DomainError
from content_workbench.domain.services import Workbench
from content_workbench.storage.db import connect, dumps, immediate, loads, new_id, payload_hash, utcnow


def at(seconds=0):
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class JobStore:
    def __init__(self, db_path=None):
        self.db_path = str(db_path) if db_path else None

    def conn(self, readonly=False):
        return connect(self.db_path, readonly=readonly)

    def enqueue(self, kind, input_data, aggregate_id=None, idempotency_key=None, scope=None,
                max_attempts=3, resource_key=None, available_at=None):
        key = idempotency_key or new_id("request")
        scope = scope or kind
        body_hash = payload_hash(input_data)
        with self.conn() as conn, immediate(conn):
            existing = conn.execute("SELECT * FROM wb_jobs WHERE idempotency_scope=? AND idempotency_key=?", (scope, key)).fetchone()
            if existing:
                if existing["input_hash"] != body_hash:
                    raise DomainError("IDEMPOTENCY_CONFLICT", "同一幂等键对应了不同输入", 409, "Idempotency-Key", "使用新的请求键")
                return self.job_dict(existing)
            job_id = new_id("job")
            timestamp = utcnow()
            conn.execute("""INSERT INTO wb_jobs
                (id,kind,aggregate_id,status,stage,progress,input_json,input_hash,route_revision_id,idempotency_scope,idempotency_key,
                 priority,available_at,lease_owner,lease_expires_at,fencing_token,attempt_count,max_attempts,resource_key,
                 blocked_reason,error_json,result_json,cancel_requested_at,created_at,updated_at)
                VALUES (?,?,?,'queued','queued',0,?,?,NULL,?,?,0,?,NULL,NULL,0,0,?,?,NULL,NULL,NULL,NULL,?,?)""",
                (job_id, kind, aggregate_id, dumps(input_data), body_hash, scope, key,
                 available_at or timestamp, max_attempts, resource_key or kind, timestamp, timestamp))
            Workbench.event(conn, "job", job_id, "job.queued", {"kind": kind, "aggregate_id": aggregate_id})
            row = conn.execute("SELECT * FROM wb_jobs WHERE id=?", (job_id,)).fetchone()
            return self.job_dict(row)

    @staticmethod
    def job_dict(row):
        value = dict(row)
        value["input"] = loads(value.pop("input_json"), {})
        value["error"] = loads(value.pop("error_json"), None)
        value["result"] = loads(value.pop("result_json"), None)
        return value

    def get(self, job_id):
        with self.conn(readonly=True) as conn:
            row = conn.execute("SELECT * FROM wb_jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                raise DomainError("JOB_NOT_FOUND", "任务不存在", 404, item=job_id)
            result = self.job_dict(row)
            result["attempts"] = [dict(attempt) for attempt in conn.execute("SELECT * FROM wb_attempts WHERE job_id=? ORDER BY attempt_no", (job_id,))]
            return result

    def list(self, limit=100):
        with self.conn(readonly=True) as conn:
            return [self.job_dict(row) for row in conn.execute("SELECT * FROM wb_jobs ORDER BY created_at DESC LIMIT ?", (min(limit, 200),))]

    def lease(self, owner, lease_seconds=90):
        with self.conn() as conn, immediate(conn):
            now = utcnow()
            row = conn.execute("""SELECT * FROM wb_jobs WHERE
                (status IN ('queued','retry_wait') AND available_at<=?)
                OR (status IN ('leased','running','cancel_requested') AND lease_expires_at IS NOT NULL AND lease_expires_at<?)
                ORDER BY priority DESC,created_at LIMIT 1""", (now, now)).fetchone()
            if not row:
                return None
            if row["attempt_count"] >= row["max_attempts"]:
                conn.execute("UPDATE wb_jobs SET status='failed',error_json=?,updated_at=? WHERE id=?",
                             (dumps({"code": "ATTEMPTS_EXHAUSTED", "message": "任务重试次数已用完"}), now, row["id"]))
                return None
            token = row["fencing_token"] + 1
            attempt_no = row["attempt_count"] + 1
            expires = at(lease_seconds)
            conn.execute("""UPDATE wb_jobs SET status='leased',lease_owner=?,lease_expires_at=?,fencing_token=?,
                attempt_count=?,stage='leased',updated_at=? WHERE id=?""",
                (owner, expires, token, attempt_no, now, row["id"]))
            conn.execute("""INSERT INTO wb_attempts
                (id,job_id,attempt_no,fencing_token,status,provider_id,model_id,submission_intent_json,provider_request_id,
                 provider_job_id,request_fingerprint,usage_json,started_at,finished_at,error_json)
                VALUES (?,?,?,?,'leased',NULL,NULL,NULL,NULL,NULL,NULL,NULL,?,NULL,NULL)""",
                (new_id("attempt"), row["id"], attempt_no, token, now))
            Workbench.event(conn, "job", row["id"], "job.leased", {"owner": owner, "fencing_token": token, "attempt": attempt_no})
            leased = conn.execute("SELECT * FROM wb_jobs WHERE id=?", (row["id"],)).fetchone()
            return self.job_dict(leased)

    def assert_lease(self, job_id, owner, token):
        with self.conn(readonly=True) as conn:
            row = conn.execute("SELECT * FROM wb_jobs WHERE id=?", (job_id,)).fetchone()
            if not row or row["lease_owner"] != owner or row["fencing_token"] != token:
                raise DomainError("FENCING_REJECTED", "旧 worker 无权提交此任务", 409, item=job_id)
            if row["status"] == "cancel_requested":
                raise DomainError("JOB_CANCELLED", "任务已取消", 409, item=job_id)
            return self.job_dict(row)

    def heartbeat(self, job_id, owner, token, stage=None, progress=None):
        with self.conn() as conn, immediate(conn):
            row = conn.execute("SELECT status FROM wb_jobs WHERE id=? AND lease_owner=? AND fencing_token=?", (job_id, owner, token)).fetchone()
            if not row:
                raise DomainError("FENCING_REJECTED", "任务租约已失效", 409, item=job_id)
            if row["status"] == "cancel_requested":
                raise DomainError("JOB_CANCELLED", "任务已取消", 409, item=job_id)
            conn.execute("""UPDATE wb_jobs SET status='running',stage=COALESCE(?,stage),progress=COALESCE(?,progress),
                lease_expires_at=?,updated_at=? WHERE id=?""", (stage, progress, at(90), utcnow(), job_id))

    def finish(self, job_id, owner, token, result=None, error=None, status="succeeded", retry_delay=None):
        with self.conn() as conn, immediate(conn):
            row = conn.execute("SELECT * FROM wb_jobs WHERE id=?", (job_id,)).fetchone()
            if not row or row["lease_owner"] != owner or row["fencing_token"] != token:
                raise DomainError("FENCING_REJECTED", "拒绝旧 worker 的结果提交", 409, item=job_id)
            timestamp = utcnow()
            if status == "retry_wait":
                available = at(retry_delay or 2)
                conn.execute("""UPDATE wb_jobs SET status='retry_wait',stage='retry_wait',error_json=?,available_at=?,
                    lease_owner=NULL,lease_expires_at=NULL,updated_at=? WHERE id=?""", (dumps(error), available, timestamp, job_id))
            else:
                conn.execute("""UPDATE wb_jobs SET status=?,stage=?,progress=?,error_json=?,result_json=?,lease_owner=NULL,
                    lease_expires_at=NULL,updated_at=? WHERE id=?""",
                    (status, "succeeded" if status == "succeeded" else "failed" if status == "failed" else status,
                     1 if status == "succeeded" else row["progress"], dumps(error) if error else None,
                     dumps(result) if result is not None else None, timestamp, job_id))
            conn.execute("""UPDATE wb_attempts SET status=?,finished_at=?,error_json=?,usage_json=COALESCE(usage_json,?) WHERE
                job_id=? AND attempt_no=? AND fencing_token=?""",
                (status, timestamp, dumps(error) if error else None, dumps({}), job_id, row["attempt_count"], token))
            Workbench.event(conn, "job", job_id, "job." + status, {"error": error, "result": result})
            return self.get(job_id)

    def cancel(self, job_id):
        with self.conn() as conn, immediate(conn):
            row = conn.execute("SELECT * FROM wb_jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                raise DomainError("JOB_NOT_FOUND", "任务不存在", 404, item=job_id)
            if row["status"] in ("succeeded", "failed", "cancelled"):
                return self.job_dict(row)
            status = "cancelled" if row["status"] in ("queued", "retry_wait") else "cancel_requested"
            conn.execute("UPDATE wb_jobs SET status=?,cancel_requested_at=?,updated_at=? WHERE id=?", (status, utcnow(), utcnow(), job_id))
            Workbench.event(conn, "job", job_id, "job." + status, {})
            return self.get(job_id)

    def retry(self, job_id):
        with self.conn() as conn, immediate(conn):
            row = conn.execute("SELECT * FROM wb_jobs WHERE id=?", (job_id,)).fetchone()
            if not row or row["status"] not in ("failed", "cancelled", "blocked"):
                raise DomainError("JOB_NOT_RETRYABLE", "当前任务不能重试；unknown_remote 必须先对账", 409, item=job_id)
            conn.execute("""UPDATE wb_jobs SET status='queued',stage='queued',available_at=?,error_json=NULL,cancel_requested_at=NULL,
                lease_owner=NULL,lease_expires_at=NULL,updated_at=? WHERE id=?""", (utcnow(), utcnow(), job_id))
            return self.get(job_id)

    def events(self, after=0, aggregate_id=None):
        query = "SELECT * FROM wb_events WHERE sequence>?"
        values = [after]
        if aggregate_id:
            query += " AND aggregate_id=?"
            values.append(aggregate_id)
        query += " ORDER BY sequence LIMIT 500"
        with self.conn(readonly=True) as conn:
            result = []
            for row in conn.execute(query, values):
                item = dict(row)
                item["payload"] = loads(item.pop("payload_json"), {})
                result.append(item)
            return result
