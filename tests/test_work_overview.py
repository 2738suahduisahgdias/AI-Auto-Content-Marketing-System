import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from content_workbench.overview import overview


class WorkOverviewTest(unittest.TestCase):
    def test_original_ids_readonly_counts_and_executor_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'work.db'
            with sqlite3.connect(path) as conn:
                conn.executescript('''
                    CREATE TABLE tasks(content_id TEXT,title TEXT,state TEXT,source_json TEXT,updated_at TEXT);
                    CREATE TABLE wb_jobs(id TEXT,kind TEXT,aggregate_id TEXT,status TEXT,stage TEXT,progress REAL,blocked_reason TEXT,error_json TEXT,created_at TEXT,updated_at TEXT);
                    CREATE TABLE publish_batches(id TEXT,content_kind TEXT,source_id TEXT,source_file_id INTEGER);
                    CREATE TABLE publish_targets(id TEXT,batch_id TEXT,platform TEXT,status TEXT,updated_at TEXT);
                    INSERT INTO publish_batches VALUES('b','video','original-video',107);
                    INSERT INTO publish_targets VALUES('p','b','douyin','prepared','2026');
                    INSERT INTO wb_jobs VALUES('j','topics.sync','douyin','queued','',0,NULL,'{}','2026','2026');
                ''')
                conn.executemany('INSERT INTO tasks VALUES(?,?,?,?,?)', [(str(i),'video','draft','{}','2026') for i in range(101)])
            before = path.read_bytes()
            worker = SimpleNamespace(thread=SimpleNamespace(is_alive=lambda:True), allowed_kinds=['review.scan'], executors={'review.scan':object()})
            result = overview(path, worker)
            groups = {g['key']:g for g in result['groups']}
            self.assertEqual(groups['video']['total'],101)
            self.assertEqual(len(groups['video']['items']),100)
            self.assertEqual(groups['video']['items'][0]['href'],'/tasks/0')
            self.assertNotIn('source_json', groups['video']['items'][0])
            self.assertFalse(groups['topics']['items'][0]['executor_available'])
            self.assertIn('排队不代表正在运行',groups['topics']['items'][0]['next'])
            self.assertEqual(groups['publish']['items'][0]['href'],'/publish?kind=video&id=original-video%3A107')
            self.assertEqual(path.read_bytes(),before)
            self.assertFalse(overview(path,None)['worker']['running'])

if __name__ == '__main__':
    unittest.main()
