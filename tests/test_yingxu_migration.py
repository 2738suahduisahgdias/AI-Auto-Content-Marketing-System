import json
import tempfile
import unittest
from unittest import mock
from pathlib import Path
import app

class YingxuMigrationCase(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.old=(app.ROOT,app.DB_PATH)
        app.ROOT=Path(self.temp.name).resolve()
        app.DB_PATH=app.ROOT/'data/test.db'
        app.init_db()
        self.task=app.create_task({'title':'迁移验收','pillar':'enterprise_ai','audience':'business_owners','content':'原文保持'})
        self.snapshot={'stage':0,'shots':[],'manuscript':{'title':'迁移验收','text':'编辑后的文案'}}
    def tearDown(self):
        app.ROOT,app.DB_PATH=self.old
        self.temp.cleanup()
    def test_save_keeps_task_and_source_with_conflict_protection(self):
        result=app.save_yingxu(self.task,{'revision':0,'snapshot':self.snapshot})
        self.assertEqual(result['content_id'],self.task['content_id'])
        self.assertEqual(result['scripts']['master'],'编辑后的文案')
        self.assertEqual(result['scripts']['douyin'],'原文保持')
        self.assertEqual(result['source']['yingxu']['revision'],1)
        self.assertEqual(result['source']['type'],self.task['source']['type'])
        with self.assertRaises(app.ApiError):app.save_yingxu(self.task,{'revision':0,'snapshot':self.snapshot})
        with app.connect() as con:
            self.assertEqual(len([r for r in app.get_task(con,self.task['content_id'])['stage_revisions'] if r['stage']=='yingxu']),1)
    def test_handoff_requires_owned_file_and_is_idempotent(self):
        task=app.save_yingxu(self.task,{'revision':0,'snapshot':self.snapshot})
        with self.assertRaises(app.ApiError):app.handoff_yingxu(task,{'file_id':999,'revision':1})
        path=app.ROOT/'renders'/task['content_id']/'final.mp4';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'test-file-reference')
        with app.connect() as con:
            file_id=con.execute('INSERT INTO files(content_id,kind,original_name,relative_path,size,media_info_json,created_at) VALUES (?,?,?,?,?,?,?)',(task['content_id'],'video','final.mp4',path.relative_to(app.ROOT).as_posix(),19,'{}',app.now())).lastrowid
        result=app.handoff_yingxu(task,{'file_id':file_id,'revision':1})
        again=app.handoff_yingxu(task,{'file_id':file_id,'revision':1})
        self.assertEqual(result['source']['yingxu_handoff'],again['source']['yingxu_handoff'])
        self.assertEqual(result['source']['yingxu_handoff']['status'],'requires_review')
        self.assertFalse(result['published_at'])
        navigated=app.save_yingxu(result,{'revision':1,'snapshot':{**self.snapshot,'stage':1}})
        self.assertFalse(navigated['source']['yingxu_handoff']['stale'])
        changed=app.save_yingxu(navigated,{'revision':2,'snapshot':{**self.snapshot,'manuscript':{'text':'确实修改了文案'}}})
        self.assertTrue(changed['source']['yingxu_handoff']['stale'])
    def test_invalid_reference_rejected(self):
        with self.assertRaises(app.ApiError):app.save_yingxu(self.task,{'revision':0,'snapshot':{**self.snapshot,'shots':[{'fileId':999}]}})

    def test_render_props_follow_saved_shots_and_preview_window(self):
        self.snapshot['shots']=[{'source':'Remotion 代码','title':'知识准备','text':'明确边界','duration':12}]
        self.snapshot['format']='1920 × 1080 · 横屏'
        task=app.save_yingxu(self.task,{'revision':0,'snapshot':self.snapshot})
        props=app.yingxu_render_props(task,True)
        self.assertEqual(props['durationSeconds'],10)
        self.assertEqual(props['outputWidth'],1920)
        self.assertEqual(props['captions'][0]['text'],'明确边界')
        self.assertEqual(app.yingxu_render_props(task)['durationSeconds'],12)
        task['source']['yingxu']['snapshot']['shots'][0]['source']='AI 视频'
        with self.assertRaises(app.ApiError):app.yingxu_render_props(task)

    def test_foreign_music_reference_rejected(self):
        with self.assertRaises(app.ApiError):
            app.save_yingxu(self.task,{'revision':0,'snapshot':{**self.snapshot,'bgmFileId':999}})

    def test_script_candidate_uses_original_agent_without_replacing_draft(self):
        task=app.save_yingxu(self.task,{'revision':0,'snapshot':self.snapshot})
        with mock.patch.object(app,'get_ai_status',return_value={'ready':False}):
            with self.assertRaises(app.ApiError):app.yingxu_script_candidate(task,{'revision':1})
        with mock.patch.object(app,'get_ai_status',return_value={'ready':True}), \
             mock.patch.object(app,'agent_runtime',return_value={'prompt':'原配置','timeout_seconds':10}), \
             mock.patch.object(app,'writing_context',return_value=('原技能',{})), \
             mock.patch.object(app,'detect_kimi',return_value={}), \
             mock.patch.object(app,'run_kimi_agent_json',return_value={'master':'新的候选稿'}) as generate:
            result=app.yingxu_script_candidate(task,{'revision':1})
        self.assertEqual(result['candidate'],'新的候选稿')
        self.assertIn('原配置',generate.call_args.args[1])
        self.assertIn('原技能',generate.call_args.args[1])
        with app.connect() as conn:
            current=app.get_task(conn,task['content_id'])
        self.assertEqual(current['scripts']['master'],'编辑后的文案')
        self.assertEqual(current['source']['yingxu']['revision'],1)

if __name__=='__main__':unittest.main()
