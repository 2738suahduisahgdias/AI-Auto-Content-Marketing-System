import tempfile
import unittest
from pathlib import Path
from unittest import mock

from content_workbench.accounts.executors import AccountExecutors
from content_workbench.accounts.platform_worker import labeled_metrics, wait_for_login
from content_workbench.domain.errors import DomainError


class AccountCollectionCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="account-collection-")
        self.service = mock.Mock()
        self.service.topics.root = Path(self.temp.name)
        self.service.topics.db_path = Path(self.temp.name) / "accounts.db"
        self.executor = AccountExecutors(self.service)

    def tearDown(self):
        self.temp.cleanup()

    def test_labeled_metrics_do_not_guess_unlabeled_numbers(self):
        metrics = labeled_metrics("播放量 1.2万 点赞 340 评论 21 分享 8 收藏 16 其他数字 999", "wechat_channels")
        self.assertEqual("1.2万", metrics["views"])
        self.assertEqual("340", metrics["likes"])
        self.assertEqual("21", metrics["comments"])
        self.assertEqual("8", metrics["shares"])
        self.assertEqual("16", metrics["favorites"])
        self.assertNotIn("999", metrics.values())
        self.assertEqual({}, labeled_metrics("没有标签的 999", "wechat_channels"))

    def test_four_platform_sync_keeps_successes_and_reports_each_error(self):
        def result(action):
            count = {"xhs_notes": 1, "douyin_account": 2, "channels_account": 3, "official_account": 4}[action]
            return {"status": "ok", "profile": {}, "items": [{"title": "内容", "canonical_url": "https://example.com/" + action}] * count}
        def collect(context, action, stage):
            if action in ("xhs_notes", "douyin_account"):
                return result(action)
            raise DomainError("LOGIN_REQUIRED", "需要扫码", 409)
        with mock.patch.object(self.executor, "platform", side_effect=collect):
            data = self.executor.sync({}, mock.Mock())
        self.assertEqual(1, data["accounts"]["xiaohongshu"])
        self.assertEqual(2, data["accounts"]["douyin"])
        self.assertEqual("需要扫码", data["accounts"]["wechat_channels_error"])
        self.assertEqual("需要扫码", data["accounts"]["wechat_official_account_error"])
        self.assertEqual(2, self.service.save_snapshot.call_count)

    def test_all_platforms_failed_lists_every_reason(self):
        with mock.patch.object(self.executor, "platform", side_effect=DomainError("LOGIN_REQUIRED", "需要登录", 409)):
            with self.assertRaises(DomainError) as caught:
                self.executor.sync({}, mock.Mock())
        self.assertEqual("ACCOUNTS_UNAVAILABLE", caught.exception.code)
        for platform in ("xiaohongshu", "douyin", "wechat_channels", "wechat_official_account"):
            self.assertIn(platform, caught.exception.message)
        self.service.save_snapshot.assert_not_called()

    def test_all_login_actions_use_the_same_collection_profile(self):
        with mock.patch.object(self.executor, "platform", return_value={"status": "browser_closed"}) as open_browser:
            for platform in ("xiaohongshu", "douyin_publish", "wechat_channels", "wechat_official_account"):
                self.executor.login({"input": {"platform": platform}}, mock.Mock())
        actions = [call.args[1] for call in open_browser.call_args_list]
        self.assertEqual(["xiaohongshu_login", "douyin_publish_login", "channels_login", "official_login"], actions)

    def test_login_success_runs_full_sync_and_timeout_guides_retry(self):
        page = mock.Mock()
        with mock.patch("content_workbench.accounts.platform_worker.login_verified", side_effect=[False, True]):
            result = wait_for_login(page, "channels_login", timeout_seconds=180)
        self.assertTrue(result["login_verified"])
        page.wait_for_timeout.assert_called_once_with(3000)
        with mock.patch.object(self.executor, "platform", return_value=result), mock.patch.object(self.executor, "sync", return_value={"accounts": {"douyin": 15}}) as sync:
            completed = self.executor.login({"input": {"platform": "wechat_channels"}}, mock.Mock())
        sync.assert_called_once()
        self.assertEqual("all_account_data", completed["refresh"])
        with mock.patch("content_workbench.accounts.platform_worker.login_verified", return_value=False):
            timeout = wait_for_login(page, "official_login", timeout_seconds=0)
        self.assertEqual("login_required", timeout["status"])
        self.assertIn("重新发起登录", timeout["action"])


if __name__ == "__main__":
    unittest.main()
