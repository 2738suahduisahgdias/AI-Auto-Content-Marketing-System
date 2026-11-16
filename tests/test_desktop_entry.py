#!/usr/bin/env python3
import unittest
from pathlib import Path
from unittest import mock

from desktop.entry import main


class DesktopNativeFilePicker(unittest.TestCase):
    def test_webview_presents_license_file_picker(self):
        source = (
            Path(__file__).resolve().parents[1] / "desktop/launcher.m"
        ).read_text()
        self.assertIn("WKUIDelegate", source)
        self.assertIn("self.webView.UIDelegate = self", source)
        self.assertIn("runOpenPanelWithParameters", source)
        self.assertIn("completionHandler(panel.URLs)", source)
        self.assertIn("completionHandler(nil)", source)

    def test_file_picker_does_not_block_video_formats(self):
        source = (
            Path(__file__).resolve().parents[1] / "desktop/launcher.m"
        ).read_text()
        self.assertNotIn("panel.allowedFileTypes", source)
        self.assertNotIn("panel.allowedContentTypes", source)

    def test_external_links_use_default_browser(self):
        source = (
            Path(__file__).resolve().parents[1] / "desktop/launcher.m"
        ).read_text()
        self.assertIn("createWebViewWithConfiguration", source)
        self.assertIn("[[NSWorkspace sharedWorkspace] openURL:", source)


class DesktopMountGuard(unittest.TestCase):
    def test_shutdown_closes_reused_whisper_workers(self):
        source = (Path(__file__).resolve().parents[1] / "desktop/entry.py").read_text()
        self.assertIn("app.stop_whisper_servers()", source)

    def test_existing_stale_mount_directory_is_not_a_workspace(self):
        with (
            mock.patch(
                "sys.argv",
                ["entry.py", "--root", "/Volumes/offline-test/project", "--no-browser"],
            ),
            mock.patch("pathlib.Path.is_mount", return_value=False),
            mock.patch("pathlib.Path.exists", return_value=True),
            mock.patch("pathlib.Path.mkdir") as mkdir,
        ):
            with self.assertRaisesRegex(RuntimeError, "不会在系统盘"):
                main()
            mkdir.assert_not_called()
