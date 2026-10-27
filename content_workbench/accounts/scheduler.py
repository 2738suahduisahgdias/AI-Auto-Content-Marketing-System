from content_workbench.jobs.store import JobStore
from content_workbench.storage.db import connect, dumps, immediate, utcnow
from content_workbench.topics.scheduler import TopicScheduler, next_due

SCHEDULE_ID = "accounts.daily"


def configure_account_schedule(db_path, enabled=True, daily_time="09:30"):
    with connect(db_path) as conn, immediate(conn):
        conn.execute("""INSERT INTO wb_schedules VALUES (?,?,?,?,?,?,?,?,1) ON CONFLICT(id) DO UPDATE SET
            expression=excluded.expression,next_due_at=excluded.next_due_at,enabled=excluded.enabled,version=wb_schedules.version+1""",
            (SCHEDULE_ID, "accounts.daily", daily_time, "Asia/Shanghai", next_due(daily_time), "coalesce_latest", dumps({"kind": "account_daily"}), int(enabled)))


def tick_accounts(db_path):
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM wb_schedules WHERE id=? AND enabled=1 AND next_due_at<=?", (SCHEDULE_ID, utcnow())).fetchone()
    if not row:
        return None
    jobs = JobStore(db_path)
    job = jobs.enqueue("accounts.daily", {}, SCHEDULE_ID, "schedule:{}:{}".format(SCHEDULE_ID, row["next_due_at"]), resource_key="browser")
    with connect(db_path) as conn, immediate(conn):
        conn.execute("INSERT OR IGNORE INTO wb_schedule_runs VALUES (?,?,?,?)", (SCHEDULE_ID, row["next_due_at"], job["id"], utcnow()))
        conn.execute("UPDATE wb_schedules SET next_due_at=?,version=version+1 WHERE id=?", (next_due(row["expression"]), SCHEDULE_ID))
    return job["id"]


class AccountScheduler(TopicScheduler):
    def tick(self):
        return tick_accounts(self.db_path)
