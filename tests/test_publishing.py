import base64
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from content_workbench.domain.errors import DomainError
from content_workbench.domain.services import Workbench
from content_workbench.jobs.worker import UnknownRemote
from content_workbench.publishing.executors import PublishingExecutors
from content_workbench.publishing.service import PublishingService
from content_workbench.storage.db import connect, expand_schema


class PublishingCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="publishing-test-")
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
        self.wb = Workbench(self.db, self.root)
        self.service = PublishingService(self.db, self.root)
        image = self.root / "cover.png"
        image.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="))
        self.cover = self.wb.register_asset(image, {"kind": "cover"}, "owned")
        self.article = self.make_article()
        self.video = self.make_video()

    def tearDown(self):
        self.temp.cleanup()

    def make_article(self):
        item = self.wb.create_item("article", "wechat_official_account", "已批准文章", {"text": "测试需求"})
        self.wb.save_revision(item["id"], "draft", {"text": "真实正文", "format": "markdown"}, item["version"])
        item = self.wb.get_item(item["id"])
        draft = item["active_revisions"]["draft"]
        item = self.wb.approve(item["id"], draft, item["manifest"]["hash"], kind="article")
        return item

    def make_video(self):
        path = self.root / "renders/test/video.mp4"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"video")
        with connect(self.db) as conn:
            conn.execute("INSERT INTO tasks VALUES ('video-1','已批准视频','approved','{}','2026-10-27')")
            conn.execute("INSERT INTO files(content_id,kind,relative_path) VALUES ('video-1','video','renders/test/video.mp4')")
        return "video-1"

    def article_targets(self):
        return [
            {"platform": "wechat_official_account", "payload": {"title": "标题", "author": "老刘", "summary": "摘要", "body": "真实正文", "cover_asset_id": self.cover}},
            {"platform": "xiaohongshu", "payload": {"title": "小红书标题", "body": "真实正文"}},
        ]

    def video_targets(self):
        return [{"platform": "douyin", "payload": {"title": "视频标题", "description": "视频简介", "tags": "#AI"}}]

    def test_article_batch_is_independent_and_validates_fields(self):
        batch = self.service.create_batch("article", self.article["id"], self.article_targets())
        self.assertEqual("draft", batch["status"])
        self.assertEqual(2, len(batch["targets"]))
        with self.assertRaises(DomainError) as caught:
            self.service.create_batch("article", self.article["id"], self.video_targets())
        self.assertEqual("PUBLISH_CONTENT_PLATFORM_MISMATCH", caught.exception.code)
        invalid = self.article_targets()
        invalid[0]["payload"]["title"] = "长" * 65
        with self.assertRaises(DomainError) as caught:
            self.service.create_batch("article", self.article["id"], invalid)
        self.assertEqual("PUBLISH_FIELD_TOO_LONG", caught.exception.code)

    def test_prepare_confirm_and_duplicate_protection(self):
        batch = self.service.create_batch("article", self.article["id"], self.article_targets())
        with self.assertRaises(DomainError):
            self.service.confirm(batch["id"], batch["source_hash"])
        with mock.patch.object(self.service.jobs, "enqueue", side_effect=lambda kind, data, aggregate, *args, **kwargs: {"id": "job-" + kind, "kind": kind}):
            jobs = self.service.prepare(batch["id"], None)
            self.assertEqual(2, len(jobs))
            for target in self.service.get_batch(batch["id"])["targets"]:
                self.service.set_target_result(target["id"], "ready", {"fields_verified": ["title", "body"]})
            jobs = self.service.confirm(batch["id"], batch["source_hash"])
            self.assertEqual(2, len(jobs))
        confirmed = self.service.get_batch(batch["id"])
        self.assertIsNotNone(confirmed["confirmed_at"])
        self.assertTrue(all(target["status"] == "publishing" for target in confirmed["targets"]))
        for target in confirmed["targets"]:
            self.service.set_target_result(target["id"], "published", {"published_evidence": "success"})
        self.assertEqual("published", self.service.get_batch(batch["id"])["status"])
        with self.assertRaises(DomainError) as caught:
            self.service.create_batch("article", self.article["id"], self.article_targets())
        self.assertEqual("PUBLISH_ALREADY_RECORDED", caught.exception.code)

    def test_content_change_invalidates_old_preview(self):
        batch = self.service.create_batch("article", self.article["id"], self.article_targets())
        target = batch["targets"][0]
        self.service.set_target_result(target["id"], "ready", {"fields_verified": ["title"]})
        self.wb.save_revision(self.article["id"], "draft", {"text": "新版本"}, self.article["version"])
        with self.assertRaises(DomainError):
            self.service.confirm(batch["id"], batch["source_hash"])

    def test_video_batch_and_unknown_remote_cannot_retry(self):
        batch = self.service.create_batch("video", self.video, self.video_targets())
        target = batch["targets"][0]
        self.assertEqual("video", batch["content_kind"])
        self.service.set_target_result(target["id"], "unknown_remote", {}, {"code": "UNKNOWN_REMOTE"})
        with self.assertRaises(DomainError) as caught:
            self.service.retry(target["id"])
        self.assertEqual("PUBLISH_RETRY_BLOCKED", caught.exception.code)

    def test_same_batch_is_reused_without_losing_ready_preview(self):
        batch = self.service.create_batch("video", self.video, self.video_targets())
        target = batch["targets"][0]
        self.service.set_target_result(target["id"], "ready", {"fields_verified": ["title"]})
        repeated = self.service.create_batch("video", self.video, self.video_targets())
        self.assertEqual(batch["id"], repeated["id"])
        self.assertEqual("ready", repeated["status"])
        self.assertEqual("ready", repeated["targets"][0]["status"])

    def test_failed_target_can_prepare_again(self):
        batch = self.service.create_batch("video", self.video, self.video_targets())
        target = batch["targets"][0]
        self.service.set_target_result(target["id"], "failed", {}, {"code": "LOGIN_REQUIRED"})
        with mock.patch.object(self.service.jobs, "enqueue", return_value={"id": "job-retry", "kind": "publish.prepare"}):
            job = self.service.retry(target["id"])
        self.assertEqual("job-retry", job["id"])
        self.assertEqual("preparing", self.service.target(target["id"])[1]["status"])

    def test_executor_prepare_never_marks_published(self):
        batch = self.service.create_batch("article", self.article["id"], self.article_targets())
        target = batch["targets"][0]
        executor = PublishingExecutors(self.service)
        with mock.patch.object(executor, "run", return_value={"status": "preview_ready", "fields_verified": ["title", "body"]}) as run:
            result = executor.prepare({"id": "job-prepare", "input": {"target_id": target["id"]}}, mock.Mock())
        self.assertEqual("ready", result["status"])
        self.assertFalse(result["auto_published"])
        self.assertEqual("prepare", run.call_args.args[1])
        self.assertEqual("article", run.call_args.args[3]["source"]["kind"])
        self.assertEqual("ready", self.service.target(target["id"])[1]["status"])

    def test_executor_unknown_remote_requires_manual_reconciliation(self):
        batch = self.service.create_batch("video", self.video, self.video_targets())
        target = batch["targets"][0]
        self.service.set_target_result(target["id"], "ready", {"fields_verified": ["title"]})
        with mock.patch.object(self.service.jobs, "enqueue", side_effect=lambda kind, data, aggregate, *args, **kwargs: {"id": "job-confirm", "kind": kind}):
            self.service.confirm(batch["id"], batch["source_hash"])
        executor = PublishingExecutors(self.service)
        with mock.patch.object(executor, "run", return_value={"status": "unknown_remote", "error": "结果未知"}):
            with self.assertRaises(UnknownRemote):
                executor.execute({"id": "job-execute", "input": {"target_id": target["id"]}}, mock.Mock())
        self.assertEqual("unknown_remote", self.service.target(target["id"])[1]["status"])
        with self.assertRaises(DomainError):
            self.service.reconcile(target["id"], "已发布")
        result = self.service.reconcile(target["id"], "平台视频管理列表显示本条内容于今天发布", "https://example.com/published")
        self.assertEqual("published", result["status"])
        self.assertEqual("https://example.com/published", result["external_url"])

    def test_backend_verification_marks_only_real_evidence_published(self):
        batch = self.service.create_batch("video", self.video, self.video_targets())
        target = batch["targets"][0]
        self.service.set_target_result(target["id"], "unknown_remote", {})
        executor = PublishingExecutors(self.service)
        with mock.patch.object(executor, "run", return_value={"status": "published", "published_evidence": "笔记管理存在标题", "url": "https://example.com/note"}):
            result = executor.verify({"id": "job-verify", "input": {"target_id": target["id"]}}, mock.Mock())
        self.assertEqual("published", result["status"])
        self.assertEqual("published", self.service.target(target["id"])[1]["status"])


if __name__ == "__main__":
    unittest.main()
