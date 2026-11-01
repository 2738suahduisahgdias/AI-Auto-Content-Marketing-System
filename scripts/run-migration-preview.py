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
# Only local technical review runs in the isolated demo. Publishing and model jobs stay disabled.
from content_workbench.jobs.worker import Worker
from content_workbench.review.executors import ReviewExecutors
app.V2.review.local_only=True
review_worker=Worker(app.DB_PATH,ReviewExecutors(app.V2.review).mapping(),app.ROOT,allowed_kinds=["review.scan","review.repair"])
review_worker.before_execute=app.V2.license.require_active
review_worker.start()
app.V2.overview_worker=review_worker
app.ThreadingHTTPServer(("127.0.0.1",8876),app.Handler).serve_forever()
