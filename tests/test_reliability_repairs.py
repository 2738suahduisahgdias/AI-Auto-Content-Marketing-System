import importlib.util
import io
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from content_workbench.storage.uploads import stream_upload
from content_workbench.domain.errors import DomainError
from content_workbench.jobs.worker import Worker
from desktop.browser import open_workbench


class Repairs(unittest.TestCase):
    def test_upload_bounded_and_complete(self):
        class Stream(io.BytesIO):
            def read(self, n):
                assert n <= 1024 * 1024
                return super().read(n)

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "video"
            data = b"a" * (3 * 1024 * 1024 + 3)
            stream_upload(Stream(data), len(data), path)
            self.assertEqual(path.stat().st_size, len(data))

    def test_upload_disconnect_removes_partial(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "video"
            with self.assertRaises(DomainError):
                stream_upload(io.BytesIO(b"abc"), 100, path)
            self.assertFalse(path.exists())

    def test_disk_full_does_not_read(self):
        stream = Mock()
        with (
            tempfile.TemporaryDirectory() as folder,
            patch("shutil.disk_usage", return_value=Mock(free=0)),
        ):
            with self.assertRaises(DomainError):
                stream_upload(stream, 100, Path(folder) / "v")
        stream.read.assert_not_called()

    def test_worker_recovers_after_db_failure(self):
        worker = Worker.__new__(Worker)
        worker.store = Mock()
        worker.owner = "test"
        worker.allowed_kinds = []
        worker.poll_interval = 0.01
        worker.stop_event = threading.Event()
        worker.store.lease.side_effect = [
            sqlite3.OperationalError("locked"),
            {"id": "ok"},
        ]
        worker.execute = Mock(side_effect=lambda job: worker.stop_event.set())
        worker.stop_event.wait = Mock()
        worker.run_forever()
        worker.execute.assert_called_once_with({"id": "ok"})
        self.assertIsNone(worker.last_error)

    def test_window_reuse_runs_fixed_script(self):
        with patch(
            "desktop.browser.subprocess.run",
            return_value=Mock(returncode=0, stdout="reused\n"),
        ) as run:
            self.assertEqual(open_workbench(50916), "reused")
            self.assertIn("http://127.0.0.1:50916/", run.call_args.args[0])

    def test_window_denied_does_not_open_another_url(self):
        with patch(
            "desktop.browser.subprocess.run", return_value=Mock(returncode=1)
        ) as run:
            with self.assertRaises(RuntimeError):
                open_workbench(50916)
            self.assertEqual(
                run.call_args.args[0], ["/usr/bin/open", "-a", "Google Chrome"]
            )

    def test_browser_restart_blocks_active_upload(self):
        from content_workbench.accounts.browser_connection import control

        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "db"
            with sqlite3.connect(db) as conn:
                conn.execute("CREATE TABLE wb_jobs(resource_key TEXT,status TEXT)")
                conn.execute("INSERT INTO wb_jobs VALUES ('browser','running')")
            with patch("content_workbench.accounts.browser_connection.stop") as stop:
                with self.assertRaises(DomainError) as error:
                    control("restart", db)
                self.assertEqual(error.exception.code, "BROWSER_TASK_ACTIVE")
                stop.assert_not_called()

    def test_existing_upload_is_not_deleted(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "video"
            path.write_bytes(b"original")
            with self.assertRaises(FileExistsError):
                stream_upload(io.BytesIO(b"new"), 3, path)
            self.assertEqual(path.read_bytes(), b"original")

    def test_migration_preview_prefers_apfs_and_honors_override(self) -> None:
        script = Path(__file__).resolve().parents[1] / "scripts/start-migration-demo.py"
        spec = importlib.util.spec_from_file_location("start_migration_demo", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            repo = root / "project"
            repo.mkdir()
            apfs = root / "apfs/migration-preview"
            fallback = (repo.parents[1] / "runtime/migration-preview").resolve()
            self.assertEqual(module.preview_root(repo, {}, apfs), fallback)
            (apfs / "data").mkdir(parents=True)
            (apfs / "data/content-agent.db").touch()
            self.assertEqual(module.preview_root(repo, {}, apfs), apfs.resolve())
            override = root / "override"
            self.assertEqual(
                module.preview_root(repo, {"YINGXU_PREVIEW_ROOT": str(override)}, apfs),
                override.resolve(),
            )

    def test_migration_preview_forces_shared_browser_environment(self) -> None:
        script = Path(__file__).resolve().parents[1] / "scripts/start-migration-demo.py"
        spec = importlib.util.spec_from_file_location("start_migration_demo", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            preview = Path(folder) / "migration-preview"
            environment = module.preview_environment(
                preview,
                {"YINGXU_DEDICATED_CHROME": "0"},
            )
        self.assertEqual(environment["YINGXU_DEDICATED_CHROME"], "1")
        self.assertEqual(environment["CONTENT_AGENT_ROOT"], str(preview))
        self.assertEqual(
            environment["CONTENT_AGENT_DB"],
            str(preview / "data/content-agent.db"),
        )

    def test_migration_preview_uses_playwright_python(self) -> None:
        script = Path(__file__).resolve().parents[1] / "scripts/start-migration-demo.py"
        spec = importlib.util.spec_from_file_location("start_migration_demo", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        binary = Path("/tmp/preview-python")
        with patch.object(module, "playwright_python", return_value=binary):
            self.assertEqual(module.preview_python(Path("/tmp/project")), str(binary))
        with patch.object(module, "playwright_python", return_value=None):
            with self.assertRaisesRegex(SystemExit, "Playwright"):
                module.preview_python(Path("/tmp/project"))

    def test_migration_preview_registers_login_workers(self) -> None:
        script = Path(__file__).resolve().parents[1] / "scripts/run-migration-preview.py"
        spec = importlib.util.spec_from_file_location("run_migration_preview", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for kind in ("accounts.login", "topics.login", "topics.xhs_login"):
            self.assertIn(kind, module.PREVIEW_EXECUTOR_KINDS)
            self.assertIn(kind, module.PREVIEW_WORKER_KINDS)

    def test_disconnected_mutating_request_does_not_write_another_error(self):
        import app

        handler = object.__new__(app.Handler)
        handler.path = "/api/test"
        handler.error_response = Mock()

        def disconnect():
            raise BrokenPipeError(32, "Broken pipe")

        handler._mutating_request(disconnect)
        handler.error_response.assert_not_called()
