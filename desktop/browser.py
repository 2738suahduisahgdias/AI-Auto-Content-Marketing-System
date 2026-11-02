"""Focus an existing Chrome workbench tab; create only when none exists."""
import subprocess

SCRIPT = r'''on run argv
set targetURL to item 1 of argv
set originURL to item 2 of argv
tell application "Google Chrome"
    repeat with w in windows
        set i to 0
        repeat with t in tabs of w
            set i to i + 1
            if (URL of t starts with (originURL & "demo")) or (URL of t is originURL) then
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
end run'''

def open_workbench(port):
    port = int(port)
    if not 1 <= port <= 65535:
        raise ValueError("无效的工作台端口")
    origin = "http://127.0.0.1:{}/".format(port)
    result = subprocess.run(["/usr/bin/osascript", "-e", SCRIPT, origin+"demo/", origin], capture_output=True, text=True, timeout=30)
    if result.returncode:
        # Never create another tab when automation permission is denied.
        subprocess.run(["/usr/bin/open", "-a", "Google Chrome"], capture_output=True)
        raise RuntimeError("无法定位 Chrome 工作台窗口。请在系统设置 → 隐私与安全性 → 自动化中允许映序控制 Chrome，然后重新点击 App；也可手动打开 " + origin + "demo/")
    return result.stdout.strip()
