import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from content_workbench.domain.errors import DomainError
from content_workbench.jobs.worker import JobCancelled
from content_workbench.topics.executors import TopicExecutors
from content_workbench.topics.kimi_browser import KimiBrowserCollector


class KimiBrowserCollectorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="kimi-browser-test-")
        self.context = mock.Mock()
        self.collector = KimiBrowserCollector(Path(self.temp.name), self.context)
        self.collector.provider = mock.Mock()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_login_check_uses_five_minute_timeout_and_kimi_agent(self) -> None:
        self.collector.provider.complete_json.return_value = {
            "status": "ok",
            "login_verified": True,
            "items": [],
            "errors": [],
        }
        result = self.collector.ensure_login()
        self.assertTrue(result["login_verified"])
        payload = json.loads(self.collector.provider.complete_json.call_args.args[0])
        self.assertEqual("check_login", payload["action"])
        self.assertEqual(300, payload["wait_seconds"])
        self.assertEqual(
            "douyin-collection-agent.md",
            self.collector.provider.complete_json.call_args.args[2].name,
        )
        self.assertEqual("kimi_cli", result["provider"])

    def test_login_timeout_is_visible_and_never_marked_ready(self) -> None:
        self.collector.provider.complete_json.return_value = {
            "status": "login_required",
            "login_verified": False,
            "items": [],
            "errors": [{"code": "LOGIN_REQUIRED", "message": "等待超时"}],
        }
        with self.assertRaises(DomainError) as caught:
            self.collector.ensure_login()
        self.assertEqual("LOGIN_REQUIRED", caught.exception.code)
        self.assertIn("5 分钟", caught.exception.action)

    def test_browser_unavailable_retries_once_without_login_error(self) -> None:
        failure = {
            "status": "error",
            "login_verified": False,
            "items": [],
            "errors": [
                {"code": "browser_unavailable", "message": "浏览器工具暂时不可用"}
            ],
        }
        self.collector.provider.complete_json.side_effect = [
            failure,
            {"status": "ok", "login_verified": True, "items": [], "errors": []},
        ]
        with mock.patch("content_workbench.topics.kimi_browser.time.sleep"):
            result = self.collector.ensure_login()
        self.assertTrue(result["login_verified"])
        self.assertEqual(2, self.collector.provider.complete_json.call_count)

    def test_persistent_browser_error_is_not_misreported_as_login_required(
        self,
    ) -> None:
        failure = {
            "status": "error",
            "login_verified": False,
            "items": [],
            "errors": [{"code": "browser_unavailable", "message": "浏览器工具不可用"}],
        }
        self.collector.provider.complete_json.side_effect = [failure, failure]
        with (
            mock.patch("content_workbench.topics.kimi_browser.time.sleep"),
            self.assertRaises(DomainError) as caught,
        ):
            self.collector.ensure_login()
        self.assertEqual("browser_unavailable", caught.exception.code)
        self.assertNotEqual("LOGIN_REQUIRED", caught.exception.code)

    def test_hot_sync_checks_login_before_collecting(self) -> None:
        self.collector.provider.complete_json.side_effect = [
            {"status": "ok", "login_verified": True, "items": [], "errors": []},
            {
                "status": "ok",
                "login_verified": True,
                "items": [{"title": "真实热点", "metadata": {}}],
                "errors": [],
            },
        ]
        result = self.collector.collect("hot")
        actions = [
            json.loads(call.args[0])["action"]
            for call in self.collector.provider.complete_json.call_args_list
        ]
        self.assertEqual(["check_login", "collect_hot"], actions)
        self.assertEqual("真实热点", result["items"][0]["title"])

    def test_hot_is_limited_to_twenty_in_page_order(self) -> None:
        items = [{"title": f"热点 {index}", "metadata": {}} for index in range(1, 26)]
        self.collector.provider.complete_json.side_effect = [
            {"status": "ok", "login_verified": True, "items": [], "errors": []},
            {"status": "ok", "login_verified": True, "items": items, "errors": []},
        ]
        result = self.collector.collect("hot")
        self.assertEqual(20, len(result["items"]))
        self.assertEqual("热点 1", result["items"][0]["title"])
        self.assertEqual("热点 20", result["items"][-1]["title"])
        self.assertEqual(20, result["items"][-1]["rank"])
        self.assertEqual(20, result["items"][-1]["metadata"]["rank"])

    def test_details_include_author_and_engagement(self) -> None:
        details = {
            "author_name": "真实作者",
            "author_url": "https://www.douyin.com/user/author",
            "author_followers": "1.2万",
            "like_count": "3456",
            "comment_count": "789",
        }
        self.collector.provider.complete_json.side_effect = [
            {"status": "ok", "login_verified": True, "items": [], "errors": []},
            {
                "status": "ok",
                "login_verified": True,
                "items": [],
                "errors": [],
                "details": details,
            },
        ]
        result = self.collector.collect("details", url="https://www.douyin.com/video/1")
        self.assertEqual(details, result["details"])
        self.assertEqual(
            "https://www.douyin.com/video/1",
            json.loads(self.collector.provider.complete_json.call_args.args[0])["url"],
        )

    def test_nested_item_details_are_normalized(self) -> None:
        details = {
            "author_name": "真实作者",
            "author_followers": "1.2万",
            "like_count": "3456",
            "comment_count": "789",
        }
        self.collector.provider.complete_json.side_effect = [
            {"status": "ok", "login_verified": True, "items": [], "errors": []},
            {
                "status": "ok",
                "login_verified": True,
                "items": [{"title": "作品", "details": details}],
                "errors": [],
            },
        ]
        result = self.collector.collect("details", url="https://www.douyin.com/video/1")
        self.assertEqual(details, result["details"])

    def test_batch_details_are_normalized(self) -> None:
        self.collector.provider.complete_json.side_effect = [
            {"status": "ok", "login_verified": True, "items": [], "errors": []},
            {
                "status": "ok",
                "login_verified": True,
                "items": [
                    {
                        "canonical_url": "https://www.douyin.com/video/1",
                        "details": {
                            "author_name": "作者一",
                            "author_followers": "100",
                            "like_count": "10",
                            "comment_count": "2",
                        },
                    },
                    {
                        "canonical_url": "https://www.douyin.com/video/2",
                        "details": {
                            "author_name": "作者二",
                            "author_followers": "200",
                            "like_count": "20",
                            "comment_count": "4",
                        },
                    },
                ],
                "errors": [],
            },
        ]
        result = self.collector.collect_details_batch(
            [
                "https://www.douyin.com/video/1",
                "https://www.douyin.com/video/2",
            ]
        )
        self.assertEqual(2, len(result["items"]))
        self.assertEqual("作者二", result["items"][1]["details"]["author_name"])
        self.assertEqual(
            "collect_details_batch",
            json.loads(self.collector.provider.complete_json.call_args.args[0])[
                "action"
            ],
        )

    def test_batch_results_envelope_is_normalized_with_item_snapshot(self) -> None:
        topic_url = "https://www.douyin.com/hot/2743933/example"
        video_url = "https://www.douyin.com/video/7707309687762406699"
        self.collector.provider.complete_json.side_effect = [
            {"status": "ok", "login_verified": True, "items": [], "errors": []},
            {
                "status": "ok",
                "login_verified": True,
                "items": [
                    {
                        "title": "真实作品",
                        "canonical_url": video_url,
                        "platform_item_id": "7707309687762406699",
                        "metadata": {"cover_url": "https://example.com/cover.jpg"},
                    }
                ],
                "results": [
                    {
                        "requested_url": topic_url,
                        "canonical_url": video_url,
                        "details": {
                            "author_name": "人民日报",
                            "author_followers": "2.0亿",
                            "like_count": "21.5万",
                            "comment_count": "147",
                        },
                    }
                ],
                "errors": [],
            },
        ]
        result = self.collector.collect_details_batch([topic_url])
        self.assertEqual(topic_url, result["items"][0]["requested_url"])
        self.assertEqual("真实作品", result["items"][0]["title"])
        self.assertEqual("人民日报", result["items"][0]["details"]["author_name"])
        self.assertNotIn("results", result)

    def test_collection_errors_remain_structured(self) -> None:
        self.collector.provider.complete_json.side_effect = [
            {"status": "ok", "login_verified": True, "items": [], "errors": []},
            {
                "status": "partial",
                "login_verified": True,
                "items": [],
                "errors": [{"code": "COLLECTION_NOT_FOUND", "message": "收藏夹不存在"}],
            },
        ]
        result = self.collector.collect("favorites", collection="不存在的收藏夹")
        self.assertEqual("partial", result["status"])
        self.assertEqual("COLLECTION_NOT_FOUND", result["errors"][0]["code"])
        self.assertEqual(
            "不存在的收藏夹",
            json.loads(self.collector.provider.complete_json.call_args.args[0])[
                "collection"
            ],
        )

    def test_topic_browser_actions_always_use_kimi_collector(self) -> None:
        service = mock.Mock()
        service.db_path = Path(self.temp.name) / "db"
        executor = TopicExecutors.__new__(TopicExecutors)
        executor.service = service
        executor.root = Path(self.temp.name)
        with (
            mock.patch(
                "content_workbench.topics.executors.require_agent_enabled",
                return_value={"timeout_seconds": 600},
            ),
            mock.patch(
                "content_workbench.topics.kimi_browser.KimiBrowserCollector.collect",
                return_value={"status": "ok"},
            ) as collect,
        ):
            executor.browser(self.context, "hot", "douyin_hot_top20")
        collect.assert_called_once_with("hot", collection=None, url=None)


class EnrichTest(unittest.TestCase):
    def test_existing_cover_is_cached_without_another_kimi_browser_call(self) -> None:
        with tempfile.TemporaryDirectory(prefix="enrich-test-") as directory:
            service = mock.Mock()
            service.cache_cover.return_value = True
            service.get_item.return_value = {
                "url": "https://example.com/video/1",
                "metadata": {
                    "cover_url": "https://example.com/cover.jpg",
                    "author_name": "真实作者",
                    "author_followers": "1.2万",
                    "like_count": "3456",
                    "comment_count": "789",
                },
            }
            executor = TopicExecutors.__new__(TopicExecutors)
            executor.service = service
            executor.root = Path(directory)
            with mock.patch.object(executor, "browser") as browser:
                executor.enrich("item-1", mock.Mock())
            browser.assert_not_called()
            service.cache_cover.assert_called_once_with("item-1")

    def test_unexpected_cover_error_is_not_silently_ignored(self) -> None:
        with tempfile.TemporaryDirectory(prefix="enrich-test-") as directory:
            service = mock.Mock()
            service.cache_cover.side_effect = ValueError("unexpected")
            service.get_item.return_value = {
                "url": "https://example.com/video/1",
                "metadata": {
                    "cover_url": "https://example.com/cover.jpg",
                    "author_name": "真实作者",
                    "author_followers": "1.2万",
                    "like_count": "3456",
                    "comment_count": "789",
                },
            }
            executor = TopicExecutors.__new__(TopicExecutors)
            executor.service = service
            executor.root = Path(directory)
            with (
                mock.patch.object(executor, "browser") as browser,
                self.assertRaisesRegex(ValueError, "unexpected"),
            ):
                executor.enrich("item-1", mock.Mock())
            browser.assert_not_called()

    def test_cached_cover_does_not_skip_missing_author_and_engagement(self) -> None:
        with tempfile.TemporaryDirectory(prefix="enrich-test-") as directory:
            service = mock.Mock()
            service.cache_cover.return_value = True
            service.get_item.return_value = {
                "url": "https://example.com/video/1",
                "metadata": {"cover_url": "https://example.com/cover.jpg"},
            }
            executor = TopicExecutors.__new__(TopicExecutors)
            executor.service = service
            executor.root = Path(directory)
            details = {
                "author_name": "真实作者",
                "author_followers": "1.2万",
                "like_count": "3456",
                "comment_count": "789",
            }
            with mock.patch.object(
                executor, "browser", return_value={"details": details}
            ) as browser:
                executor.enrich("item-1", mock.Mock())
            browser.assert_called_once()
            service.update_metadata.assert_any_call("item-1", details)

    def test_enrich_many_updates_each_item_and_keeps_errors(self) -> None:
        with tempfile.TemporaryDirectory(prefix="enrich-many-test-") as directory:
            service = mock.Mock()
            service.get_item.side_effect = lambda item_id: {
                "platform": "douyin",
                "url": f"https://www.douyin.com/video/{item_id}",
                "metadata": {"cover_url": "https://example.com/cover.jpg"},
            }
            executor = TopicExecutors.__new__(TopicExecutors)
            executor.service = service
            executor.root = Path(directory)
            result_items = {
                "a": {
                    "canonical_url": "https://www.douyin.com/video/a",
                    "details": {
                        "author_name": "作者一",
                        "author_followers": "100",
                        "like_count": "10",
                        "comment_count": "2",
                    },
                },
                "b": {
                    "canonical_url": "https://www.douyin.com/video/b",
                    "details": {
                        "author_name": "作者二",
                        "author_followers": "200",
                        "like_count": "20",
                        "comment_count": "4",
                    },
                },
            }

            context = mock.Mock()

            def collect_one(urls):
                item_id = urls[0].rsplit("/", 1)[-1]
                context.progress("research_metadata_batch", 0.3)
                return {
                    "status": "partial" if item_id == "b" else "ok",
                    "items": [result_items[item_id]],
                    "errors": [{"code": "ONE_FAILED", "message": "一条失败"}]
                    if item_id == "b"
                    else [],
                }

            with mock.patch(
                "content_workbench.topics.kimi_browser.KimiBrowserCollector.collect_details_batch",
                side_effect=collect_one,
            ) as batch:
                result = executor.enrich_many(["a", "b"], context)
            self.assertEqual(2, batch.call_count)
            batch.assert_any_call(["https://www.douyin.com/video/a"])
            batch.assert_any_call(["https://www.douyin.com/video/b"])
            self.assertEqual(2, result["succeeded"])
            self.assertEqual(2, result["processed"])
            self.assertEqual(1, len(result["errors"]))
            context.progress.assert_any_call("author_engagement_backfill", 0.5)
            context.progress.assert_any_call("author_engagement_backfill", 1.0)

    def test_enrich_many_tracks_hot_topic_and_resolved_video_urls(self) -> None:
        service = mock.Mock()
        topic_url = "https://www.douyin.com/hot/2743890/example"
        video_url = "https://www.douyin.com/video/123456"
        service.get_item.return_value = {
            "platform": "douyin",
            "url": topic_url,
            "metadata": {},
        }
        executor = TopicExecutors.__new__(TopicExecutors)
        executor.service = service
        executor.root = Path(".")
        details = {
            "author_name": "真实作者",
            "author_followers": "100",
            "like_count": "10",
            "comment_count": "2",
        }
        with mock.patch(
            "content_workbench.topics.kimi_browser.KimiBrowserCollector.collect_details_batch",
            return_value={
                "status": "ok",
                "items": [
                    {
                        "requested_url": topic_url,
                        "canonical_url": video_url,
                        "details": details,
                    }
                ],
                "errors": [],
            },
        ):
            result = executor.enrich_many(["hot-item"], mock.Mock())
        self.assertEqual(1, result["succeeded"])
        service.update_metadata.assert_called_once_with(
            "hot-item", {**details, "detail_source_url": video_url}
        )

    def test_enrich_many_saves_before_cancellation_and_resumes_only_missing(
        self,
    ) -> None:
        metadata = {"a": {}, "b": {}}
        service = mock.Mock()
        service.get_item.side_effect = lambda item_id: {
            "platform": "douyin",
            "url": f"https://www.douyin.com/video/{item_id}",
            "metadata": metadata[item_id],
        }
        service.update_metadata.side_effect = lambda item_id, values: metadata[
            item_id
        ].update(values)
        executor = TopicExecutors.__new__(TopicExecutors)
        executor.service = service
        executor.root = Path(".")
        details = {
            "author_name": "真实作者",
            "author_followers": "100",
            "like_count": "10",
            "comment_count": "2",
        }

        def cancel_on_second(urls):
            item_id = urls[0].rsplit("/", 1)[-1]
            if item_id == "b":
                raise JobCancelled()
            return {
                "status": "ok",
                "items": [{"requested_url": urls[0], "details": details}],
                "errors": [],
            }

        with (
            mock.patch(
                "content_workbench.topics.kimi_browser.KimiBrowserCollector.collect_details_batch",
                side_effect=cancel_on_second,
            ),
            self.assertRaises(JobCancelled),
        ):
            executor.enrich_many(["a", "b"], mock.Mock())
        self.assertEqual(details, {key: metadata["a"][key] for key in details})

        with mock.patch(
            "content_workbench.topics.kimi_browser.KimiBrowserCollector.collect_details_batch",
            return_value={
                "status": "ok",
                "items": [
                    {
                        "requested_url": "https://www.douyin.com/video/b",
                        "details": details,
                    }
                ],
                "errors": [],
            },
        ) as resume:
            result = executor.enrich_many(["a", "b"], mock.Mock())
        resume.assert_called_once_with(["https://www.douyin.com/video/b"])
        self.assertEqual(1, result["succeeded"])
        self.assertEqual(1, result["total"])

    def test_metadata_backfill_only_reads_unique_collection_douyin_items(self) -> None:
        service = mock.Mock()
        service.bootstrap.return_value = {
            "sources": {
                "hot": [{"id": "hot-item", "platform": "douyin", "source_key": "hot"}],
                "featured": [
                    {"id": "same", "platform": "douyin", "source_key": "featured"},
                    {
                        "id": "xhs",
                        "platform": "xiaohongshu",
                        "source_key": "xhs_featured",
                    },
                ],
                "competitor": [
                    {"id": "same", "platform": "douyin", "source_key": "competitor"}
                ],
            }
        }
        executor = TopicExecutors.__new__(TopicExecutors)
        executor.service = service
        with mock.patch.object(
            executor, "enrich_many", return_value={"succeeded": 0}
        ) as enrich:
            executor.metadata_backfill({}, mock.Mock())
        enrich.assert_called_once_with(["same"], mock.ANY)


if __name__ == "__main__":
    unittest.main()
