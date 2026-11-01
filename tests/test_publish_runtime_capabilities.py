import unittest
from unittest.mock import Mock,patch
from content_workbench.publishing.api import PublishingAPI
from content_workbench.publishing.executors import PublishingExecutors
from content_workbench.domain.errors import DomainError

class PublishRuntimeTest(unittest.TestCase):
    def test_disabled_executor_cannot_queue_publication(self):
        app=Mock(publishing_execution_enabled=False);service=Mock()
        with self.assertRaises(DomainError) as error:
            PublishingAPI(app,service).handle(Mock(),'POST','/api/publishing/batches/test/confirm',{}, {})
        self.assertEqual(error.exception.code,'PUBLISH_EXECUTOR_DISABLED')
        service.confirm.assert_not_called()

    def test_bootstrap_reports_actual_executor_state(self):
        app=Mock(publishing_execution_enabled=False);service=Mock()
        service.bootstrap.return_value={}
        PublishingAPI(app,service).handle(Mock(),'GET','/api/publishing/bootstrap',{}, {})
        self.assertFalse(app.response.call_args.args[1]['execution_enabled'])

    def test_publish_fields_use_selected_codex_without_kimi(self):
        service=Mock();context=Mock()
        service.source.return_value={'title':'验收','body':'通用验收正文'}
        config={'engine':'codex_cli','prompt':'','timeout_seconds':60}
        executor=PublishingExecutors(service)
        with patch('content_workbench.publishing.executors.require_agent_enabled',return_value=config),patch('content_workbench.providers.text.CodexCLIProvider.complete_json',return_value={'platforms':{'xiaohongshu':{'title':'验收','body':'正文'}}}) as codex:
            result=executor.generate_fields({'input':{'content_kind':'article','source_id':'test','platforms':['xiaohongshu']}},context)
        self.assertEqual(result['provider'],'codex_cli')
        self.assertFalse(result['auto_published'])
        codex.assert_called_once()
        context.run_process.assert_not_called()
