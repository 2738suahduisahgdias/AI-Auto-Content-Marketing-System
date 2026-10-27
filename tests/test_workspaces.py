import tempfile
import unittest
from pathlib import Path
from unittest import mock

from content_workbench.accounts.executors import AccountExecutors
from content_workbench.accounts.scheduler import configure_account_schedule
from content_workbench.accounts.service import AccountService
from content_workbench.domain.errors import DomainError
from content_workbench.knowledge.service import KnowledgeService
from content_workbench.storage.db import connect, expand_schema
from content_workbench.topics.service import TopicService


class WorkspaceCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="workspace-test-")
        self.root = Path(self.temp.name)
        self.db = self.root / "test.db"
        with connect(self.db) as conn:
            expand_schema(conn)
            conn.execute("""CREATE TABLE tasks(
                content_id TEXT PRIMARY KEY,title TEXT NOT NULL,angle TEXT,
                audience TEXT,pillar TEXT,state TEXT)""")
            conn.execute("""CREATE TABLE files(
                id INTEGER PRIMARY KEY,content_id TEXT NOT NULL,kind TEXT NOT NULL,
                original_name TEXT,relative_path TEXT NOT NULL,size INTEGER DEFAULT 0,
                media_info_json TEXT DEFAULT '{}',created_at TEXT DEFAULT '')""")
        self.topics = TopicService(self.db, self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_account_schedule_and_daily_bootstrap(self):
        configure_account_schedule(self.db)
        with connect(self.db, readonly=True) as conn:
            schedule = conn.execute("SELECT * FROM wb_schedules WHERE id='accounts.daily'").fetchone()
            self.assertEqual("09:30", schedule["expression"])
            self.assertEqual(1, schedule["enabled"])
        accounts = AccountService(self.db, self.topics)
        accounts.save_snapshot("xiaohongshu", {"connection": "ready"}, [{"title": "真实笔记", "views": None}])
        data = accounts.bootstrap()
        self.assertEqual(1, len(data["accounts"]))
        self.assertIsNone(data["accounts"][0]["items"][0]["views"])

    def test_knowledge_backfill_is_idempotent_and_keeps_evidence(self):
        item_id = self.topics.upsert_item({"title": "企业AI验收证据", "canonical_url": "https://example.com/evidence"}, "industry", platform="xiaohongshu")
        self.topics.save_candidates("industry", [{"title": "如何验收企业AI", "angle": "真实任务", "evidence_ids": [item_id]}])
        with connect(self.db) as conn:
            conn.execute("INSERT INTO tasks VALUES ('task-1','真实内容','验收角度','business_owners','enterprise_ai','idea')")
        knowledge = KnowledgeService(self.db, self.root)
        first = knowledge.backfill()
        with connect(self.db, readonly=True) as conn:
            counts = tuple(conn.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] for table in ("kb_entities", "kb_relations", "kb_rules"))
        second = knowledge.backfill()
        with connect(self.db, readonly=True) as conn:
            repeated = tuple(conn.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] for table in ("kb_entities", "kb_relations", "kb_rules"))
            relation = conn.execute("SELECT evidence_json FROM kb_relations WHERE predicate='supported_by'").fetchone()
        self.assertEqual(counts, repeated)
        self.assertEqual(first, second)
        self.assertIsNotNone(relation)
        data = knowledge.bootstrap("如何验收", "Topic")
        self.assertEqual(1, len(data["entities"]))
        self.assertTrue(any(rel["predicate"] == "supported_by" for rel in data["relations"]))

    def test_wechat_and_xhs_sources_remain_separate(self):
        self.topics.upsert_item({"title": "微信选题", "canonical_url": "https://example.com/wechat", "metadata": {"tag": "精选"}}, "wechat_inbox", platform="wechat_channels")
        self.topics.upsert_item({"title": "小红书笔记", "canonical_url": "https://example.com/xhs"}, "xhs_notes", platform="xiaohongshu")
        data = self.topics.bootstrap()
        self.assertEqual("wechat_channels", data["sources"]["wechat_inbox"][0]["platform"])
        self.assertEqual("xiaohongshu", data["sources"]["xhs_notes"][0]["platform"])
        self.assertEqual([], data["sources"]["featured"])

    def test_account_agent_configuration_reaches_real_prompt(self):
        accounts = AccountService(self.db, self.topics)
        accounts.save_snapshot("douyin", {"fans": "45"}, [])
        executor = AccountExecutors(accounts)
        candidate = {"title": "测试推荐", "reason": "事实与推断", "angle": "下一步实验"}
        with mock.patch("content_workbench.accounts.executors.TopicExecutors.kimi_json", return_value=[candidate]) as generate:
            result = executor.recommend({"input": {}}, mock.Mock())
        self.assertEqual(1, result["candidates"])
        prompt = generate.call_args.args[2]
        timeout = generate.call_args.args[3]
        self.assertIn("agent_supplement", prompt)
        self.assertIn("区分事实、推断和待验证实验", prompt)
        self.assertEqual(600, timeout)

    def test_publish_rejects_unapproved_video_path(self):
        relative = "renders/test/unapproved.mp4"
        path = self.root / relative
        path.parent.mkdir(parents=True)
        path.write_bytes(b"test")
        with connect(self.db) as conn:
            conn.execute("INSERT INTO tasks VALUES ('task-1','未批准','角度','business_owners','enterprise_ai','rendered')")
            conn.execute("INSERT INTO files(content_id,kind,relative_path) VALUES ('task-1','video',?)", (relative,))
        executor = AccountExecutors(AccountService(self.db, self.topics))
        with self.assertRaises(DomainError) as caught:
            executor.publish_preview({"input": {"video_path": relative, "title": "标题", "description": "简介"}}, mock.Mock())
        self.assertEqual("PUBLISH_VIDEO_NOT_APPROVED", caught.exception.code)
        with connect(self.db) as conn:
            conn.execute("UPDATE tasks SET state='approved' WHERE content_id='task-1'")
        with mock.patch.object(executor, "platform", return_value={"status": "preview_ready"}) as platform:
            result = executor.publish_preview({"input": {"video_path": relative, "title": "标题", "description": "简介"}}, mock.Mock())
        self.assertFalse(result["auto_published"])
        self.assertEqual("user_required", result["final_confirmation"])
        self.assertEqual("标题", platform.call_args.kwargs["title"])
        self.assertEqual("简介", platform.call_args.kwargs["description"])


if __name__ == "__main__":
    unittest.main()
