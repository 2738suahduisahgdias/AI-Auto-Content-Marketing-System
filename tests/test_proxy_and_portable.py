import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import app
from content_workbench.media.proxy import prepare
from content_workbench.media.probe import probe
from content_workbench.storage.portable import export_workspace,restore_workspace
from content_workbench.storage.db import expand_schema,file_hash
from content_workbench.domain.services import Workbench
from content_workbench.domain.errors import DomainError

class LocalDesktopFlows(unittest.TestCase):
 def setUp(self):
  temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.base=Path(temp.name).resolve();self.root=self.base/'workspace'
  for name,value in [('ROOT',self.root),('DB_PATH',self.root/'data/content-agent.db'),('REMOTION_APP',self.root/'runtime/remotion')]:
   patch=mock.patch.object(app,name,value);patch.start();self.addCleanup(patch.stop)
  app.init_db()
  with app.connect() as c:expand_schema(c)
  self.clip=self.base/'external.mp4'
  subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=s=960x540:d=2','-f','lavfi','-i','sine=frequency=440:duration=2','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(self.clip)],check=True)
  self.task=app.create_task({'title':'代理迁移验收','content':'隔离测试'})
  self.file=app.import_yingxu_file(self.task,{'path':str(self.clip),'kind':'asset'})
  with app.connect() as c:self.task=app.get_task(c,self.task['content_id'])
  self.task=app.save_yingxu(self.task,{'revision':0,'snapshot':{'shots':[{'title':'镜头','text':'测试','fileId':self.file['id'],'source':'人工上传','duration':99}]}})
 def test_portable_excludes_wechat_credentials(self):
  config=self.root/'config';config.mkdir(exist_ok=True)
  (config/'wechat-client.json').write_text('{"token":"test-only-secret"}')
  (config/'wechat-inbox.env').write_text('TOKEN=test-only-secret')
  (config/'video_templates.json').write_text('{}')
  package=self.base/'package-clean'
  export_workspace(app.DB_PATH,self.root,package)
  self.assertFalse((package/'config/wechat-client.json').exists())
  self.assertFalse((package/'config/wechat-inbox.env').exists())
  self.assertTrue((package/'config/video_templates.json').exists())

 def test_proxy_real_audio_duration_reuse_and_final_original(self):
  original=file_hash(self.clip);directory=app.REMOTION_APP/'public-static/yingxu-assets'
  proxy=prepare(self.clip,directory,1024**3);info=probe(proxy)
  self.assertLessEqual(max(s.get('width',0) for s in info['streams']),720)
  self.assertTrue(any(s['codec_type']=='audio' for s in info['streams']))
  self.assertAlmostEqual(info['duration_seconds'],2,places=1)
  mtime=proxy.stat().st_mtime_ns;self.assertEqual(prepare(self.clip,directory,0),proxy);self.assertEqual(proxy.stat().st_mtime_ns,mtime)
  moved=self.base/'moved.mp4';self.clip.rename(moved);self.clip=moved
  Workbench(app.DB_PATH,self.root).relink_asset(self.file['media_info']['wb_asset_id'],moved)
  self.assertEqual(prepare(moved,directory,0),proxy);self.assertEqual(proxy.stat().st_mtime_ns,mtime)
  preview=app.yingxu_render_props(self.task,True,0);final=app.yingxu_render_props(self.task,False)
  self.assertEqual(preview['scenes'][0]['type'],'media')
  self.assertEqual(final['scenes'][0]['type'],'media')
  self.assertEqual(preview['scenes'][0]['media']['src'],'yingxu-assets/'+proxy.name)
  self.assertEqual(file_hash(app.REMOTION_APP/'public-static'/final['scenes'][0]['media']['src']),original)
  proxy.write_bytes(b'corrupt');self.assertEqual(prepare(self.clip,directory,1024**3),proxy)
  self.assertEqual(file_hash(self.clip),original)
 def test_proxy_no_capacity_fallback_uses_original(self):
  with mock.patch.object(app,'task_proxy',side_effect=DomainError('PROXY_SPACE','空间不足',409)):
   props=app.yingxu_render_props(self.task,True,0)
  self.assertEqual(file_hash(app.REMOTION_APP/'public-static'/props['scenes'][0]['media']['src']),file_hash(self.clip))
 def test_workspace_portable_restore_preserves_project_and_reference(self):
  package=self.base/'package';destination=self.base/'restored'
  from content_workbench.jobs.store import JobStore
  job=JobStore(app.DB_PATH).enqueue('article.draft',{},'migration-test')
  wb=Workbench(app.DB_PATH,self.root);article=wb.create_item('article','wechat_official_account','保留文章',{})
  revision=wb.save_revision(article['id'],'draft',{'text':'完整保留的文章正文'},article['version'])
  from content_workbench.storage.drafts import DraftStore
  drafts=DraftStore(app.DB_PATH);drafts.save({'key':'article:new:title','data':'迁移草稿','expected_revision':0});identity=drafts.bootstrap()['workspace_id']
  before=file_hash(self.clip);export_workspace(app.DB_PATH,self.root,package)
  self.clip.rename(self.base/'offline-original.mp4')
  restore_workspace(package,destination)
  restored_drafts=DraftStore(destination/'data/content-agent.db').bootstrap();self.assertEqual(restored_drafts['drafts'][0]['data'],'迁移草稿');self.assertNotEqual(restored_drafts['workspace_id'],identity)
  with mock.patch.object(app,'ROOT',destination),mock.patch.object(app,'DB_PATH',destination/'data/content-agent.db'):
   with app.connect() as c:task=app.get_task(c,self.task['content_id'])
   self.assertEqual(task['source']['yingxu']['revision'],1)
   self.assertEqual(JobStore(app.DB_PATH).get(job['id'])['status'],'cancelled')
   restored_article=Workbench(app.DB_PATH,destination).get_item(article['id'])
   self.assertEqual(restored_article['active_revisions']['draft'],revision)
   self.assertEqual(file_hash(app.resolved_task_file(task['files'][0])),before)
  with self.assertRaises(DomainError):restore_workspace(package,destination)
  self.assertTrue((self.root/'data/content-agent.db').is_file())
 def test_corrupt_or_escape_package_is_rejected(self):
  package=self.base/'package';export_workspace(app.DB_PATH,self.root,package)
  manifest=json.loads((package/'manifest.json').read_text());manifest['files'][0]['path']='../outside'
  (package/'manifest.json').write_text(json.dumps(manifest))
  with self.assertRaises(DomainError):restore_workspace(package,self.base/'bad')
  self.assertFalse((self.base/'bad').exists())

 def test_http_preview_is_proxy_but_download_is_original(self):
  import io
  from types import SimpleNamespace
  def request(download):
   stream=io.BytesIO();headers={}
   handler=SimpleNamespace(headers={},wfile=stream,send_response=mock.Mock(),send_header=lambda k,v:headers.update({k:v}),end_headers=lambda:None)
   app.Handler.serve_media(handler,self.file['id'],download=download,proxy=True)
   return stream.getvalue(),headers
  preview,headers=request(False)
  self.assertEqual(headers['X-Yingxu-Preview'],'ready')
  original,headers=request(True)
  self.assertEqual(original,self.clip.read_bytes())
  self.assertNotEqual(preview,original)
  self.assertEqual(headers['X-Yingxu-Preview'],'original')
