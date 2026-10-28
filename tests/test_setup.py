import tempfile
import unittest
from pathlib import Path

from content_workbench.accounts.service import AccountService
from content_workbench.accounts.setup import setup_status
from content_workbench.storage.db import PROJECT_ROOT, connect, expand_schema
from content_workbench.topics.service import TopicService


class SetupCase(unittest.TestCase):
    def test_environment_contract_and_real_platform_evidence(self):
        with tempfile.TemporaryDirectory(prefix="setup-test-") as temp:
            db = Path(temp) / "setup.db"
            with connect(db) as conn:
                expand_schema(conn)
                conn.executescript((PROJECT_ROOT / "migrations/003_publishing.sql").read_text())
            topics = TopicService(db, Path(temp))
            accounts = AccountService(db, topics)
            initial = setup_status(db)
            self.assertTrue(initial["first_run"])
            self.assertIn("local_url", initial)
            self.assertTrue(all("action" in item for item in initial["dependencies"]))
            self.assertNotIn("cookie", str(initial).lower())
            self.assertNotIn("token", str(initial).lower())
            accounts.save_snapshot("douyin", {"account_name": "测试"}, [])
            data = setup_status(db)
            self.assertFalse(data["first_run"])
            self.assertEqual("snapshot", next(item for item in data["platforms"] if item["platform"] == "douyin")["status"])
            self.assertEqual("not_verified", next(item for item in data["platforms"] if item["platform"] == "wechat_channels")["status"])


if __name__ == "__main__":
    unittest.main()
