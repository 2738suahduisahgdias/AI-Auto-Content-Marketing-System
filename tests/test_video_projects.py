#!/usr/bin/env python3
import io
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import app


class VideoProjectCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="video-projects-")
        self.root = Path(self.temp.name).resolve()
        self.old = app.ROOT, app.DB_PATH
        app.ROOT = self.root
        app.DB_PATH = self.root / "data/content-agent.db"
        app.init_db()

    def tearDown(self):
        app.ROOT, app.DB_PATH = self.old
        self.temp.cleanup()

    def test_create_original_project_preserves_workflow_metadata(self):
        task = app.create_task(
            {
                "title": "原创项目",
                "source_type": "original",
                "direction": "解释能力换轨",
                "target_platforms": ["douyin", "xiaohongshu"],
                "aspect": "1080x1920",
                "content": "真实文案",
            }
        )
        self.assertEqual("original", task["source"]["project_type"])
        self.assertEqual("解释能力换轨", task["source"]["direction"])
        self.assertEqual(["douyin", "xiaohongshu"], task["source"]["target_platforms"])
        self.assertEqual("1080x1920", task["source"]["aspect"])
        self.assertEqual("真实文案", task["scripts"]["master"])

    def test_benchmark_report_uses_real_scene_frames_and_single_transcript(self):
        media = self.root / "reference.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=red:s=360x640:d=1",
                "-f",
                "lavfi",
                "-i",
                "color=c=blue:s=360x640:d=1",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:duration=2",
                "-filter_complex",
                "[0:v][1:v]concat=n=2:v=1:a=0[v]",
                "-map",
                "[v]",
                "-map",
                "2:a",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                str(media),
            ],
            check=True,
            capture_output=True,
        )
        task = app.create_task(
            {
                "title": "对标项目",
                "source_type": "benchmark",
                "usage_boundary": "本人制作",
            }
        )
        with (
            mock.patch("app.resolved_task_file", return_value=media),
            media.open("rb") as handle,
        ):
            file = app.upload_file(
                task, "video", media.name, (handle, media.stat().st_size), studio=True
            )
            task["files"].append(file)
            result = app.analyze_benchmark(
                task,
                {
                    "file_id": file["id"],
                    "usage_boundary": "本人制作",
                    "focus": "镜头节奏",
                },
            )
        snapshot = result["source"]["yingxu"]["snapshot"]
        report = snapshot["benchmark_report"]
        self.assertEqual("本人制作", report["usage_boundary"])
        self.assertEqual("镜头节奏", report["focus"])
        self.assertGreater(report["duration_seconds"], 1.5)
        self.assertTrue(snapshot["shots"])
        self.assertIn("transcript_status", report)
        self.assertEqual(1, snapshot["transcript_runs"])
        for shot in snapshot["shots"]:
            self.assertIn("start_seconds", shot)
            self.assertIn("end_seconds", shot)
            self.assertIn("keyframe_file_id", shot)
            self.assertIn("visual_observation", shot)

    def test_music_adapt_creates_distinct_real_audio_version(self):
        source = self.root / "music.wav"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:duration=2",
                "-c:a",
                "pcm_s16le",
                str(source),
            ],
            check=True,
            capture_output=True,
        )
        task = app.create_task({"title": "音乐项目", "source_type": "original"})
        with source.open("rb") as handle:
            file = app.upload_file(
                task, "audio", source.name, (handle, source.stat().st_size), studio=True
            )
        task["files"].append(file)
        original_file_id = file["id"]
        result = app.adapt_project_music(
            task,
            {"file_id": original_file_id, "method": "trim_fade", "duration_seconds": 1},
        )
        adapted = next(
            file
            for file in result["files"]
            if file["media_info"].get("adapted_from") == original_file_id
        )
        self.assertLessEqual(adapted["media_info"]["duration_seconds"], 1.05)
        self.assertNotEqual(file["id"], adapted["id"])
        self.assertTrue(source.is_file())

    def test_music_adapt_keep_silence_pads_to_requested_duration(self):
        source = self.root / "short-music.wav"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:duration=2",
                "-c:a",
                "pcm_s16le",
                str(source),
            ],
            check=True,
            capture_output=True,
        )
        task = app.create_task({"title": "保留无音乐段落", "source_type": "original"})
        with source.open("rb") as handle:
            file = app.upload_file(
                task, "audio", source.name, (handle, source.stat().st_size), studio=True
            )
        task["files"].append(file)
        result = app.adapt_project_music(
            task,
            {"file_id": file["id"], "method": "keep_silence", "duration_seconds": 4},
        )
        adapted = next(
            item
            for item in result["files"]
            if item["media_info"].get("adapted_from") == file["id"]
        )
        self.assertAlmostEqual(4, adapted["media_info"]["duration_seconds"], delta=0.05)
        self.assertEqual("keep_silence", adapted["media_info"]["adaptation_method"])

    def test_benchmark_render_honors_timing_audio_versions_and_music_choice(self):
        video = self.root / "replacement.mp4"
        narration = self.root / "narration.wav"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=navy:s=360x640:d=2",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=220:duration=2",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-shortest",
                str(video),
            ],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:duration=1",
                "-c:a",
                "pcm_s16le",
                str(narration),
            ],
            check=True,
            capture_output=True,
        )
        task = app.create_task({"title": "对标合成", "source_type": "benchmark"})
        with video.open("rb") as handle:
            video_file = app.upload_file(
                task, "video", video.name, (handle, video.stat().st_size), studio=True
            )
        with narration.open("rb") as handle:
            narration_file = app.upload_file(
                task,
                "audio",
                narration.name,
                (handle, narration.stat().st_size),
                studio=True,
            )
        task["files"].extend([video_file, narration_file])
        base = {
            "title": "镜头",
            "text": "新旁白",
            "desc": "真实画面",
            "source": "user_upload",
        }
        snapshot = {
            "manuscript": {"title": "对标合成", "text": "新旁白"},
            "musicConflict": "original",
            "bgmFileId": narration_file["id"],
            "shots": [
                {
                    **base,
                    "id": "one",
                    "fileId": video_file["id"],
                    "duration": 4,
                    "duration_choice": "original",
                    "trim_start": 0.5,
                    "fill_method": "loop",
                    "audio_source": "mute",
                },
                {
                    **base,
                    "id": "two",
                    "fileId": video_file["id"],
                    "narrationFileId": narration_file["id"],
                    "duration": 4,
                    "duration_choice": "new",
                    "trim_start": 0.25,
                    "audio_source": "replace",
                },
            ],
        }
        saved = app.save_yingxu(task, {"revision": 0, "snapshot": snapshot})
        old_remotion = app.REMOTION_APP
        app.REMOTION_APP = self.root / "remotion"
        try:
            props = app.yingxu_render_props(saved)
        finally:
            app.REMOTION_APP = old_remotion
        first, second = props["scenes"]
        self.assertEqual(4, first["end_seconds"] - first["start_seconds"])
        self.assertEqual(0.5, first["source_start_seconds"])
        self.assertTrue(first["media"]["loop"])
        self.assertTrue(first["media"]["muted"])
        self.assertAlmostEqual(
            1.75, second["end_seconds"] - second["start_seconds"], places=2
        )
        self.assertTrue(second["media"]["muted"])
        self.assertNotIn("backgroundMusic", props)
        self.assertNotIn("audio", props)
        self.assertEqual(4, props["audioSegments"][0]["timeline_start_seconds"])
        self.assertEqual(
            narration_file["id"],
            saved["source"]["yingxu"]["snapshot"]["shots"][1]["narrationFileId"],
        )

    def test_audio_separation_uses_kimi_plan_and_local_demucs(self):
        from content_workbench.media.ai_music import synthesize

        source = self.root / "source.wav"
        synthesize(
            {
                "duration_seconds": 1,
                "notes": [{"frequency": 440, "start": 0, "duration": 1, "volume": 0.2}],
            },
            source,
        )
        task = app.create_task({"title": "声音分离", "source_type": "original"})
        with source.open("rb") as handle:
            audio = app.upload_file(
                task,
                "audio",
                "source.wav",
                (handle, source.stat().st_size),
                studio=True,
            )
        provider = mock.Mock()
        provider.complete_json.return_value = {
            "engine": "demucs",
            "model": "htdemucs",
            "two_stems": "vocals",
        }
        demucs_binary = self.root / "demucs-python"
        demucs_binary.write_text("")

        def execute(arguments, timeout, output_limit, stage, cwd=None):
            folder = (
                Path(arguments[arguments.index("-o") + 1])
                / "htdemucs"
                / Path(arguments[-1]).stem
            )
            folder.mkdir(parents=True)
            for name in ("vocals.wav", "no_vocals.wav"):
                (folder / name).write_bytes(source.read_bytes())
            return "{}", ""

        with (
            mock.patch(
                "content_workbench.providers.system.provider_for", return_value=provider
            ) as factory,
            mock.patch.object(app, "run_process", side_effect=execute),
            mock.patch(
                "content_workbench.media.tools.demucs_python",
                return_value=demucs_binary,
            ),
        ):
            result = app.separate_project_audio(task, {"file_id": audio["id"]})
        factory.assert_called_once_with(app.ROOT, "kimi_cli")
        self.assertEqual(
            provider.complete_json.call_args.kwargs["model"], "default_unpinned"
        )
        self.assertEqual(2, len(result["files"]) - 1)
        roles = {
            file["media_info"]["separation_role"]
            for file in result["files"]
            if "separation_role" in file["media_info"]
        }
        self.assertEqual({"vocals", "accompaniment"}, roles)

    def test_visual_analysis_uses_kimi_and_real_keyframes(self):
        from tests.test_article_images import PNG

        task = app.create_task({"title": "视觉分析", "source_type": "benchmark"})
        keyframe = app.upload_file(
            task, "asset", "frame.png", (io.BytesIO(PNG), len(PNG)), studio=True
        )
        saved = app.save_yingxu(
            task,
            {
                "revision": 0,
                "snapshot": {
                    "shots": [
                        {
                            "id": "scene-01",
                            "title": "镜头 01",
                            "text": "",
                            "desc": "待分析",
                            "duration": 1,
                            "source": "reference",
                            "keyframe_file_id": keyframe["id"],
                        }
                    ],
                    "benchmark_report": {"source_file_id": keyframe["id"]},
                },
            },
        )
        provider = mock.Mock()
        provider.complete_json.return_value = {
            "shots": [
                {
                    "id": "scene-01",
                    "visual_observation": "蓝色背景",
                    "desc": "纯色测试画面",
                }
            ]
        }
        with mock.patch(
            "content_workbench.providers.system.provider_for", return_value=provider
        ) as factory:
            result = app.analyze_benchmark_visual(saved)
        factory.assert_called_once_with(app.ROOT, "kimi_cli")
        shot = result["source"]["yingxu"]["snapshot"]["shots"][0]
        self.assertEqual("蓝色背景", shot["visual_observation"])
        self.assertEqual("纯色测试画面", shot["desc"])
        request = provider.complete_json.call_args.args[0]
        self.assertIn("frame.png", request)
        self.assertIn(str(app.ROOT), request)

    def test_ai_video_candidate_uses_current_shot_and_stays_separate(self):
        task = app.create_task({"title": "Kimi 单镜", "source_type": "original"})
        saved = app.save_yingxu(
            task,
            {
                "revision": 0,
                "snapshot": {
                    "shots": [
                        {
                            "title": "镜头",
                            "text": "文案",
                            "desc": "信息图",
                            "duration": 1,
                            "source": "Remotion 代码",
                        }
                    ],
                },
            },
        )
        rendered = mock.Mock(return_value={"id": 99, "media_info": {}})
        with mock.patch.object(app, "render_yingxu", rendered):
            result = app.generate_ai_video(saved, {"revision": 1, "shot_index": 0})
        payload = rendered.call_args.args[1]
        self.assertTrue(payload["candidate"])
        self.assertEqual(0, payload["shot_index"])
        self.assertTrue(result["media_info"]["ai_candidate"])

    def test_ai_music_synthesis_writes_real_wav(self):
        from content_workbench.media.ai_music import synthesize

        output = self.root / "music.wav"
        score = {
            "duration_seconds": 1,
            "notes": [
                {
                    "frequency": 440,
                    "start": 0,
                    "duration": 1,
                    "volume": 0.2,
                    "wave": "sine",
                }
            ],
        }
        info = synthesize(score, output)
        self.assertTrue(output.is_file())
        self.assertEqual(1, info["duration_seconds"])
        self.assertEqual(1, info["note_count"])

    def test_generate_project_music_uses_kimi_and_stores_file(self):
        task = app.create_task({"title": "Kimi 配乐", "source_type": "original"})
        score = {
            "duration_seconds": 1,
            "notes": [
                {
                    "frequency": 440,
                    "start": 0,
                    "duration": 1,
                    "volume": 0.2,
                    "wave": "sine",
                }
            ],
        }
        provider = mock.Mock()
        provider.complete_json.return_value = score
        with mock.patch(
            "content_workbench.providers.system.provider_for", return_value=provider
        ) as factory:
            result = app.generate_project_music(
                task, {"duration_seconds": 1, "direction": "平静"}
            )
        factory.assert_called_once_with(app.ROOT, "kimi_cli")
        generated = result["files"][-1]
        self.assertEqual("kimi_cli", generated["media_info"]["provider"])
        self.assertEqual("local_score_synth", generated["media_info"]["renderer"])
        self.assertEqual(1, generated["media_info"]["duration_seconds"])

    def test_render_self_test_tolerates_already_removed_temp_dir(self):
        old_public = app.REMOTION_PUBLIC
        app.REMOTION_PUBLIC = self.root / "remotion-public"
        try:
            original_rmtree = app.shutil.rmtree

            def remove_tree(path, **kwargs):
                if Path(path).name.startswith("_render_test_"):
                    raise FileNotFoundError(2, "No such file or directory")
                return original_rmtree(path, **kwargs)

            with (
                mock.patch.object(app.subprocess, "run"),
                mock.patch.object(app, "run_remotion_render"),
                mock.patch.object(app, "validate_rendered_mp4"),
                mock.patch.object(app.shutil, "rmtree", side_effect=remove_tree),
            ):
                result = app.test_render_agent()
            self.assertTrue(result["ready"])
        finally:
            app.REMOTION_PUBLIC = old_public

    def test_kimi_agent_files_have_frontmatter(self):
        agents = Path(app.__file__).resolve().parent / "agents"
        for agent_file in agents.glob("*.md"):
            with self.subTest(agent=agent_file.name):
                content = agent_file.read_text(encoding="utf-8")
                self.assertTrue(content.startswith("---\n"))
                frontmatter = content.split("---", 2)[1]
                self.assertIn("name:", frontmatter)
                self.assertIn("description:", frontmatter)
                if agent_file.name == "visual-analysis-agent.md":
                    self.assertIn("- ReadMediaFile", frontmatter)
                elif agent_file.name == "douyin-collection-agent.md":
                    self.assertIn("- mcp__chrome-persistent__", frontmatter)
                    self.assertNotIn("- Bash", frontmatter)
                elif agent_file.name == "douyin-download-agent.md":
                    self.assertIn("- Bash", frontmatter)
                elif agent_file.name == "xiaohongshu-collection-agent.md":
                    self.assertIn("- mcp__chrome-persistent__", frontmatter)
                    self.assertNotIn("- Bash", frontmatter)
                elif agent_file.name == "xiaohongshu-download-agent.md":
                    self.assertIn("- Bash", frontmatter)
                    self.assertIn(
                        "- mcp__chrome-persistent__evaluate_script", frontmatter
                    )
                else:
                    self.assertIn("tools: []", frontmatter)
                    self.assertNotIn("Bash", frontmatter)


if __name__ == "__main__":
    unittest.main()
