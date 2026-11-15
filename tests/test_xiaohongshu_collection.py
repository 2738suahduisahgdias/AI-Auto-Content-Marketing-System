import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from content_workbench.domain.errors import DomainError
from content_workbench.topics.xiaohongshu_browser import XHSBrowserCollector
from content_workbench.topics.xiaohongshu_download import (
    download_xiaohongshu_media,
    probe_xiaohongshu_media,
    validate_xiaohongshu_url,
)


class XHSBrowserCollectorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="xhs-browser-test-")
        self.context = mock.Mock()
        self.collector = XHSBrowserCollector(Path(self.temp.name), self.context)
        self.collector.provider = mock.Mock()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_login_uses_kimi_cli_and_real_personal_page(self) -> None:
        self.collector.provider.complete_json.return_value = {
            "status": "ok",
            "login_verified": True,
            "items": [],
            "errors": [],
        }
        result = self.collector.login()
        self.assertTrue(result["login_verified"])
        request = json.loads(self.collector.provider.complete_json.call_args.args[0])
        self.assertEqual("check_login", request["action"])
        self.assertEqual("xiaohongshu", request["platform"])
        self.assertEqual(300, request["wait_seconds"])
        self.assertEqual(
            "xiaohongshu-collection-agent.md",
            self.collector.provider.complete_json.call_args.args[2].name,
        )

    def test_hot_uses_real_hot_source_without_login_or_personal_collection(
        self,
    ) -> None:
        self.collector.provider.complete_json.return_value = {
            "status": "ok",
            "login_verified": False,
            "items": [
                {
                    "title": "平台热点一",
                    "canonical_url": "https://www.xiaohongshu.com/explore/hot1",
                    "platform_item_id": "hot1",
                    "metadata": {"heat": "10万"},
                }
            ],
            "errors": [],
        }
        result = self.collector.collect_hot()
        self.assertEqual("xhs_hot", result["items"][0]["metadata"]["source_key"])
        self.assertEqual(1, result["items"][0]["metadata"]["rank"])
        request = json.loads(self.collector.provider.complete_json.call_args.args[0])
        self.assertEqual("collect_hot", request["action"])
        self.assertNotIn("wait_seconds", request)

    def test_collection_and_details_keep_source_and_author_evidence(self) -> None:
        self.collector.provider.complete_json.side_effect = [
            {"status": "ok", "login_verified": True, "items": [], "errors": []},
            {
                "status": "ok",
                "items": [
                    {
                        "title": "精选作品",
                        "canonical_url": "https://www.xiaohongshu.com/explore/note1?xsec_token=abc",
                        "platform_item_id": "note1",
                        "metadata": {
                            "source_key": "xhs_featured",
                            "cover_url": "https://example.com/cover.jpg",
                        },
                    }
                ],
                "errors": [],
            },
            {"status": "ok", "login_verified": True, "items": [], "errors": []},
            {
                "status": "ok",
                "items": [],
                "results": [
                    {
                        "requested_url": "https://www.xiaohongshu.com/explore/note1?xsec_token=abc",
                        "canonical_url": "https://www.xiaohongshu.com/explore/note1?xsec_token=abc",
                        "details": {
                            "author_name": "真实作者",
                            "author_followers": "1.2万",
                            "like_count": "3456",
                            "comment_count": "78",
                            "media_kind": "image_set",
                        },
                    }
                ],
                "errors": [],
            },
        ]
        collected = self.collector.collect_favorites({"xhs_featured": "选题"})
        details = self.collector.collect_details_batch(
            [collected["items"][0]["canonical_url"]]
        )
        self.assertEqual(
            "xhs_featured", collected["items"][0]["metadata"]["source_key"]
        )
        self.assertEqual("真实作者", details["items"][0]["details"]["author_name"])
        self.assertEqual("image_set", details["items"][0]["details"]["media_kind"])


class XHSDownloadTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="xhs-download-test-")
        self.root = Path(self.temp.name)
        self.context = mock.Mock()
        self.url = "https://www.xiaohongshu.com/explore/note1?xsec_token=abc"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_rejects_non_xiaohongshu_links(self) -> None:
        with self.assertRaises(DomainError):
            validate_xiaohongshu_url("https://example.com/video/1")

    def test_probe_returns_real_formats_without_downloading(self) -> None:
        with mock.patch(
            "content_workbench.topics.xiaohongshu_download.KimiCLIProvider"
        ) as provider:
            provider.return_value.complete_json.return_value = {
                "status": "ok",
                "media_kind": "video",
                "formats": [{"id": "1", "label": "720p H.264", "format_arg": "bv*+ba"}],
                "errors": [],
            }
            result = probe_xiaohongshu_media(self.url, self.context)
        self.assertEqual("video", result["media_kind"])
        self.assertEqual("720p H.264", result["formats"][0]["label"])
        request = json.loads(provider.return_value.complete_json.call_args.args[0])
        self.assertEqual("probe", request["action"])

    def test_download_image_set_returns_all_real_files(self) -> None:
        with mock.patch(
            "content_workbench.topics.xiaohongshu_download.KimiCLIProvider"
        ) as provider:

            def complete_json(request, context, agent_path, **kwargs):
                payload = json.loads(request)
                library = Path(payload["output_dir"])
                for name in ("1.jpg", "2.jpg"):
                    (library / name).write_bytes(b"real-image-content" * 10)
                return {
                    "status": "ok",
                    "media_kind": "image_set",
                    "files": [
                        {"path": str(library / "1.jpg")},
                        {"path": str(library / "2.jpg")},
                    ],
                    "errors": [],
                }

            provider.return_value.complete_json.side_effect = complete_json
            result = download_xiaohongshu_media(
                self.url, self.root / "out", self.context, "compat"
            )
        self.assertEqual("image_set", result["media_kind"])
        self.assertEqual(2, result["file_count"])
        self.assertEqual(2, len(result["files"]))
        self.assertTrue(all(Path(item["path"]).is_file() for item in result["files"]))

    def test_download_requires_explicit_mode(self) -> None:
        with self.assertRaises(DomainError):
            download_xiaohongshu_media(self.url, self.root / "out", self.context, "")


if __name__ == "__main__":
    unittest.main()
