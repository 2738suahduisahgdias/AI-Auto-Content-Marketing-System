#!/usr/bin/env python3
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from content_workbench.media import slim


class SlimDependenciesTest(unittest.TestCase):
    def setUp(self) -> None:
        slim._WORKER = None
        self.environment = mock.patch.dict("os.environ", {"CONTENT_AGENT_SLIM": "1"})
        self.environment.start()

    def tearDown(self) -> None:
        self.environment.stop()
        slim._WORKER = None

    def test_empty_workspace_requires_all_downloads(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            result = slim.status(Path(folder))
            self.assertTrue(result["slim"])
            self.assertTrue(result["required"])
            self.assertFalse(result["complete"])
            self.assertEqual(result["completed"], 0)
            self.assertEqual(result["total"], 9)

    def test_existing_browser_is_not_downloaded_again(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            marker = (
                root / "tools/playwright-browsers/chromium-1140/INSTALLATION_COMPLETE"
            )
            marker.parent.mkdir(parents=True)
            marker.write_text("ok")
            self.assertTrue(slim._ready(root, "browser_media"))
            result = slim.status(root)
            browser = next(
                item for item in result["items"] if item["id"] == "browser_media"
            )
            self.assertEqual(browser["status"], "succeeded")

    def test_failure_is_saved_with_log_and_stops_remaining_items(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            resources = root / "resources"
            with (
                mock.patch.object(slim, "_ready", return_value=False),
                mock.patch.object(
                    slim.subprocess,
                    "run",
                    side_effect=subprocess.CalledProcessError(1, "download"),
                ) as run,
                mock.patch.object(slim, "_tail", return_value="network down"),
            ):
                slim._run(root, resources)
            self.assertEqual(run.call_count, 1)
            state = json.loads((root / "cache/slim-dependencies.json").read_text())
            self.assertIsNone(state["active"])
            self.assertEqual(state["items"]["python"]["status"], "failed")
            self.assertIn("network down", state["error"])

    def test_full_edition_does_not_require_downloads(self) -> None:
        self.environment.stop()
        with (
            mock.patch.dict("os.environ", {}, clear=True),
            mock.patch.object(slim, "is_slim", return_value=False),
        ):
            result = slim.status(Path("/unused"))
            self.assertFalse(result["slim"])
            self.assertFalse(result["required"])
            self.assertEqual(result["edition"], "全量离线版")
        self.environment.start()


if __name__ == "__main__":
    unittest.main()
