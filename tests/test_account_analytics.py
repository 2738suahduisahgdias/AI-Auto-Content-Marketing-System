import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from content_workbench.accounts.analytics import AccountAnalytics, public_number
from content_workbench.accounts.service import AccountService
from content_workbench.storage.db import PROJECT_ROOT, connect, expand_schema
from content_workbench.topics.service import TopicService


class AccountAnalyticsCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="account-analytics-")
        self.root = Path(self.temp.name)
        self.db = self.root / "analytics.db"
        with connect(self.db) as conn:
            expand_schema(conn)
            conn.executescript((PROJECT_ROOT / "migrations/003_publishing.sql").read_text())
        self.topics = TopicService(self.db, self.root)
        self.accounts = AccountService(self.db, self.topics)

    def tearDown(self):
        self.temp.cleanup()

    def publish(self, batch_id, source_id, kind, targets):
        with connect(self.db) as conn:
            conn.execute("INSERT INTO publish_batches VALUES (?,?,?,?,'published',NULL,NULL,?,?)",
                         (batch_id, kind, source_id, "hash-" + batch_id, "2026-10-28T01:00:00Z", "2026-10-28T01:00:00Z"))
            for target_id, platform, status, updated_at in targets:
                conn.execute("""INSERT INTO publish_targets(id,batch_id,platform,payload_json,status,preview_json,created_at,updated_at)
                                VALUES (?,?,?,?,?,'{}',?,?)""",
                             (target_id, batch_id, platform, '{"title":"真实内容"}', status, updated_at, updated_at))

    def test_verified_ranges_snapshots_and_competitor_boundaries(self):
        self.publish("batch-1", "same-original", "video", [
            ("target-1", "douyin", "published", "2026-10-28T01:00:00Z"),
            ("target-2", "xiaohongshu", "published", "2026-10-28T01:10:00Z"),
            ("target-3", "wechat_channels", "failed", "2026-10-28T01:10:00Z"),
        ])
        self.publish("batch-2", "old-original", "article", [
            ("target-4", "wechat_official_account", "published", "2026-10-27T01:00:00Z"),
        ])
        self.accounts.save_snapshot("douyin", {"account_name": "真实账号"}, [
            {"title": "公开作品", "canonical_url": "https://example.com/video/1", "metadata": {"like_count": "1.2万"}},
        ])
        self.topics.upsert_item({"title": "竞对作品", "canonical_url": "https://example.com/video/2",
                                 "metadata": {"author": "竞对账号", "like_count": 126}}, "competitor")
        data = AccountAnalytics(self.db).bootstrap(datetime(2026, 10, 28, 12, tzinfo=ZoneInfo("Asia/Shanghai")))

        self.assertEqual(1, data["totals"]["today"]["originals"])
        self.assertEqual(2, data["totals"]["today"]["publications"])
        self.assertEqual(0, data["platforms"]["wechat_channels"]["metrics"]["today"]["publications"])
        self.assertEqual(2, data["totals"]["7d"]["originals"])
        self.assertEqual(1, data["totals"]["yesterday"]["originals"])
        self.assertIsNone(data["totals"]["today"]["reach"])
        self.assertEqual(12000, data["platforms"]["douyin"]["snapshot"]["totals"]["likes"])
        self.assertIsNone(data["platforms"]["douyin"]["snapshot"]["totals"]["reach"])
        self.assertEqual("累计公开快照，不代表今日新增", data["sync"][0]["detail"])
        self.assertEqual(1, data["competitor_analytics"]["summary"]["total"])
        self.assertEqual(126, data["competitor_analytics"]["items"][0]["likes"])
        self.assertIsNone(data["competitor_analytics"]["items"][0]["comments"])

    def test_empty_database_and_public_number(self):
        data = AccountAnalytics(self.db).bootstrap(datetime(2026, 10, 28, 12, tzinfo=ZoneInfo("Asia/Shanghai")))
        self.assertEqual(0, data["totals"]["today"]["publications"])
        self.assertEqual([], data["competitor_analytics"]["items"])
        self.assertEqual(12000, public_number("1.2万"))
        self.assertEqual(340, public_number("340"))
        self.assertIsNone(public_number("未读取"))


if __name__ == "__main__":
    unittest.main()
