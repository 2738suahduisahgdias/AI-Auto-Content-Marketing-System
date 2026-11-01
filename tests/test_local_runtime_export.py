import tempfile
import unittest
from pathlib import Path
from content_workbench.storage.db import connect, expand_schema
from content_workbench.domain.services import Workbench
from content_workbench.jobs.store import JobStore
from content_workbench.jobs.worker import Worker
from content_workbench.providers.local import LocalExecutors

class LocalExportTest(unittest.TestCase):
    def test_approved_article_exports_in_separate_data_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);db=root/'test.db'
            with connect(db) as conn: expand_schema(conn)
            wb=Workbench(db,root)
            item=wb.create_item('article','wechat_official_account','本地导出验收',{'text':'测试'})
            revision=wb.save_revision(item['id'],'draft',{'text':'# 本地文章\n\n保留原版本与真实导出。','format':'markdown'},item['version'])
            item=wb.get_item(item['id'])
            wb.approve(item['id'],revision,item['manifest']['hash'],kind='article')
            item=wb.get_item(item['id']);store=JobStore(db)
            job=store.enqueue('article.export',{'revision_id':revision,'expected_version':item['version']},item['id'])
            worker=Worker(db,LocalExecutors(wb).mapping(),root,allowed_kinds=['article.export'])
            worker.execute(store.lease(worker.owner,kinds=['article.export']))
            result=store.get(job['id'])
            self.assertEqual(result['status'],'succeeded',result['error'])
            final=wb.get_item(item['id']);self.assertIn('export',final['active_revisions'])
            self.assertTrue(any(root.rglob('*.html')))
            self.assertTrue(any(root.rglob('*.md')))
