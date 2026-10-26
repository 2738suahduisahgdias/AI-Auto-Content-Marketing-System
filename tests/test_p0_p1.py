import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path

from content_workbench.domain.errors import DomainError
from content_workbench.domain.services import Workbench
from content_workbench.domain.workflow_registry import workflow_bootstrap
from content_workbench.jobs.store import JobStore
from content_workbench.jobs.worker import UnknownRemote, Worker
from content_workbench.providers.local import LocalExecutors
from content_workbench.storage.db import PROJECT_ROOT, connect, expand_schema, immediate
from content_workbench.storage.migrate import migrate

BACKUP = PROJECT_ROOT / "data/backups/p0-p1-20261026T072556Z/source.db"
SRT = "1\n00:00:00,000 --> 00:00:01,800\n测试字幕\n\n"


class Case(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="workbench-test-")
        self.root = Path(self.temp.name)
        self.db = self.root / "test.db"
        with connect(self.db) as conn:
            expand_schema(conn)
        self.wb = Workbench(self.db, self.root)
        self.store = JobStore(self.db)

    def tearDown(self):
        self.temp.cleanup()

    def article(self):
        item = self.wb.create_item("article", "wechat_official_account", "独立文章", {"text": "共同 brief"})
        self.wb.save_revision(item["id"], "outline", {"text": "一、方法"}, item["version"])
        item = self.wb.get_item(item["id"])
        draft = self.wb.save_revision(item["id"], "draft", {"text": "完整正文", "format": "markdown"}, item["version"])
        return self.wb.get_item(item["id"]), draft

    def audio(self, name="a.wav", seconds=2):
        path = self.root / name
        frequency = 440 if name.startswith("a") else 660
        subprocess.run([shutil.which("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency={}:duration={}".format(frequency, seconds),
                        "-ac", "1", "-ar", "44100", str(path)], check=True, timeout=30)
        return self.wb.register_asset(path, {"kind": "test_audio"}, "owned")

    def subtitle_asset(self):
        path = self.root / "subtitle.srt"
        path.write_text(SRT, encoding="utf-8")
        return self.wb.register_asset(path, {"kind": "test_subtitle"}, "owned")

    def video(self, matching=True):
        item = self.wb.create_item("video", "douyin", "独立视频", {"text": "视频 brief"})
        script = self.wb.save_revision(item["id"], "script", {"text": "只生成抖音口播"}, item["version"])
        item = self.wb.get_item(item["id"])
        audio_a = self.audio("a.wav")
        audio_b = self.audio("b.wav")
        self.wb.add_asset_revision(item["id"], "audio", audio_a, item["version"])
        item = self.wb.get_item(item["id"])
        subtitle = self.subtitle_asset()
        source = audio_a if matching else audio_b
        self.wb.add_asset_revision(item["id"], "subtitle", subtitle, item["version"], source, {"provider": "faster_whisper", "model": "base"})
        return self.wb.get_item(item["id"]), script, audio_a, audio_b, subtitle

    def test_a01_registry_bootstrap_contract(self):
        workflows = workflow_bootstrap()
        self.assertEqual({"article", "video"}, set(workflows))
        self.assertIn("draft", workflows["article"]["stages"][2]["states"])
        self.assertNotIn("audio", workflows["article"]["stages"][0]["id"])

    def test_a02_real_backup_migration_twice(self):
        if not BACKUP.is_file():
            self.skipTest("真实备份不存在")
        target = self.root / "migration.db"
        first = migrate(BACKUP, target, "test-real-backup")
        second = migrate(BACKUP, target, "test-real-backup")
        self.assertGreater(first["changed"], 0)
        self.assertEqual(0, second["changed"])
        self.assertEqual(first["verification"]["source_tasks"], second["verification"]["mapped_campaigns"])
        self.assertEqual("ok", second["verification"]["integrity_check"])
        self.assertEqual([], second["verification"]["foreign_key_errors"])
        with connect(target, readonly=True) as conn:
            self.assertEqual(first["verification"]["revisions"], conn.execute("SELECT COUNT(*) FROM wb_revisions").fetchone()[0])
            self.assertEqual(first["verification"]["events"], conn.execute("SELECT COUNT(*) FROM wb_events").fetchone()[0])

    def test_a03_article_independent_full_flow(self):
        item, draft = self.article()
        video = self.wb.create_item("video", "douyin", "兄弟视频")
        video_state = video["state"]
        item = self.wb.submit_review(item["id"], item["version"])
        item = self.wb.approve(item["id"], draft, item["manifest"]["hash"])
        item, export = self.wb.export_article(item["id"], draft, item["version"])
        self.assertEqual("exported", item["state"])
        self.assertTrue(revision_asset(item, export, "markdown_asset_id"))
        item = self.wb.record_publication(item["id"], draft, "https://example.com/article-1")
        self.assertEqual("published", item["state"])
        self.assertEqual(video_state, self.wb.get_item(video["id"])["state"])
        self.assertFalse(any(kind in item["active_revisions"] for kind in ("audio", "subtitle", "render")))

    def test_a04_video_requires_only_current_platform_script(self):
        item = self.wb.create_item("video", "douyin", "只要抖音稿")
        revision = self.wb.save_revision(item["id"], "script", {"text": "独立抖音稿"}, item["version"])
        item = self.wb.get_item(item["id"])
        self.assertEqual("script_draft", item["state"])
        self.assertEqual([revision], [value for kind, value in item["active_revisions"].items() if kind == "script"])
        self.assertNotIn("draft", item["active_revisions"])
        self.assertNotIn("wechat_channels", json.dumps(item["active_revisions"]))

    def test_a05_mismatch_rejected_and_matching_real_render(self):
        item, *_ = self.video(matching=False)
        with self.assertRaises(DomainError) as caught:
            self.wb.validate_render(item["id"])
        self.assertEqual("SUBTITLE_AUDIO_MISMATCH", caught.exception.code)
        self.assertEqual(422, caught.exception.status)
        item, script, audio, _, subtitle = self.video(matching=True)
        manifest = self.wb.validate_render(item["id"])
        self.assertEqual(audio, manifest["audio_asset_id"])
        (self.root / "remotion-app").symlink_to(PROJECT_ROOT / "remotion-app", target_is_directory=True)
        job = self.store.enqueue("video.render", {"expected_version": item["version"], "manifest": manifest}, item["id"], "render-a05")
        worker = Worker(self.db, LocalExecutors(self.wb).mapping(), self.root)
        leased = self.store.lease(worker.owner)
        worker.execute(leased)
        result = self.store.get(job["id"])
        self.assertEqual("succeeded", result["status"], result.get("error"))
        rendered = self.wb.get_item(item["id"])
        self.assertIn("render", rendered["active_revisions"])
        render_revision = revision(rendered, "render")
        info = render_revision["payload"]["metadata"]["media_info"]
        self.assertTrue(any(stream["codec_type"] == "audio" for stream in info["streams"]))
        self.assertTrue(any(stream["codec_type"] == "video" for stream in info["streams"]))

    def test_a06_subtitle_edit_preserves_source_and_history(self):
        item, _, audio, _, _ = self.video()
        old_id = item["active_revisions"]["subtitle"]
        edited = self.wb.edit_subtitle(item["id"], old_id, SRT.replace("测试字幕", "人工校对"), item["version"])
        new_id = edited["active_revisions"]["subtitle"]
        self.assertNotEqual(old_id, new_id)
        new = self.wb.get_revision(new_id)
        old = self.wb.get_revision(old_id)
        self.assertEqual(audio, new["source_audio_asset_id"])
        self.assertEqual("base", new["payload"]["metadata"]["model"])
        self.assertTrue(new["payload"]["metadata"]["edited"])
        self.assertEqual(old_id, new["payload"]["metadata"]["edited_from_revision_id"])
        self.assertEqual("valid", old["validity"])

    def test_a07_job_survives_reader_refresh(self):
        started = threading.Event()
        def slow(job, context):
            started.set()
            time.sleep(0.4)
            return {"done": True}
        worker = Worker(self.db, {"test.slow": slow}, self.root, poll_interval=0.02)
        job = self.store.enqueue("test.slow", {}, idempotency_key="refresh")
        worker.start()
        self.assertTrue(started.wait(2))
        other_connection_view = JobStore(self.db).get(job["id"])
        self.assertIn(other_connection_view["status"], ("leased", "running"))
        deadline = time.time() + 3
        while JobStore(self.db).get(job["id"])["status"] != "succeeded" and time.time() < deadline:
            time.sleep(0.03)
        worker.stop()
        self.assertEqual("succeeded", self.store.get(job["id"])["status"])

    def test_a08_expired_lease_and_fencing_rejected(self):
        job = self.store.enqueue("test.fence", {}, idempotency_key="fence")
        first = self.store.lease("old-worker", lease_seconds=-1)
        second = self.store.lease("new-worker")
        self.assertGreater(second["fencing_token"], first["fencing_token"])
        with self.assertRaises(DomainError) as caught:
            self.store.finish(job["id"], "old-worker", first["fencing_token"], result={"bad": True})
        self.assertEqual("FENCING_REJECTED", caught.exception.code)

    def test_a09_remote_id_reused_after_worker_restart(self):
        job = self.store.enqueue("remote.fake", {}, idempotency_key="remote-recovery")
        first = self.store.lease("remote-old", lease_seconds=-1)
        with self.store.conn() as conn, immediate(conn):
            conn.execute("UPDATE wb_attempts SET provider_job_id='remote-123',status='running' WHERE job_id=? AND attempt_no=?", (job["id"], first["attempt_count"]))
        submissions = []
        def resume(leased, context):
            with self.store.conn(readonly=True) as conn:
                remote = conn.execute("SELECT provider_job_id FROM wb_attempts WHERE job_id=? AND provider_job_id IS NOT NULL ORDER BY attempt_no DESC LIMIT 1", (job["id"],)).fetchone()[0]
            if not remote:
                submissions.append("submitted")
                return {"remote": "new"}
            return {"remote": remote, "resumed": True}
        worker = Worker(self.db, {"remote.fake": resume}, self.root)
        second = self.store.lease(worker.owner)
        worker.execute(second)
        self.assertEqual([], submissions)
        self.assertEqual("remote-123", self.store.get(job["id"])["result"]["remote"])

    def test_a10_unknown_remote_never_auto_resubmits(self):
        def unknown(job, context):
            raise UnknownRemote("提交结果未知，禁止重提")
        job = self.store.enqueue("remote.unknown", {}, idempotency_key="unknown")
        worker = Worker(self.db, {"remote.unknown": unknown}, self.root)
        worker.execute(self.store.lease(worker.owner))
        self.assertEqual("unknown_remote", self.store.get(job["id"])["status"])
        with self.assertRaises(DomainError):
            self.store.retry(job["id"])

    def test_a26_cas_conflict_does_not_overwrite(self):
        item, _ = self.article()
        stale_version = item["version"]
        self.wb.save_revision(item["id"], "draft", {"text": "窗口 A 新正文"}, stale_version)
        with self.assertRaises(DomainError) as caught:
            self.wb.save_revision(item["id"], "draft", {"text": "窗口 B 覆盖"}, stale_version)
        self.assertEqual("VERSION_CONFLICT", caught.exception.code)
        current = self.wb.get_item(item["id"])
        active = current["revisions"][next(index for index, value in enumerate(current["revisions"]) if value["id"] == current["active_revisions"]["draft"])]
        self.assertEqual("窗口 A 新正文", active["payload"]["text"])

    def test_cancel_terminates_local_process(self):
        job = self.store.enqueue("test.process", {}, idempotency_key="cancel")
        worker = Worker(self.db, {"test.process": lambda job, context: context.run_process(["/bin/sleep", "20"], timeout=30)}, self.root)
        leased = self.store.lease(worker.owner)
        timer = threading.Timer(0.4, lambda: self.store.cancel(job["id"]))
        timer.start()
        started = time.monotonic()
        worker.execute(leased)
        timer.cancel()
        self.assertLess(time.monotonic() - started, 5)
        self.assertEqual("cancelled", self.store.get(job["id"])["status"])


def revision(item, kind):
    revision_id = item["active_revisions"][kind]
    return next(value for value in item["revisions"] if value["id"] == revision_id)


def revision_asset(item, revision_id, key):
    value = next(value for value in item["revisions"] if value["id"] == revision_id)
    return value["payload"].get(key)


if __name__ == "__main__":
    unittest.main()
