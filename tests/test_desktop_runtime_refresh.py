#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from desktop.entry import refresh_renderer_code


class RuntimeRefreshTest(unittest.TestCase):
    def test_upgrade_refreshes_code_and_preserves_customer_media(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            resources, runtime = root / "bundle", root / "runtime"
            (resources / "remotion-app/scripts").mkdir(parents=True)
            (resources / "remotion-app/scripts/render.mjs").write_text("new renderer")
            (runtime / "scripts").mkdir(parents=True)
            (runtime / "scripts/render.mjs").write_text("old renderer")
            (runtime / "public/assets").mkdir(parents=True)
            (runtime / "public/assets/customer.mp4").write_bytes(b"original media")
            (runtime / ".cache").mkdir()
            (runtime / ".cache/keep").write_text("cache")
            refresh_renderer_code(resources, runtime)
            refresh_renderer_code(resources, runtime)
            self.assertEqual(
                (runtime / "scripts/render.mjs").read_text(), "new renderer"
            )
            self.assertEqual(
                (runtime / "public/assets/customer.mp4").read_bytes(), b"original media"
            )
            self.assertEqual((runtime / ".cache/keep").read_text(), "cache")
            self.assertFalse(list(runtime.rglob("*.upgrade-tmp")))

    def test_shared_model_cache_is_copied_once_without_overwriting_customer_files(self):
        from desktop.entry import prepare_shared_cache

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            resources = root / "bundle"
            workspace = root / "workspace"
            source = resources / "models/huggingface/hub/model"
            source.mkdir(parents=True)
            (source / "weights").write_text("bundled")
            existing = workspace / "cache/huggingface/hub/customer"
            existing.mkdir(parents=True)
            (existing / "weights").write_text("keep")
            with mock.patch.dict("os.environ", {}, clear=True):
                prepare_shared_cache(resources, workspace)
                prepare_shared_cache(resources, workspace)
            self.assertEqual(
                (workspace / "cache/huggingface/hub/model/weights").read_text(),
                "bundled",
            )
            self.assertEqual((existing / "weights").read_text(), "keep")
            self.assertFalse(list(workspace.rglob("*.partial")))

    def test_browser_replacement_removes_only_generated_readonly_copies(self):
        from desktop.runtime_bundle import replace_tree

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source"
            destination = root / "destination"
            source.mkdir()
            destination.mkdir()
            (source / "browser").write_text("new")
            (destination / "browser").write_text("old")
            (destination / "browser").chmod(0o444)
            replace_tree(source, destination)
            self.assertEqual((destination / "browser").read_text(), "new")
            self.assertEqual((source / "browser").read_text(), "new")

    def test_readonly_runtime_disables_bytecode_for_child_processes(self):
        import os
        import sys

        from desktop.entry import configure_readonly_runtime

        with (
            mock.patch.dict("os.environ", {}, clear=True),
            mock.patch.object(sys, "dont_write_bytecode", False),
        ):
            configure_readonly_runtime()
            self.assertTrue(sys.dont_write_bytecode)
            self.assertEqual(os.environ["PYTHONDONTWRITEBYTECODE"], "1")

    def test_slim_workspace_uses_downloaded_resources_outside_app(self):
        import os

        from desktop.entry import prepare_shared_cache, prepare_slim_workspace

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            resources = root / "bundle"
            workspace = root / "workspace"
            (resources / "OpenVoice/openvoice").mkdir(parents=True)
            (resources / "OpenVoice/openvoice/api.py").write_text("code")
            (resources / "OpenVoice/checkpoints_v2/converter").mkdir(parents=True)
            (
                resources / "OpenVoice/checkpoints_v2/converter/checkpoint.pth"
            ).write_text("model")
            (resources / "slim-build.json").write_text('{"edition":"精简版"}')
            with mock.patch.dict("os.environ", {}, clear=True):
                prepare_slim_workspace(resources, workspace)
                prepare_shared_cache(resources, workspace)
                self.assertEqual(os.environ["CONTENT_AGENT_SLIM"], "1")
                self.assertEqual(
                    os.environ["PLAYWRIGHT_BROWSERS_PATH"],
                    str(workspace / "tools/playwright-browsers"),
                )
            self.assertTrue((workspace / "tools/OpenVoice/openvoice/api.py").is_file())
            self.assertFalse((workspace / "tools/OpenVoice/checkpoints_v2").exists())
            self.assertTrue((workspace / "cache/huggingface/hub").is_dir())


class OpenSSLRuntimeTest(unittest.TestCase):
    def test_packaging_selects_explicit_openssl3(self):
        from desktop.runtime_bundle import find_openssl

        with (
            mock.patch.dict(
                "os.environ", {"YINGXU_OPENSSL": "/test/openssl3"}, clear=True
            ),
            mock.patch("desktop.runtime_bundle.Path.is_file", return_value=True),
            mock.patch(
                "desktop.runtime_bundle.subprocess.run",
                return_value=mock.Mock(returncode=0, stdout="OpenSSL 3.0.0\n"),
            ),
        ):
            self.assertEqual(find_openssl(), Path("/test/openssl3"))

    def test_packaging_rejects_libressl(self):
        from desktop.runtime_bundle import find_openssl

        with (
            mock.patch.dict(
                "os.environ", {"YINGXU_OPENSSL": "/test/libressl"}, clear=True
            ),
            mock.patch("desktop.runtime_bundle.Path.is_file", return_value=True),
            mock.patch(
                "desktop.runtime_bundle.subprocess.run",
                return_value=mock.Mock(returncode=0, stdout="LibreSSL 3.3.6\n"),
            ),
            self.assertRaisesRegex(RuntimeError, "OpenSSL 3"),
        ):
            find_openssl()

    def test_repeated_packaging_replaces_readonly_generated_files(self):
        from desktop.runtime_bundle import prepare_openssl_runtime

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source"
            source.mkdir()
            for name in ("openssl", "libcrypto.3.dylib", "libssl.3.dylib"):
                (source / name).write_bytes(name.encode())
            destination = root / "generated"
            destination.mkdir()
            for name in ("openssl", "libcrypto.3.dylib", "libssl.3.dylib"):
                (destination / name).write_bytes(b"old")
                (destination / name).chmod(0o444)
            inspection = "\n".join(
                (
                    "openssl:",
                    f"\t{source / 'libcrypto.3.dylib'} (compatibility)",
                    f"\t{source / 'libssl.3.dylib'} (compatibility)",
                )
            )
            with (
                mock.patch(
                    "desktop.runtime_bundle.find_openssl",
                    return_value=source / "openssl",
                ),
                mock.patch(
                    "desktop.runtime_bundle.subprocess.check_output",
                    return_value=inspection,
                ),
                mock.patch(
                    "desktop.runtime_bundle.subprocess.run",
                    return_value=mock.Mock(returncode=0, stdout="OpenSSL 3.0.0\n"),
                ),
            ):
                prepare_openssl_runtime(destination)
                prepare_openssl_runtime(destination)
            self.assertEqual((destination / "openssl").read_bytes(), b"openssl")


class DesktopRuntimePathTest(unittest.TestCase):
    def test_apple_double_files_are_excluded_from_signed_runtime(self):
        from desktop.runtime_bundle import remove_apple_double

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "workers").mkdir()
            (root / "workers/._whisper.py").write_text("metadata")
            (root / "workers/.___pycache__").write_text("metadata")
            (root / "workers/whisper.py").write_text("code")
            remove_apple_double(root)
            self.assertFalse((root / "workers/._whisper.py").exists())
            self.assertFalse((root / "workers/.___pycache__").exists())
            self.assertEqual((root / "workers/whisper.py").read_text(), "code")

    def test_slim_path_prioritizes_bundled_openssl(self):
        from desktop.entry import runtime_binary_directories

        resources = Path("/app/resources")
        root = Path("/workspace")
        paths = runtime_binary_directories(resources, root, slim=True)
        self.assertEqual(paths[0], resources / "bin")
        self.assertIn(root / "tools/node/bin", paths)
        self.assertIn(root / "tools/bin", paths)
