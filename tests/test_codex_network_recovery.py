import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from content_workbench.providers.text import CodexCLIProvider,codex_direct_retry,process_failure_message

class NetworkRecoveryTest(unittest.TestCase):
 def test_terminal_error_survives_long_plugin_warnings(self):
  text='Reading stdin\n'+'WARN plugin catalog failed '+('x'*900)+'\nERROR: workspace routing discovery failed\nWARN shutdown failed'
  self.assertIn('workspace routing discovery failed',process_failure_message(text))
  self.assertNotIn('catalog',process_failure_message(text))
  self.assertEqual(process_failure_message('WARN start\nError: login required\nWARN shutdown'),'Error: login required')
 def test_explicit_proxy_and_unrelated_errors_are_not_bypassed(self):
  with patch('sys.platform','darwin'),patch.dict(os.environ,{'HTTPS_PROXY':'http://company:123'},clear=True):
   self.assertIsNone(codex_direct_retry(['codex','exec'],Exception('workspace routing discovery failed')))
  with patch('sys.platform','darwin'),patch.dict(os.environ,{},clear=True):
   self.assertIsNone(codex_direct_retry(['codex','exec'],Exception('login required')))
  with patch('sys.platform','win32'),patch.dict(os.environ,{},clear=True):
   self.assertIsNone(codex_direct_retry(['codex','exec'],Exception('workspace routing discovery failed')))
 def test_retry_is_once_preserves_sandbox_and_discards_partial_output(self):
  with tempfile.TemporaryDirectory() as temp:
   agent=Path(temp)/'agent.md';agent.write_text('JSON only')
   calls=[]
   class Context:
    def run_process(self,args,timeout,stage,cwd):
     calls.append(args)
     output=Path(args[args.index('-o')+1])
     if len(calls)==1:
      output.write_text('partial')
      raise RuntimeError('workspace routing discovery failed')
     assert not output.exists()
     assert args[0]=='/usr/bin/env'
     assert args[args.index('--sandbox')+1]=='read-only'
     assert '--ignore-user-config' in args
     assert '--disable' in args
     assert not any('NO_PROXY=*' in arg for arg in args)
     output.write_text('{"ok":true}')
     return '',''
   with patch.object(CodexCLIProvider,'binary',return_value='/bin/codex'),patch('sys.platform','darwin'),patch.dict(os.environ,{},clear=True):
    self.assertEqual(CodexCLIProvider().complete_json('test',Context(),agent),{'ok':True})
   self.assertEqual(len(calls),2)
 def test_failed_recovery_is_propagated_without_a_loop(self):
  with tempfile.TemporaryDirectory() as temp:
   agent=Path(temp)/'agent';agent.write_text('test');calls=[]
   class Context:
    def run_process(self,*args,**kwargs):
     calls.append(1);raise RuntimeError('workspace routing discovery failed')
   with patch.object(CodexCLIProvider,'binary',return_value='/bin/codex'),patch('sys.platform','darwin'),patch.dict(os.environ,{},clear=True):
    with self.assertRaises(RuntimeError):CodexCLIProvider().complete_text('test',Context(),agent)
   self.assertEqual(len(calls),2)
