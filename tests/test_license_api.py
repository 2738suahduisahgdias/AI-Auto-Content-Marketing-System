import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from content_workbench.api.v2 import V2Application
from content_workbench.domain.errors import DomainError
from operator_tools.license_issuer import Issuer

class LicenseAPITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name)
        self.creator=Mock(return_value={'content_id':'first-video'})
        self.app=V2Application(root/'test.db',root,self.creator)
        self.app.license.mode='required'
        self.app.sessions.add('test-session')
        self.headers={'Host':'127.0.0.1:8876','Cookie':'wb_session=test-session','X-CSRF-Token':self.app.csrf('test-session')}
    def handler(self,path,body=None):
        handler=Mock();handler.path=path;handler.headers=self.headers.copy();handler.read_json.return_value=body or {}
        return handler
    def activate(self):
        issuer=Issuer(Path(self.tmp.name)/'operator');issuer.initialize('test-password-12345')
        (self.app.license.folder/'public-keys.json').write_text(json.dumps(issuer.status()['publicKeys']))
        code=issuer.issue({'name':'测试','requestCode':self.app.license.status()['requestCode'],'days':30,'password':'test-password-12345'})['token']
        self.app.license.activate(code)
    def test_existing_read_allowed_and_original_writes_blocked(self):
        self.app.authenticate(self.handler('/api/bootstrap'))
        for path in ('/api/tasks','/api/v2/content-items','/api/publishing/batches'):
            with self.assertRaisesRegex(DomainError,'激活'):self.app.authenticate(self.handler(path),True)
    def test_activation_still_requires_csrf(self):
        handler=self.handler('/api/v2/license/activate');handler.headers.pop('X-CSRF-Token')
        with self.assertRaisesRegex(DomainError,'校验'):self.app.authenticate(handler,True)
    def test_first_project_uses_original_creator_once(self):
        self.activate()
        path='/api/v2/license/first-project'
        for _ in range(2):
            handler=self.handler(path)
            self.app.handle(handler,'POST',path,{})
            handler.json_response.assert_called_with({'projectId':'first-video'},200)
        self.creator.assert_called_once()
        self.assertEqual(self.creator.call_args.args[0]['title'],'AI 客服如何落地')
    def test_onboarding_cannot_bypass_activation(self):
        handler=self.handler('/api/v2/license/onboarding',{'step':'complete'})
        self.app.handle(handler,'POST',handler.path,{})
        self.assertEqual(handler.json_response.call_args.args[1],403)
    def test_client_does_not_expose_issuer(self):
        self.assertFalse(self.app.matches('/api/issue'))
        self.assertFalse(self.app.matches('/api/key-backup'))
