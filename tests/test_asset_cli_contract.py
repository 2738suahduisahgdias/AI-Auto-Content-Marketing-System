import unittest
from unittest.mock import patch
import app


class AssetCLIContractTest(unittest.TestCase):
    def test_asset_array_is_preserved_and_object_parser_is_not_used(self):
        for engine, provider in [('codex_cli', 'CodexCLIProvider'), ('kimi_cli', 'KimiCLIProvider')]:
            with self.subTest(engine=engine), patch.object(app, 'agent_runtime', return_value={'engine': engine}), patch('content_workbench.providers.text.' + provider + '.complete_text', return_value='```json\n[{"id":"shot1"}]\n```'), patch('content_workbench.providers.text.' + provider + '.complete_json', side_effect=AssertionError('object parser used')):
                self.assertEqual(app.run_kimi_agent_json(app.ASSET_AGENT_PATH, 'test'), [{'id': 'shot1'}])

    def test_invalid_json_remains_failure(self):
        with patch.object(app, 'agent_runtime', return_value={'engine': 'codex_cli'}), patch('content_workbench.providers.text.CodexCLIProvider.complete_text', return_value='not JSON'):
            with self.assertRaises(app.ApiError):
                app.run_kimi_agent_json(app.ASSET_AGENT_PATH, 'test')
