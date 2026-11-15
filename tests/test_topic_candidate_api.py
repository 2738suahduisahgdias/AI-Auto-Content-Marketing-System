import tempfile
import unittest
from pathlib import Path
from unittest import mock

from content_workbench.domain.errors import DomainError
from content_workbench.storage.db import connect, expand_schema
from content_workbench.topics.api import TopicAPI
from content_workbench.topics.service import TopicService


class TopicCandidateApiCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="topic-candidate-")
        self.root = Path(self.temp.name)
        with connect(self.root / "topics.db") as conn:
            expand_schema(conn)
            conn.execute(
                "CREATE TABLE tasks(content_id TEXT PRIMARY KEY,source_json TEXT)"
            )
        self.service = TopicService(self.root / "topics.db", self.root)
        self.app = mock.Mock()
        self.app.response.side_effect = lambda handler, data, status=200: (data, status)
        self.creator = mock.Mock(return_value={"content_id": "task-real-1"})
        self.api = TopicAPI(self.app, self.service, self.creator)

    def tearDown(self):
        self.temp.cleanup()

    def test_converts_recommendation_once_and_preserves_sources(self):
        candidate_id = self.service.save_candidates(
            "douyin",
            [
                {
                    "title": "真实推荐",
                    "reason": "真实痛点",
                    "angle": "案例切入",
                    "pillar": "enterprise_ai",
                    "audience": "business_owners",
                    "evidence_ids": ["research-1", "research-2"],
                }
            ],
        )[0]
        task, status = self.api.handle(
            None, "POST", f"/api/topics/candidates/{candidate_id}/create-task", {}, {}
        )
        self.assertEqual(201, status)
        self.assertEqual("task-real-1", task["content_id"])
        self.assertEqual("topic_candidate", task["source"]["type"])
        self.assertEqual(["research-1", "research-2"], task["source"]["evidence_ids"])
        self.assertEqual("真实痛点", self.creator.call_args.args[0]["pain_point"])
        converted = self.service.get_candidate(candidate_id)
        self.assertEqual("converted", converted["status"])
        self.assertEqual("task-real-1", converted["task_id"])
        with self.assertRaises(DomainError) as caught:
            self.api.handle(
                None,
                "POST",
                f"/api/topics/candidates/{candidate_id}/create-task",
                {},
                {},
            )
        self.assertEqual("TOPIC_CANDIDATE_CONVERTED", caught.exception.code)
        self.creator.assert_called_once()

    def test_metadata_backfill_enqueues_kimi_browser_job(self):
        self.service.upsert_item(
            {
                "title": "待补全作品",
                "canonical_url": "https://www.douyin.com/video/1",
                "metadata": {"cover_url": "https://example.com/cover.jpg"},
            },
            "hot",
        )
        self.app.jobs.enqueue_active_once.return_value = {"id": "job-backfill"}
        result, status = self.api.handle(
            None, "POST", "/api/topics/metadata-backfill", {}, {}
        )
        self.assertEqual(202, status)
        self.assertEqual("job-backfill", result["id"])
        self.assertEqual(
            ("topics.metadata_backfill", {}, "metadata"),
            self.app.jobs.enqueue_active_once.call_args.args[:3],
        )
        self.assertEqual(
            "browser",
            self.app.jobs.enqueue_active_once.call_args.kwargs["resource_key"],
        )

    def test_xhs_probe_and_download_mode_use_real_job_contract(self):
        self.app.jobs.enqueue.side_effect = [
            {"id": "job-probe"},
            {"id": "job-download"},
        ]
        probe, probe_status = self.api.handle(
            None, "POST", "/api/topics/items/note-1/download/probe", {}, {}
        )
        download, download_status = self.api.handle(
            None,
            "POST",
            "/api/topics/items/note-1/analyze",
            {},
            {"mode": "compat"},
        )
        self.assertEqual((202, 202), (probe_status, download_status))
        self.assertEqual("job-probe", probe["id"])
        self.assertEqual("job-download", download["id"])
        self.assertEqual(
            "research.probe", self.app.jobs.enqueue.call_args_list[0].args[0]
        )
        self.assertEqual(
            {"mode": "compat"}, self.app.jobs.enqueue.call_args_list[1].args[1]
        )


if __name__ == "__main__":
    unittest.main()
