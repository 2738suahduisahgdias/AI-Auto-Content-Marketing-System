import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from content_workbench.knowledge.service import KnowledgeService
from content_workbench.domain.errors import DomainError
from content_workbench.topics.executors import TopicExecutors
from types import SimpleNamespace
import json


class GrowthMemoryCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.service = KnowledgeService(self.root / 'memory.db', self.root)
        self.draft = dict(title='客服内容经验', platform='douyin', kind='video', outcome='hypothesis', lesson='先讲具体问题', evidence='', metrics='', enabled=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_evidence_required_and_update_disable_persist(self):
        with self.assertRaises(DomainError):
            self.service.save_memory({**self.draft, 'outcome': 'effective'})
        saved = self.service.save_memory(self.draft)
        self.assertEqual(1, len(self.service.memories('douyin')))
        self.assertEqual([], self.service.memories('industry'))
        self.service.save_memory({**saved, 'enabled': False})
        reloaded = KnowledgeService(self.root / 'memory.db', self.root)
        self.assertEqual([], reloaded.memories('douyin'))
        self.assertEqual(1, len(reloaded.memories()))

    def test_recommendation_context_and_reference_validation(self):
        memory = self.service.save_memory(self.draft)
        captured = {}
        executor = object.__new__(TopicExecutors)
        executor.root = self.root
        def save(agent, candidates):
            captured['candidates'] = candidates
            return ['candidate_1']
        executor.service = SimpleNamespace(db_path=self.service.db_path, bootstrap=lambda: {'settings': {'industry_scope':'AI', 'douyin_prompt':'推荐'}, 'sources': {'hot':[{'id':'source_1'}]}}, save_candidates=save)
        def generate(context, agent, prompt, timeout, engine="codex_cli"):
            captured['prompt'] = json.loads(prompt)
            return [{'title':'客服落地', 'memory_ids':[memory['id'],'fabricated',memory['id']]}]
        executor.kimi_json = generate
        with patch('content_workbench.topics.executors.require_agent_enabled', return_value={'prompt':'', 'timeout_seconds':30, 'engine':'codex_cli'}):
            executor.recommend({'input':{'agent':'douyin'}}, SimpleNamespace(progress=lambda *args:None))
        self.assertEqual(memory['id'], captured['prompt']['growth_memories'][0]['id'])
        self.assertEqual([memory['id']], captured['candidates'][0]['memory_ids'])
        self.assertEqual('先讲具体问题', captured['candidates'][0]['memory_evidence'][0]['lesson'])
