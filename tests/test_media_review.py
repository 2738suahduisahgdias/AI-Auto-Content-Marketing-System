import hashlib
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from content_workbench.review.media_review import (
    DEFAULT_OCR_PYTHON,
    MediaReviewer,
    build_safe_transcode_command,
    review_media,
)


FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def issue_types(report):
    return {item["type"] for item in report["issues"]}


@unittest.skipUnless(FFMPEG and FFPROBE, "需要 FFmpeg 和 FFprobe 生成并检查真实媒体")
class MediaReviewCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="media-review-test-")
        cls.root = Path(cls.temp.name)
        cls.sources = {}
        cls.make_video("normal", "testsrc2=size=360x640:rate=12:duration=2",
                       "sine=frequency=440:duration=2")
        cls.make_video("black", "color=black:size=360x640:rate=12:duration=2",
                       "sine=frequency=440:duration=2")
        cls.make_video("silent", "testsrc2=size=360x640:rate=12:duration=2",
                       "anullsrc=channel_layout=mono:sample_rate=44100")
        cls.make_video("landscape", "testsrc2=size=640x360:rate=12:duration=2",
                       "sine=frequency=440:duration=2")
        cls.hashes = {name: file_hash(path) for name, path in cls.sources.items()}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @classmethod
    def make_video(cls, name, video_source, audio_source):
        path = cls.root / (name + ".mp4")
        command = [FFMPEG, "-v", "error", "-y",
                   "-f", "lavfi", "-i", video_source,
                   "-f", "lavfi", "-i", audio_source,
                   "-c:v", "libx264", "-pix_fmt", "yuv420p",
                   "-c:a", "aac", "-shortest", "-movflags", "+faststart", str(path)]
        if name == "silent":
            command[command.index("-shortest"):command.index("-shortest")] = ["-t", "2"]
        subprocess.run(command, check=True, timeout=60)
        cls.sources[name] = path

    def reviewer(self, **options):
        values = {"target_width": 360, "target_height": 640, "min_width": 180,
                  "min_height": 320, "min_duration": 0.5, "max_duration": 10,
                  "ocr_interval": 1, "ocr_max_frames": 4, "command_timeout": 60}
        values.update(options)
        return MediaReviewer(**values)

    def review(self, name, check_ocr=False, **options):
        return self.reviewer(**options).review(self.sources[name], check_ocr=check_ocr)

    def test_normal_real_video_passes_machine_checks(self):
        report = self.review("normal")
        self.assertEqual("passed", report["status"], report["issues"])
        self.assertTrue(report["machine_checks_passed"])
        self.assertTrue(report["human_review_required"])
        self.assertEqual([], report["issues"])
        self.assertTrue(report["source"]["unchanged"])
        self.assertTrue(report["media"]["faststart"])
        self.assertEqual("h264", report["media"]["video"]["codec_name"])
        self.assertEqual("aac", report["media"]["audio"]["codec_name"])
        self.assertEqual("yuv420p", report["media"]["video"]["pix_fmt"])
        self.assertEqual("skipped", report["checks"]["subtitle_bounds"])

    def test_black_frames_have_time_evidence_and_no_auto_cut(self):
        report = self.review("black")
        issues = [item for item in report["issues"] if item["type"] == "black_frames"]
        self.assertTrue(issues, report)
        self.assertEqual("warning", issues[0]["severity"])
        self.assertIsNotNone(issues[0]["timestamp_seconds"])
        self.assertGreater(issues[0]["end_seconds"], issues[0]["timestamp_seconds"])
        self.assertGreater(issues[0]["evidence"]["duration_seconds"], 0)
        self.assertEqual([], report["automatic_repairs_applied"])
        self.assertFalse(issues[0]["auto_fixable"])

    def test_silent_audio_has_time_evidence_and_volume_warning(self):
        report = self.review("silent")
        self.assertIn("silence", issue_types(report))
        self.assertIn("volume_too_low", issue_types(report))
        silence = next(item for item in report["issues"] if item["type"] == "silence")
        self.assertGreater(silence["end_seconds"], silence["timestamp_seconds"])
        self.assertFalse(silence["auto_fixable"])
        self.assertEqual([], report["automatic_repairs_applied"])

    def test_wrong_aspect_and_resolution_are_structured(self):
        report = self.review("landscape")
        self.assertIn("aspect_ratio_mismatch", issue_types(report))
        self.assertIn("resolution_mismatch", issue_types(report))
        issue = next(item for item in report["issues"] if item["type"] == "aspect_ratio_mismatch")
        self.assertEqual(640, issue["evidence"]["width"])
        self.assertEqual(360, issue["evidence"]["height"])
        self.assertTrue(report["safe_transcode_candidate"]["eligible"])
        self.assertTrue(report["safe_transcode_candidate"]["required"])

    def test_safe_transcode_candidate_runs_without_changing_source(self):
        source = self.sources["landscape"]
        before = file_hash(source)
        report = self.review("landscape")
        command = list(report["safe_transcode_candidate"]["command"])
        output = self.root / "landscape-safe.mp4"
        command[-1] = str(output)
        subprocess.run(command, check=True, timeout=60)
        converted = self.reviewer().review(output, check_ocr=False)
        self.assertEqual("passed", converted["status"], converted["issues"])
        self.assertEqual(before, file_hash(source))
        self.assertEqual("h264", converted["media"]["video"]["codec_name"])
        self.assertEqual("aac", converted["media"]["audio"]["codec_name"])
        self.assertEqual("yuv420p", converted["media"]["video"]["pix_fmt"])
        self.assertTrue(converted["media"]["faststart"])
        self.assertNotIn("silenceremove", command)
        self.assertNotIn("blackdetect", command)

    def test_full_range_input_is_normalized_to_limited_yuv420p(self):
        source = self.sources["normal"]
        full_range = self.root / "full-range.mp4"
        subprocess.run([FFMPEG, "-v", "error", "-y", "-i", str(source),
                        "-vf", "scale=out_range=pc", "-color_range", "pc", "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", "-c:a", "copy", str(full_range)], check=True, timeout=60)
        output = self.root / "limited-range.mp4"
        command = build_safe_transcode_command(full_range, output, 360, 640)
        subprocess.run(command, check=True, timeout=60)
        converted = self.reviewer().review(output, check_ocr=False)
        self.assertEqual("passed", converted["status"], converted["issues"])
        self.assertEqual("yuv420p", converted["media"]["video"]["pix_fmt"])
        self.assertTrue(converted["machine_checks_passed"])

    def test_safe_candidate_refuses_overwrite_and_non_mp4(self):
        source = self.sources["normal"]
        with self.assertRaises(ValueError):
            build_safe_transcode_command(source, source, 360, 640)
        with self.assertRaises(ValueError):
            build_safe_transcode_command(source, self.root / "output.mov", 360, 640)

    def test_subtitle_out_of_bounds_contains_box_and_timestamp(self):
        reviewer = self.reviewer()
        ocr = [{"timestamp_seconds": 1.0, "lines": [{
            "box": [[0, 610], [200, 610], [200, 639], [0, 639]],
            "text": "越界字幕", "confidence": 0.98,
        }]}]
        with mock.patch.object(reviewer, "_ocr", return_value=(ocr, False)):
            report = reviewer.review(self.sources["normal"], check_ocr=True)
        issue = next(item for item in report["issues"] if item["type"] == "subtitle_out_of_bounds")
        self.assertEqual(1.0, issue["timestamp_seconds"])
        self.assertEqual("越界字幕", issue["evidence"]["text"])
        self.assertEqual(0, issue["evidence"]["box_pixels"]["left"])
        self.assertIn("safe_area_pixels", issue["evidence"])
        self.assertEqual("warning", report["checks"]["subtitle_bounds"])

    def test_unavailable_ocr_is_explicit_failure_not_a_pass(self):
        report = self.review("normal", check_ocr=True,
                             ocr_python=self.root / "missing-ocr-python")
        self.assertIn("ocr_unavailable", issue_types(report))
        self.assertEqual("failed", report["checks"]["subtitle_bounds"])
        self.assertEqual("failed", report["status"])
        self.assertFalse(report["machine_checks_passed"])

    def test_duration_and_issue_contract(self):
        report = self.review("normal", max_duration=1)
        issue = next(item for item in report["issues"] if item["type"] == "duration_out_of_range")
        for key in ("type", "severity", "timestamp_seconds", "evidence", "recommendation"):
            self.assertIn(key, issue)
        self.assertEqual("failed", report["checks"]["duration"])

    def test_every_source_file_remains_byte_identical(self):
        for name, path in self.sources.items():
            report = self.review(name)
            self.assertTrue(report["source"]["unchanged"])
            self.assertEqual(self.hashes[name], file_hash(path), name)

    @unittest.skipUnless(DEFAULT_OCR_PYTHON.is_file(), "需要项目现有 RapidOCR 隔离环境")
    def test_real_rapidocr_executes_and_reports_coverage(self):
        report = self.review("normal", check_ocr=True, ocr_timeout=180)
        self.assertNotIn("ocr_unavailable", issue_types(report), report["issues"])
        self.assertIn(report["checks"]["subtitle_bounds"], ("passed", "warning"))
        self.assertTrue(any("OCR" in value for value in report["limitations"]))


if __name__ == "__main__":
    unittest.main()
