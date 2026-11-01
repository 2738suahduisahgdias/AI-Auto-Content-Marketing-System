import subprocess
import unittest
from pathlib import Path
from unittest import mock
from tests.test_yingxu_migration import YingxuMigrationCase

class RecordedTimelineCase(unittest.TestCase):
    tearDown = YingxuMigrationCase.tearDown
    def setUp(self):
        YingxuMigrationCase.setUp(self)
        import app
        self.stage=self.enterContext(mock.patch.object(app,'REMOTION_APP',app.ROOT/'render-app')) if hasattr(self,'enterContext') else None
        if self.stage is None:
            patcher=mock.patch.object(app,'REMOTION_APP',app.ROOT/'render-app');patcher.start();self.addCleanup(patcher.stop)
        self.clip=app.ROOT/'real.mp4';self.voice=app.ROOT/'voice.wav'
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=blue:s=160x240:d=2','-c:v','libx264','-pix_fmt','yuv420p',str(self.clip)],check=True)
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=440:duration=8',str(self.voice)],check=True)
        video=app.upload_file(self.task,'asset','real.mp4',self.clip,studio=True)
        audio=app.upload_file(self.task,'audio','voice.wav',self.voice,studio=True)
        with app.connect() as conn:self.task=app.get_task(conn,self.task['content_id'])
        self.snapshot.update({'rhythm':'旁白驱动','voiceFileId':audio['id'],'shots':[{'source':'人工上传','fileId':video['id'],'duration':99,'title':'实拍','text':'实拍保持完整'},{'source':'Remotion 代码','duration':2,'title':'讲解','text':'配合旁白'}]})
        self.task=app.save_yingxu(self.task,{'revision':0,'snapshot':self.snapshot})

    def test_actual_video_duration_and_recording_drive_timeline_without_read_bytes(self):
        import app
        with mock.patch.object(Path,'read_bytes',side_effect=AssertionError('must stream large files')):
            props=app.yingxu_render_props(self.task)
        self.assertAlmostEqual(props['durationSeconds'],8,places=2)
        self.assertAlmostEqual(props['scenes'][0]['end_seconds'],2,places=2)
        self.assertAlmostEqual(props['scenes'][1]['start_seconds'],2,places=2)
        self.assertAlmostEqual(props['scenes'][1]['end_seconds'],8,places=2)
        self.assertEqual(props['captions'][-1]['endMs'],8000)

    def test_recording_cannot_shorten_complete_live_footage(self):
        import app
        voice_id=self.snapshot['voiceFileId']
        next(f for f in self.task['files'] if f['id']==voice_id)['media_info']['duration_seconds']=1
        with self.assertRaises(app.ApiError):app.yingxu_render_props(self.task)

    def test_modified_imported_media_is_rejected(self):
        import app
        video_id=self.snapshot['shots'][0]['fileId']
        file=next(f for f in self.task['files'] if f['id']==video_id)
        (app.ROOT/file['relative_path']).write_bytes(b'replaced')
        with self.assertRaises(app.ApiError):app.yingxu_render_props(self.task)

    def test_selected_preview_rebases_scene_caption_and_recording(self):
        import app
        props=app.yingxu_render_props(self.task,True,1)
        self.assertEqual(len(props['scenes']),1)
        self.assertEqual(props['scenes'][0]['start_seconds'],0)
        self.assertAlmostEqual(props['durationSeconds'],6)
        self.assertAlmostEqual(props['audioSegments'][0]['start_seconds'],2)
        self.assertAlmostEqual(props['audioSegments'][0]['end_seconds'],8)
        self.assertEqual(props['captions'][0]['startMs'],0)
        with self.assertRaises(app.ApiError):app.yingxu_render_props(self.task,False,1)
        with self.assertRaises(app.ApiError):app.yingxu_render_props(self.task,True,99)

    def test_damaged_render_cache_is_rebuilt_without_changing_original(self):
        import app
        from content_workbench.storage.db import file_hash
        props=app.yingxu_render_props(self.task)
        cache=app.REMOTION_APP/'public-static'/props['scenes'][0]['media']['src']
        original_hash=file_hash(self.clip)
        cache.write_bytes(b'interrupted-copy')
        app.yingxu_render_props(self.task)
        self.assertEqual(file_hash(cache),original_hash)
        self.assertEqual(file_hash(self.clip),original_hash)

    def test_incomplete_render_does_not_register_a_deliverable(self):
        import app, shutil
        def incomplete(props, output, **kwargs):shutil.copyfile(self.clip,output)
        with mock.patch.object(app,'run_remotion_render',side_effect=incomplete):
            with self.assertRaises(app.ApiError):app.render_yingxu(self.task,{'revision':1,'preview':False})
        with app.connect() as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM files WHERE content_id=? AND kind='video'",(self.task['content_id'],)).fetchone()[0],0)
