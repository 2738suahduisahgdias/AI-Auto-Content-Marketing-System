"""Own FFmpeg fixtures only: task -> referenced asset -> review -> publish source."""
import tempfile
import subprocess
import unittest
from pathlib import Path
from unittest import mock
import app
from content_workbench.storage.db import connect, expand_schema, file_hash
from content_workbench.domain.services import Workbench
from content_workbench.domain.errors import DomainError
from content_workbench.review.service import ReviewService
from content_workbench.review.executors import ReviewExecutors

class Context:
    def progress(self, *args): pass

class TaskReferences(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name).resolve(); self.root=self.folder/'project'
        for key,value in [('ROOT',self.root),('DB_PATH',self.root/'data/test.db'),('REMOTION_APP',self.root/'render-app')]:
            patch=mock.patch.object(app,key,value);patch.start();self.addCleanup(patch.stop)
        app.init_db()
        with connect(app.DB_PATH) as conn: expand_schema(conn)
        self.wb=Workbench(app.DB_PATH,app.ROOT)
        self.clip=self.folder/'original.mp4'
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=blue:s=360x640:d=2','-f','lavfi','-i','sine=frequency=440:duration=2','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(self.clip)],check=True)
        self.task=app.create_task({'title':'引用验收','content':'隔离素材测试','source_type':'topic'})
    def refresh(self):
        with app.connect() as conn: self.task=app.get_task(conn,self.task['content_id'])
        return self.task
    def attach(self,kind='asset',copy=False):
        return app.import_yingxu_file(self.task,{'path':str(self.clip),'kind':kind,'copy':copy})
    def test_reference_no_copy_duration_relink_and_replaced(self):
        digest=file_hash(self.clip);file=self.attach()
        self.assertEqual(file['id'],self.attach()['id'])
        self.assertEqual(app.resolved_task_file(file),self.clip)
        self.assertFalse(any(p.is_file() for p in (app.ROOT/'assets').rglob('*')))
        task=self.refresh()
        task=app.save_yingxu(task,{'revision':0,'snapshot':{'shots':[{'source':'人工上传','fileId':file['id'],'duration':99,'title':'实拍','text':'原片'}]}})
        props=app.yingxu_render_props(task,True,0)
        self.assertAlmostEqual(props['durationSeconds'],2,places=1)
        self.assertEqual(file_hash(self.clip),digest)
        moved=self.folder/'moved.mp4';self.clip.rename(moved)
        self.assertFalse(self.refresh()['files'][0]['available'])
        with self.assertRaises(app.ApiError): app.yingxu_render_props(task)
        wrong=self.folder/'wrong.mp4';wrong.write_bytes(b'not same')
        with self.assertRaises(DomainError):self.wb.relink_asset(file['media_info']['wb_asset_id'],wrong)
        self.wb.relink_asset(file['media_info']['wb_asset_id'],moved)
        self.assertTrue(self.refresh()['files'][0]['available'])
        self.assertAlmostEqual(app.yingxu_render_props(self.task)['durationSeconds'],2,places=1)
        moved.write_bytes(b'replaced')
        with self.assertRaises(app.ApiError):app.yingxu_render_props(self.task)
    def test_copy_upgrade_preserves_task_id(self):
        file=self.attach();copied=self.attach(copy=True)
        self.assertEqual(file['id'],copied['id'])
        self.clip.unlink()
        self.assertTrue(app.resolved_task_file(copied).is_file())
    def test_relocated_review_approval_and_publish_source_no_copy(self):
        file=self.attach('video');self.refresh()
        self.task=app.save_yingxu(self.task,{'revision':0,'snapshot':{'format':'360 × 640','shots':[]}})
        self.task=app.handoff_yingxu(self.task,{'revision':1,'file_id':file['id']})
        review=ReviewService(app.DB_PATH,app.ROOT);batch=review.receive_delivery(self.task['content_id']);item=batch['items'][0]['id']
        moved=self.folder/'moved.mp4';self.clip.rename(moved)
        self.wb.relink_asset(file['media_info']['wb_asset_id'],moved)
        ReviewExecutors(review).scan({'input':{'batch_id':batch['id']}},Context())
        self.assertEqual(review.decide(item,'approved'),str(moved))
        self.assertFalse((self.folder/'审核通过').exists())
        moved_again=self.folder/'again.mp4';moved.rename(moved_again)
        self.wb.relink_asset(file['media_info']['wb_asset_id'],moved_again)
        self.assertEqual(review.source_for_publish(item)['absolute_video_path'],str(moved_again))
        moved_again.write_bytes(b'changed')
        with self.assertRaises(DomainError):review.source_for_publish(item)
    def test_wrong_media_type_rejected(self):
        with self.assertRaises(app.ApiError):app.import_yingxu_file(self.task,{'path':str(self.clip),'kind':'asset','accept':'image/*'})

    def test_zip_streams_reference_and_cleans_temporary_export(self):
        import zipfile
        from types import SimpleNamespace
        self.attach('video')
        output=self.folder/'download.zip'
        with output.open('wb') as stream:
            handler=SimpleNamespace(wfile=stream,send_response=mock.Mock(),send_header=mock.Mock(),end_headers=mock.Mock())
            with mock.patch.object(app.io,'BytesIO',side_effect=AssertionError('whole archive in memory')):
                app.Handler.serve_task_zip(handler,self.task['content_id'])
        with zipfile.ZipFile(output) as archive:
            self.assertEqual(len(archive.namelist()),1)
            self.assertEqual(archive.read(archive.namelist()[0]),self.clip.read_bytes())
        self.assertEqual(list((app.ROOT/'cache/exports').iterdir()),[])
        with mock.patch.object(app.shutil,'disk_usage',return_value=SimpleNamespace(free=0)):
            with self.assertRaises(app.ApiError):app.Handler.serve_task_zip(handler,self.task['content_id'])
