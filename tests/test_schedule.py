import subprocess
import tempfile
import unittest
from collections import Counter
from datetime import datetime
from pathlib import Path
from unittest import mock

from content_workbench.domain.errors import DomainError
from content_workbench.jobs.store import JobStore
from content_workbench.jobs.worker import Worker
from content_workbench.publishing.executors import PublishingExecutors
from content_workbench.publishing.service import PublishingService
from content_workbench.schedule import ScheduleService
from content_workbench.storage.db import connect, expand_schema


class ScheduleCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="schedule-test-")
        self.root = Path(self.temp.name).resolve()
        self.db = self.root / "test.db"
        with connect(self.db) as conn:
            expand_schema(conn)
            conn.execute("""CREATE TABLE tasks(
                content_id TEXT PRIMARY KEY,title TEXT NOT NULL,state TEXT NOT NULL,
                scripts_json TEXT NOT NULL DEFAULT '{}',updated_at TEXT NOT NULL)""")
            conn.execute("""CREATE TABLE files(
                id INTEGER PRIMARY KEY,content_id TEXT NOT NULL,kind TEXT NOT NULL,
                relative_path TEXT NOT NULL)""")
        self.publishing = PublishingService(self.db, self.root)
        self.service = ScheduleService(self.db, self.root, publishing=self.publishing)
        self.jobs = JobStore(self.db)
        self.video_no = 0

    def tearDown(self):
        self.temp.cleanup()

    def make_batch(self, platforms=("douyin", "xiaohongshu"), ready=True):
        self.video_no += 1
        video_id = "video-{}".format(self.video_no)
        relative = "renders/{}/video.mp4".format(video_id)
        path = self.root / relative
        path.parent.mkdir(parents=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=360x640:d=1",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], check=True, capture_output=True)
        with connect(self.db) as conn:
            conn.execute("INSERT INTO tasks VALUES (?,?,'approved','{}','2026-10-27')", (video_id, "已批准视频 " + video_id))
            conn.execute("INSERT INTO files(content_id,kind,relative_path) VALUES (?,'video',?)", (video_id, relative))
        targets = [{"platform": platform, "payload": {"title": "视频标题", "description": "视频简介", "tags": "#AI"}}
                   for platform in platforms]
        batch = self.publishing.create_batch("video", video_id, targets)
        if ready:
            for target in batch["targets"]:
                self.publishing.set_target_result(target["id"], "ready", {"fields_verified": ["title", "description"]})
            batch = self.publishing.get_batch(batch["id"])
        return batch

    @staticmethod
    def request(batch, target_ids=None):
        value = {"batch_id": batch["id"], "source_hash": batch["source_hash"]}
        if target_ids is not None:
            value["target_ids"] = target_ids
        return value

    def create(self, batches, **kwargs):
        settings = {"first_run_at": "2026-01-01T10:00:00Z", "interval_minutes": 30, "daily_limit": 20}
        settings.update(kwargs)
        return self.service.create_schedule([self.request(batch) for batch in batches], **settings)

    def test_requires_preview_current_human_confirmation_and_supported_platform(self):
        unready = self.make_batch(platforms=("douyin",), ready=False)
        with self.assertRaises(DomainError) as caught:
            self.create([unready])
        self.assertEqual("PUBLISH_PREVIEW_REQUIRED", caught.exception.code)
        ready = self.make_batch(platforms=("douyin",))
        request = self.request(ready)
        request["source_hash"] = "stale"
        with self.assertRaises(DomainError) as caught:
            self.service.create_schedule([request], "2026-01-01T10:00:00Z")
        self.assertEqual("PUBLISH_CONFIRMATION_STALE", caught.exception.code)
        channels = self.make_batch(platforms=("wechat_channels",))
        schedule = self.create([channels])
        self.assertEqual("wechat_channels", schedule["queue"][0]["platform"])
        self.service.cancel_schedule(schedule["id"])
        with connect(self.db, readonly=True) as conn:
            self.assertEqual(1, conn.execute("SELECT COUNT(*) FROM publish_schedules").fetchone()[0])
            self.assertEqual([], conn.execute("PRAGMA foreign_key_check").fetchall())

    def test_video_platform_rows_are_independent_and_confirmation_is_recorded(self):
        first = self.make_batch()
        second = self.make_batch(platforms=("douyin",))
        schedule = self.create([first, second], actor="reviewer-1")
        self.assertEqual("active", schedule["status"])
        self.assertEqual(3, len(schedule["queue"]))
        self.assertEqual({("video-1", "douyin"), ("video-1", "xiaohongshu"), ("video-2", "douyin")},
                         {(row["video_id"], row["platform"]) for row in schedule["queue"]})
        self.assertEqual(schedule["queue"][0]["scheduled_for"], schedule["next_run_at"])
        self.assertTrue(all(row["status"] == "queued" and row["job_id"] is None for row in schedule["queue"]))
        confirmed = self.publishing.get_batch(first["id"])
        self.assertEqual("reviewer-1", confirmed["confirmed_by"])
        self.assertIsNotNone(confirmed["confirmed_at"])
        self.assertTrue(all(target["status"] == "publishing" for target in confirmed["targets"]))
        with connect(self.db, readonly=True) as conn:
            self.assertEqual(0, conn.execute("SELECT COUNT(*) FROM wb_jobs WHERE kind='publish.execute'").fetchone()[0])

    def test_slots_keep_global_interval_and_daily_limit_across_midnight(self):
        batches = [self.make_batch() for _ in range(3)]
        schedule = self.create(batches, first_run_at="2026-01-01T23:30:00Z", interval_minutes=45, daily_limit=2)
        times = [datetime.fromisoformat(row["scheduled_for"].replace("Z", "+00:00")) for row in schedule["queue"]]
        counts = Counter(value.date() for value in times)
        self.assertTrue(all(value <= 2 for value in counts.values()), counts)
        gaps = [(later - earlier).total_seconds() for earlier, later in zip(times, times[1:])]
        self.assertTrue(all(gap >= 45 * 60 for gap in gaps), gaps)
        self.assertEqual("2026-01-01T23:30:00.000Z", schedule["queue"][0]["scheduled_for"])
        self.assertEqual("2026-01-02T00:15:00.000Z", schedule["queue"][1]["scheduled_for"])

    def test_create_and_dispatch_are_idempotent(self):
        batch = self.make_batch(platforms=("douyin",))
        requests = [self.request(batch)]
        first = self.service.create_schedule(requests, "2026-01-01T10:00:00Z", idempotency_key="schedule-request-1")
        repeated = self.service.create_schedule(requests, "2026-01-01T10:00:00Z", idempotency_key="schedule-request-1")
        self.assertEqual(first["id"], repeated["id"])
        with self.assertRaises(DomainError) as caught:
            self.service.create_schedule(requests, "2026-01-01T11:00:00Z", idempotency_key="schedule-request-1")
        self.assertEqual("IDEMPOTENCY_CONFLICT", caught.exception.code)
        with self.assertRaises(DomainError):
            self.service.create_schedule(requests, "2026-01-01T10:00:00Z", idempotency_key="schedule-request-2")
        self.assertEqual([], self.service.due_jobs("2026-01-01T09:59:59Z"))
        due = self.service.due_jobs("2026-01-01T10:00:00Z")
        again = self.service.due_jobs("2026-01-01T10:00:00Z")
        self.assertEqual(1, len(due))
        self.assertEqual([due[0]["id"]], [job["id"] for job in again])
        self.assertEqual("publish.execute", due[0]["kind"])
        self.assertEqual(1, due[0]["max_attempts"])
        with connect(self.db, readonly=True) as conn:
            self.assertEqual(1, conn.execute("SELECT COUNT(*) FROM publish_schedules").fetchone()[0])
            self.assertEqual(1, conn.execute("SELECT COUNT(*) FROM publish_queue").fetchone()[0])
            self.assertEqual(1, conn.execute("SELECT COUNT(*) FROM wb_jobs").fetchone()[0])

    def test_actual_dispatch_daily_limit_and_pause_are_enforced(self):
        batches = [self.make_batch() for _ in range(3)]
        schedule = self.create(batches, first_run_at="2026-01-01T20:00:00Z", interval_minutes=30, daily_limit=2)
        paused = self.service.update_schedule(schedule["id"], status="paused")
        self.assertIsNone(paused["next_run_at"])
        self.assertEqual([], self.service.due_jobs("2026-01-05T00:00:00Z"))
        self.service.update_schedule(schedule["id"], status="active")
        first = self.service.due_jobs("2026-01-05T00:00:00Z")
        second = self.service.due_jobs("2026-01-06T00:00:00Z")
        third = self.service.due_jobs("2026-01-07T00:00:00Z")
        self.assertEqual([2, 4, 6], [len(first), len(second), len(third)])
        with connect(self.db, readonly=True) as conn:
            self.assertEqual(6, conn.execute("SELECT COUNT(DISTINCT job_id) FROM publish_queue").fetchone()[0])
            self.assertEqual([2, 2, 2], [row[0] for row in conn.execute(
                "SELECT COUNT(*) FROM publish_queue GROUP BY dispatch_day ORDER BY dispatch_day")])

    def test_due_job_runs_through_existing_worker_and_publishing_executor(self):
        batch = self.make_batch(platforms=("douyin",))
        schedule = self.create([batch])
        job = self.service.due_jobs("2026-01-01T10:00:00Z")[0]
        executor = PublishingExecutors(self.publishing)
        worker = Worker(self.db, executor.mapping(), self.root)
        with mock.patch.object(executor, "run", return_value={"status": "published", "published_evidence": "test-only", "url": None}) as run:
            leased = self.jobs.lease(worker.owner)
            self.assertEqual(job["id"], leased["id"])
            worker.execute(leased)
        self.assertEqual("execute", run.call_args.args[1])
        self.assertEqual("succeeded", self.jobs.get(job["id"])["status"])
        self.assertEqual("published", self.publishing.target(batch["targets"][0]["id"])[1]["status"])
        completed = self.service.get_schedule(schedule["id"])
        self.assertEqual("completed", completed["status"])
        self.assertEqual("published", completed["queue"][0]["status"])
        self.assertIsNone(completed["next_run_at"])

    def make_mixed_schedule(self):
        batches = [self.make_batch() for _ in range(2)]
        schedule = self.create(batches)
        self.service.due_jobs("2026-01-02T00:00:00Z")
        statuses = {schedule["queue"][0]["target_id"]: "running",
                    schedule["queue"][1]["target_id"]: "published",
                    schedule["queue"][2]["target_id"]: "unknown_remote"}
        for _ in range(3):
            leased = self.jobs.lease("schedule-test-worker")
            status = statuses[leased["aggregate_id"]]
            if status == "running":
                self.jobs.heartbeat(leased["id"], "schedule-test-worker", leased["fencing_token"], "running")
                continue
            self.jobs.finish(leased["id"], "schedule-test-worker", leased["fencing_token"],
                             status="succeeded" if status == "published" else status,
                             result={"status": status} if status == "published" else None,
                             error={"code": "UNKNOWN_REMOTE"} if status == "unknown_remote" else None)
            self.publishing.set_target_result(leased["aggregate_id"], status, {"test_only": True})
        return schedule, batches

    def test_update_only_reschedules_queued_and_updates_existing_wb_job(self):
        schedule, _ = self.make_mixed_schedule()
        before = self.service.get_schedule(schedule["id"])
        self.assertEqual(["running", "published", "unknown_remote", "queued"], [row["status"] for row in before["queue"]])
        protected = {row["id"]: (row["status"], row["scheduled_for"]) for row in before["queue"][:3]}
        queued_job_id = before["queue"][3]["job_id"]
        updated = self.service.update_schedule(schedule["id"], first_run_at="2026-02-01T12:00:00Z",
                                               interval_minutes=90, daily_limit=2)
        for row in updated["queue"][:3]:
            self.assertEqual(protected[row["id"]], (row["status"], row["scheduled_for"]))
        self.assertNotEqual(before["queue"][3]["scheduled_for"], updated["queue"][3]["scheduled_for"])
        self.assertEqual(updated["queue"][3]["scheduled_for"], self.jobs.get(queued_job_id)["available_at"])
        self.assertEqual(updated["queue"][3]["scheduled_for"], updated["next_run_at"])
        paused = self.service.update_schedule(schedule["id"], status="paused")
        self.assertEqual("9999-12-31T23:59:59.000Z", self.jobs.get(queued_job_id)["available_at"])
        self.assertEqual(protected, {row["id"]: (row["status"], row["scheduled_for"]) for row in paused["queue"][:3]})
        resumed = self.service.update_schedule(schedule["id"], status="active")
        self.assertEqual(resumed["queue"][3]["scheduled_for"], self.jobs.get(queued_job_id)["available_at"])

    def test_cancel_only_cancels_queued_and_preserves_other_states(self):
        schedule, _ = self.make_mixed_schedule()
        before = self.service.get_schedule(schedule["id"])
        cancelled = self.service.cancel_schedule(schedule["id"])
        self.assertEqual("cancelled", cancelled["status"])
        self.assertIsNone(cancelled["next_run_at"])
        self.assertEqual(["running", "published", "unknown_remote", "cancelled"], [row["status"] for row in cancelled["queue"]])
        for index in range(3):
            self.assertEqual(before["queue"][index]["scheduled_for"], cancelled["queue"][index]["scheduled_for"])
        self.assertEqual("cancelled", self.jobs.get(before["queue"][3]["job_id"])["status"])
        self.assertEqual("ready", self.publishing.target(before["queue"][3]["target_id"])[1]["status"])
        self.assertEqual("publishing", self.publishing.target(before["queue"][0]["target_id"])[1]["status"])
        with self.assertRaises(DomainError) as caught:
            self.service.cancel_schedule(schedule["id"])
        self.assertEqual("SCHEDULE_NOTHING_CANCELLABLE", caught.exception.code)
        with self.assertRaises(DomainError):
            self.service.update_schedule(schedule["id"], interval_minutes=15)

    def test_invalid_settings_and_empty_selection_are_rejected(self):
        batch = self.make_batch(platforms=("douyin",))
        for field, value in (("interval_minutes", 0), ("daily_limit", -1), ("interval_minutes", True)):
            with self.subTest(field=field, value=value):
                with self.assertRaises(DomainError) as caught:
                    self.service.create_schedule([self.request(batch)], "2026-01-01T10:00:00Z", **{field: value})
                self.assertEqual("SCHEDULE_SETTING_INVALID", caught.exception.code)
        with self.assertRaises(DomainError):
            self.service.create_schedule([], "2026-01-01T10:00:00Z")
        with self.assertRaises(DomainError) as caught:
            self.service.create_schedule([self.request(batch)], "not-a-time")
        self.assertEqual("SCHEDULE_TIME_INVALID", caught.exception.code)


if __name__ == "__main__":
    unittest.main()
