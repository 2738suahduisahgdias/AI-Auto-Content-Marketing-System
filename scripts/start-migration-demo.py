"""Start the isolated migration API and the original-workspace Vite preview."""
from pathlib import Path
import os,subprocess,time,urllib.request
repo=Path(__file__).resolve().parents[1]
preview=Path(os.environ.get('YINGXU_PREVIEW_ROOT',str(repo.parents[1]/'runtime/migration-preview'))).resolve()
database=preview/'data/content-agent.db'
if not database.is_file():
    raise SystemExit('找不到隔离演示数据库；请先准备副本。不会自动使用正式数据库。')
def ready(url):
    try:
        with urllib.request.urlopen(url,timeout=2) as response:return response.status==200
    except Exception:return False
if not ready('http://127.0.0.1:8876/'):
    env={**os.environ,'CONTENT_AGENT_ROOT':str(preview),'CONTENT_AGENT_DB':str(database),'CONTENT_AGENT_MEDIA_BASE_URL':'http://127.0.0.1:8876'}
    if (preview/'license/public-keys.json').is_file():
        env['CONTENT_AGENT_LICENSE_MODE']='required'
    with (preview/'server.log').open('ab') as log:
        process=subprocess.Popen(['python3',str(repo/'scripts/run-migration-preview.py')],cwd=repo,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
    (preview/'server.pid').write_text(str(process.pid))
    for _ in range(40):
        if ready('http://127.0.0.1:8876/'):break
        if process.poll() is not None:raise SystemExit('预览 API 启动失败，请查看隔离目录 server.log')
        time.sleep(.25)
    else:raise SystemExit('预览 API 未就绪，请查看 server.log')
subprocess.run(['python3',str(repo/'scripts/start-yingxu-preview.py')],cwd=repo,check=True)
