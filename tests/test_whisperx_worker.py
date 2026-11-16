#!/usr/bin/env python3
import io
import json
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class WhisperXWorkerCase(unittest.TestCase):
    def test_writes_real_word_timestamps_next_to_srt(self):
        class Word:
            def __init__(self, start, end, text):
                self.start = start
                self.end = end
                self.word = text

        class Segment:
            def __init__(self):
                self.start = 0.0
                self.end = 1.0
                self.text = "真实 旁白"
                self.words = [Word(0.0, 0.4, "真实"), Word(0.4, 0.9, "旁白")]

        class Model:
            def __init__(self, *args, **kwargs):
                pass

            def transcribe(self, *args, **kwargs):
                return [Segment()], None

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "voice.srt"
            with (
                mock.patch.dict(
                    sys.modules,
                    {"faster_whisper": type("Module", (), {"WhisperModel": Model})},
                    clear=False,
                ),
                mock.patch.object(
                    sys,
                    "argv",
                    [
                        "whisperx_worker.py",
                        "--audio",
                        "voice.wav",
                        "--output",
                        str(output),
                    ],
                ),
            ):
                runpy.run_path("workers/whisperx_worker.py", run_name="__main__")
            words = json.loads(output.with_suffix(".words.json").read_text())
            self.assertEqual(
                [
                    {"text": "真实", "start": 0.0, "end": 0.4},
                    {"text": "旁白", "start": 0.4, "end": 0.9},
                ],
                words,
            )

    def test_server_reuses_model_and_reports_real_progress(self):
        instances = []

        class Word:
            def __init__(self):
                self.start = 0.0
                self.end = 0.4
                self.word = "词"

        class Segment:
            def __init__(self, end):
                self.start = 0.0
                self.end = end
                self.text = "旁白"
                self.words = [Word()]

        class Model:
            def __init__(self, *args, **kwargs):
                instances.append(self)

            def transcribe(self, *args, **kwargs):
                return [Segment(1.0), Segment(2.0)], None

        with tempfile.TemporaryDirectory() as directory:
            first = str(Path(directory) / "first.srt")
            second = str(Path(directory) / "second.srt")
            requests = (
                "\n".join(
                    json.dumps({"audio": "voice.wav", "output": output})
                    for output in (first, second)
                )
                + "\n"
            )
            with (
                mock.patch.dict(
                    sys.modules,
                    {"faster_whisper": type("Module", (), {"WhisperModel": Model})},
                    clear=False,
                ),
                mock.patch.object(
                    sys, "argv", ["whisperx_worker.py", "--serve", "--model", "base"]
                ),
                mock.patch.object(sys, "stdin", io.StringIO(requests)),
                mock.patch.object(sys, "stdout", io.StringIO()) as output,
            ):
                runpy.run_path("workers/whisperx_worker.py", run_name="__main__")
            events = [json.loads(line) for line in output.getvalue().splitlines()]
            self.assertEqual(len(instances), 1)
            self.assertIn("model_ready", [event.get("stage") for event in events])
            self.assertEqual(
                [0.0, 1.0, 2.0, 0.0, 1.0, 2.0],
                [
                    event["completed_seconds"]
                    for event in events
                    if event.get("stage") == "transcribing"
                ],
            )
            self.assertEqual(
                [event["type"] for event in events if event["type"] == "result"],
                ["result", "result"],
            )

    def test_server_uses_manuscript_prompt_and_stable_beam(self):
        calls = []

        class Word:
            def __init__(self):
                self.start = 0.0
                self.end = 0.4
                self.word = "Claude"

        class Segment:
            def __init__(self):
                self.start = 0.0
                self.end = 0.4
                self.text = "Claude"
                self.words = [Word()]

        class Model:
            def __init__(self, *args, **kwargs):
                pass

            def transcribe(self, *args, **kwargs):
                calls.append(kwargs)
                return [Segment()], None

        with tempfile.TemporaryDirectory() as directory:
            output = str(Path(directory) / "voice.srt")
            request = json.dumps(
                {
                    "audio": "voice.wav",
                    "output": output,
                    "initial_prompt": "定稿 Claude for Manufacturing",
                }
            )
            with (
                mock.patch.dict(
                    sys.modules,
                    {"faster_whisper": type("Module", (), {"WhisperModel": Model})},
                    clear=False,
                ),
                mock.patch.object(sys, "argv", ["whisperx_worker.py", "--serve"]),
                mock.patch.object(sys, "stdin", io.StringIO(request + "\n")),
                mock.patch.object(sys, "stdout", io.StringIO()),
            ):
                runpy.run_path("workers/whisperx_worker.py", run_name="__main__")
            self.assertEqual(5, calls[0]["beam_size"])
            self.assertEqual("定稿 Claude for Manufacturing", calls[0]["initial_prompt"])
            self.assertNotIn("hotwords", calls[0])


if __name__ == "__main__":
    unittest.main()
