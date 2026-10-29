import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from content_workbench.domain.errors import DomainError
from content_workbench.domain.services import Workbench
from content_workbench.jobs.worker import UnknownRemote
from content_workbench.publishing.executors import PublishingExecutors
from content_workbench.publishing.knowledge import publish_knowledge
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

    def test_retrospective_contains_only_verified_records_and_boundaries(self):
        article = self.service.create_batch("article", self.article["id"], self.article_targets())
        video = self.service.create_batch("video", self.video, self.video_targets())
        published = article["targets"][0]
        self.service.set_target_result(published["id"], "published", {"published_evidence": "公众号首页已发表", "reconciled_at": "2026-10-28T01:00:00Z"})
        self.service.set_target_result(video["targets"][0]["id"], "unknown_remote", {})
        data = self.service.retrospective()
        self.assertEqual(1, data["total_published"])
        self.assertEqual({"douyin", "xiaohongshu", "wechat_channels", "wechat_official_account"}, set(data["platforms"]))
        item = data["platforms"]["wechat_official_account"]["items"][0]
        self.assertEqual("标题", item["title"])
        self.assertEqual("article", item["content_kind"])
        self.assertEqual("2026-10-28T01:00:00Z", item["verified_at"])
        self.assertEqual([], data["platforms"]["douyin"]["items"])
        self.assertIn("暂不能判断传播效果", data["platforms"]["douyin"]["data_boundary"])
        self.assertIn("不是平台效果结论", data["platforms"]["xiaohongshu"]["suggestion_kind"])

    def test_field_generation_returns_only_editable_text_without_publishing(self):
        job = self.service.generate_fields("article", self.article["id"], ["wechat_official_account"], "面向企业主", "generate-request")
        self.assertEqual("publish.fields", job["kind"])
        self.assertEqual("cloud_text", job["resource_key"])
        self.assertEqual(job["id"], self.service.bootstrap("article", self.article["id"])["field_jobs"][0]["id"])
        model_fields = {"title": "生成标题", "body": "生成正文", "author": "老刘", "summary": "生成摘要",
                        "cover_asset_id": "模型不能指定封面", "original": True}
        stdout = json.dumps({"type": "assistant", "content": json.dumps({"platforms": {"wechat_official_account": model_fields}}, ensure_ascii=False)})
        context = mock.Mock()
        context.run_process.return_value = (stdout, "")
        config = {"prompt": "保留事实", "timeout_seconds": 600}
        with mock.patch("content_workbench.publishing.executors.require_agent_enabled", return_value=config), \
                mock.patch("content_workbench.providers.local.LocalExecutors.kimi", return_value="/fake/kimi"):
            result = PublishingExecutors(self.service).generate_fields(job, context)
        generated = result["platforms"]["wechat_official_account"]
        self.assertEqual("生成标题", generated["title"])
        self.assertNotIn("cover_asset_id", generated)
        self.assertNotIn("original", generated)
        self.assertFalse(result["auto_saved"])
        self.assertFalse(result["auto_published"])
        self.assertIsNone(self.service.bootstrap("article", self.article["id"])["batch"])

    def test_generated_fields_enforce_platform_limits(self):
        payload = {"platforms": {"douyin": {"title": "长" * 301, "description": "简介"}}}
        with self.assertRaises(DomainError) as caught:
            PublishingExecutors.validate_generated_fields("video", ["douyin"], payload)
        self.assertEqual("PUBLISH_GENERATED_FIELD_TOO_LONG", caught.exception.code)
        self.assertEqual("douyin.title", caught.exception.field)
        with self.assertRaises(DomainError):
            self.service.generate_fields("article", self.article["id"], ["douyin"])

    def test_publish_knowledge_matches_actual_validation_contract(self):
        official = publish_knowledge(platform="wechat_official_account", content_kind="article")["platforms"][0]
        fields = {field["name"]: field for field in official["content_types"][0]["fields"]}
        self.assertEqual(64, fields["title"]["max_length"])
        self.assertEqual(200000, fields["body"]["max_length"])
        self.assertTrue(fields["cover_asset_id"]["required"])
        self.assertEqual(8, fields["author"]["max_length"])
        self.assertEqual(120, fields["summary"]["max_length"])
        video = publish_knowledge(platform="douyin", content_kind="video")["platforms"][0]
        video_fields = {field["name"]: field for field in video["content_types"][0]["fields"]}
        self.assertEqual(300, video_fields["title"]["max_length"])
        self.assertEqual(5000, video_fields["description"]["max_length"])
        self.assertTrue(video_fields["video_path"]["required"])
        self.assertEqual("已验证发布字段", video["verification"])


if __name__ == "__main__":
    unittest.main()
