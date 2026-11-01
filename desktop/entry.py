"""Mac entry point for the existing workbench, not a replacement application."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import runpy
import threading
import time
import urllib.request


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root');parser.add_argument('--port',type=int,default=8848);parser.add_argument('--no-browser',action='store_true');parser.add_argument('--smoke-test',action='store_true')
    args=parser.parse_args()
    resources=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))
    pointer=Path.home()/'Library/Application Support/Yingxu/workspace.json'
    root=args.root or os.environ.get('CONTENT_AGENT_ROOT')
    if not root and pointer.is_file():
        previous=json.loads(pointer.read_text())['root']
        choice=subprocess.run(['/usr/bin/osascript','-e','button returned of (display dialog "选择映序工作区" buttons {"选择其他工作区", "打开上次工作区"} default button "打开上次工作区")'],capture_output=True,text=True)
        if choice.returncode:return 0
        if '打开上次工作区' in choice.stdout:root=previous
    if not root:
        choice=subprocess.run(['/usr/bin/osascript','-e','POSIX path of (choose folder with prompt "选择新的空工作区文件夹，或已有恢复目录（建议外置硬盘）")'],capture_output=True,text=True)
        if choice.returncode:return 0
        root=str(Path(choice.stdout.strip()))
        pointer.parent.mkdir(parents=True,exist_ok=True);pointer.write_text(json.dumps({'root':root}))
    root=Path(root).expanduser().resolve()
    if str(root).startswith('/Volumes/') and not Path('/Volumes',root.parts[2]).is_mount():
        raise RuntimeError('外置硬盘未连接，请连接后重启；不会在系统盘创建替代工作区')
    root.mkdir(parents=True,exist_ok=True)
    os.environ.update(CONTENT_AGENT_ROOT=str(root),CONTENT_AGENT_DB=str(root/'data/content-agent.db'),CONTENT_AGENT_LICENSE_MODE='required',CONTENT_AGENT_MEDIA_BASE_URL=f'http://127.0.0.1:{args.port}')
    os.environ['PATH']=os.pathsep.join([str(resources/'bin'),str(Path.home()/'.local/bin'),'/opt/homebrew/bin','/usr/local/bin',os.environ.get('PATH','/usr/bin:/bin')])
    temporary=root/'cache/tmp';temporary.mkdir(parents=True,exist_ok=True)
    os.environ['TMPDIR']=str(temporary)
    import tempfile
    tempfile.tempdir=str(temporary)
    if not args.smoke_test:
        (root/'logs').mkdir(exist_ok=True)
        sys.stdout=(root/'logs/desktop.log').open('a',buffering=1)
        sys.stderr=sys.stdout
    lock=(root/'.desktop.lock').open('a')
    try:fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        current=json.loads((root/'data/desktop-session.json').read_text())
        if not args.no_browser:subprocess.run(['/usr/bin/open',f'http://127.0.0.1:{current["port"]}/demo/'])
        return 0
    # Writable build/cache directory stays with user data, not inside signed application.
    runtime=root/'runtime/remotion-0.1.0'
    if not runtime.exists():
        if not args.no_browser:subprocess.run(['/usr/bin/osascript','-e','display notification "首次启动正在准备本地视频运行依赖，请勿拔出硬盘。完成后将打开工作台。" with title "映序工作台"'])
        if shutil.disk_usage(root).free < 2*1024**3:raise RuntimeError('首次运行需要至少 2 GB 可用空间，请选择空间充足的工作区')
        runtime.parent.mkdir(parents=True,exist_ok=True)
        stage=runtime.with_name(runtime.name+'.partial')
        if stage.exists():shutil.rmtree(stage)
        stage.mkdir()
        for item in (resources/'remotion-app').iterdir():
            if item.name=='node_modules':continue
            if item.is_dir():shutil.copytree(item,stage/item.name)
            else:shutil.copyfile(item,stage/item.name)
        (stage/'node_modules').symlink_to(resources/'remotion-app/node_modules',target_is_directory=True)
        stage.rename(runtime)
    dependency=runtime/'node_modules'
    if dependency.is_symlink():
        dependency.unlink();dependency.symlink_to(resources/'remotion-app/node_modules',target_is_directory=True)
    keys=resources/'license/public-keys.json'
    if keys.is_file() and not (root/'license/public-keys.json').exists():
        (root/'license').mkdir(exist_ok=True);shutil.copyfile(keys,root/'license/public-keys.json')
    (root/'config').mkdir(exist_ok=True)
    template_path=root/'config/video_templates.json'
    if not template_path.exists():shutil.copyfile(resources/'config/video_templates.json',template_path)
    os.environ['CONTENT_AGENT_TEMPLATE_PATH']=str(template_path)
    import app
    from content_workbench.api.v2 import V2Application
    app.REMOTION_APP=runtime;app.REMOTION_PUBLIC=runtime/'public'
    app.init_db();app.V2=V2Application(app.DB_PATH,app.ROOT,app.create_task,{'video.produce':app.produce_video_task,'video.preview':app.produce_visual_preview})
    # Delivery stops at platform prefill. Final platform publish remains a human action.
    app.V2.publishing_execution_enabled=False
    app.V2.worker.allowed_kinds=[key for key in app.V2.worker.executors if key!='publish.execute']
    try:server=app.ThreadingHTTPServer(('127.0.0.1',args.port),app.Handler)
    except OSError:server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
    args.port=server.server_port
    os.environ['CONTENT_AGENT_MEDIA_BASE_URL']=f'http://127.0.0.1:{args.port}'
    (root/'data/desktop-session.json').write_text(json.dumps({'port':args.port}))
    if args.smoke_test:
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        import http.cookiejar
        opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        with opener.open(f'http://127.0.0.1:{server.server_port}/demo/') as response:assert response.status==200
        with opener.open(f'http://127.0.0.1:{server.server_port}/api/v2/license') as response:
            license_state=json.load(response);assert license_state['mode']=='required' and license_state['configured']
        with opener.open(f'http://127.0.0.1:{server.server_port}/yingxu-original/assets/scene-0.jpg') as response:
            assert response.headers['Content-Type'].startswith('image/')
        for binary in ('node','ffmpeg','ffprobe','openssl'):
            result=subprocess.run([str(resources/'bin'/binary),'-version' if binary.startswith('ff') else '--version' if binary=='node' else 'version'],capture_output=True)
            if result.returncode:raise RuntimeError(binary+' runtime failed')
        print(json.dumps({'status':'ok','root':str(root),'port':server.server_port,'license':app.V2.license.status()['status']}))
        server.shutdown();server.server_close();return 0
    app.V2.worker.before_execute=app.V2.license.require_active
    app.V2.worker.start()
    if not args.no_browser:subprocess.run(['/usr/bin/open',f'http://127.0.0.1:{args.port}/demo/'])
    try:server.serve_forever()
    finally:app.V2.worker.stop();server.server_close();lock.close()
    return 0

if __name__=='__main__':
    # Existing subprocess workers can use the bundled runtime like Python.
    if len(sys.argv)>2 and sys.argv[1]=='-c':
        exec(sys.argv[2],{'__name__':'__main__'});raise SystemExit(0)
    if len(sys.argv)>2 and sys.argv[1]=='-m':
        module=sys.argv[2];sys.argv=sys.argv[2:];runpy.run_module(module,run_name='__main__');raise SystemExit(0)
    if len(sys.argv)>1 and sys.argv[1].endswith('.py'):
        script=Path(sys.argv[1]).resolve();resources=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1])).resolve()
        if resources not in script.parents:raise SystemExit('只运行随应用分发的工作脚本')
        sys.argv=sys.argv[1:];runpy.run_path(str(script),run_name='__main__');raise SystemExit(0)
    try:raise SystemExit(main())
    except Exception as error:
        print(str(error),file=sys.stderr)
        if '--no-browser' not in sys.argv:subprocess.run(['/usr/bin/osascript','-e','on run argv\ndisplay alert "映序启动失败" message (item 1 of argv)\nend run',str(error)])
        raise
