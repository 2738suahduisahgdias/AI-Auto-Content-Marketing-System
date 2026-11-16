import tempfile
import unittest
from pathlib import Path
from unittest import mock

from content_workbench.domain.errors import DomainError
from content_workbench.topics import browser_worker


class DedicatedBrowserTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="yingxu-browser-test-")
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_launch_uses_fixed_app_profile_and_loopback_only(self) -> None:
        from content_workbench.accounts import dedicated_browser

        process = mock.Mock()
        process.poll.return_value = None
        with (
            mock.patch.object(dedicated_browser, "ROOT", self.root),
            mock.patch.object(
                dedicated_browser,
                "_managed_process",
                side_effect=[None, (123, "Chrome")],
            ),
            mock.patch.object(
                dedicated_browser, "_version", return_value={"Browser": "Chrome/157"}
            ),
            mock.patch.object(
                dedicated_browser.subprocess, "Popen", return_value=process
            ) as launch,
            mock.patch.object(dedicated_browser.time, "sleep"),
        ):
            self.assertEqual(
                "http://127.0.0.1:9223", dedicated_browser.ensure_started()
            )
        arguments = launch.call_args.args[0]
        profile = (self.root / "data/yingxu-chrome-profile").resolve()
        self.assertIn("--remote-debugging-address=127.0.0.1", arguments)
        self.assertIn("--remote-debugging-port=9223", arguments)
        self.assertIn("--user-data-dir=" + str(profile), arguments)
        self.assertNotIn("--remote-allow-origins=*", arguments)
        self.assertTrue(profile.is_dir())

    def test_reuses_only_the_same_dedicated_profile(self) -> None:
        from content_workbench.accounts import dedicated_browser

        with (
            mock.patch.object(
                dedicated_browser, "_managed_process", return_value=(123, "Chrome")
            ) as process,
            mock.patch.object(
                dedicated_browser, "_version", return_value={"Browser": "Chrome/157"}
            ),
            mock.patch.object(dedicated_browser.subprocess, "Popen") as launch,
        ):
            self.assertEqual(
                "http://127.0.0.1:9223", dedicated_browser.ensure_started()
            )
        process.assert_called_once()
        launch.assert_not_called()

    def test_rejects_a_browser_owned_by_another_profile(self) -> None:
        from content_workbench.accounts import dedicated_browser

        with (
            mock.patch.object(
                dedicated_browser,
                "_managed_process",
                side_effect=DomainError(
                    "BROWSER_PORT_OCCUPIED", "端口属于其他浏览器", 409
                ),
            ),
            mock.patch.object(dedicated_browser.subprocess, "Popen") as launch,
        ):
            with self.assertRaises(DomainError) as caught:
                dedicated_browser.ensure_started()
        self.assertEqual("BROWSER_PORT_OCCUPIED", caught.exception.code)
        launch.assert_not_called()

    def test_attached_task_never_closes_the_shared_browser(self) -> None:
        context = mock.Mock()
        with mock.patch.dict("os.environ", {"CONTENT_AGENT_DESKTOP": "1"}, clear=True):
            browser_worker.close_context(context)
        context.close.assert_not_called()

    def test_embedded_fallback_can_still_be_closed(self) -> None:
        context = mock.Mock()
        with mock.patch.dict("os.environ", {}, clear=True):
            browser_worker.close_context(context)
        context.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
