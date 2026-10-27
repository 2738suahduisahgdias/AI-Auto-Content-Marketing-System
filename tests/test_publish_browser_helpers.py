import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from content_workbench.publishing import browser_worker


class XiaohongshuControlCase(unittest.TestCase):
    def page_with_control(self, attributes):
        page = mock.Mock()
        frame = mock.Mock()
        page.frames = [frame]
        controls = mock.Mock()
        controls.count.return_value = 1
        control = mock.Mock()
        controls.nth.return_value = control
        control.get_attribute.side_effect = lambda name: attributes.get(name)
        control.is_visible.return_value = True
        control.is_enabled.return_value = True
        frame.locator.return_value = controls
        frame.get_by_text.return_value.count.return_value = 0
        return page, control

    def test_publish_host_requires_exact_action_and_enabled_state(self):
        page, control = self.page_with_control({
            "submit-text": "发布",
            "submit-disabled": "false",
            "submit-loading": "false",
        })
        self.assertIs(control, browser_worker.xhs_action_control(page, "发布"))
        self.assertIsNone(browser_worker.xhs_action_control(page, "下一步"))

        page, _ = self.page_with_control({
            "submit-text": "发布",
            "submit-disabled": "true",
            "submit-loading": "false",
        })
        self.assertIsNone(browser_worker.xhs_publish_control(page))

    def test_publish_host_does_not_fall_back_to_unrelated_publish_text(self):
        page = mock.Mock()
        frame = mock.Mock()
        page.frames = [frame]
        frame.locator.return_value.count.return_value = 0
        frame.get_by_text.return_value.count.return_value = 0
        self.assertIsNone(browser_worker.xhs_publish_control(page))
        frame.get_by_text.assert_called_once_with("发布", exact=True)

    def test_standard_button_is_supported_alongside_custom_host(self):
        page = mock.Mock()
        frame = mock.Mock()
        page.frames = [frame]
        frame.locator.return_value.count.return_value = 0
        controls = mock.Mock()
        controls.count.return_value = 1
        control = controls.nth.return_value
        control.is_visible.return_value = True
        control.is_enabled.return_value = True
        frame.get_by_text.return_value = controls
        self.assertIs(control, browser_worker.xhs_action_control(page, "一键排版"))

    def test_custom_host_clicks_submit_side_not_draft(self):
        control = mock.Mock()
        control.bounding_box.return_value = {"width": 680, "height": 90}
        control.get_attribute.return_value = "true"
        self.assertTrue(browser_worker.click_xhs_control(control))
        control.click.assert_called_once_with(position={"x": 408, "y": 45})

    def test_standard_button_clicks_its_center(self):
        control = mock.Mock()
        control.bounding_box.return_value = {"width": 120, "height": 40}
        control.get_attribute.return_value = None
        self.assertTrue(browser_worker.click_xhs_control(control))
        control.click.assert_called_once_with(position={"x": 60, "y": 20})


class ChannelsMediaCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="publish-browser-helpers-")
        self.video = Path(self.temp.name) / "sample.mp4"
        self.video.write_bytes(b"mp4")

    def tearDown(self):
        self.temp.cleanup()

    def probe(self, codec="h264", duration=6):
        return mock.Mock(returncode=0, stdout=json.dumps({
            "streams": [{"codec_name": codec}],
            "format": {"duration": str(duration)},
        }))

    def test_valid_h264_mp4_within_limits(self):
        with mock.patch.object(browser_worker.subprocess, "run", return_value=self.probe()):
            self.assertIsNone(browser_worker.validate_channels_video(self.video))

    def test_rejects_non_h264_and_over_eight_hours(self):
        for probe in (self.probe(codec="hevc"), self.probe(duration=28801), self.probe(duration=0)):
            with self.subTest(probe=probe.stdout):
                with mock.patch.object(browser_worker.subprocess, "run", return_value=probe):
                    self.assertIsNotNone(browser_worker.validate_channels_video(self.video))

    def test_rejects_over_twenty_gb_before_upload(self):
        with mock.patch.object(Path, "is_file", return_value=True), \
                mock.patch.object(Path, "stat", return_value=SimpleNamespace(st_size=20 * 1024 ** 3 + 1)), \
                mock.patch.object(browser_worker.subprocess, "run") as probe:
            self.assertIn("20GB", browser_worker.validate_channels_video(self.video))
        probe.assert_not_called()

    def test_topic_names_accepts_space_and_chinese_comma(self):
        self.assertEqual(["企业AI", "AI应用", "审核"],
                         browser_worker.topic_names("#企业AI #AI应用，审核"))

    def test_invalid_media_never_opens_platform(self):
        page = mock.Mock()
        data = {"source": {"absolute_video_path": str(self.video) + ".mov"},
                "payload": {"title": "标题", "description": "描述"}}
        result = browser_worker.prepare_wechat_channels(page, data, "prepare")
        self.assertEqual("error", result["status"])
        self.assertEqual("video_path", result["field"])
        page.goto.assert_not_called()


class WechatArticleValidationCase(unittest.TestCase):
    def test_length_limit_is_checked_before_opening_platform(self):
        page = mock.Mock()
        data = {"payload": {"title": "长" * 65, "body": "正文", "cover_path": "cover.jpg"}}
        result = browser_worker.prepare_wechat_article(page, data, "prepare")
        self.assertEqual("title", result["field"])
        page.goto.assert_not_called()

    def test_cover_is_required_before_opening_platform(self):
        page = mock.Mock()
        data = {"payload": {"title": "标题", "body": "正文"}}
        result = browser_worker.prepare_wechat_article(page, data, "prepare")
        self.assertEqual("cover_asset_id", result["field"])
        page.goto.assert_not_called()


class PublishVerificationCase(unittest.TestCase):
    def test_sms_verification_is_not_a_publish_success(self):
        page = mock.Mock()
        page.locator.return_value.inner_text.return_value = "接收短信验证码 请输入验证码 获取验证码"
        page.screenshot.return_value = None
        result = browser_worker.click_publish(page, "douyin", "target-sms")
        self.assertEqual("login_required", result["status"])
        self.assertEqual("verification", result["field"])
        page.get_by_role.assert_not_called()
        page.get_by_text.assert_not_called()

    def test_normal_publish_help_text_is_not_authentication(self):
        page = mock.Mock()
        page.locator.return_value.inner_text.return_value = "视频发布成功后，价格将无法更改"
        self.assertIsNone(browser_worker.authentication_required(page))


if __name__ == "__main__":
    unittest.main()
