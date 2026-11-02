import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from operator_tools.license_issuer import Issuer
from content_workbench.licensing.protocol import canonical, decode, encode, request_code, verify
from content_workbench.licensing.service import LicenseService
from content_workbench.domain.errors import DomainError

class OfflineLicenseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.issuer = Issuer(Path(cls.tmp.name)/'operator')
        cls.password = 'test-only-secret-12345'
        cls.issuer.initialize(cls.password)
        cls.keys = cls.issuer.status()['publicKeys']
    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
    def setUp(self):
        self.tmp_customer = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_customer.cleanup)
        self.customer = LicenseService(self.tmp_customer.name, mode='required')
        (self.customer.folder/'public-keys.json').write_text(json.dumps(self.keys))
    def issue(self, **kwargs):
        return self.issuer.issue({'name':'测试客户', 'wechat':'测试备注', 'requestCode':self.customer.status()['requestCode'], 'days':30, 'password':self.password, **kwargs})
    def test_presented_guide_persists_without_marking_steps_complete(self):
        self.customer.activate(self.issue()['token'])
        self.customer.onboarding({'step':'seen'})
        reloaded=LicenseService(self.tmp_customer.name,mode='required')
        self.assertTrue(reloaded.status()['onboarding']['presented'])
        self.assertFalse(reloaded.status()['onboarding']['completed'])
        reloaded.onboarding({'step':'restart'})
        self.assertFalse(reloaded.status()['onboarding']['presented'])

    def test_activate_restart_and_first_run_persist(self):
        with self.assertRaises(DomainError): self.customer.require_active()
        record=self.issue()
        self.assertEqual(self.customer.activate(record['token'])['status'],'valid')
        self.customer.require_active()
        self.customer.onboarding({'step':'environment'})
        self.customer.onboarding({'step':'complete'})
        reopened=LicenseService(self.tmp_customer.name,'required')
        self.assertTrue(reopened.status()['onboarding']['completed'])
        self.assertIn('environment',reopened.status()['onboarding']['steps'])
        self.assertEqual(reopened.status()['license']['licenseId'],record['licenseId'])
        self.assertNotIn('private', ''.join(p.name for p in self.customer.folder.iterdir()))
    def test_wrong_installation(self):
        record=self.issue(requestCode=request_code('a'*32))
        with self.assertRaisesRegex(DomainError,'另一台'): self.customer.activate(record['token'])
    def test_tamper_cannot_replace_valid_license(self):
        record=self.issue()
        self.customer.activate(record['token'])
        v,p,s=record['token'].split('.')
        data=json.loads(decode(p));data['expiresAt']=None
        with self.assertRaisesRegex(DomainError,'签名无效'): self.customer.activate(v+'.'+encode(canonical(data))+'.'+s)
        self.assertEqual(self.customer.status()['status'],'valid')
    def test_expiry_and_clock(self):
        record=self.issue(days=1)
        with self.assertRaisesRegex(DomainError,'到期'): verify(record['token'],self.keys,self.customer.status()['installationId'],datetime.now(timezone.utc)+timedelta(days=2))
        with self.assertRaisesRegex(DomainError,'时间'): verify(record['token'],self.keys,self.customer.status()['installationId'],datetime.now(timezone.utc)-timedelta(days=2))
    def test_renewal_and_no_downgrade(self):
        record=self.issue(days=7);self.customer.activate(record['token'])
        renewed=self.issue(days=365,parentId=record['licenseId'])
        self.customer.activate(renewed['token'])
        self.assertEqual(record['customerId'],renewed['customerId'])
        with self.assertRaisesRegex(DomainError,'缩短'): self.customer.activate(record['token'])
    def test_malformed_and_unknown_key(self):
        for token in ('invalid',None,'x'*17000,'YXLIC2.abc.def'):
            with self.assertRaises(DomainError): self.customer.activate(token)
        record=self.issue()
        with self.assertRaisesRegex(DomainError,'公钥'): verify(record['token'],{},self.customer.status()['installationId'])
    def test_encrypted_key_restore_and_customer_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            restored=Issuer(folder)
            restored.initialize(self.password,self.issuer.key.read_text())
            self.assertEqual(restored.status()['publicKeys'],self.keys)
            original = self.issue()
            edited = self.issuer.update_customer({"licenseId": original["licenseId"], "name": "更新称呼", "wechat": "新备注", "notes": "已跟进"})
            self.assertEqual(original["token"], edited["token"])
            self.assertEqual(edited["notes"], "已跟进")
            records=self.issuer.records()
            restored.restore_records(records);restored.restore_records(records)
            self.assertEqual(len(restored.records()),len(records))
            record=restored.issue({'name':'恢复后发码','requestCode':self.customer.status()['requestCode'],'days':1,'password':self.password})
            self.customer.activate(record['token'])
    def test_wrong_password_and_no_key_overwrite(self):
        with self.assertRaises(ValueError): self.issue(password='wrong')
        with self.assertRaises(ValueError): self.issuer.initialize(self.password)
    def test_invalid_request_and_parent(self):
        with self.assertRaises(DomainError): self.issue(requestCode='bad')
        with self.assertRaises(ValueError): self.issue(parentId='missing')
    def test_failed_import_keeps_projects(self):
        sample=Path(self.tmp_customer.name)/'existing.mp4';sample.write_bytes(b'original')
        with self.assertRaises(DomainError): self.customer.activate('invalid')
        self.assertEqual(sample.read_bytes(),b'original')
    def test_corrupted_state_fails_closed(self):
        self.customer.state_path.write_text('broken')
        with self.assertRaises(DomainError):self.customer.require_active()

if __name__=='__main__':unittest.main()
