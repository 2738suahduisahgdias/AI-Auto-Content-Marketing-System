#!/usr/bin/env python3
"""Start the local-only preview independently of a temporary terminal session."""
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request

root = Path(__file__).resolve().parents[1]
url = 'http://127.0.0.1:8847/demo/'
def ready():
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return response.status == 200
    except Exception:
        return False
if ready():
    print('映序预览已运行：' + url)
    raise SystemExit(0)
node = shutil.which('node') or '/usr/local/bin/node'
vite = root / 'webapp/node_modules/vite/bin/vite.js'
if not vite.exists():
    raise SystemExit('缺少前端依赖，请先在 webapp 目录运行 npm ci。')
logs = root / 'reports'
logs.mkdir(exist_ok=True)
with (logs / 'yingxu-preview.log').open('ab') as log:
    process = subprocess.Popen([node, str(vite), '--host', '127.0.0.1', '--port', '8847', '--strictPort'], cwd=root/'webapp', stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
for _ in range(30):
    if process.poll() is not None:
        raise SystemExit('启动失败，请查看 reports/yingxu-preview.log。')
    if ready():
        print('映序预览已启动：' + url)
        print('仅监听本机。重启电脑或拔出外接盘后，需要重新启动。')
        break
    time.sleep(.2)
else:
    raise SystemExit('服务未及时就绪，请查看 reports/yingxu-preview.log。')
