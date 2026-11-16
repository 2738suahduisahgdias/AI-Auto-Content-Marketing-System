#!/usr/bin/env python3
import unittest
from unittest.mock import Mock, patch

from content_workbench.accounts import browser_connection as b
from content_workbench.domain.errors import DomainError
from content_workbench.topics import browser_worker


class BrowserConnectionTest(unittest.TestCase):
    def test_rejects_commands(self):
        with self.assertRaises(DomainError):
            b.control("restart; touch /tmp/x")

    def test_missing_binary(self):
        with patch.object(
            b,
            "ensure_started",
            side_effect=DomainError("BROWSER_CHROME_MISSING", "尚未安装 Chrome", 422),
        ):
            with self.assertRaises(DomainError):
                b.control("start")

    def test_restart_only_controls_dedicated_browser(self):
        with (
            patch.object(b, "stop", return_value={"stopped": True}),
            patch.object(
                b, "ensure_started", return_value="http://127.0.0.1:9223"
            ) as start,
            patch.object(b, "status", return_value={"running": True}),
        ):
            self.assertTrue(b.control("restart")["running"])
        start.assert_called_once_with()


class SharedBrowserTest(unittest.TestCase):
    def test_desktop_uses_persistent_dedicated_browser(self):
        playwright = Mock()
        playwright.chromium.connect_over_cdp.return_value = Mock(
            contexts=["main-context"]
        )
        with (
            patch.dict("os.environ", {"CONTENT_AGENT_DESKTOP": "1"}, clear=True),
            patch(
                "content_workbench.accounts.dedicated_browser.ensure_started",
                return_value="http://127.0.0.1:9223",
            ),
        ):
            self.assertEqual(
                browser_worker.open_context(playwright, "/unused"), "main-context"
            )
        playwright.chromium.connect_over_cdp.assert_called_once_with(
            "http://127.0.0.1:9223"
        )
        playwright.chromium.launch_persistent_context.assert_not_called()

    def test_rejects_remote_cdp_endpoint(self):
        with patch.dict(
            "os.environ",
            {"CONTENT_AGENT_CDP_URL": "http://192.168.1.8:9223"},
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "本机回环地址"):
                browser_worker.open_context(Mock(), "/unused")
