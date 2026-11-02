import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from content_workbench.jobs.store import JobStore
from content_workbench.storage.db import connect, expand_schema
from content_workbench.topics.service import TopicService
from content_workbench.topics.executors import TopicExecutors
from content_workbench.knowledge.service import KnowledgeService

class WorkspaceCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root/'test.db'
        with connect(self.db) as c:
            expand_schema(c)
            c.execute('CREATE TABLE tasks (title TEXT, updated_at TEXT)')
            c.execute("INSERT INTO tasks VALUES ('已做过的题目','today')")
        self.service = TopicService(self.db, self.root)
    def tearDown(self): self.temp.cleanup()
    def test_active_sync_reused_but_new_sync_after_completion(self):
        jobs = JobStore(self.db)
        one = jobs.enqueue_active_once('topics.sync',{},'source_douyin_main','browser')
        two = jobs.enqueue_active_once('topics.sync',{},'source_douyin_main','browser')
        self.assertEqual(one['id'], two['id'])
        with connect(self.db) as c:c.execute("UPDATE wb_jobs SET status='succeeded' WHERE id=?",(one['id'],))
        self.assertNotEqual(one['id'], jobs.enqueue_active_once('topics.sync',{},'source_douyin_main','browser')['id'])
    def test_chrome_enrichment_explicitly_caches_cover_without_duplicate_item(self):
        item_id = self.service.upsert_item({'title':'封面','canonical_url':'https://www.douyin.com/video/123','metadata':{'cover_url':'https://example.com/image.jpg'}},'featured')
        executor = object.__new__(TopicExecutors); executor.root=self.root; executor.service=self.service
        with patch.object(executor,'browser',return_value={'details':{'author_name':'test'}}), patch.object(self.service,'cache_cover',return_value=True) as cache:
            executor.enrich(item_id,SimpleNamespace())
        cache.assert_called_once_with(item_id)
        with connect(self.db) as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM wb_research_items').fetchone()[0],1)
    def test_cross_platform_recommendation_includes_memory_rules_and_existing_titles(self):
        for source,platform in [('featured','douyin'),('xhs_featured','xiaohongshu'),('wechat_inbox','wechat')]:
            self.service.upsert_item({'title':source,'canonical_url':'https://example.com/'+source},source,platform=platform)
        knowledge=KnowledgeService(self.db,self.root)
        memory=knowledge.save_memory(dict(title='经验',lesson='先讲真实问题',platform='xiaohongshu',kind='video',outcome='hypothesis',enabled=True))
        captured={}
        executor=object.__new__(TopicExecutors);executor.root=self.root;executor.service=self.service
        def generate(context,agent,prompt,*args,**kwargs):
            captured.update(json.loads(prompt));return [{'title':'新选题','memory_ids':[memory['id']],'reason':'理由','angle':'切入','content_format':'article'},{'title':'已做过的题目'}]
        executor.kimi_json=generate
        with patch('content_workbench.topics.executors.require_agent_enabled',return_value={'prompt':'','timeout_seconds':30,'engine':'codex_cli'}):
            result=executor.recommend({'input':{'agent':'all'}},SimpleNamespace(progress=lambda *a:None))
        self.assertEqual(result['candidates'],1)
        self.assertIn('wechat_inbox',captured['sources'])
        self.assertIn('xhs_featured',captured['sources'])
        self.assertIn('已做过的题目',captured['existing_content_titles'])
        saved=self.service.bootstrap()['recommendations']['all'][0]
        self.assertEqual(saved['content_format'],'article')
        self.assertEqual(saved['memory_ids'],[memory['id']])
