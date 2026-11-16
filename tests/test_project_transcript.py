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
