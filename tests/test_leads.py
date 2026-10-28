import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from content_workbench.accounts.analytics import AccountAnalytics
from content_workbench.accounts.leads import LeadService
from content_workbench.domain.errors import DomainError
from content_workbench.storage.db import connect, expand_schema


class LeadCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lead-test-")
        self.db = Path(self.temp.name) / "leads.db"
        with connect(self.db) as conn:
            expand_schema(conn)
        self.service = LeadService(self.db)

    def tearDown(self):
        self.temp.cleanup()

    def create(self, alias="制造业老板", stage="inquiry", revenue=None):
        return self.service.create({"platform": "douyin", "author_alias": alias, "profile_text": "40 人企业",
                                    "message_text": "想评估AI报价流程，下个月启动", "need_text": "报价流程试点",
                                    "occurred_at": "2026-10-27T02:00:00Z" if stage == "deal" else "2026-10-28T02:00:00Z",
                                    "deal_at": "2026-10-28T03:00:00Z" if stage == "deal" else None,
                                    "stage": stage, "revenue": revenue})

    def test_create_update_and_conflict_preserve_message(self):
        lead = self.create()
        self.assertEqual("inquiry", lead["stage"])
        updated = self.service.update(lead["id"], {"stage": "qualified", "expected_updated_at": lead["updated_at"]})
        self.assertEqual("qualified", updated["stage"])
        self.assertEqual(lead["message_text"], updated["message_text"])
        with self.assertRaises(DomainError) as caught:
            self.service.update(lead["id"], {"stage": "not_qualified", "expected_updated_at": lead["updated_at"]})
        self.assertEqual("LEAD_EDIT_CONFLICT", caught.exception.code)
        with self.assertRaises(DomainError):
            self.service.create({"platform": "douyin", "author_alias": "缺少正文"})

    def test_real_acquisition_aggregation(self):
        self.create("有效用户", "qualified")
        self.create("暂无效用户", "not_qualified")
        self.create("成交用户", "deal", 19900)
        data = AccountAnalytics(self.db).bootstrap(datetime(2026, 10, 28, 12, tzinfo=ZoneInfo("Asia/Shanghai")))
        today = data["totals"]["today"]
        self.assertEqual(2, today["inquiries"])
        self.assertEqual(1, today["qualifiedLeads"])
        self.assertEqual(0, today["highIntentLeads"])
        self.assertEqual(0, today["meetings"])
        self.assertEqual(1, today["deals"])
        self.assertEqual(19900, today["revenue"])
        self.assertEqual(3, len(data["leads"]))
        self.assertEqual(1, data["totals"]["yesterday"]["inquiries"])
        self.assertEqual(0, data["totals"]["yesterday"]["deals"])

    def test_bulk_delete_only_selected_local_leads(self):
        first = self.create("删除一")
        second = self.create("删除二")
        keep = self.create("保留")
        self.assertEqual(2, self.service.delete([first["id"], second["id"], second["id"]])["deleted"])
        self.assertEqual([keep["id"]], [item["id"] for item in self.service.list()])
        with self.assertRaises(DomainError):
            self.service.delete([])


if __name__ == "__main__":
    unittest.main()
