import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from content_workbench.domain.errors import DomainError
from content_workbench.publishing.service import PublishingService
from content_workbench.review.executors import ReviewExecutors
from content_workbench.review.service import ReviewService
from content_workbench.storage.db import connect, expand_schema, file_hash


class Context:
    def progress(self, *args):
        pass

    def run_process(self, arguments, timeout=600, stage=None, cwd=None):
        result = subprocess.run(arguments, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        if result.returncode:
            raise RuntimeError(result.stderr[-500:])
        return result.stdout, result.stderr


class ReviewCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="review-service-")
        self.root = Path(self.temp.name).resolve()
        self.db = self.root / "test.db"
        with connect(self.db) as conn:
            expand_schema(conn)
            conn.execute("CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
        self.service = ReviewService(self.db, self.root)
        self.folder = self.root / "A"
        self.folder.mkdir()
        self.video = self.folder / "sample.mp4"
        self.make_video(self.video)
        self.rules = {"check_ocr": False, "ai_risk": False, "max_duration": 180}

    def tearDown(self):
        self.temp.cleanup()

    def make_video(self, path):
        subprocess.run([shutil.which("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:s=160x160:d=2",
                        "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-movflags", "+faststart", str(path)], check=True, timeout=30)

    def test_batch_scan_decision_and_publish_source(self):
        original_hash = file_hash(self.video)
        batch = self.service.create_batch(self.folder, self.rules)
        self.assertEqual(1, batch["counts"]["total"])
        with self.assertRaises(DomainError):
            self.service.source_for_publish(batch["items"][0]["id"])
        self.service.start(batch["id"])
        ReviewExecutors(self.service).scan({"input": {"batch_id": batch["id"]}}, Context())
        item = self.service.get_batch(batch["id"])["items"][0]
        self.assertTrue(item["report"]["safe_transcode_candidate"]["eligible"])
        ReviewExecutors(self.service).repair({"input": {"item_id": item["id"]}}, Context())
        output = self.service.decide(item["id"], "approved")
        self.assertTrue(Path(output).is_file())
        self.assertEqual(self.folder / "审核通过" / "sample.mp4", Path(output))
        self.assertEqual(original_hash, file_hash(self.video))
        self.assertNotEqual(original_hash, file_hash(output))
        source = self.service.source_for_publish(item["id"])
        self.assertEqual("video", source["kind"])
        self.assertEqual("sample", source["title"])
        publishing_source = PublishingService(self.db, self.root).source("video", item["id"])
        self.assertEqual(output, publishing_source["absolute_video_path"])
        self.assertEqual(output, self.service.decide(item["id"], "approved"))

    def test_ai_risk_is_scoped_evidence(self):
        batch = self.service.create_batch(self.folder, self.rules)
        ReviewExecutors(self.service).scan({"input": {"batch_id": batch["id"]}}, Context())
        item = batch["items"][0]
        payload = {"items": [{"item_id": item["id"], "evidence_scope": "只有技术报告", "risks": [{"category": "exaggeration", "severity": "warning", "evidence": "示例", "reason": "待核查", "action": "修改"}]}]}
        stream = json.dumps({"type": "assistant", "content": json.dumps(payload, ensure_ascii=False)}) + "\n"
        context = mock.Mock()
        context.run_process.return_value = (stream, "")
        result = ReviewExecutors(self.service).ai({"input": {"batch_id": batch["id"]}}, context)
        self.assertEqual(1, result["items"])
        risk = self.service.get_batch(batch["id"])["items"][0]["ai_risk"]
        self.assertEqual("只有技术报告", risk["evidence_scope"])
        self.assertTrue(result["human_review_required"])

    def test_invalid_folder_and_empty_rules_are_rejected(self):
        with self.assertRaises(DomainError):
            self.service.create_batch(self.folder / "missing", self.rules)
        with self.assertRaises(DomainError):
            self.service.create_batch(self.folder, {**self.rules, "min_duration": 10, "max_duration": 2})


if __name__ == "__main__":
    unittest.main()
