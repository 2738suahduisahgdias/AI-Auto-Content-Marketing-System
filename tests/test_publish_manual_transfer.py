import unittest
from content_workbench.publishing.schemas import validate_payload
from content_workbench.domain.errors import DomainError
class ManualTransferTest(unittest.TestCase):
    def test_manual_official_needs_no_cover(self):
        result = validate_payload("article", "wechat_official_account", {"title":"标题", "body":"正文", "manual_transfer":True})
        self.assertTrue(result["manual_transfer"])
        self.assertNotIn("cover_asset_id", result)
    def test_automatic_still_requires_cover(self):
        with self.assertRaises(DomainError):
            validate_payload("article", "wechat_official_account", {"title":"标题", "body":"正文"})
    def test_other_platform_cannot_enable_manual_flag(self):
        result = validate_payload("video", "douyin", {"title":"标题", "description":"正文", "manual_transfer":True})
        self.assertNotIn("manual_transfer", result)
