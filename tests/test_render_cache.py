import tempfile
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock
import app
from content_workbench.media.render_cache import lease, stats
from content_workbench.domain.errors import DomainError
from content_workbench.storage.db import expand_schema
from content_workbench.domain.services import Workbench

class RenderCacheTest(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name).resolve()
        for key,value in [('ROOT',self.root),('DB_PATH',self.root/'data/test.db'),('REMOTION_APP',self.root/'remotion')]:
            patch=mock.patch.object(app,key,value);patch.start();self.addCleanup(patch.stop)
        app.init_db()
        with app.connect() as conn:expand_schema(conn)
        self.directory=app.REMOTION_APP/'public-static/yingxu-assets';self.directory.mkdir(parents=True)
    def test_cleanup_preserves_original_reference_unknown_and_symlink(self):
        derived=self.directory/('a'*64+'.mp4');derived.write_bytes(b'cache')
        partial=self.directory/('f'*64+'.mp4.'+'a'*32+'.staging');partial.write_bytes(b'partial')
        original=self.root/'original.srt';original.write_text('1\n00:00:00,000 --> 00:00:01,000\nhello\n')
        linked=self.directory/('b'*64+'.srt');linked.write_bytes(original.read_bytes())
        Workbench(app.DB_PATH,self.root).import_local_asset(linked)
        symlink=self.directory/('c'*64+'.srt');symlink.symlink_to(original)
        unknown=self.directory/'notes.txt';unknown.write_text('keep')
        final=self.root/'renders/final.mp4';final.parent.mkdir(exist_ok=True);final.write_bytes(b'final')
        result=app.manage_yingxu_cache({'action':'clear'})
        self.assertEqual(result['removed_bytes'],12)
        self.assertFalse(derived.exists())
        self.assertFalse(partial.exists())
        for path in [linked,symlink,original,unknown,final]:self.assertTrue(path.exists())
        self.assertEqual(result['protected_files'],1)
    def test_busy_render_blocks_cleanup_and_limits(self):
        with lease(self.directory):
            child = subprocess.run([sys.executable, '-c', 'from content_workbench.media.render_cache import lease; from pathlib import Path; import sys; context=lease(Path(sys.argv[1])); context.__enter__()', str(self.directory)], capture_output=True, text=True)
            self.assertNotEqual(child.returncode, 0)
            self.assertIn('正在渲染或整理缓存', child.stderr)
            with self.assertRaises(app.ApiError):app.manage_yingxu_cache({'action':'clear'})
            with self.assertRaises(DomainError):
                with lease(self.directory, allow_reentry=False):pass
        self.assertEqual(app.manage_yingxu_cache({'action':'limit','limit_gb':3})['limit_gb'],3)
        for invalid in [0,1001,True,1.2,'2']:
            with self.assertRaises(app.ApiError):app.manage_yingxu_cache({'action':'limit','limit_gb':invalid})
    def test_limit_blocks_new_cache_without_deleting_input(self):
        # Sparse cache file makes a 1GB quota test cheap, without large memory use.
        large=self.directory/('d'*64+'.mp4')
        with large.open('wb') as handle:handle.truncate(1024**3)
        source=self.root/'image.png';source.write_bytes(b'isolated-image')
        app.manage_yingxu_cache({'action':'limit','limit_gb':1})
        task={'source':{'yingxu':{'snapshot':{'shots':[{'fileId':1,'duration':2}]}}},'files':[{'id':1,'relative_path':'image.png','media_info':{}}]}
        with self.assertRaises(app.ApiError):app.yingxu_render_props(task)
        self.assertEqual(source.read_bytes(),b'isolated-image')
        self.assertTrue(large.exists())
