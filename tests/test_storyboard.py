import unittest

from content_workbench.media.storyboard import ENGINE_VERSION, build_preview_props, build_storyboard


class StoryboardCase(unittest.TestCase):
    def setUp(self):
        self.props = {
            "title": "企业 AI 落地",
            "audio": "audio.wav",
            "durationSeconds": 24,
            "captions": [
                {"text": "减少40%的重复工作", "startMs": 0, "endMs": 5000, "timestampMs": None, "confidence": None},
                {"text": "第一步找任务，第二步接数据，第三步验收", "startMs": 5000, "endMs": 11000, "timestampMs": None, "confidence": None},
                {"text": "传统方式对比AI方式", "startMs": 11000, "endMs": 17000, "timestampMs": None, "confidence": None},
                {"text": "从华东扩展到华南", "startMs": 17000, "endMs": 23000, "timestampMs": None, "confidence": None},
            ],
            "scenes": [
                {"id": "m", "name": "效率", "description": "减少40%的重复工作", "start_seconds": 0, "end_seconds": 6, "media": None},
                {"id": "p", "name": "路径", "description": "第一步找任务，第二步接数据，第三步验收", "start_seconds": 6, "end_seconds": 12, "media": None},
                {"id": "c", "name": "对比", "description": "传统方式对比AI方式", "start_seconds": 12, "end_seconds": 18, "media": None},
                {"id": "l", "name": "布局", "description": "从华东扩展到华南", "start_seconds": 18, "end_seconds": 24, "media": None},
            ],
        }

    def test_semantic_types_metrics_and_visual_beats(self):
        result = build_storyboard(self.props, "20261030-001")
        self.assertEqual(["metric", "process", "comparison", "map"], [scene["type"] for scene in result["scenes"]])
        self.assertEqual(40, result["scenes"][0]["data"]["metric"]["value"])
        self.assertEqual(ENGINE_VERSION, result["storyboard"]["engine_version"])
        for scene in result["scenes"]:
            offsets = [beat["offset_seconds"] for beat in scene["visualBeats"]]
            self.assertGreaterEqual(len(offsets), 2)
            self.assertTrue(all(2 <= second - first <= 4 for first, second in zip(offsets, offsets[1:])))
        self.assertEqual(result, build_storyboard(self.props, "20261030-001"))

    def test_traditional_whisper_text_uses_same_semantics(self):
        props = {**self.props, "scenes": [
            {"id": "traditional", "name": "方式", "description": "第三步人工驗收結果，傳統方式靠人工反覆操作。", "start_seconds": 0, "end_seconds": 5, "media": None},
            {"id": "locations", "name": "布局", "description": "業務從華東擴展到華南時，也能複製這套流程。", "start_seconds": 5, "end_seconds": 10, "media": None},
        ]}
        result = build_storyboard(props, "20261030-001")
        self.assertEqual(["comparison", "map"], [scene["type"] for scene in result["scenes"]])
        self.assertEqual(["华东", "华南"], result["scenes"][1]["locations"])

    def test_preview_uses_real_segments_and_aligned_audio(self):
        full = build_storyboard(self.props, "20261030-001")
        preview = build_preview_props(full)
        self.assertEqual(10, preview["durationSeconds"])
        self.assertNotIn("audio", preview)
        self.assertEqual(len(preview["scenes"]), len(preview["audioSegments"]))
        self.assertIn("process", [scene["type"] for scene in preview["scenes"]])
        timeline = 0
        for scene, audio in zip(preview["scenes"], preview["audioSegments"]):
            self.assertAlmostEqual(timeline, scene["start_seconds"], places=2)
            self.assertAlmostEqual(scene["source_start_seconds"], audio["start_seconds"])
            self.assertAlmostEqual(scene["source_end_seconds"], audio["end_seconds"])
            self.assertAlmostEqual(scene["start_seconds"], audio["timeline_start_seconds"])
            timeline = scene["end_seconds"]
        self.assertAlmostEqual(10, timeline)
        self.assertTrue(all(caption["startMs"] >= 0 and caption["endMs"] <= 10050 for caption in preview["captions"]))


if __name__ == "__main__":
    unittest.main()
