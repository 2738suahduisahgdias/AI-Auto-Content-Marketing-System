"""Local Chrome bridge lifecycle; never accepts shell commands from clients."""
import json
import subprocess
import threading
import urllib.request
from pathlib import Path
from content_workbench.domain.errors import DomainError

_lock = threading.Lock()

def binary():
    return Path.home() / ".kimi-webbridge/bin/kimi-webbridge"

def status():
    running = connected = False
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open("http://127.0.0.1:10086/status", timeout=2) as response:
            result = json.loads(response.read(65536))
            running = True
            connected = result.get("extension_connected") is True
    except Exception:
        pass
    chrome = any(p.exists() for p in (Path("/Applications/Google Chrome.app"), Path.home()/"Applications/Google Chrome.app"))
    reason = "Chrome、服务与扩展已连接；平台账号仍需分别登录" if connected else "服务已启动，请打开 Chrome，安装或启用扩展并确认权限" if running else "浏览器服务未启动，点击启动连接" if binary().is_file() else "尚未安装浏览器服务，请按官方安装说明完成安装后重新检测"
    return dict(chrome_installed=chrome, service_installed=binary().is_file(), running=running, extension_connected=connected, reason=reason)

def control(action, db_path=None):
    if action not in {"start", "stop", "restart"}:
        raise DomainError("BROWSER_ACTION_INVALID", "不支持的连接操作", 422)
    if not binary().is_file():
        raise DomainError("BROWSER_SERVICE_MISSING", "请先按官方说明安装浏览器服务", 422)
    if not _lock.acquire(blocking=False):
        raise DomainError("BROWSER_SERVICE_BUSY", "连接操作正在进行，请稍后重新检测", 409)
    from contextlib import nullcontext
    from content_workbench.storage.db import connect, immediate
    try:
        with (connect(db_path) if db_path else nullcontext()) as conn, (immediate(conn) if conn else nullcontext()):
            if conn and action in {"stop", "restart"}:
                busy = conn.execute("SELECT 1 FROM wb_jobs WHERE resource_key='browser' AND status IN ('queued','leased','running','retry_wait','cancel_requested') LIMIT 1").fetchone()
                if busy:
                    raise DomainError("BROWSER_TASK_ACTIVE", "浏览器任务尚未结束，请等待完成或在任务页取消后再重连", 409)
            return _run(action)
    finally:
        _lock.release()

def _run(action):
    try:
        result = subprocess.run([str(binary()), action], capture_output=True, timeout=20, check=False)
        if result.returncode:
            raise DomainError("BROWSER_SERVICE_FAILED", "浏览器服务操作失败，请重新安装服务后检测连接", 503)
        return status()
    except (OSError, subprocess.TimeoutExpired):
        raise DomainError("BROWSER_SERVICE_TIMEOUT", "服务未及时响应，请重新检测；仍失败时重新安装服务", 503)
