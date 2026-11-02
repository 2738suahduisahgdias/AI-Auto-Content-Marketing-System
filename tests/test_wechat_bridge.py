import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

from workers import wechat_inbox_bridge


class WechatBridgeCase(unittest.TestCase):
    def test_endpoint_rejects_external_hosts(self):
        with mock.patch.dict("os.environ", {"CONTENT_AGENT_WECHAT_ENDPOINT":"https://example.com/api/topics/wechat/messages"}):
            with self.assertRaises(ValueError): wechat_inbox_bridge.endpoint()

    def test_endpoint_tracks_workspace_port(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/"data").mkdir();(root/"data/desktop-session.json").write_text('{"port":50916}')
            with mock.patch.dict("os.environ", {"CONTENT_AGENT_ROOT":directory,"CONTENT_AGENT_WECHAT_ENDPOINT":""}):
                self.assertEqual("http://127.0.0.1:50916/api/topics/wechat/messages",wechat_inbox_bridge.endpoint())

    def test_bridge_posts_only_to_local_inbox_without_exposing_token(self):
        request_result = io.BytesIO(json.dumps({"id": "message-1", "category": "unclassified", "ingest_status": "saved"}).encode())
        response = mock.Mock(status=201)
        response.read.return_value = request_result.getvalue()
        response.__enter__ = mock.Mock(return_value=response)
        response.__exit__ = mock.Mock(return_value=False)
        argv = ["bridge.py", json.dumps({"msgid": "wx-1", "text": "真实想法", "original_url": "https://example.com/1"})]
        output = io.StringIO()
        with mock.patch.dict("os.environ", {"CONTENT_AGENT_WECHAT_TOKEN": "secret", "CONTENT_AGENT_WECHAT_SENDER_ID": "sender-1", "CONTENT_AGENT_WECHAT_ENDPOINT":"http://127.0.0.1:8765/api/topics/wechat/messages"}), \
                mock.patch.object(sys, "argv", argv), \
                mock.patch.object(wechat_inbox_bridge.urllib.request, "urlopen", return_value=response) as call, redirect_stdout(output):
            result = wechat_inbox_bridge.main()
        self.assertEqual(0, result)
        self.assertEqual("saved", json.loads(output.getvalue())["status"])
        self.assertNotIn("secret", output.getvalue())
        request = call.call_args.args[0]
        self.assertEqual("http://127.0.0.1:8765/api/topics/wechat/messages", request.full_url)
        self.assertEqual("secret", request.get_header("X-wechat-ingest-token"))
        payload = json.loads(request.data)
        self.assertEqual("sender-1", payload["sender_id"])
        self.assertEqual("openclaw", payload["source"])
        self.assertNotIn("CONTENT_AGENT_WECHAT_TOKEN", json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
