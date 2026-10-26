import tempfile
import unittest
from pathlib import Path

from content_workbench.agents.registry import AGENTS, agent_config, all_agent_configs, require_agent_enabled, save_agent_config
from content_workbench.domain.errors import DomainError
from content_workbench.storage.db import connect, expand_schema, immediate
from content_workbench.topics.scheduler import TopicScheduler, configure_schedule
from content_workbench.topics.service import TopicService


class AgentRegistryCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="agent-config-")
        self.db = Path(self.temp.name) / "agents.db"
        with connect(self.db) as conn:
            expand_schema(conn)
        TopicService(self.db, Path(self.temp.name))

    def tearDown(self):
        self.temp.cleanup()

    def test_all_independent_agents_have_defaults(self):
        configs = all_agent_configs(self.db)
        self.assertEqual(set(AGENTS), set(configs))
        self.assertGreaterEqual(len(configs), 12)
        self.assertFalse(configs["quality_agent"]["enabled"])
        self.assertEqual("small", configs["caption_agent"]["model"])

    def test_save_and_reset_only_one_agent(self):
        other = agent_config(self.db, "douyin_topic_agent")["prompt"]
        updated = save_agent_config(self.db, "industry_topic_agent", {"prompt": "只保留真实业务案例", "timeout_seconds": 300, "max_attempts": 2, "concurrency": 1})
        self.assertEqual("只保留真实业务案例", updated["prompt"])
        self.assertEqual(300, updated["timeout_seconds"])
        self.assertEqual(other, agent_config(self.db, "douyin_topic_agent")["prompt"])
        reset = save_agent_config(self.db, "industry_topic_agent", {"reset": True})
        self.assertNotEqual(updated["prompt"], reset["prompt"])
        self.assertEqual(other, agent_config(self.db, "douyin_topic_agent")["prompt"])

    def test_invalid_config_and_unconnected_enable_rejected(self):
        with self.assertRaises(DomainError):
            save_agent_config(self.db, "quality_agent", {"enabled": True})
        with self.assertRaises(DomainError):
            save_agent_config(self.db, "script_agent", {"engine": "unknown"})
        with self.assertRaises(DomainError):
            save_agent_config(self.db, "script_agent", {"timeout_seconds": 5})
        with self.assertRaises(DomainError):
            save_agent_config(self.db, "caption_agent", {"model": "large"})

    def test_disabled_agent_and_scheduler_block_new_work(self):
        save_agent_config(self.db, "industry_topic_agent", {"enabled": False})
        with self.assertRaises(DomainError) as caught:
            require_agent_enabled(self.db, "industry_topic_agent")
        self.assertEqual("AGENT_DISABLED", caught.exception.code)
        configure_schedule(self.db, {"daily_time": "09:00", "daily_enabled": True})
        with connect(self.db) as conn, immediate(conn):
            conn.execute("UPDATE wb_schedules SET next_due_at='2000-01-01T00:00:00Z' WHERE id='topics.daily'")
        save_agent_config(self.db, "workflow_agent", {"enabled": False})
        scheduler = TopicScheduler(self.db)
        self.assertEqual(0, scheduler.tick())


if __name__ == "__main__":
    unittest.main()
