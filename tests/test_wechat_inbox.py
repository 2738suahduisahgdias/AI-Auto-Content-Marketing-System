import tempfile
import unittest
from pathlib import Path
from unittest import mock

from content_workbench.api.v2 import V2Application
from content_workbench.domain.errors import DomainError
from content_workbench.storage.db import PROJECT_ROOT, connect, expand_schema, loads
from content_workbench.topics.service import TopicService
from content_workbench.topics.wechat_inbox import WechatInboxService


class WechatInboxCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="wechat-inbox-")
        self.root = Path(self.temp.name)
        with connect(self.root / "topics.db") as conn:
            expand_schema(conn)
        self.topics = TopicService(self.root / "topics.db", self.root)
        self.inbox = WechatInboxService(self.topics.db_path, self.topics)
        self.sender_env = mock.patch.dict("os.environ", {"CONTENT_AGENT_WECHAT_SENDER_ID": "sender-1"})
        self.sender_env.start()

    def tearDown(self):
        self.sender_env.stop()
        self.temp.cleanup()

    def test_ingest_dedup_repeat_url_and_backend_edit(self):
        payload = {"msgid": "wx-1", "sender_id": "sender-1", "source": "openclaw", "message_type": "text",
                   "text": "记录这个开头 https://example.com/video/1"}
        first, created = self.inbox.ingest(payload)
        self.assertTrue(created)
        self.assertEqual("unclassified", first["category"])
        self.assertEqual("https://example.com/video/1", first["original_url"])
        duplicate, created = self.inbox.ingest(payload)
        self.assertFalse(created)
        self.assertEqual(first["id"], duplicate["id"])
        second, created = self.inbox.ingest({**payload, "msgid": "wx-2", "text": "同一视频的新想法 https://example.com/video/1"})
        self.assertTrue(created)
        self.assertNotEqual(first["research_item_id"], second["research_item_id"])
        self.assertEqual(2, len(self.inbox.list()))
        updated = self.inbox.update(first["id"], {"title": "后台标题", "note": "后台补充备注", "category": "featured"})
        self.assertEqual("后台标题", updated["title"])
        self.assertEqual("精选", updated["category_name"])
        self.assertEqual(payload["text"], updated["raw_text"])
        research = self.topics.get_item(first["research_item_id"])
        self.assertEqual("后台标题", research["title"])
        self.assertEqual("精选", research["metadata"]["tag"])
        self.assertEqual("后台补充备注", research["metadata"]["raw_note"])

    def test_plain_text_and_empty_message_validation(self):
        message, created = self.inbox.ingest({"text": "只有一句想法"})
        self.assertTrue(created)
        self.assertIsNone(message["original_url"])
        self.assertEqual("只有一句想法", message["title"])
        with self.assertRaises(DomainError):
            self.inbox.ingest({"text": ""})

    def test_legacy_wechat_items_are_preserved(self):
        item_id = self.topics.upsert_item({"title": "历史消息", "canonical_url": "https://example.com/old",
            "metadata": {"title": "历史消息", "raw_message": "旧想法", "tag": "竞品", "source_key": "wechat_inbox"}},
            "wechat_inbox", platform="wechat_channels")
        service = WechatInboxService(self.topics.db_path, self.topics)
        messages = service.list()
        self.assertEqual(1, len(messages))
        self.assertEqual(item_id, messages[0]["research_item_id"])
        self.assertEqual("competitor", messages[0]["category"])
        self.assertEqual("https://example.com/old", messages[0]["original_url"])

    def test_openclaw_sender_must_be_allowlisted(self):
        with self.assertRaises(DomainError) as caught:
            self.inbox.ingest({"msgid": "wx-other", "sender_id": "other", "source": "openclaw", "text": "越权消息"})
        self.assertEqual("WECHAT_SENDER_FORBIDDEN", caught.exception.code)
        with mock.patch.dict("os.environ", {"CONTENT_AGENT_WECHAT_SENDER_ID": ""}):
            with self.assertRaises(DomainError) as missing:
                self.inbox.ingest({"msgid": "wx-missing", "sender_id": "sender-1", "source": "openclaw", "text": "未配置"})
        self.assertEqual("WECHAT_SENDER_NOT_CONFIGURED", missing.exception.code)

    def test_external_ingest_requires_dedicated_token(self):
        handler = mock.Mock()
        handler.path = "/api/topics/wechat/messages"
        handler.headers = {"Host": "127.0.0.1:8765", "X-Wechat-Ingest-Token": "secret"}
        app = V2Application.__new__(V2Application)
        app.license = mock.Mock()
        with mock.patch.dict("os.environ", {"CONTENT_AGENT_WECHAT_TOKEN": "secret"}):
            self.assertEqual("wechat_ingest", app.authenticate(handler, write=True))
            app.license.require_active.assert_called_once()
        with mock.patch.dict("os.environ", {"CONTENT_AGENT_WECHAT_TOKEN": "different"}):
            with self.assertRaises(DomainError) as caught:
                app.authenticate(handler, write=True)
        self.assertEqual("WECHAT_INGEST_UNAUTHORIZED", caught.exception.code)


if __name__ == "__main__":
    unittest.main()
