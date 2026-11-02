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
            def read(self,n):
                assert n <= 1024*1024
                return super().read(n)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'video'
            data=b'a'*(3*1024*1024+3)
            stream_upload(Stream(data),len(data),path)
            self.assertEqual(path.stat().st_size,len(data))
    def test_upload_disconnect_removes_partial(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'video'
            with self.assertRaises(DomainError):stream_upload(io.BytesIO(b'abc'),100,path)
            self.assertFalse(path.exists())
    def test_disk_full_does_not_read(self):
        stream=Mock()
        with tempfile.TemporaryDirectory() as folder, patch('shutil.disk_usage',return_value=Mock(free=0)):
            with self.assertRaises(DomainError):stream_upload(stream,100,Path(folder)/'v')
        stream.read.assert_not_called()
    def test_worker_recovers_after_db_failure(self):
        worker=Worker.__new__(Worker);worker.store=Mock();worker.owner='test';worker.allowed_kinds=[];worker.poll_interval=0.01;worker.stop_event=threading.Event()
        worker.store.lease.side_effect=[sqlite3.OperationalError('locked'),{'id':'ok'}]
        worker.execute=Mock(side_effect=lambda job:worker.stop_event.set())
        worker.stop_event.wait=Mock()
        worker.run_forever()
        worker.execute.assert_called_once_with({'id':'ok'})
        self.assertIsNone(worker.last_error)
    def test_window_reuse_runs_fixed_script(self):
        with patch('desktop.browser.subprocess.run',return_value=Mock(returncode=0,stdout='reused\n')) as run:
            self.assertEqual(open_workbench(50916),'reused')
            self.assertIn('http://127.0.0.1:50916/',run.call_args.args[0])
    def test_window_denied_does_not_open_another_url(self):
        with patch('desktop.browser.subprocess.run',return_value=Mock(returncode=1)) as run:
            with self.assertRaises(RuntimeError):open_workbench(50916)
            self.assertEqual(run.call_args.args[0],['/usr/bin/open','-a','Google Chrome'])

    def test_browser_restart_blocks_active_upload(self):
        from content_workbench.accounts.browser_connection import control
        with tempfile.TemporaryDirectory() as folder:
            db=Path(folder)/"db"
            with sqlite3.connect(db) as conn:
                conn.execute("CREATE TABLE wb_jobs(resource_key TEXT,status TEXT)")
                conn.execute("INSERT INTO wb_jobs VALUES ('browser','running')")
            with patch('content_workbench.accounts.browser_connection.binary',return_value=Mock(is_file=lambda:True)), patch('content_workbench.accounts.browser_connection._run') as run:
                with self.assertRaises(DomainError) as error:control('restart',db)
                self.assertEqual(error.exception.code,'BROWSER_TASK_ACTIVE')
                run.assert_not_called()

    def test_existing_upload_is_not_deleted(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'video';path.write_bytes(b'original')
            with self.assertRaises(FileExistsError):stream_upload(io.BytesIO(b'new'),3,path)
            self.assertEqual(path.read_bytes(),b'original')
