import unittest
from unittest.mock import patch, Mock
from content_workbench.accounts import browser_connection as b
from content_workbench.domain.errors import DomainError
class BrowserConnectionTest(unittest.TestCase):
    def test_rejects_commands(self):
        with self.assertRaises(DomainError): b.control("restart; touch /tmp/x")
    def test_missing_binary(self):
        with patch.object(b,"binary",return_value=Mock(is_file=lambda:False)):
            with self.assertRaises(DomainError): b.control("start")
    def test_fixed_arguments(self):
        with patch.object(b,"binary",return_value=Mock(is_file=lambda:True,__str__=lambda s:"/safe/kimi-webbridge")), patch.object(b.subprocess,"run",return_value=Mock(returncode=0)) as run, patch.object(b,"status",return_value={"running":True}):
            self.assertTrue(b.control("restart")["running"])
            self.assertEqual(run.call_args.args[0],["/safe/kimi-webbridge","restart"])
    def test_failure_not_success(self):
        with patch.object(b,"binary",return_value=Mock(is_file=lambda:True)), patch.object(b.subprocess,"run",return_value=Mock(returncode=1)):
            with self.assertRaises(DomainError): b.control("start")
