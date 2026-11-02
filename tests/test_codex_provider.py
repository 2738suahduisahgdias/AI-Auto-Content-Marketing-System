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

class RecommendationProviderTest(unittest.TestCase):
    def test_recommendation_calls_codex_and_rejects_invalid_arrays(self):
        from content_workbench.topics.executors import TopicExecutors
        from unittest.mock import Mock
        executor = object.__new__(TopicExecutors)
        valid = '[{"title":"AI客服","reason":"示意资料","angle":"知识库","audience":"business_owners","pillar":"enterprise_ai"}]'
        with patch('content_workbench.providers.text.CodexCLIProvider.complete_text',return_value=valid) as provider:
            result = executor.kimi_json(Mock(), 'industry-topic-agent', 'test')
            self.assertEqual('AI客服',result[0]['title'])
            provider.assert_called_once()
        with patch('content_workbench.providers.text.CodexCLIProvider.complete_text',return_value='{}'):
            with self.assertRaises(DomainError): executor.kimi_json(Mock(),'industry-topic-agent','test')

    def test_kimi_selection_never_falls_back_to_codex(self):
        from content_workbench.topics.executors import TopicExecutors
        from unittest.mock import Mock
        executor = object.__new__(TopicExecutors)
        executor.root = Path('/tmp')
        valid = '[{"title":"选题","reason":"真实来源","angle":"说明"}]'
        with patch('content_workbench.providers.text.KimiCLIProvider.complete_text',return_value=valid) as kimi, patch('content_workbench.providers.text.CodexCLIProvider.complete_text') as codex:
            self.assertEqual('选题',executor.kimi_json(Mock(),'industry-topic-agent','test',engine='kimi_cli')[0]['title'])
            kimi.assert_called_once();codex.assert_not_called()
        with patch('content_workbench.providers.text.KimiCLIProvider.complete_text',side_effect=DomainError('LOGIN_REQUIRED','需要登录')), patch('content_workbench.providers.text.CodexCLIProvider.complete_text') as codex:
            with self.assertRaises(DomainError): executor.kimi_json(Mock(),'industry-topic-agent','test',engine='kimi_cli')
            codex.assert_not_called()
