import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from content_workbench.readiness import runtime_readiness

class ReadinessTest(unittest.TestCase):
    def test_installed_tools_do_not_claim_login_or_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            worker=SimpleNamespace(thread=SimpleNamespace(is_alive=lambda:True),executors={'article.export':object()},allowed_kinds=['article.export'])
            app=SimpleNamespace(root=Path(tmp),worker=worker)
            with patch('content_workbench.readiness.shutil.which',return_value=None):
                result=runtime_readiness(app)
            entries={r['name']:r for r in result['capabilities']}
            self.assertEqual(entries['文章文档导出']['status'],'requires_validation')
            self.assertEqual(entries['文案生成']['status'],'blocked')
            self.assertEqual(entries['图文图片搜索与生成']['status'],'not_implemented')
            self.assertTrue(all(r['status']=='requires_login_verification' for r in result['platforms']))
            self.assertEqual(list(Path(tmp).iterdir()),[])
