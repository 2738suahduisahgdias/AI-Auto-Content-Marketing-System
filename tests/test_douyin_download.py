import tempfile
import unittest
from pathlib import Path
from unittest import mock

from content_workbench.domain.errors import DomainError
from content_workbench.storage.db import connect, expand_schema
from content_workbench.topics.douyin_download import download_douyin_video, validate_douyin_url
from content_workbench.topics.executors import TopicExecutors
from content_workbench.topics.service import TopicService


class DownloadContext:
    def __init__(self, source):
        self.source = source
        self.calls = []
        self.stages = []

    def progress(self, stage, _value):
        self.stages.append(stage)

    def run_process(self, arguments, timeout=600, stage=None, cwd=None):
        self.calls.append({"arguments": arguments, "timeout": timeout, "stage": stage, "cwd": cwd})
        output_dir = Path(arguments[-1])
        downloaded = output_dir / "author" / "video.mp4"
        downloaded.parent.mkdir(parents=True)
        downloaded.write_bytes(self.source)
        return "Download complete", ""


class DouyinDownloadCase(unittest.TestCase):
    def test_skill_download_copies_verified_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "download.sh"
            script.write_text("# test skill", encoding="utf-8")
            context = DownloadContext(b"video" * 300)
            output = root / "analysis" / "source.mp4"
            media_info = {"duration_seconds": 3, "streams": [
                {"codec_type": "video", "codec_name": "h264", "width": 1024, "height": 576},
                {"codec_type": "audio", "codec_name": "aac"},
            ]}
            with mock.patch("content_workbench.topics.douyin_download.probe", return_value=media_info):
                result = download_douyin_video("https://v.douyin.com/abc/", output, context, script_path=script)
            self.assertEqual(str(output.resolve()), result["path"])
            self.assertEqual("video-downloader", result["downloader"])
            self.assertEqual("douyin-compat", result["source_kind"])
            self.assertEqual(len(b"video" * 300), output.stat().st_size)
            call = context.calls[0]
            self.assertEqual("douyin_skill_download", call["stage"])
            self.assertEqual(["bash", str(script), "compat", "https://v.douyin.com/abc/"], call["arguments"][:4])
            self.assertIn("douyin_skill_download", context.stages)

    def test_rejects_non_official_url_and_missing_skill(self):
        with self.assertRaises(DomainError) as invalid:
            validate_douyin_url("https://example.com/video/1")
        self.assertEqual("INVALID_DOUYIN_URL", invalid.exception.code)
        with tempfile.TemporaryDirectory() as directory:
            context = DownloadContext(b"video" * 300)
            with self.assertRaises(DomainError) as missing:
                download_douyin_video("https://v.douyin.com/abc/", Path(directory) / "video.mp4", context,
                                      script_path=Path(directory) / "missing.sh")
            self.assertEqual("DOUYIN_SKILL_MISSING", missing.exception.code)

    def test_topic_analysis_uses_skill_not_legacy_browser(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with connect(root / "topics.db") as conn:
                expand_schema(conn)
            service = TopicService(root / "topics.db", root)
            item_id = service.upsert_item({"title": "抖音视频", "canonical_url": "https://www.douyin.com/video/7123456789012345678"}, "featured")
            executor = TopicExecutors(service)
            context = DownloadContext(b"video" * 300)
            with mock.patch("content_workbench.topics.executors.download_douyin_video",
                            return_value={"downloader": "video-downloader", "source_kind": "douyin-compat",
                                          "duration_seconds": 3, "bytes": 1500, "verification": "ffprobe"}) as skill, \
                    mock.patch("content_workbench.topics.executors.analyze_video",
                               return_value={"analysis_id": "analysis-1", "cache_hit": False}), \
                    mock.patch.object(executor, "browser", side_effect=AssertionError("不应使用旧浏览器下载")) as browser:
                result = executor.analyze({"aggregate_id": item_id}, context)
            self.assertEqual("video-downloader", result["download"]["downloader"])
            self.assertEqual("analysis-1", result["analysis_id"])
            skill.assert_called_once()
            browser.assert_not_called()


if __name__ == "__main__":
    unittest.main()
