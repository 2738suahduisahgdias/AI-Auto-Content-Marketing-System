import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from content_workbench.api.v2 import V2Application
from content_workbench.domain.errors import DomainError
from content_workbench.providers.text import CodexCLIProvider, TextProviderRegistry, assistant_text, json_object
from content_workbench.social.catalog import catalog, get_operation
from content_workbench.social.executors import SocialExecutors, parse_srt
from content_workbench.social.service import SocialDataService
from content_workbench.storage.db import connect, expand_schema
from content_workbench.topics.service import TopicService


class FakeProvider:
    provider_id = "kimi_cli"

    def status(self):
        return {"id": "kimi_cli", "available": True, "reason": None}

    def complete_json(self, prompt, context, agent_path, timeout=600, stage="kimi_cli"):
        return {"items": [{"title": "公开作品", "text": "页面正文", "canonical_url": "https://invalid.example/injected",
                           "author": "公开作者", "metrics": {"like_count": 12}}], "profile": {}, "metrics": {}, "evidence": ["页面正文"]}


class DummyContext:
    def __init__(self, stdout=""):
        self.stdout = stdout

    def progress(self, *args):
        pass

    def run_process(self, arguments, timeout=600, stage=None, cwd=None):
        return self.stdout, ""


class FakeBridge:
    def goto(self, url):
        self.url = url

    def snapshot(self):
        return {"url": self.url}

    def evaluate(self, script):
        return {"title": "公开页面", "canonical_url": self.url, "cover_url": "",
                "links": [{"url": "https://www.douyin.com/video/real", "text": "真实作品"}]}


class SocialCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="social-test-")
        self.root = Path(self.temp.name)
        self.db = self.root / "social.db"
        with connect(self.db) as conn:
            expand_schema(conn)
        self.topics = TopicService(self.db, self.root)
        registry = TextProviderRegistry(self.root, providers={"kimi_cli": FakeProvider(), "codex_cli": CodexCLIProvider()})
        self.service = SocialDataService(self.db, self.root, registry)
        self.executors = SocialExecutors(self.service, self.topics)

    def tearDown(self):
        self.temp.cleanup()

    def test_catalog_has_167_unique_operations_and_honest_coverage(self):
        data = catalog()
        self.assertEqual(167, data["coverage"]["total"])
        self.assertEqual(167, len({item["id"] for item in data["items"]}))
        self.assertEqual(data["coverage"]["total"], data["coverage"]["supported"] + data["coverage"]["adapter_required"])
        self.assertEqual("supported", get_operation("douyin:video/detail")["status"])
        self.assertEqual("adapter_required", get_operation("xhs:pgy/creator/profile")["status"])
        self.assertFalse(data["runtime"]["external_social_api"])
        self.assertNotIn("socialdatax", json.dumps(data).lower())

    def test_unsupported_operation_fails_instead_of_returning_fake_data(self):
        with self.assertRaises(DomainError) as caught:
            self.service.create_run("xhs:pgy/creator/profile", {"user_id": "author"})
        self.assertEqual(501, caught.exception.status)
        self.assertEqual("SOCIAL_ADAPTER_REQUIRED", caught.exception.code)

    def test_run_lifecycle_and_input_validation(self):
        run = self.service.create_run("douyin:hot/search/list", {})
        self.assertEqual("queued", run["status"])
        self.service.start_run(run["id"])
        self.service.finish_run(run["id"], {"items": [{"title": "热点"}]})
        self.assertEqual("succeeded", self.service.get_run(run["id"])["status"])
        with self.assertRaises(DomainError):
            self.service.create_run("douyin:video/search", {})
        with self.assertRaises(DomainError):
            self.service.create_run("douyin:video/detail", {})
        with mock.patch("content_workbench.providers.text.discover_cli", return_value=None), self.assertRaises(DomainError):
            self.service.create_run("douyin:video/detail", {"url": "https://www.douyin.com/video/1"}, "codex_cli")

    def test_douyin_hot_uses_existing_browser_and_saves_research_items(self):
        run = self.service.create_run("douyin:hot/search/list", {})
        items = [{"title": "真实热点", "canonical_url": "https://www.douyin.com/hot/1", "rank": 1}]
        with mock.patch("content_workbench.social.executors.TopicExecutors.browser", return_value={"items": items}):
            result = self.executors.execute({"aggregate_id": run["id"]}, DummyContext())
        self.assertEqual("succeeded", result["status"])
        self.assertEqual(1, self.service.get_run(run["id"])["result"]["items"][0]["rank"])
        self.assertEqual(1, self.topics.bootstrap()["hot_count"])

    @mock.patch("content_workbench.social.executors.time.sleep", return_value=None)
    @mock.patch("content_workbench.social.executors.Bridge", FakeBridge)
    @mock.patch("content_workbench.social.executors.body", return_value="公开页面正文，作者和互动指标。" * 200)
    def test_browser_model_rejects_url_not_found_in_page_evidence(self, *_):
        run = self.service.create_run("douyin:video/detail", {"url": "https://www.douyin.com/video/real"})
        self.executors.execute({"aggregate_id": run["id"]}, DummyContext())
        result = self.service.get_run(run["id"])["result"]
        self.assertEqual("", result["items"][0]["canonical_url"])
        self.assertEqual("公开作品", result["items"][0]["title"])
        item = self.topics.bootstrap()["sources"]["competitor"][0]
        self.assertEqual("https://www.douyin.com/video/real", item["url"])

    def test_local_download_returns_real_ytdlp_tracks(self):
        payload = {"id": "bv1", "title": "公开视频", "webpage_url": "https://www.bilibili.com/video/bv1",
                   "http_headers": {"Referer": "https://www.bilibili.com/"},
                   "formats": [{"format_id": "1", "url": "https://cdn.example/video.m4s", "ext": "m4s", "vcodec": "avc1"}]}
        run = self.service.create_run("bilibili:video/download-links", {"url": "https://www.bilibili.com/video/bv1"})
        with mock.patch("content_workbench.social.executors.shutil.which", return_value="/usr/local/bin/yt-dlp"):
            self.executors.execute({"aggregate_id": run["id"]}, DummyContext(json.dumps(payload)))
        result = self.service.get_run(run["id"])["result"]
        self.assertEqual("yt_dlp", result["provider"])
        self.assertEqual("https://cdn.example/video.m4s", result["download_manifest"]["tracks"][0]["url"])

    def test_srt_parser_and_local_media_boundary(self):
        segments = parse_srt("1\n00:00:00,000 --> 00:00:01,500\n第一句\n\n2\n00:00:01,500 --> 00:00:03,000\n第二句\n")
        self.assertEqual(1500, segments[1]["start_ms"])
        self.assertEqual("第二句", segments[1]["text"])
        with self.assertRaises(DomainError) as caught:
            self.executors.local_transcript({"media_path": "/etc/passwd", "model": "base"}, DummyContext())
        self.assertEqual("SOCIAL_MEDIA_INVALID", caught.exception.code)

    def test_v2_application_registers_social_routes(self):
        app = V2Application(self.db, self.root)
        self.assertTrue(app.matches("/api/social/catalog"))
        self.assertIn("social.execute", app.worker.executors)
        self.assertEqual(167, app.social.bootstrap()["coverage"]["total"])


class TextProviderCase(unittest.TestCase):
    def test_stream_and_json_parsing(self):
        stream = '{"type":"assistant","content":[{"type":"text","text":"{\\"ok\\":true}"}]}\n'
        self.assertEqual('{"ok":true}', assistant_text(stream))
        self.assertEqual({"ok": True}, json_object('```json\n{"ok":true}\n```'))
        with self.assertRaises(DomainError):
            json_object("[]")

    @mock.patch("content_workbench.providers.text.discover_cli", return_value=None)
    def test_codex_missing_binary_is_unavailable(self, _which):
        registry = TextProviderRegistry(".", providers={"codex_cli": CodexCLIProvider()})
        self.assertFalse(registry.status()["items"][0]["available"])
        with self.assertRaises(DomainError) as caught:
            registry.get("codex_cli")
        self.assertEqual("MODEL_PROVIDER_UNAVAILABLE", caught.exception.code)


if __name__ == "__main__":
    unittest.main()
