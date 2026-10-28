import os
import platform
import shutil
import sys
from pathlib import Path

from content_workbench.storage.db import PROJECT_ROOT, connect


def chrome_candidates():
    system = platform.system()
    if system == "Darwin":
        return [Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")]
    if system == "Windows":
        roots = [os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA")]
        return [Path(root) / "Google/Chrome/Application/chrome.exe" for root in roots if root]
    return []


def dependency(name, installed, required, action):
    return {"name": name, "installed": bool(installed), "required": required, "action": action}


def setup_status(db_path):
    root = PROJECT_ROOT
    system = platform.system()
    chrome = next((path for path in chrome_candidates() if path.is_file()), None)
    chrome = chrome or shutil.which("google-chrome") or shutil.which("chrome") or shutil.which("chromium")
    dependencies = [
        dependency("Python 3.9+", sys.version_info >= (3, 9), True, "安装 Python 3.9 或更高版本，并加入 PATH"),
        dependency("Node.js 与 npm", shutil.which("node") and shutil.which("npm"), True, "安装 Node.js 20 LTS 或兼容版本"),
        dependency("FFmpeg / FFprobe", shutil.which("ffmpeg") and shutil.which("ffprobe"), True, "安装 FFmpeg 并将 ffmpeg、ffprobe 加入 PATH"),
        dependency("Chrome", chrome, True, "安装 Google Chrome；采集和平台登录使用本机浏览器"),
        dependency("Playwright 隔离环境", (root / ".venv-topics/bin/python").is_file() or (root / ".venv-topics/Scripts/python.exe").is_file(), True, "运行项目提供的安装脚本"),
        dependency("Remotion 依赖", (root / "remotion-app/node_modules").is_dir(), False, "在 remotion-app 执行 npm ci；仅视频渲染需要"),
        dependency("前端生产构建", (root / "web/react-dist/index.html").is_file(), True, "在 webapp 执行 npm ci && npm run build"),
        dependency("Kimi CLI（可选）", shutil.which("kimi"), False, "需要 AI 生成时安装并登录 Kimi CLI，不复制凭据"),
    ]
    with connect(db_path, readonly=True) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        snapshots = set()
        published = set()
        if "account_daily_snapshots" in tables:
            snapshots = {row[0] for row in conn.execute("SELECT DISTINCT platform FROM account_daily_snapshots")}
        if "publish_targets" in tables:
            published = {row[0] for row in conn.execute("SELECT DISTINCT platform FROM publish_targets WHERE status='published'")}
    platforms = []
    for key, name in (("douyin", "抖音"), ("xiaohongshu", "小红书"), ("wechat_channels", "视频号"), ("wechat_official_account", "公众号")):
        status = "published" if key in published else "snapshot" if key in snapshots else "not_verified"
        platforms.append({"platform": key, "name": name, "status": status,
                          "verified": status != "not_verified",
                          "action": "已有真实发布证据" if status == "published" else "已有账号快照，可继续核验登录" if status == "snapshot" else "打开登录窗口，本人完成扫码后重新检查"})
    return {"os": system, "os_name": "macOS" if system == "Darwin" else "Windows" if system == "Windows" else system,
            "python_version": platform.python_version(), "local_url": "http://127.0.0.1:8765/",
            "dependencies": dependencies, "platforms": platforms,
            "first_run": not snapshots and not published,
            "core_ready": all(item["installed"] for item in dependencies if item["required"]),
            "boundary": "只检查本机环境与真实证据；打开登录窗口不代表已连接，不读取或返回账号凭据。"}
