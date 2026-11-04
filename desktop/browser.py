"""Focus an existing Chrome workbench tab; create only when none exists."""
import fcntl
import subprocess
from pathlib import Path

SCRIPT = r'''on run argv
set targetURL to item 1 of argv
set originURL to item 2 of argv
with timeout of 8 seconds
tell application id "com.google.Chrome"
    repeat with w in windows
        set tabURLs to URL of every tab of w
        repeat with i from 1 to count tabURLs
            set tabURL to item i of tabURLs
            if (tabURL starts with (originURL & "demo")) or (tabURL is originURL) then
                set active tab index of w to i
                set index of w to 1
                activate
                return "reused"
            end if
        end repeat
    end repeat
    if (count windows) is 0 then make new window
    set URL of (make new tab at end of tabs of front window) to targetURL
    activate
    return "opened"
end tell
end timeout
end run'''

def open_workbench(port):
    port = int(port)
    if not 1 <= port <= 65535:
        raise ValueError("无效的工作台端口")
    origin = "http://127.0.0.1:{}/".format(port)
    lock_path = Path.home() / "Library/Application Support/Yingxu/browser-open.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return "opening"
        try:
            result = subprocess.run(
                ["/usr/bin/osascript", "-e", SCRIPT, origin + "demo/", origin],
                capture_output=True, text=True, timeout=10,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("Chrome 暂未响应。请确认 Chrome 没有待处理弹窗，再点击映序重试。工作台地址：" + origin + "demo/") from None
        if result.returncode:
            subprocess.run(["/usr/bin/open", "-a", "Google Chrome"], capture_output=True, timeout=5)
            if "-1743" in str(result.stderr):
                message = "请在系统设置 → 隐私与安全性 → 自动化中允许映序控制 Chrome。"
            else:
                message = "Chrome 暂未响应，请处理 Chrome 弹窗后重试。"
            raise RuntimeError(message + "工作台地址：" + origin + "demo/")
        return result.stdout.strip()

if __name__ == "__main__":
    import json
    import time
    import urllib.request

    pointer = Path.home() / "Library/Application Support/Yingxu/workspace.json"
    root = Path(json.loads(pointer.read_text())["root"])
    for attempt in range(120):
        try:
            session = json.loads((root / "data/desktop-session.json").read_text())
            port = int(session["port"])
            with urllib.request.urlopen("http://127.0.0.1:{}/demo/".format(port), timeout=1) as response:
                if response.status != 200:
                    raise OSError("工作台尚未就绪")
            print(open_workbench(port), flush=True)
            break
        except (OSError, ValueError, KeyError):
            if attempt == 119:
                raise RuntimeError("映序服务尚未就绪，请稍后重试")
            time.sleep(0.5)
