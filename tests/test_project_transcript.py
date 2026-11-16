import json
import queue
import unittest
from unittest import mock

from content_workbench.providers.local import LocalExecutors


class ProjectTranscriptCase(unittest.TestCase):
    def test_executor_returns_word_timestamps_and_progress_context(self):
        task = {"content_id": "task-1"}
        payload = {"file_id": 7}
        context = mock.Mock()
        result_task = {
            "files": [
                {
                    "id": 8,
                    "kind": "srt",
                    "media_info": {
                        "source_audio_file_id": 7,
                        "duration_seconds": 1.25,
                        "words": [{"text": "真实", "start": 0.0, "end": 0.4}],
                    },
                }
            ]
        }
        job = {"aggregate_id": "task-1", "input": {"task": task, "payload": payload}}
        with mock.patch("app.transcribe_audio", return_value=result_task) as transcribe:
            result = LocalExecutors(mock.Mock()).project_transcript(job, context)
        transcribe.assert_called_once_with(task, payload, context)
        self.assertEqual(result["words"], [{"text": "真实", "start": 0.0, "end": 0.4}])
        self.assertEqual(result["source_file_id"], 7)
        self.assertEqual(result["duration_seconds"], 1.25)

    def test_transcript_prompt_is_short_and_contains_domain_terms(self):
        from app import transcript_prompt

        task = {
            "title": "制造业 AI",
            "source": {
                "yingxu": {
                    "snapshot": {
                        "manuscript": {
                            "title": "Claude for Manufacturing",
                            "text": "报价和质检。Claude、Team、Enterprise、Autodesk Fusion、Infor、Microsoft 365、Oracle NetSuite。",
                        }
                    }
                }
            },
        }
        prompt = transcript_prompt(task)
        self.assertLessEqual(len(prompt), 200)
        self.assertIn("Claude", prompt)
        self.assertIn("Infor", prompt)
        self.assertIn("报价和质检", prompt)

    def test_whisper_server_sends_manuscript_prompt_to_worker(self):
        from app import WhisperServer

        process = mock.Mock()
        process.poll.return_value = None
        server = WhisperServer.__new__(WhisperServer)
        server.process = process
        server.lock = mock.MagicMock()
        server.events = queue.Queue()
        server.events.put({"type": "result"})
        with mock.patch("app.probe_media", return_value={"duration_seconds": 1.0}):
            server.request("voice.wav", "out.srt", 1, mock.Mock(), "定稿 Claude")
        request = json.loads(process.stdin.write.call_args.args[0])
        self.assertEqual("定稿 Claude", request["initial_prompt"])

    def test_whisper_server_stop_closes_process(self):
        from app import WhisperServer

        process = mock.Mock()
        process.poll.return_value = None
        server = WhisperServer.__new__(WhisperServer)
        server.process = process
        server.stop()
        process.stdin.close.assert_called_once_with()
        process.wait.assert_called_once_with(timeout=5)
        process.terminate.assert_not_called()

    def test_whisper_server_stop_terminates_unresponsive_process(self):
        import subprocess

        from app import WhisperServer

        process = mock.Mock()
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired("worker", 5), None]
        server = WhisperServer.__new__(WhisperServer)
        server.process = process
        server.stop()
        process.terminate.assert_called_once_with()
        self.assertEqual(process.wait.call_count, 2)


if __name__ == "__main__":
    unittest.main()
