import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from content_workbench.api.v2 import V2Application
from content_workbench.accounts.executors import AccountExecutors
from content_workbench.storage.db import connect
from content_workbench.domain.errors import DomainError

class PausedAnalyticsTests(unittest.TestCase):
    def test_schedule_and_worker_retired_but_login_and_topics_remain(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);app=V2Application(root/'test.db',root,Mock())
            with connect(root/'test.db') as c:
                self.assertEqual(c.execute("SELECT enabled FROM wb_schedules WHERE id='accounts.daily'").fetchone()[0],0)
            for kind in ('accounts.sync','accounts.daily','accounts.recommend'):
                self.assertNotIn(kind,app.worker.allowed_kinds)
            self.assertIn('accounts.login',app.worker.allowed_kinds)
            self.assertTrue(any(k.startswith('topics.') for k in app.worker.allowed_kinds))
            for path in ('/api/accounts/sync','/api/accounts/recommend'):
                with self.assertRaises(DomainError) as e:app.account_api.handle(None,'POST',path,{})
                self.assertEqual(e.exception.code,'ACCOUNT_ANALYTICS_PAUSED')
    def test_login_does_not_trigger_analytics(self):
        service=Mock();service.topics.root=Path('/tmp')
        executor=AccountExecutors(service)
        with patch.object(executor,'platform',return_value={'login_verified':True}),patch.object(executor,'sync') as sync:
            result=executor.login({'input':{'platform':'douyin_publish'}},Mock())
            sync.assert_not_called();self.assertEqual(result['refresh'],'login_only')
