import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from content_workbench.domain.errors import DomainError
from content_workbench.domain.services import Workbench
from content_workbench.storage.db import PROJECT_ROOT, connect, expand_schema
from content_workbench.topics.media_analysis import analyze_video
from content_workbench.topics.scheduler import configure_schedule, next_due
from content_workbench.topics.service import TopicService


class DummyContext:
    def progress(self, *args):
        pass

    def run_process(self, arguments, timeout=600, stage=None, cwd=None):
        result = subprocess.run(arguments, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        if result.returncode:
            raise RuntimeError(result.stderr[-500:])
        return result.stdout, result.stderr


class TopicCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="topic-test-")
        self.root = Path(self.temp.name)
        self.db = self.root / "topics.db"
        with connect(self.db) as conn:
            expand_schema(conn)
        self.service = TopicService(self.db, self.root)
        self.workbench = Workbench(self.db, self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_hot_limit_partial_and_collection_dedup(self):
        for index in range(20):
            self.service.upsert_item({"title": "热点" + str(index), "canonical_url": "https://www.douyin.com/hot/" + str(index), "rank": index + 1}, "hot")
        data = self.service.bootstrap()
        self.assertEqual(20, data["hot_count"])
        self.assertTrue(data["hot_complete"])
        for _ in range(2):
            self.service.upsert_item({"title": "同一收藏", "canonical_url": "https://www.douyin.com/video/abc"}, "featured", collection_title="选题")
        data = self.service.bootstrap()
        self.assertEqual(1, len(data["sources"]["featured"]))
        with connect(self.db, readonly=True) as conn:
            self.assertEqual(1, conn.execute("SELECT COUNT(*) FROM wb_research_items WHERE canonical_url='https://www.douyin.com/video/abc'").fetchone()[0])
            self.assertEqual(1, conn.execute("SELECT COUNT(*) FROM wb_memberships").fetchone()[0])
        run_id = self.service.start_sync("full", {"test": True})
        self.service.finish_sync(run_id, "succeeded", {"hot": 20}, True)
        with connect(self.db, readonly=True) as conn:
            self.assertEqual("succeeded", conn.execute("SELECT status FROM wb_sync_runs WHERE id=?", (run_id,)).fetchone()[0])

    def test_reconcile_requires_two_complete_scans(self):
        keep = self.service.upsert_item({"title": "保留", "canonical_url": "https://www.douyin.com/video/keep"}, "featured", collection_title="选题")
        remove = self.service.upsert_item({"title": "移除", "canonical_url": "https://www.douyin.com/video/remove"}, "featured", collection_title="选题")
        self.service.reconcile_collection("选题", [keep], "run-1", complete=True)
        with connect(self.db, readonly=True) as conn:
            self.assertEqual("present", conn.execute("SELECT status FROM wb_memberships WHERE item_id=?", (remove,)).fetchone()[0])
        self.service.reconcile_collection("选题", [keep], "run-2", complete=True)
        with connect(self.db, readonly=True) as conn:
            self.assertEqual("removed", conn.execute("SELECT status FROM wb_memberships WHERE item_id=?", (remove,)).fetchone()[0])
        self.service.reconcile_collection("选题", [], "run-partial", complete=False)
        with connect(self.db, readonly=True) as conn:
            self.assertEqual("present", conn.execute("SELECT status FROM wb_memberships WHERE item_id=?", (keep,)).fetchone()[0])

    def test_settings_and_daily_schedule(self):
        settings = self.service.save_settings({"industry_scope": "企业AI", "industry_prompt": "测试行业提示词", "douyin_prompt": "测试抖音提示词", "daily_time": "08:30", "daily_enabled": True})
        self.assertEqual("08:30", settings["daily_time"])
        with connect(self.db, readonly=True) as conn:
            schedule = conn.execute("SELECT * FROM wb_schedules WHERE id='topics.daily'").fetchone()
            self.assertEqual(1, schedule["enabled"])
            self.assertEqual("coalesce_latest", schedule["misfire_policy"])
        after = datetime(2026, 10, 26, 1, 0, tzinfo=timezone.utc)
        self.assertEqual("2026-10-27T01:00:00.000Z", next_due("09:00", after))

    def test_video_frames_ocr_and_cache(self):
        ocr_python = PROJECT_ROOT / ".venv-topics/bin/python"
        if not ocr_python.is_file() or subprocess.run([str(ocr_python), "-c", "import rapidocr_onnxruntime"], capture_output=True).returncode:
            self.skipTest("RapidOCR 尚未安装")
        from PIL import Image, ImageDraw, ImageFont
        font = ImageFont.truetype("/System/Library/Fonts/STHeiti Medium.ttc", 60)
        for index, text in enumerate(("企业AI落地", "结果需要验收"), 1):
            image = Image.new("RGB", (1280, 720), "white")
            draw = ImageDraw.Draw(image)
            draw.text((150, 300), text, font=font, fill="black")
            image.save(self.root / ("text%d.png" % index))
        command = [shutil.which("ffmpeg"), "-v", "error", "-y"]
        for index in (1, 2):
            command += ["-loop", "1", "-t", "2", "-i", str(self.root / ("text%d.png" % index))]
        command += ["-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0,format=yuv420p[v]", "-map", "[v]", str(self.root / "sample.mp4")]
        subprocess.run(command, check=True, timeout=60)
        item_id = self.service.upsert_item({"title": "测试视频", "canonical_url": "https://example.com/video/1"}, "featured")
        result = analyze_video(self.workbench, self.service, item_id, self.root / "sample.mp4", DummyContext())
        self.assertGreaterEqual(result["frames"], 2)
        cached = analyze_video(self.workbench, self.service, item_id, self.root / "sample.mp4", DummyContext())
        self.assertTrue(cached["cache_hit"])
        item = self.service.get_item(item_id)
        self.assertEqual("succeeded", item["analysis_status"])
        report = item["analyses"][0]["report"]
        self.assertEqual(2, report["frame_interval_seconds"])
        self.assertEqual(0, report["timeline"][0]["start_ms"])
        self.assertEqual(2000, report["timeline"][1]["start_ms"])
        recognized = " ".join(frame["text"] for frame in report["timeline"])
        self.assertTrue("企业" in recognized or "验收" in recognized, recognized)
    def test_audio_only_rejected_and_short_video_keeps_first_frame(self):
        from PIL import Image, ImageDraw, ImageFont
        item_id = self.service.upsert_item({"title": "纯音频", "canonical_url": "https://example.com/audio-only"}, "featured")
        subprocess.run([shutil.which("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2", str(self.root / "audio-only.mp4")], check=True, timeout=30)
        with self.assertRaises(DomainError) as caught:
            analyze_video(self.workbench, self.service, item_id, self.root / "audio-only.mp4", DummyContext())
        self.assertEqual("VIDEO_STREAM_MISSING", caught.exception.code)
        image = Image.new("RGB", (1280, 720), "white")
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype("/System/Library/Fonts/STHeiti Medium.ttc", 60)
        draw.text((150, 300), "首帧保留", font=font, fill="black")
        image.save(self.root / "short.png")
        subprocess.run([shutil.which("ffmpeg"), "-v", "error", "-y", "-loop", "1", "-t", "1", "-i", str(self.root / "short.png"),
                        "-pix_fmt", "yuv420p", str(self.root / "short.mp4")], check=True, timeout=30)
        result = analyze_video(self.workbench, self.service, item_id, self.root / "short.mp4", DummyContext())
        self.assertGreaterEqual(result["frames"], 1)


if __name__ == "__main__":
    unittest.main()
