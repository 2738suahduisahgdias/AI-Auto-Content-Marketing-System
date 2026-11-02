import json
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from content_workbench.storage.activity import ActivityGate
from content_workbench.storage.drafts import DraftStore
from content_workbench.storage.db import PROJECT_ROOT
from content_workbench.domain.errors import DomainError
from content_workbench.media.render_cache import stats,clear

class DeliveryStability(unittest.TestCase):
 def test_workspace_transition_rejects_inflight_then_closes_gate(self):
  gate=ActivityGate();called=[]
  with gate.operation():
   with self.assertRaises(DomainError):gate.switch(lambda:called.append(True))
  self.assertEqual(called,[])
  gate.switch(lambda:called.append(True))
  with self.assertRaises(DomainError):
   with gate.operation():pass
  self.assertEqual(called,[True])
 def test_failed_selection_keeps_old_workspace_writable(self):
  gate=ActivityGate()
  def failure():raise ValueError('invalid workspace')
  with self.assertRaises(ValueError):gate.switch(failure)
  with gate.operation():self.assertFalse(gate.switching)
 def test_drafts_survive_new_store_and_reject_stale_window(self):
  with tempfile.TemporaryDirectory() as tmp:
   db=Path(tmp)/'a.db';a=DraftStore(db);identifier=a.bootstrap()['workspace_id']
   a.save({'key':'article:new:title','data':'持久化内容','expected_revision':0})
   b=DraftStore(db);self.assertEqual(b.bootstrap()['workspace_id'],identifier)
   self.assertEqual(b.bootstrap()['drafts'][0]['data'],'持久化内容')
   with self.assertRaises(DomainError):b.save({'key':'article:new:title','data':'旧窗口','expected_revision':0})
   self.assertNotEqual(DraftStore(Path(tmp)/'b.db').bootstrap()['workspace_id'],identifier)
 def test_cache_counts_and_clears_old_build_copies_never_original(self):
  with tempfile.TemporaryDirectory() as tmp:
   runtime=Path(tmp);inputs=runtime/'public-static/yingxu-assets';inputs.mkdir(parents=True)
   original=runtime/'customer.mp4';original.write_bytes(b'keep')
   (inputs/('a'*64+'.mp4')).write_bytes(b'12345')
   old=runtime/'out/bundle-cache/old/public/yingxu-assets';old.mkdir(parents=True)
   (old/'old.mp4').write_bytes(b'1234567890')
   self.assertEqual(stats(inputs)['bytes'],15)
   self.assertEqual(clear(inputs),15)
   self.assertEqual(stats(inputs)['bytes'],0);self.assertEqual(original.read_bytes(),b'keep')
 def test_cache_deduplicates_hardlinks(self):
  import os
  with tempfile.TemporaryDirectory() as tmp:
   runtime=Path(tmp);inputs=runtime/'public-static/yingxu-assets';inputs.mkdir(parents=True)
   p=inputs/('b'*64+'.mp4');p.write_bytes(b'12345')
   bundle=runtime/'out/bundle-cache/test';bundle.mkdir(parents=True);os.link(p,bundle/'same.mp4')
   self.assertEqual(stats(inputs)['bytes'],5);self.assertEqual(clear(inputs),5)
 def test_selective_render_assets_and_network_rules(self):
  subprocess.run(['node','--test','scripts/render-stability.test.mjs'],cwd=PROJECT_ROOT/'remotion-app',check=True,capture_output=True)

 def test_cache_cleanup_rejected_during_nested_render_lease(self):
  from content_workbench.media.render_cache import lease
  with tempfile.TemporaryDirectory() as tmp:
   directory=Path(tmp)/'public-static/yingxu-assets'
   errors=[]
   def concurrent_clear():
    try:
     with lease(directory):clear(directory)
    except DomainError as e:errors.append(e.code)
   with lease(directory):
    with lease(directory):
     t=threading.Thread(target=concurrent_clear);t.start();t.join()
   self.assertEqual(errors,['RENDER_CACHE_BUSY'])
