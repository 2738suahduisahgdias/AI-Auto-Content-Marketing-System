import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from content_workbench.domain.errors import DomainError
from content_workbench.media.remotion_codegen import prepare_scene_code, skill_documents
from content_workbench.storage.db import PROJECT_ROOT

CODE="""import React from 'react';
import {AbsoluteFill,useCurrentFrame,interpolate} from 'remotion';
export const GeneratedScene=({scene,appearance}:any)=>{const frame=useCurrentFrame();return <AbsoluteFill style={{background:appearance.background,opacity:interpolate(frame,[0,10],[0,1],{extrapolateRight:'clamp'})}}><div>{scene.headline}</div></AbsoluteFill>};"""
class RemotionCodegenCase(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.runtime=self.root/'runtime';(self.runtime/'src').mkdir(parents=True)
  self.task={'content_id':'test-code','title':'AI客服','source':{'yingxu':{'snapshot':{'manuscript':{'title':'AI客服'},'shots':[{'title':'知识库','text':'先整理知识库','desc':'流程图逐项出现','duration':2,'source':'Remotion 代码','status':'待生成'}]}}}}
 def tearDown(self):self.temp.cleanup()
 def test_official_skill_is_present_and_actual_documents_are_sent_to_generation(self):
  generate=Mock(return_value=CODE)
  result=prepare_scene_code(self.task,{},self.runtime,self.root,generate,Mock())
  request=json.loads(generate.call_args[0][0]);self.assertEqual(request['skill_documents'][0]['path'],'SKILL.md');self.assertEqual(request['output_geometry'],{'width':1080,'height':1920})
  self.assertIn('name: remotion-best-practices',request['skill_documents'][0]['content'])
  self.assertTrue(any('useCurrentFrame' in doc['content'] for doc in request['skill_documents']))
  self.assertEqual(len(result['skill_commit']),40);self.assertTrue(Path(result['entry']).is_file())
 def test_identical_content_reuses_code_even_after_status_or_selection_changes(self):
  generate=Mock(return_value=CODE)
  prepare_scene_code(self.task,{},self.runtime,self.root,generate,Mock())
  task=copy.deepcopy(self.task);task['source']['yingxu']['snapshot']['shots'][0]['status']='已生成';task['source']['yingxu']['snapshot']['selected']=[0]
  result=prepare_scene_code(task,{},self.runtime,self.root,generate,Mock());self.assertTrue(result['cache_hit']);self.assertEqual(generate.call_count,1)
 def test_visual_change_regenerates_without_overwriting_previous_code(self):
  generate=Mock(return_value=CODE);a=prepare_scene_code(self.task,{},self.runtime,self.root,generate,Mock())
  self.task['source']['yingxu']['snapshot']['shots'][0]['desc']='改为对比结构'
  b=prepare_scene_code(self.task,{},self.runtime,self.root,generate,Mock());self.assertNotEqual(a['entry'],b['entry']);self.assertTrue(Path(a['entry']).is_file())
 def test_material_only_does_not_call_model(self):
  self.task['source']['yingxu']['snapshot']['shots'][0].update(source='人工上传',fileId=123)
  model=Mock();self.assertIsNone(prepare_scene_code(self.task,{},self.runtime,self.root,model,Mock()));model.assert_not_called()
 def test_external_edits_are_not_silently_overwritten(self):
  result=prepare_scene_code(self.task,{},self.runtime,self.root,Mock(return_value=CODE),Mock())
  path=Path(result['manifest']).parent/'GeneratedScene.tsx';path.write_text(CODE+'\n// manual edit')
  with self.assertRaises(DomainError):prepare_scene_code(self.task,{},self.runtime,self.root,Mock(return_value=CODE),Mock())
 def test_invalid_code_gets_one_repair_and_never_becomes_cache_hit(self):
  model=Mock(return_value=CODE);validator=Mock(side_effect=ValueError('bad code'))
  with self.assertRaises(DomainError):prepare_scene_code(self.task,{},self.runtime,self.root,model,validator)
  self.assertEqual(model.call_count,2);self.assertEqual(list(self.root.glob('assets/remotion-code/**/manifest.json')),[])
 def test_validator_rejects_network_and_dynamic_import_but_accepts_scene(self):
  directory=PROJECT_ROOT/'remotion-app';script=directory/'scripts/validate-generated.mjs';path=self.root/'test.tsx'
  for code,valid in [(CODE,True),(CODE.replace('<div>{scene.headline}</div>','<div>{scene.headline}<br/>下一行</div>'),True),(CODE+'\nfetch("https://example.com");',False),(CODE+'\nimport("node:fs");',False),(CODE+'\nwhile(true){}',False),(CODE+"\nconst {['fe'+'tch']:send}=self;send('ht'+'tps://example.invalid/');",False),(CODE+'\nconst x=()=>this;',False)]:
   path.write_text(code);r=subprocess.run(['node',str(script),str(path)],cwd=directory,capture_output=True,text=True)
   self.assertEqual(r.returncode==0,valid,r.stderr)
