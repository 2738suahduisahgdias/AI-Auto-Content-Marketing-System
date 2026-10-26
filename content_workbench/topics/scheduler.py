import threading
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from content_workbench.agents.registry import agent_config
from content_workbench.jobs.store import JobStore
from content_workbench.storage.db import connect, dumps, immediate, utcnow

SCHEDULE_ID = "topics.daily"


def next_due(daily_time, after=None):
    zone = ZoneInfo("Asia/Shanghai")
    now = (after or datetime.now(timezone.utc)).astimezone(zone)
    hour, minute = [int(value) for value in daily_time.split(":")]
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def configure_schedule(db_path, settings):
    with connect(db_path) as conn, immediate(conn):
        conn.execute("""INSERT INTO wb_schedules(id,kind,expression,timezone,next_due_at,misfire_policy,payload_json,enabled,version)
            VALUES (?,?,?,?,?,?,?,?,1) ON CONFLICT(id) DO UPDATE SET expression=excluded.expression,next_due_at=excluded.next_due_at,
            enabled=excluded.enabled,version=wb_schedules.version+1""",
            (SCHEDULE_ID, "topics.daily", settings["daily_time"], "Asia/Shanghai", next_due(settings["daily_time"]),
             "coalesce_latest", dumps({"agent": "daily_topics"}), int(settings["daily_enabled"])))


class TopicScheduler:
    def __init__(self, db_path):
        self.db_path = str(db_path)
        self.jobs = JobStore(db_path)
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self.run, name="topic-scheduler", daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(2)

    def run(self):
        while not self.stop_event.is_set():
            try:
                self.tick()
            except Exception as error:
                print("topic scheduler error:", repr(error), flush=True)
            self.stop_event.wait(30)

    def tick(self):
        if not agent_config(self.db_path, "workflow_agent")["enabled"]:
            return 0
        with connect(self.db_path) as conn:
            due = conn.execute("SELECT * FROM wb_schedules WHERE id=? AND enabled=1 AND next_due_at<=?", (SCHEDULE_ID, utcnow())).fetchone()
        if not due:
            return 0
        due_at = due["next_due_at"]
        created = []
        for kind, input_data in (("topics.sync", {}), ("topics.industry", {"agent": "industry"}),
                                 ("topics.recommend", {"agent": "industry"}), ("topics.recommend", {"agent": "douyin"})):
            job = self.jobs.enqueue(kind, input_data, SCHEDULE_ID, "schedule:{}:{}:{}".format(SCHEDULE_ID, due_at, kind + str(input_data)), resource_key="topics")
            created.append(job["id"])
        with connect(self.db_path) as conn, immediate(conn):
            conn.execute("INSERT OR IGNORE INTO wb_schedule_runs VALUES (?,?,?,?)", (SCHEDULE_ID, due_at, created[0], utcnow()))
            conn.execute("UPDATE wb_schedules SET next_due_at=?,version=version+1 WHERE id=?", (next_due(due["expression"]), SCHEDULE_ID))
        return len(created)
