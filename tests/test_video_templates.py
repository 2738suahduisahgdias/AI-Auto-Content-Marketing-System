import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import app
from content_workbench.media.templates import TemplateError, load_templates, resolve_template, stable_templates, template_props


class TemplateRegistryCase(unittest.TestCase):
    def test_stable_registry_and_props(self):
        self.assertEqual(10, len(load_templates()))
        self.assertEqual({"founder-ip@1.0.0", "enterprise-explainer@1.0.0", "warm-story@0.1.0", "promo@1.0.0",
                          "tech-showcase@1.0.0", "data-story@1.0.0", "audiogram@1.0.0", "map-story@1.0.0",
                          "karaoke-caption@1.0.0", "kinetic-text@1.0.0"},
                         {item["key"] for item in stable_templates()})
        template = resolve_template("founder-ip@1.0.0", for_render=True)
        props = template_props(template, {"appearance": {"accentColor": "#123456"}})
        self.assertEqual("#123456", props["appearance"]["accentColor"])
        self.assertEqual("#10251e", props["appearance"]["background"])
        with self.assertRaises(TemplateError):
            template_props(template, {"compositionId": "Injected"})
        with self.assertRaises(TemplateError):
            resolve_template("missing@9.9.9", for_render=True)

    def test_legacy_and_multiple_template_requests(self):
        legacy = app.render_template_requests({"mode": "remotion"}, "remotion")
        self.assertEqual("founder-ip@1.0.0", legacy[0][0]["key"])
        multiple = app.render_template_requests({"template_ids": ["founder-ip@1.0.0", "enterprise-explainer@1.0.0"]}, "remotion")
        self.assertEqual(2, len(multiple))
        with self.assertRaises(app.ApiError):
            app.render_template_requests({"template_ids": ["missing@9.9.9"]}, "remotion")
        with self.assertRaises(app.ApiError):
            app.render_template_requests({"template_ids": ["founder-ip@1.0.0"]}, "upload")

    def test_template_status_lifecycle(self):
        import shutil
        from content_workbench.media.templates import TEMPLATE_PATH, set_template_status

        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "templates.json"
            shutil.copy(TEMPLATE_PATH, path)
            updated = set_template_status("warm-story@0.1.0", "stable", path=path)
            self.assertEqual("stable", next(item["status"] for item in updated if item["id"] == "warm-story"))
            updated = set_template_status("warm-story@0.1.0", "deprecated", path=path)
            self.assertEqual("deprecated", next(item["status"] for item in updated if item["id"] == "warm-story"))
            with self.assertRaises(TemplateError):
                set_template_status("missing@9.9.9", "stable", path=path)
            with self.assertRaises(TemplateError):
                set_template_status("warm-story@0.1.0", "broken", path=path)
            self.assertEqual("stable", next(item["status"] for item in load_templates() if item["id"] == "warm-story"))

    def test_input_hash_tracks_content_and_props(self):
        first = app.render_input_hash({"audio_file_id": 1}, {"appearance": {"accentColor": "green"}})
        self.assertEqual(first, app.render_input_hash({"audio_file_id": 1}, {"appearance": {"accentColor": "green"}}))
        self.assertNotEqual(first, app.render_input_hash({"audio_file_id": 2}, {"appearance": {"accentColor": "green"}}))
        self.assertNotEqual(first, app.render_input_hash({"audio_file_id": 1}, {"appearance": {"accentColor": "blue"}}))


class RenderRunCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="video-template-test-")
        self.root = Path(self.temp.name).resolve()
        self.old = (app.ROOT, app.DB_PATH, app.REMOTION_PUBLIC)
        app.ROOT = self.root
        app.DB_PATH = self.root / "data" / "test.db"
        app.REMOTION_PUBLIC = self.root / "remotion-public"
        app.REMOTION_PUBLIC.mkdir(parents=True)
        app.init_db()
        self.content_id = "20261029-001"
        with app.connect() as conn:
            conn.execute("""INSERT INTO tasks(content_id,title,pillar,audience,state,created_at,updated_at)
                            VALUES (?,?,?,?,?,?,?)""",
                         (self.content_id, "模板测试", "enterprise_ai", "business_owners", "assets_approved", app.now(), app.now()))
            audio = self.root / "voice" / self.content_id / "audio.wav"
            audio.parent.mkdir(parents=True)
            audio.write_bytes(b"test-audio")
            subtitle = self.root / "subtitles" / self.content_id / "captions.srt"
            subtitle.parent.mkdir(parents=True)
            subtitle.write_text("1\n00:00:00,000 --> 00:00:01,800\n测试字幕\n\n", encoding="utf-8")
            for kind, path, media_info in (
                ("audio", audio, {"duration_seconds": 2}),
                ("srt", subtitle, {}),
            ):
                conn.execute("""INSERT INTO files(content_id,kind,original_name,relative_path,size,media_info_json,created_at)
                                VALUES (?,?,?,?,?,?,?)""",
                             (self.content_id, kind, path.name, path.relative_to(self.root).as_posix(), path.stat().st_size,
                              json.dumps(media_info), app.now()))
        with app.connect() as conn:
            self.task = app.get_task(conn, self.content_id)

    def tearDown(self):
        app.ROOT, app.DB_PATH, app.REMOTION_PUBLIC = self.old
        self.temp.cleanup()

    def approve_previews(self, payload):
        for key in payload["template_ids"]:
            result = app.create_visual_preview(self.task, {**payload, "template_ids": [key]})
            with app.DB_LOCK, app.connect() as conn:
                conn.execute("UPDATE visual_previews SET status='succeeded',approved_at=? WHERE id=?",
                             (app.now(), result["preview"]["id"]))

    def render(self, fake_render):
        payload = {"mode": "remotion", "platform": "douyin",
                   "template_ids": ["founder-ip@1.0.0", "enterprise-explainer@1.0.0"]}
        self.approve_previews(payload)
        with mock.patch.object(app, "run_remotion_render", side_effect=fake_render) as renderer, \
                mock.patch.object(app, "validate_rendered_mp4", return_value={"duration_seconds": 2, "streams": []}), \
                mock.patch.object(app, "record_render_result"):
            result = app.render_task(self.task, payload)
        return result, renderer

    def test_render_requires_approved_current_preview(self):
        payload = {"mode": "remotion", "platform": "douyin", "template_ids": ["founder-ip@1.0.0"]}
        with self.assertRaises(app.ApiError) as blocked:
            app.render_task(self.task, payload)
        self.assertEqual(409, blocked.exception.status)
        self.approve_previews(payload)
        candidate = app.visual_preview_candidate(self.task, payload)
        changed = {**self.task, "scripts": {"douyin": "修改后的文稿"}}
        changed_candidate = app.visual_preview_candidate(changed, payload)
        self.assertNotEqual(candidate["fingerprint"], changed_candidate["fingerprint"])

    def test_multiple_templates_and_cache(self):
        def success(_props, output, _timeout, _composition_id, **_kwargs):
            Path(output).write_bytes(b"mp4")

        result, renderer = self.render(success)
        self.assertEqual(["succeeded", "succeeded"], [item["status"] for item in result["render_results"]])
        self.assertEqual(2, renderer.call_count)
        self.assertEqual(4, len(result["files"]))
        self.assertEqual(2, len(result["render_runs"]))
        for run in result["render_runs"]:
            self.assertEqual(64, len(run["input_hash"]))
        with app.connect() as conn:
            task = app.get_task(conn, self.content_id)
        cached, renderer = self.render(success)
        self.assertEqual(["cached", "cached"], [item["status"] for item in cached["render_results"]])
        self.assertEqual(0, renderer.call_count)
        self.assertEqual(4, len(cached["files"]))

    def test_partial_failure_keeps_success(self):
        def fail_enterprise(props, output, _timeout, _composition_id, **_kwargs):
            if props["appearance"]["background"] != "#10251e":
                raise app.ApiError(502, "模拟单模板失败")
            Path(output).write_bytes(b"mp4")

        result, _ = self.render(fail_enterprise)
        self.assertEqual({"succeeded", "failed"}, {item["status"] for item in result["render_results"]})
        self.assertEqual(3, len(result["files"]))
        self.assertEqual("founder-ip", result["generated_file"]["media_info"]["template_id"])
        self.assertTrue(any(run["status"] == "failed" for run in result["render_runs"]))

    def test_background_production_and_contracts(self):
        class Context:
            def __init__(self):
                self.events = []
            def progress(self, stage, value):
                self.events.append((stage, value))
            def check_cancelled(self):
                return None

        def success(_props, output, _timeout, _composition_id, **_kwargs):
            Path(output).write_bytes(b"mp4")

        context = Context()
        job = {"aggregate_id": self.content_id, "input": {"mode": "remotion", "template_ids": ["founder-ip@1.0.0"]}}
        self.approve_previews(job["input"])
        with mock.patch.object(app, "run_remotion_render", side_effect=success), \
                mock.patch.object(app, "validate_rendered_mp4", return_value={"duration_seconds": 2, "streams": []}), \
                mock.patch.object(app, "record_render_result"):
            result = app.produce_video_task(job, context)
        self.assertEqual(self.content_id, result["content_id"])
        self.assertEqual("render", result["stage_timings"][-1]["stage"])
        self.assertEqual(1, len(result["video_package"]["variants"]))
        self.assertEqual(3, result["video_package"]["variants"][0]["file_id"])
        brief = app.video_brief(self.task)
        self.assertEqual("agent", brief["review_mode"])
        self.assertEqual("local_only", brief["publish_mode"])
        self.assertTrue(any(stage == "completed" for stage, _ in context.events))

    def test_same_preview_request_is_deduplicated_not_superseded(self):
        payload = {"mode": "remotion", "platform": "douyin", "template_ids": ["founder-ip@1.0.0"]}
        first = app.create_visual_preview(self.task, payload)
        second = app.create_visual_preview(self.task, payload)
        self.assertEqual(first["preview"]["id"], second["preview"]["id"])
        self.assertEqual("queued", second["preview"]["status"])

    def test_preview_worker_persists_video_cover_and_approval(self):
        payload = {"mode": "remotion", "platform": "douyin", "template_ids": ["founder-ip@1.0.0"]}
        created = app.create_visual_preview(self.task, payload)
        preview_id = created["preview"]["id"]
        scales = []

        def success(_props, output, _timeout, _composition_id, **kwargs):
            Path(output).write_bytes(b"png" if str(output).endswith(".png") else b"mp4")
            scales.append(kwargs.get("scale"))

        class Context:
            def progress(self, _stage, _value):
                return None

        with mock.patch.object(app, "run_remotion_render", side_effect=success), \
                mock.patch.object(app, "validate_rendered_mp4", return_value={"duration_seconds": 2, "streams": []}), \
                mock.patch.object(app, "probe_media", return_value={"width": 540, "height": 960}):
            result = app.produce_visual_preview({"aggregate_id": self.content_id, "input": {"preview_id": preview_id}}, Context())
        self.assertEqual("succeeded", result["status"])
        self.assertEqual([0.5, 0.5], scales)
        with app.connect() as conn:
            row = app.get_preview(conn, self.content_id, preview_id)
            self.assertEqual("succeeded", row["status"])
            self.assertIsNotNone(row["video_file_id"])
            self.assertIsNotNone(row["cover_file_id"])
        approved = app.approve_visual_preview(self.task, preview_id)
        self.assertTrue(approved["preview"]["approved"])

    def test_two_variants_are_approved_independently(self):
        def success(_props, output, _timeout, _composition_id, **_kwargs):
            Path(output).write_bytes(b"mp4")

        result, _ = self.render(success)
        variants = result["variants"]
        self.assertEqual(2, len(variants))
        for variant in variants:
            with app.connect() as conn:
                task = app.get_task(conn, self.content_id)
            payload = {"checks": {key: True for key in app.QUALITY_KEYS}, "note": "通过", "variant_id": variant["id"]}
            app.save_quality(task, payload)
            with app.connect() as conn:
                task = app.get_task(conn, self.content_id)
            app.task_action(task, {"action": "submit_review", "variant_id": variant["id"]})
            with app.connect() as conn:
                task = app.get_task(conn, self.content_id)
            app.task_action(task, {"action": "approve_final", "variant_id": variant["id"]})
        with app.connect() as conn:
            task = app.get_task(conn, self.content_id)
        self.assertTrue(all(item["approved_at"] for item in task["variants"]))
        return task

    def test_publication_queue_lists_approved_variants(self):
        from content_workbench.publishing.service import PublishingService

        self.test_two_variants_are_approved_independently()
        queue = PublishingService(app.DB_PATH, app.ROOT).publication_queue()
        items = queue["items"]
        self.assertEqual(2, len(items))
        self.assertEqual(2, len({item["variant_id"] for item in items}))
        self.assertTrue(all(item["variant_id"] and item["file_id"] for item in items))

    def test_cover_from_frame_and_ai(self):
        import subprocess

        video = self.root / "renders" / self.content_id / "source.mp4"
        video.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=360x640:d=1",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)], check=True, capture_output=True)
        with app.connect() as conn:
            conn.execute("""INSERT INTO files(content_id,kind,original_name,relative_path,size,media_info_json,created_at)
                            VALUES (?,?,?,?,?,?,?)""",
                         (self.content_id, "video", "source.mp4", video.relative_to(self.root).as_posix(),
                          video.stat().st_size, json.dumps({"duration_seconds": 1}), app.now()))
        with app.connect() as conn:
            task = app.get_task(conn, self.content_id)
        result = app.generate_cover(task, {"source": "frame"})
        cover = result["generated_file"]
        self.assertEqual("cover", cover["kind"])
        self.assertEqual((360, 640), (cover["media_info"]["width"], cover["media_info"]["height"]))
        self.assertTrue((self.root / cover["relative_path"]).is_file())

        def fake_render(_props, output, _timeout, _composition_id, **_kwargs):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=white:s=1080x1920:d=0.1",
                            "-frames:v", "1", str(output)], check=True, capture_output=True)

        with mock.patch.object(app, "run_remotion_render", side_effect=fake_render):
            result = app.generate_cover(task, {"source": "ai", "template": "founder-ip@1.0.0"})
        self.assertEqual("cover", result["generated_file"]["kind"])
        self.assertEqual(1080, result["generated_file"]["media_info"]["width"])

    def test_audio_upload_triggers_auto_subtitle_attempt(self):
        import subprocess
        import time

        with app.connect() as conn:
            conn.execute("UPDATE tasks SET state='script_approved' WHERE content_id=?", (self.content_id,))
        wav = self.root / "voice-in.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                        str(wav)], check=True, capture_output=True)
        with app.connect() as conn:
            task = app.get_task(conn, self.content_id)
        app.upload_file(task, "audio", "voice.wav", wav.read_bytes())
        deadline = time.time() + 10
        events = []
        while time.time() < deadline:
            with app.connect() as conn:
                events = [row["event"] for row in conn.execute("SELECT event FROM events WHERE content_id=?",
                                                               (self.content_id,)).fetchall()]
            if any(event.startswith("自动字幕") for event in events):
                break
            time.sleep(0.2)
        self.assertTrue(any(event.startswith("自动字幕") for event in events))


if __name__ == "__main__":
    unittest.main()
