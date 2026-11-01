"""Isolated preview: original API, no background schedulers or workers."""
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
if not os.environ.get('CONTENT_AGENT_ROOT') or app.ROOT.name != 'migration-preview':
    raise SystemExit('本脚本只允许使用名为 migration-preview 的隔离目录，请运行 start-migration-demo.py')
if app.ROOT.resolve() not in app.DB_PATH.resolve().parents:
    raise SystemExit('隔离数据库必须在预览目录中')
from content_workbench.api.v2 import V2Application
app.init_db()
app.V2=V2Application(app.DB_PATH,app.ROOT,app.create_task,{"video.produce":app.produce_video_task,"video.preview":app.produce_visual_preview})
# Local article/review jobs and guarded Xiaohongshu prefill run here. Public publishing remains disabled.
from content_workbench.jobs.worker import Worker
from content_workbench.review.executors import ReviewExecutors
app.V2.review.local_only=True
local_executors=ReviewExecutors(app.V2.review).mapping()
for kind in ("article.outline","article.draft","article.export","article.image"):
    local_executors[kind]=app.V2.worker.executors[kind]
def prepare_validated_platform(job, context):
    from content_workbench.domain.errors import DomainError
    from content_workbench.publishing.executors import PublishingExecutors
    from content_workbench.publishing.service import PublishingService
    service=PublishingService(app.DB_PATH,app.ROOT)
    _,target=service.target(job["input"]["target_id"])
    if target["platform"]!="xiaohongshu":
        raise DomainError("PLATFORM_ACCEPTANCE_PENDING","该平台尚待现场验收；预填未执行",409)
    return PublishingExecutors(service).prepare(job,context)
local_executors["publish.prepare"]=prepare_validated_platform
review_worker=Worker(app.DB_PATH,local_executors,app.ROOT,allowed_kinds=["publish.prepare","review.scan","review.repair","article.export","article.outline","article.draft","article.image"])
review_worker.before_execute=app.V2.license.require_active
review_worker.start()
app.V2.overview_worker=review_worker
app.ThreadingHTTPServer(("127.0.0.1",8876),app.Handler).serve_forever()
