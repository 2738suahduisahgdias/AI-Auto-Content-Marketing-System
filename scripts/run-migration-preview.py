"""Isolated preview API with local workers and no background schedulers."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app

PREVIEW_EXECUTOR_KINDS = (
    "article.outline",
    "article.draft",
    "article.export",
    "article.image",
    "publish.fields",
    "accounts.login",
    "topics.login",
    "topics.xhs_login",
)
PREVIEW_WORKER_KINDS = (
    "publish.fields",
    "publish.prepare",
    "review.scan",
    "review.repair",
    "article.export",
    "article.outline",
    "article.draft",
    "article.image",
    "accounts.login",
    "topics.login",
    "topics.xhs_login",
)


def main() -> None:
    if not os.environ.get("CONTENT_AGENT_ROOT") or app.ROOT.name != "migration-preview":
        raise SystemExit("本脚本只允许使用名为 migration-preview 的隔离目录，请运行 start-migration-demo.py")
    if app.ROOT.resolve() not in app.DB_PATH.resolve().parents:
        raise SystemExit("隔离数据库必须在预览目录中")
    from content_workbench.api.v2 import V2Application

    app.init_db()
    app.V2 = V2Application(
        app.DB_PATH,
        app.ROOT,
        app.create_task,
        {
            "video.produce": app.produce_video_task,
            "video.preview": app.produce_visual_preview,
        },
    )
    app.V2.publishing_execution_enabled = False
    # Login and local article/review jobs run here. Public publishing remains disabled.
    from content_workbench.jobs.worker import Worker
    from content_workbench.review.executors import ReviewExecutors

    app.V2.review.local_only = True
    local_executors = ReviewExecutors(app.V2.review).mapping()
    for kind in PREVIEW_EXECUTOR_KINDS:
        local_executors[kind] = app.V2.worker.executors[kind]

    def prepare_validated_platform(job, context):
        from content_workbench.domain.errors import DomainError
        from content_workbench.publishing.executors import PublishingExecutors
        from content_workbench.publishing.service import PublishingService

        service = PublishingService(app.DB_PATH, app.ROOT)
        _, target = service.target(job["input"]["target_id"])
        if target["platform"] != "xiaohongshu":
            raise DomainError("PLATFORM_ACCEPTANCE_PENDING", "该平台尚待现场验收；预填未执行", 409)
        return PublishingExecutors(service).prepare(job, context)

    local_executors["publish.prepare"] = prepare_validated_platform
    review_worker = Worker(
        app.DB_PATH,
        local_executors,
        app.ROOT,
        allowed_kinds=list(PREVIEW_WORKER_KINDS),
    )
    review_worker.before_execute = app.V2.license.require_active
    review_worker.start()
    app.V2.overview_worker = review_worker
    app.ThreadingHTTPServer(("127.0.0.1", 8876), app.Handler).serve_forever()


if __name__ == "__main__":
    main()
