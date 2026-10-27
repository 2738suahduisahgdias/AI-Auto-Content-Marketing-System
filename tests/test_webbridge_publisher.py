import unittest
from unittest import mock

from content_workbench.publishing import webbridge_worker


class WebBridgeChannelsCase(unittest.TestCase):
    def setUp(self):
        self.data = {
            "source": {"absolute_video_path": "/tmp/approved.mp4"},
            "payload": {"title": "短标题", "description": "人工审核后的视频描述"},
            "target_id": "target-1",
        }
        self.bridge = mock.Mock()
        self.bridge.snapshot.return_value = {"tree": [{"name": "封面预览"}]}
        self.bridge.result.side_effect = lambda target, status, fields=None, extra=None: {
            "status": status, "fields_verified": sorted(fields or []), **(extra or {})}
        nodes = [
            {"nodeId": "title", "backendDOMNodeId": 11, "name": {"value": "填写短标题"}},
            {"nodeId": "description", "parentId": "label", "name": {"value": "视频描述"}},
            {"nodeId": "label", "backendDOMNodeId": 12, "parentId": "form"},
            {"nodeId": "form", "backendDOMNodeId": 13},
        ]
        self.bridge.cdp.return_value = {"nodes": nodes}

    def test_existing_manual_upload_resumes_without_uploading_again(self):
        values = {"11": "短标题", "13": "人工审核后的视频描述"}
        with mock.patch.object(webbridge_worker, "set_channels_value", side_effect=lambda _b, node, _v, rich=False: values[str(node)]), \
                mock.patch.object(webbridge_worker, "media_duration", return_value=117.8), \
                mock.patch.object(webbridge_worker, "channels_video_duration", return_value=117.8):
            result = webbridge_worker.prepare_channels(self.bridge, self.data, "prepare")
        self.assertEqual("preview_ready", result["status"])
        self.assertEqual({"video", "short_title", "description"}, set(result["fields_verified"]))
        self.assertNotIn("upload", [call.args[0] for call in self.bridge.call.call_args_list])
        self.assertNotIn("发表", [call.args[0] for call in self.bridge.click_text.call_args_list])

    def test_stale_video_is_rejected_before_fields_or_publish(self):
        with mock.patch.object(webbridge_worker, "media_duration", return_value=117.8), \
                mock.patch.object(webbridge_worker, "channels_video_duration", return_value=40.16), \
                mock.patch.object(webbridge_worker, "set_channels_value") as set_value:
            result = webbridge_worker.prepare_channels(self.bridge, self.data, "prepare")
        self.assertEqual("manual_required", result["status"])
        self.assertEqual(40.16, result["actual_duration"])
        self.assertIn("禁止发布旧内容", result["error"])
        set_value.assert_not_called()

    def test_missing_upload_returns_exact_manual_action(self):
        self.bridge.snapshot.return_value = {"tree": [{"name": "上传视频"}]}
        with mock.patch.object(webbridge_worker.time, "sleep"):
            result = webbridge_worker.prepare_channels(self.bridge, self.data, "prepare")
        self.assertEqual("manual_required", result["status"])
        self.assertIn("/tmp/approved.mp4", result["action"])
        self.assertEqual("video_path", result["field"])


class WebBridgeSafetyCase(unittest.TestCase):
    def test_failed_final_click_is_not_marked_published(self):
        bridge = mock.Mock()
        bridge.click_text.return_value = False
        bridge.error.side_effect = lambda platform, field, message, action: {
            "status": "error", "field": field, "error": message, "action": action}
        result = webbridge_worker.execute_bridge(bridge, "wechat_channels", "target-1", "发表")
        self.assertEqual("error", result["status"])
        self.assertNotEqual("published", result["status"])

    def test_uncertain_final_result_requires_reconciliation(self):
        bridge = mock.Mock()
        bridge.click_text.return_value = True
        bridge.snapshot.return_value = {"tree": [{"name": "正在处理"}]}
        bridge.result.side_effect = lambda target, status, fields=None, extra=None: {"status": status, **(extra or {})}
        with mock.patch.object(webbridge_worker.time, "sleep"):
            result = webbridge_worker.execute_bridge(bridge, "wechat_channels", "target-1", "发表")
        self.assertEqual("unknown_remote", result["status"])
        self.assertIn("禁止直接重试", result["action"])


if __name__ == "__main__":
    unittest.main()
