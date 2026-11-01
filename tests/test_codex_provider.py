import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from content_workbench.providers.text import CodexCLIProvider
from content_workbench.domain.errors import DomainError

class CodexProviderTest(unittest.TestCase):
    @patch('content_workbench.providers.text.shutil.which',return_value='/usr/bin/codex')
    def test_final_file_used_without_passing_project_directory(self,_which):
        with tempfile.TemporaryDirectory() as tmp:
            agent=Path(tmp)/'agent.md';agent.write_text('Return JSON text')
            class Context:
                def run_process(self,args,timeout,stage,cwd):
                    assert '--ignore-user-config' in args
                    assert args[args.index('--sandbox')+1]=='read-only'
                    assert Path(cwd)!=agent.parent
                    Path(args[args.index('-o')+1]).write_text('{"text":"有效文本"}')
                    return 'not the answer',''
            self.assertEqual(CodexCLIProvider().complete_json('通用测试',Context(),agent),{'text':'有效文本'})
    @patch('content_workbench.providers.text.shutil.which',return_value='/usr/bin/codex')
    def test_missing_final_message_is_not_success(self,_which):
        with tempfile.TemporaryDirectory() as tmp:
            agent=Path(tmp)/'a';agent.write_text('test')
            class Context:
                def run_process(self,*args,**kwargs):return '',''
            with self.assertRaises(DomainError):CodexCLIProvider().complete_text('test',Context(),agent)
