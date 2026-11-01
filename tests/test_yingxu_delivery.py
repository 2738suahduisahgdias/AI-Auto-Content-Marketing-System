import json
import subprocess
import tempfile
import unittest
from pathlib import Path
import app
from content_workbench.review.service import ReviewService
from content_workbench.review.executors import ReviewExecutors
from content_workbench.publishing.service import PublishingService
from content_workbench.storage.db import file_hash, connect, expand_schema
from content_workbench.domain.errors import DomainError
from content_workbench.jobs.store import JobStore

class Context:
    def progress(self,*args): pass

class DeliveryCase(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.old=app.ROOT,app.DB_PATH
        app.ROOT=Path(self.temp.name).resolve();app.DB_PATH=app.ROOT/'data/test.db';app.init_db()
        with connect(app.DB_PATH) as conn: expand_schema(conn)
        self.review=ReviewService(app.DB_PATH,app.ROOT)
        self.publish=PublishingService(app.DB_PATH,app.ROOT)
        self.task=app.create_task({'title':'交接验收','content':'客服如何落地','source_type':'topic'})
        self.snapshot={'stage':0,'format':'360 × 640 · 竖屏','shots':[],'manuscript':{'title':'交接验收','text':'客服如何落地'}}
        self.task=app.save_yingxu(self.task,{'revision':0,'snapshot':self.snapshot})
        self.path=app.ROOT/'renders'/self.task['content_id']/'final.mp4';self.path.parent.mkdir(parents=True,exist_ok=True)
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=blue:s=360x640:d=1','-f','lavfi','-i','sine=frequency=440:duration=1','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart',str(self.path)],check=True,capture_output=True)
        with app.connect() as conn:
            self.file_id=conn.execute('INSERT INTO files(content_id,kind,original_name,relative_path,size,media_info_json,created_at) VALUES (?,?,?,?,?,?,?)',(self.task['content_id'],'video','final.mp4',self.path.relative_to(app.ROOT).as_posix(),self.path.stat().st_size,'{}',app.now())).lastrowid
        self.task=app.handoff_yingxu(self.task,{'file_id':self.file_id,'revision':1})
        self.batch=self.review.receive_delivery(self.task['content_id']);self.item=self.batch['items'][0]['id']
    def tearDown(self):
        app.ROOT,app.DB_PATH=self.old;self.temp.cleanup()
    def scan(self):
        ReviewExecutors(self.review).scan({'input':{'batch_id':self.batch['id']}},Context())
    def test_real_scan_approve_and_prepare_original_publish(self):
        self.assertEqual(self.batch['id'],self.review.receive_delivery(self.task['content_id'])['id'])
        self.assertEqual(1,len(self.batch['items']))
        with self.assertRaises(DomainError):self.review.decide(self.item,'approved')
        self.scan()
        # Technical warnings are retained for human judgment; no fabricated report.
        output=self.review.decide(self.item,'approved')
        self.assertEqual(str(self.path),output)
        self.assertEqual(file_hash(self.path),self.review.source_for_publish(self.item)['source_hash'])
        with app.connect() as conn:
            task=app.get_task(conn,self.task['content_id'])
        self.assertEqual('approved',task['source']['yingxu_handoff']['status'])
        again=app.handoff_yingxu(task,{'file_id':self.file_id,'revision':1})
        self.assertEqual('approved',again['source']['yingxu_handoff']['status'])
        queue=self.publish.publication_queue()['items'];self.assertEqual(self.item,queue[0]['id'])
        batch=self.publish.create_batch('video',self.item,[{'platform':'douyin','payload':{'title':'交接验收','description':'客服如何落地','tags':'#AI'}}])
        jobs=self.publish.prepare(batch['id'],['douyin']);self.assertEqual('publish.prepare',jobs[0]['kind'])
        with self.assertRaises(DomainError):self.publish.confirm(batch['id'],batch['source_hash'])
        self.assertEqual('preparing',self.publish.get_batch(batch['id'])['status'])
        changed=app.save_yingxu(task,{'revision':1,'snapshot':{**self.snapshot,'manuscript':{'text':'新正文'}}})
        self.assertTrue(changed['source']['yingxu_handoff']['stale'])
        for action in [lambda:self.review.source_for_publish(self.item),lambda:self.publish.prepare(batch['id'],['douyin']),lambda:self.review.decide(self.item,'approved')]:
            with self.assertRaises(DomainError):action()
        self.assertEqual([],self.publish.publication_queue()['items'])
        new_delivery=app.handoff_yingxu(changed,{'file_id':self.file_id,'revision':2})
        next_batch=self.review.receive_delivery(new_delivery['content_id'])
        self.assertNotEqual(self.batch['id'],next_batch['id'])
        with self.assertRaises(DomainError):self.review.source_for_publish(self.item)
    def test_rejected_and_replaced_file_cannot_publish(self):
        self.scan();self.review.decide(self.item,'rejected')
        with self.assertRaises(DomainError):self.review.source_for_publish(self.item)
        self.path.write_bytes(b'replaced')
        with self.assertRaises(DomainError):self.review.receive_delivery(self.task['content_id'])
    def test_navigation_keeps_delivery_but_legacy_path_cannot_bypass_review(self):
        app.save_yingxu(self.task,{'revision':1,'snapshot':{**self.snapshot,'stage':2}})
        self.assertFalse(self.review.get_batch(self.batch['id'])['items'][0]['delivery']['stale'])
        with app.connect() as conn:conn.execute("UPDATE tasks SET state='approved' WHERE content_id=?",(self.task['content_id'],))
        with self.assertRaises(DomainError):self.publish.source('video',self.task['content_id'],self.file_id)
    def test_worker_allowlist_never_leases_publish_or_model(self):
        store=JobStore(app.DB_PATH)
        publish=store.enqueue('publish.execute',{},'forbidden')
        store.enqueue('article.draft',{},'forbidden')
        scan=store.enqueue('review.scan',{'batch_id':self.batch['id']},self.batch['id'])
        leased=store.lease('review-only',kinds=['review.scan','review.repair'])
        self.assertEqual(scan['id'],leased['id'])
        self.assertEqual('queued',store.get(publish['id'])['status'])
