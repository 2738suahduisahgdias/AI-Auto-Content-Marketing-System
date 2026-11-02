import copy,json,unittest
from unittest.mock import Mock
from content_workbench.media.yingxu_director import context,generate_plan,validate_plan,narration
from content_workbench.domain.errors import DomainError

class DirectorCase(unittest.TestCase):
 def setUp(self):
  self.task={'content_id':'test','title':'任务','source':{'yingxu':{'revision':3,'snapshot':{'manuscript':{'title':'换轨','text':'S01｜开头\n学习会暂时变慢。\n\nS02｜解释\n因为旧习惯正在重建。'},'rhythm':'旁白驱动','voiceFileId':12,'scene':'知识卡片','effectPrompt':'黑白线条和橙色强调','shots':[]}}},'files':[{'id':12,'media_info':{'duration_seconds':146.822}}]}
  self.plan={'palette':{'background':'#111111','text':'#EEEEEE','accent':'#FF9900'},'style_summary':'线条与信息层级','timing_note':'两段递进','shots':[{'title':'开头','label':'钩子','text':'学习会暂时变慢。','purpose':'提出矛盾','desc':'速度曲线下降','motion':'曲线从左绘制到右','emphasis':'变慢','sound_effect':'','duration':3,'source':'Remotion 代码','locked_index':None},{'title':'解释','label':'原因','text':'因为旧习惯正在重建。','purpose':'解释变化','desc':'旧线路淡出、新线路连通','motion':'旧线逐段退场，新线接续','emphasis':'重建','sound_effect':'','duration':7,'source':'Remotion 代码','locked_index':None}]}
 def test_whole_document_and_real_voice_define_plan_without_mutating_task(self):
  original=copy.deepcopy(self.task);generate=Mock(return_value=json.dumps(self.plan,ensure_ascii=False))
  result=generate_plan(self.task,generate);request=json.loads(generate.call_args[0][0]);self.assertEqual(request['narration_text'],'学习会暂时变慢。\n\n因为旧习惯正在重建。')
  self.assertEqual(request['brief']['effectPrompt'],'黑白线条和橙色强调')
  self.assertEqual(result['candidate']['duration_seconds'],146.822);self.assertEqual(len(result['candidate']['shots']),2)
  self.assertEqual(self.task,original)
 def test_omitted_or_rewritten_narration_rejected_preserves_old_plan(self):
  self.plan['shots'][0]['text']='模型擅自改稿';generate=Mock(return_value=json.dumps(self.plan,ensure_ascii=False))
  with self.assertRaises(DomainError):generate_plan(self.task,generate)
  self.assertEqual(generate.call_count,2);self.assertEqual(self.task['source']['yingxu']['snapshot']['shots'],[])
 def test_locked_media_must_be_retained_and_cannot_be_replaced_by_fabricated_id(self):
  original={**self.plan['shots'][0],'locked':True,'fileId':42,'actualDuration':12,'duration':12,'source':'人工上传'}
  self.task['source']['yingxu']['snapshot']['shots']=[original]
  request=context(self.task)
  with self.assertRaises(ValueError):validate_plan(self.plan,request)
  self.plan['shots'][0].update(locked_index=0,fileId=999,source='AI 视频')
  result=validate_plan(self.plan,request)
  self.assertEqual(result['shots'][0]['fileId'],42);self.assertEqual(result['shots'][0]['source'],'人工上传');self.assertEqual(result['shots'][0]['duration'],12)
 def test_no_voice_is_allowed_with_honest_estimated_duration(self):
  self.task['files']=[];request=context(self.task);result=validate_plan(self.plan,request)
  self.assertEqual(result['duration_source'],'estimated_narration')
 def test_section_headers_do_not_become_spoken_copy(self):
  self.assertEqual(narration('S01｜引子\n正文\n\nS02｜结尾\n结束'),'正文\n\n结束')
