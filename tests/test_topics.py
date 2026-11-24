import subprocess
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest import mock

from content_workbench.domain.services import Workbench
from content_workbench.storage.db import connect, expand_schema
from content_workbench.topics.scheduler import next_due
from content_workbench.topics.service import TopicService


class DummyContext:
    def progress(self, *args):
        pass

    def run_process(self, arguments, timeout=600, stage=None, cwd=None):
        result = subprocess.run(
            arguments, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
        if result.returncode:
            raise RuntimeError(result.stderr[-500:])
        return result.stdout, result.stderr


class TopicCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="topic-test-")
        self.root = Path(self.temp.name)
        self.db = self.root / "topics.db"
        with connect(self.db) as conn:
            expand_schema(conn)
        self.service = TopicService(self.db, self.root)
        self.workbench = Workbench(self.db, self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_hot_limit_partial_and_collection_dedup(self):
        for index in range(20):
            self.service.upsert_item(
                {
                    "title": "热点" + str(index),
                    "canonical_url": "https://www.douyin.com/hot/" + str(index),
                    "rank": index + 1,
                },
                "hot",
            )
        data = self.service.bootstrap()
        self.assertEqual(20, data["hot_count"])
        self.assertTrue(data["hot_complete"])
        for _ in range(2):
            self.service.upsert_item(
                {
                    "title": "同一收藏",
                    "canonical_url": "https://www.douyin.com/video/abc",
                },
                "featured",
                collection_title="选题",
            )
        data = self.service.bootstrap()
        self.assertEqual(1, len(data["sources"]["featured"]))
        with connect(self.db, readonly=True) as conn:
            self.assertEqual(
                1,
                conn.execute(
                    "SELECT COUNT(*) FROM wb_research_items WHERE canonical_url='https://www.douyin.com/video/abc'"
                ).fetchone()[0],
            )
            self.assertEqual(
                1, conn.execute("SELECT COUNT(*) FROM wb_memberships").fetchone()[0]
            )
        run_id = self.service.start_sync("full", {"test": True})
        self.service.finish_sync(run_id, "succeeded", {"hot": 20}, True)
        with connect(self.db, readonly=True) as conn:
            self.assertEqual(
                "succeeded",
                conn.execute(
                    "SELECT status FROM wb_sync_runs WHERE id=?", (run_id,)
                ).fetchone()[0],
            )

    def test_reconcile_requires_two_complete_scans(self):
        keep = self.service.upsert_item(
            {"title": "保留", "canonical_url": "https://www.douyin.com/video/keep"},
            "featured",
            collection_title="选题",
        )
        remove = self.service.upsert_item(
            {"title": "移除", "canonical_url": "https://www.douyin.com/video/remove"},
            "featured",
            collection_title="选题",
        )
        self.service.reconcile_collection("选题", [keep], "run-1", complete=True)
        with connect(self.db, readonly=True) as conn:
            self.assertEqual(
                "present",
                conn.execute(
                    "SELECT status FROM wb_memberships WHERE item_id=?", (remove,)
                ).fetchone()[0],
            )
        self.service.reconcile_collection("选题", [keep], "run-2", complete=True)
        with connect(self.db, readonly=True) as conn:
            self.assertEqual(
                "removed",
                conn.execute(
                    "SELECT status FROM wb_memberships WHERE item_id=?", (remove,)
                ).fetchone()[0],
            )
        self.service.reconcile_collection("选题", [], "run-partial", complete=False)
        with connect(self.db, readonly=True) as conn:
            self.assertEqual(
                "present",
                conn.execute(
                    "SELECT status FROM wb_memberships WHERE item_id=?", (keep,)
                ).fetchone()[0],
            )

    def test_settings_and_daily_schedule(self):
        settings = self.service.save_settings(
            {
                "industry_scope": "企业AI",
                "industry_prompt": "测试行业提示词",
                "douyin_prompt": "测试抖音提示词",
                "daily_time": "08:30",
                "daily_enabled": True,
            }
        )
        self.assertEqual("08:30", settings["daily_time"])
        with connect(self.db, readonly=True) as conn:
            schedule = conn.execute(
                "SELECT * FROM wb_schedules WHERE id='topics.daily'"
            ).fetchone()
            self.assertEqual(1, schedule["enabled"])
            self.assertEqual("coalesce_latest", schedule["misfire_policy"])
        after = datetime(2026, 10, 26, 1, 0, tzinfo=UTC)
        self.assertEqual("2026-10-27T01:00:00.000Z", next_due("09:00", after))

    def test_douyin_login_uses_playwright_worker(self):
        from content_workbench.topics.executors import TopicExecutors

        executor = TopicExecutors(self.service)
        context = mock.Mock()
        context.run_process.return_value = ('{"status":"ready"}', "")
        with (
            mock.patch(
                "content_workbench.topics.executors.require_agent_enabled",
                return_value={"timeout_seconds": 600},
            ),
            mock.patch(
                "content_workbench.topics.kimi_browser.KimiBrowserCollector.collect"
            ) as collector,
        ):
            result = executor.login({"input": {}}, context)
        self.assertEqual(result["status"], "ready")
        arguments = context.run_process.call_args.args[0]
        self.assertEqual(arguments[1], "-m")
        self.assertEqual(arguments[2], "content_workbench.topics.browser_worker")
        self.assertEqual(arguments[arguments.index("--action") + 1], "login")
        self.assertEqual(
            context.run_process.call_args.kwargs["cwd"],
            Path(__file__).resolve().parents[1],
        )
        collector.assert_not_called()

    def test_xhs_login_uses_shared_playwright_browser(self):
        from content_workbench.topics.executors import TopicExecutors

        executor = TopicExecutors(self.service)
        with (
            mock.patch(
                "content_workbench.topics.xiaohongshu_browser.XHSBrowserCollector"
            ) as collector,
            mock.patch(
                "content_workbench.accounts.existing_browser.run",
                return_value={"status": "ok", "login_verified": True},
            ) as browser,
            mock.patch.object(
                executor, "xhs_sync", return_value={"status": "succeeded"}
            ),
        ):
            result = executor.xhs_login({"input": {}}, DummyContext())
        self.assertTrue(result["login"]["login_verified"])
        browser.assert_called_once_with("xhs_personal_login")
        collector.assert_not_called()

    def test_xhs_collections_sync_once_and_recommend_real_sources(self):
        from content_workbench.topics.executors import TopicExecutors

        self.service.upsert_item(
            {
                "title": "抖音精选",
                "canonical_url": "https://www.douyin.com/video/shared",
            },
            "featured",
            collection_title="选题",
        )
        sources = ("xhs_hot", "xhs_featured", "xhs_competitor", "xhs_high_praise")
        items = [
            {
                "title": "小红书" + source,
                "canonical_url": "https://www.xiaohongshu.com/explore/" + source,
                "metadata": {"source_key": source},
            }
            for source in sources
        ]
        executor = TopicExecutors(self.service)
        with (
            mock.patch(
                "content_workbench.topics.xiaohongshu_browser.XHSBrowserCollector"
            ) as browser,
            mock.patch.object(self.service, "cache_cover", return_value=True),
            mock.patch.object(
                executor, "enrich_many", return_value={"errors": []}
            ) as enrich,
        ):
            collector = browser.return_value
            collector.collect_hot.return_value = {"items": items[:1], "errors": []}
            collector.collect_favorites.return_value = {
                "items": items[1:],
                "errors": [],
            }
            result = executor.xhs_sync({"input": {}}, DummyContext())
        self.assertEqual("succeeded", result["status"])
        self.assertEqual(1, browser.call_count)
        self.assertEqual(
            {"xhs_featured", "xhs_competitor", "xhs_high_praise"},
            {
                next(iter(call.args[0]))
                for call in collector.collect_favorites.call_args_list
            },
        )
        data = self.service.bootstrap()
        for source in sources:
            self.assertEqual(1, len(data["sources"][source]))
        self.assertEqual(1, len(data["sources"]["featured"]))
        self.assertEqual("抖音精选", data["sources"]["featured"][0]["title"])
        self.assertIsNotNone(data["xhs_last_sync"])
        enriched_ids = enrich.call_args.args[0]
        self.assertEqual(3, len(enriched_ids))
        for item_id in enriched_ids:
            self.assertNotEqual(
                "xhs_hot",
                self.service.get_item(item_id)["metadata"]["source_key"],
            )

        candidate = {
            "title": "新推荐",
            "reason": "真实收藏证据",
            "angle": "新场景",
            "evidence_ids": [],
        }
        with mock.patch.object(
            executor, "kimi_json", return_value=[candidate]
        ) as model:
            recommended = executor.recommend(
                {"input": {"agent": "xiaohongshu"}}, DummyContext()
            )
        self.assertEqual(1, recommended["candidates"])
        prompt = model.call_args.args[2]
        for source in sources:
            self.assertIn(source, prompt)
        self.assertNotIn('"hot"', prompt)
        self.assertEqual(
            1, len(self.service.bootstrap()["recommendations"]["xiaohongshu"])
        )

    def test_xhs_hot_does_not_need_personal_collection_name(self):
        from content_workbench.topics.executors import TopicExecutors

        executor = TopicExecutors(self.service)
        with mock.patch(
            "content_workbench.topics.xiaohongshu_browser.XHSBrowserCollector"
        ) as browser:
            collector = browser.return_value
            collector.collect_hot.return_value = {"items": [], "errors": []}
            collector.collect_favorites.return_value = {"items": [], "errors": []}
            result = executor.xhs_sync({"input": {}}, DummyContext())
        self.assertNotIn("xhs_hot", collector.collect_favorites.call_args.args[0])
        self.assertEqual(0, result["stats"]["xhs_hot"])
        self.assertEqual("succeeded", result["status"])

    def test_xhs_token_change_reuses_existing_real_work(self):
        self.service.save_settings({"xhs_featured_collection": "精选选题"})
        original = self.service.upsert_item(
            {
                "title": "原作品",
                "canonical_url": "https://www.xiaohongshu.com/explore/note1?xsec_token=old",
                "platform_item_id": "note1",
            },
            "xhs_featured",
            collection_title="精选选题",
            platform="xiaohongshu",
        )
        updated = self.service.upsert_item(
            {
                "title": "原作品",
                "canonical_url": "https://www.xiaohongshu.com/explore/note1?xsec_token=new",
                "platform_item_id": "note1",
            },
            "xhs_featured",
            collection_title="精选选题",
            platform="xiaohongshu",
        )
        self.assertEqual(original, updated)
        self.assertEqual(1, len(self.service.bootstrap()["sources"]["xhs_featured"]))

    def test_archive_and_restore_keep_research_snapshot(self):
        item_id = self.service.upsert_item(
            {"title": "不想继续的选题", "canonical_url": "https://example.com/archive"},
            "featured",
            collection_title="选题",
        )
        self.service.set_archived(item_id, True)
        data = self.service.bootstrap()
        self.assertEqual([], data["sources"]["featured"])
        self.assertEqual(1, data["archived_count"])
        self.assertTrue(data["archived"][0]["archived"])
        self.service.set_archived(item_id, False)
        restored = self.service.bootstrap()
        self.assertEqual(0, restored["archived_count"])
        self.assertEqual(item_id, restored["sources"]["featured"][0]["id"])

    def test_bootstrap_includes_probe_job_result_for_download_modal(self):
        job = self.service.jobs.enqueue(
            "research.probe", {}, "research_xhs", resource_key="download"
        )
        jobs = self.service.bootstrap()["jobs"]
        self.assertIn(job["id"], [item["id"] for item in jobs])
        self.assertEqual(
            "research_xhs",
            next(item for item in jobs if item["id"] == job["id"])["aggregate_id"],
        )


if __name__ == "__main__":
    unittest.main()
