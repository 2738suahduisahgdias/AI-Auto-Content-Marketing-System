import base64
import tempfile
import unittest
import zipfile
from pathlib import Path
from content_workbench.domain.services import Workbench
from content_workbench.domain.errors import DomainError
from content_workbench.storage.db import connect, expand_schema

PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jf1sAAAAASUVORK5CYII=')
class ArticleImagesTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.db=self.root/'db.sqlite'
        with connect(self.db) as conn:expand_schema(conn)
        self.wb=Workbench(self.db,self.root/'data')
        self.path=self.root/'image.png';self.path.write_bytes(PNG)
        self.asset=self.wb.import_local_asset(self.path)
        self.item=self.wb.create_item('article','wechat_official_account','配图验收',{})
    def save(self,position=1):
        item=self.wb.get_item(self.item['id'])
        return self.wb.save_revision(item['id'],'draft',{'text':'第一段\n\n第二段','creative_plan':{'pictures':[{'asset_id':self.asset,'after_paragraph':position,'description':'<script>alert(1)</script>'}]}},item['version'])
    def approve(self,revision):
        item=self.wb.get_item(self.item['id']);self.wb.approve(item['id'],revision,item['manifest']['hash'],kind='article')
    def test_portable_package_and_self_contained_html(self):
        revision=self.save();self.approve(revision)
        item,export=self.wb.export_article(self.item['id'],revision)
        payload=self.wb.get_revision(export)['payload']
        with self.wb.conn(readonly=True) as conn:
            package=conn.execute('SELECT * FROM wb_assets WHERE id=?',(payload['package_asset_id'],)).fetchone()
            dependencies=conn.execute('SELECT depends_asset_id FROM wb_revision_dependencies WHERE revision_id=?',(revision,)).fetchall()
        self.assertIn(self.asset,[r[0] for r in dependencies])
        with zipfile.ZipFile(self.wb.resolve_asset_path(package)) as archive:
            html=archive.read('article.html').decode();markdown=archive.read('article.md').decode()
            self.assertIn('data:image/png;base64,',html)
            self.assertNotIn('<script>',html)
            self.assertLess(html.index('第一段'),html.index('<figure>'))
            self.assertLess(html.index('<figure>'),html.index('第二段'))
            self.assertIn('images/'+self.asset+'.png',markdown)
            self.assertEqual(archive.read('images/'+self.asset+'.png'),PNG)
    def test_reposition_revokes_approval_and_missing_file_blocks_export(self):
        old=self.save();self.approve(old);new=self.save(0)
        with self.assertRaises(DomainError):self.wb.export_article(self.item['id'],new)
        self.approve(new);self.path.unlink()
        with self.assertRaises(DomainError) as caught:self.wb.export_article(self.item['id'],new)
        self.assertEqual(caught.exception.code,'ASSET_FILE_MISSING')
    def test_invalid_positions_and_non_images_are_rejected(self):
        with self.assertRaises(DomainError):self.save(99)
        self.path.write_text('not an image')
        with self.assertRaises(DomainError):self.save()
    def test_publish_source_retains_images_and_prevents_silent_text_only_prefill(self):
        from unittest.mock import Mock
        from content_workbench.publishing.service import PublishingService
        from content_workbench.publishing.executors import PublishingExecutors
        revision=self.save();self.approve(revision)
        service=PublishingService(self.db,self.wb.root)
        source=service.source('article',self.item['id'])
        self.assertEqual(source['article_images'][0]['asset_id'],self.asset)
        fake=Mock(root=self.wb.root)
        fake.target.return_value=({'content_kind':'article'}, {'id':'target','job_id':'job-test','platform':'xiaohongshu','payload':{},'status':'draft'})
        fake.assert_current=Mock(return_value=source)
        executor=PublishingExecutors(fake);executor.run=Mock(return_value={'status':'preview_ready','fields_verified':['title','body']})
        with self.assertRaises(DomainError) as caught:
            executor.prepare({'id':'job-test','input':{'target_id':'target'}},Mock())
        self.assertEqual(caught.exception.code,'ARTICLE_IMAGES_NOT_VERIFIED')
        executor.run.assert_called_once()

    def test_export_cannot_activate_after_concurrent_edit(self):
        from unittest.mock import patch
        from content_workbench.articles.layout import build_delivery
        revision=self.save();self.approve(revision)
        def concurrent(*args):
            result=build_delivery(*args)
            self.save(0)
            return result
        with patch('content_workbench.articles.layout.build_delivery',side_effect=concurrent):
            with self.assertRaises(DomainError) as caught:self.wb.export_article(self.item['id'],revision)
        self.assertEqual(caught.exception.code,'VERSION_CONFLICT')
        self.assertNotIn('export',self.wb.get_item(self.item['id'])['active_revisions'])

    def test_changed_image_cannot_be_approved(self):
        revision=self.save()
        self.path.write_text('replaced image')
        with self.assertRaises(DomainError) as caught:self.approve(revision)
        self.assertEqual(caught.exception.code,'ASSET_CHANGED')

    def test_search_attribution_survives_delivery(self):
        self.asset=self.wb.register_asset(self.path,{'kind':'image_search','author':'Author <name>','license':'CC BY 4.0','source_url':'https://commons.wikimedia.org/wiki/File:test.png'},'research_only')
        revision=self.save();self.approve(revision)
        _,export=self.wb.export_article(self.item['id'],revision)
        payload=self.wb.get_revision(export)['payload']
        with self.wb.conn(readonly=True) as conn:asset=conn.execute('SELECT * FROM wb_assets WHERE id=?',(payload['package_asset_id'],)).fetchone()
        with zipfile.ZipFile(self.wb.resolve_asset_path(asset)) as archive:
            self.assertIn('CC BY 4.0',archive.read('article.html').decode())
            self.assertIn('Author &lt;name&gt;',archive.read('article.html').decode())
            self.assertIn('source_url',archive.read('image-credits.json').decode())
