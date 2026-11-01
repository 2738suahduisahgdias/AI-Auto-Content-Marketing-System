import tempfile
import unittest
from pathlib import Path
from unittest import mock

from content_workbench.domain.errors import DomainError
from content_workbench.storage.db import connect, expand_schema
from content_workbench.topics.dynamic_snapshot import parse_dynamic_document
from content_workbench.topics.link_snapshot import detect_platform, fetch_public_snapshot, parse_html, validate_public_url
from content_workbench.topics.service import TopicService
from content_workbench.topics.snapshot_executor import WechatSnapshotExecutor
from content_workbench.topics.wechat_inbox import WechatInboxService


class LinkSnapshotCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="link-snapshot-")
        self.root = Path(self.temp.name)
        with connect(self.root / "topics.db") as conn:
            expand_schema(conn)
        self.topics = TopicService(self.root / "topics.db", self.root)
        self.inbox = WechatInboxService(self.topics.db_path, self.topics)
        self.executor = WechatSnapshotExecutor(self.inbox)
        self.message, _ = self.inbox.ingest({"msgid": "link-1", "text": "案例 https://example.com/case"})

    def tearDown(self):
        self.temp.cleanup()

    def test_parse_open_graph_metadata(self):
        html = """<html><head><title>普通标题</title><meta property="og:title" content="真实案例标题">
        <meta property="og:description" content="真实摘要"><meta property="og:site_name" content="案例媒体">
        <meta property="og:image" content="/cover.jpg"><meta property="og:url" content="https://example.com/canonical">
        </head><body><script>忽略脚本</script><p>公开正文</p></body></html>"""
        snapshot = parse_html(html, "https://example.com/source")
        self.assertEqual("真实案例标题", snapshot["title"])
        self.assertEqual("真实摘要", snapshot["description"])
        self.assertEqual("https://example.com/cover.jpg", snapshot["cover_url"])
        self.assertEqual("案例媒体", snapshot["site_name"])
        self.assertIn("公开正文", snapshot["excerpt"])
        self.assertFalse(snapshot["limited"])

    def test_rejects_private_addresses(self):
        with self.assertRaises(DomainError) as caught:
            validate_public_url("http://127.0.0.1/topics/wechat")
        self.assertEqual("SNAPSHOT_PRIVATE_URL_BLOCKED", caught.exception.code)

    def test_executor_saves_success_and_failure(self):
        snapshot = {"title": "真实标题", "site_name": "真实站点", "platform": "generic", "limited": False}
        with mock.patch("content_workbench.topics.snapshot_executor.fetch_public_snapshot", return_value=snapshot):
            result = self.executor.run({"aggregate_id": self.message["id"]}, mock.Mock())
        self.assertEqual("succeeded", result["snapshot_status"])
        self.assertEqual("真实标题", self.inbox.get(self.message["id"])["snapshot"]["title"])
        with mock.patch("content_workbench.topics.snapshot_executor.fetch_public_snapshot",
                        side_effect=DomainError("SNAPSHOT_FETCH_FAILED", "页面不存在", 502, "original_url", "检查链接")):
            with self.assertRaises(DomainError):
                self.executor.run({"aggregate_id": self.message["id"]}, mock.Mock())
        failed = self.inbox.get(self.message["id"])
        self.assertEqual("failed", failed["snapshot_status"])
        self.assertIn("页面不存在", failed["snapshot_error"])

    def test_json_ld_author_and_dynamic_douyin_fields(self):
        html = """<html><head><script type="application/ld+json">{"@type":"VideoObject","headline":"公开视频",
        "author":{"@type":"Person","name":"真实作者"},"datePublished":"2026-10-13"}</script></head></html>"""
        snapshot = parse_html(html, "https://www.bilibili.com/video/BV123")
        self.assertEqual("真实作者", snapshot["author"])
        self.assertEqual("2026-10-13", snapshot["published_at"])
        self.assertEqual("bilibili", snapshot["platform"])
        text = """第1集 | Vibe知识大赏保姆级教程
4.5万
726
3.4万
9316
发布时间：2026-10-13 19:30
小冯不意why
粉丝 9052 获赞 7.6万"""
        dynamic = parse_dynamic_document(text, {"heading": "Vibe知识大赏保姆级教程", "cover_url": "https://example.com/poster.jpg"},
                                         "https://www.douyin.com/video/7696040551015025929")
        self.assertEqual("小冯不意why", dynamic["author"])
        self.assertEqual("9052", dynamic["author_followers"])
        self.assertEqual("2026-10-13 19:30", dynamic["published_at"])
        self.assertEqual("douyin", dynamic["platform"])
        self.assertEqual("https://example.com/poster.jpg", dynamic["cover_url"])
        self.assertEqual("douyin", detect_platform("https://v.douyin.com/ACOh4f2OQMM/"))
        self.assertEqual("wechat_channels", detect_platform("https://channels.weixin.qq.com/finder-preview/pages/sph"))


if __name__ == "__main__":
    unittest.main()
