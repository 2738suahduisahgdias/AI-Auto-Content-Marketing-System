import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from content_workbench.topics.wechat_client import WechatClient, checked_base

class ClientTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.inbox=Mock();self.inbox.ingest.return_value=({'id':'one','ingest_status':'saved'},True)
        self.transport=Mock(return_value={})
        self.c=WechatClient(self.tmp.name,self.inbox,self.transport)
        self.c.state={'owner':'owner','bot':'bot','token':'secret','base':'https://ilinkai.weixin.qq.com','cursor':'before'}
        self.msg={'message_id':7522849335951112840,'from_user_id':'owner','message_type':1,'context_token':'ctx','item_list':[{'type':1,'text_item':{'text':'验收'}}]}
    def tearDown(self): self.tmp.cleanup()
    def test_persist_before_ack(self):
        def send(*a): self.inbox.ingest.assert_called_once(); return {}
        self.transport.side_effect=send
        self.c.process(self.msg)
        self.assertEqual(self.inbox.ingest.call_args.args[0]['msgid'],'weixin:bot:7522849335951112840')
    def test_failure_never_acknowledges_or_advances(self):
        self.transport.return_value={'msgs':[self.msg],'get_updates_buf':'after'}
        self.inbox.ingest.side_effect=RuntimeError('disk unavailable')
        with self.assertRaises(RuntimeError): self.c.run_once()
        self.assertEqual(self.c.state['cursor'],'before')
        self.assertEqual(self.transport.call_count,1)
    def test_retry_keeps_identity(self):
        self.c.process(self.msg); self.inbox.ingest.return_value=({'id':'one','ingest_status':'saved'},False)
        self.c.process(self.msg)
        calls=self.inbox.ingest.call_args_list
        self.assertEqual(calls[0],calls[1])
        self.assertEqual(self.c.state['received'],1)
    def test_other_sender_and_group_ignored(self):
        self.c.process({**self.msg,'from_user_id':'stranger'});self.c.process({**self.msg,'group_id':'group'})
        self.inbox.ingest.assert_not_called()
    def test_credentials_private_and_restart_cursor(self):
        self.c.save(); self.assertEqual(self.c.path.stat().st_mode & 0o777,0o600)
        other=WechatClient(self.tmp.name,self.inbox,self.transport)
        self.assertEqual(other.state['cursor'],'before');self.assertNotIn('secret',str(other.status()))
    def test_reject_untrusted_api_host(self):
        for url in ['http://ilinkai.weixin.qq.com','https://evil.test','https://ilinkai.weixin.qq.com@evil.test','https://ilinkai.weixin.qq.com/steal']:
            with self.assertRaises(ValueError):checked_base(url)
    def test_missing_identity_cannot_connect(self):
        self.c.login={'base':'https://ilinkai.weixin.qq.com','qrcode':'q'}
        self.transport.return_value={'status':'confirmed','bot_token':'x'}
        with self.assertRaises(ValueError):self.c.poll_login()

    def test_disconnect_clears_only_connection_not_topics(self):
        self.c.save()
        result=self.c.disconnect()
        self.assertEqual(result['status'],'disconnected')
        self.assertEqual(self.c.state,{})
        self.inbox.ingest.assert_not_called()
        self.assertNotIn('secret',self.c.path.read_text())
