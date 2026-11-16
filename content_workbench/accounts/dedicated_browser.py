"""Manage Yingxu's persistent Chrome without touching the user's everyday browser."""

import json
import os
import platform
import shutil
import subprocess
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

from content_workbench.accounts.setup import chrome_candidates
from content_workbench.domain.errors import DomainError
from content_workbench.storage.db import PROJECT_ROOT, ROOT

HOST = "127.0.0.1"
DEFAULT_PORT = 9223
PROFILE_DIRECTORY = Path("data/yingxu-chrome-profile")
_launch_lock = threading.Lock()


def port() -> int:
    value = int(os.environ.get("YINGXU_CHROME_DEBUG_PORT", str(DEFAULT_PORT)))
    if not 1024 <= value <= 65535:
        raise DomainError(
            "BROWSER_PORT_INVALID", "映序浏览器端口必须在 1024～65535 之间", 422
        )
    return value


def endpoint() -> str:
    return "http://{}:{}".format(HOST, port())


def profile_path() -> Path:
    return (ROOT / PROFILE_DIRECTORY).resolve()


def chrome_path() -> Optional[Path]:
    installed = next((path for path in chrome_candidates() if path.is_file()), None)
    discovered = installed or shutil.which("google-chrome") or shutil.which("chrome")
    return Path(discovered).resolve() if discovered else None


def _version() -> dict:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(endpoint() + "/json/version", timeout=2) as response:
        result = json.loads(response.read(65536))
    if not str(result.get("Browser", "")).startswith("Chrome/"):
        raise DomainError("BROWSER_NOT_CHROME", "本机调试端口上的程序不是 Chrome", 409)
    return result


def _listener_processes() -> list[tuple[int, str]]:
    system = platform.system()
    if system == "Darwin":
        result = subprocess.run(
            [
                "/usr/sbin/lsof",
                "-nP",
                "-iTCP:{}".format(port()),
                "-sTCP:LISTEN",
                "-Fpn",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode not in (0, 1):
            raise DomainError("BROWSER_STATUS_FAILED", "无法检查映序浏览器端口", 503)
        pids = []
        for line in result.stdout.splitlines():
            if line.startswith("n") and line[1:] != "{}:{}".format(HOST, port()):
                raise DomainError(
                    "BROWSER_ADDRESS_UNSAFE",
                    "映序浏览器调试端口不能只监听本机以外的地址",
                    409,
                )
            if line.startswith("p"):
                pids.append(int(line[1:]))
        return [
            (
                pid,
                subprocess.run(
                    ["/bin/ps", "-p", str(pid), "-o", "command="],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=5,
                ).stdout.strip(),
            )
            for pid in pids
        ]
    if system == "Windows":
        command = (
            "Get-NetTCPConnection -State Listen -LocalPort {0} | "
            'ForEach-Object {{ $p=Get-CimInstance Win32_Process -Filter "ProcessId=$($_.OwningProcess)"; '
            "Write-Output ($_.LocalAddress + '|' + $_.OwningProcess + '|' + $p.CommandLine) }}"
        ).format(port())
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if result.returncode:
            return []
        processes = []
        for line in result.stdout.splitlines():
            address, pid, command_line = line.split("|", 2)
            if address not in (HOST, "::1"):
                raise DomainError(
                    "BROWSER_ADDRESS_UNSAFE", "映序浏览器调试端口只能监听本机", 409
                )
            processes.append((int(pid), command_line))
        return processes
    return []


def _managed_process() -> Optional[tuple[int, str]]:
    processes = _listener_processes()
    if not processes:
        return None
    profile = str(profile_path())
    for pid, command in processes:
        if "--user-data-dir=" + profile in command and (
            "Google Chrome" in command or "chrome.exe" in command.lower()
        ):
            return pid, command
    raise DomainError(
        "BROWSER_PORT_OCCUPIED",
        "端口 {} 已被其他程序或其他 Chrome 占用；映序没有关闭或连接它".format(port()),
        409,
        "browser",
        "关闭占用该端口的专用测试浏览器，或关闭它后在接入向导重试；日常 Chrome 不受影响",
    )


def status() -> dict:
    installed = chrome_path() is not None
    result = {
        "chrome_installed": installed,
        "service_installed": installed,
        "running": False,
        "persistent_profile": True,
        "transport": "dedicated_chrome_cdp",
        "address": HOST,
        "port": port(),
        "reason": "Chrome 尚未安装"
        if not installed
        else "映序专用 Chrome 未运行；点击启动后会保留窗口和登录状态",
    }
    try:
        process = _managed_process()
        if process:
            version = _version()
            result.update(
                running=True,
                browser_version=version["Browser"],
                reason="映序专用 Chrome 已连接；重复打开平台会复用当前窗口和登录状态",
            )
    except DomainError as error:
        result.update(
            occupied=error.code == "BROWSER_PORT_OCCUPIED", reason=error.message
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        result["reason"] = "浏览器状态暂时无法读取，请点击重新检测"
    return result


def ensure_started() -> str:
    if not chrome_path():
        raise DomainError(
            "BROWSER_CHROME_MISSING",
            "尚未安装 Google Chrome",
            422,
            "browser",
            "安装 Chrome 后回到接入向导重新检测",
        )
    with _launch_lock:
        if _managed_process():
            _version()
            return endpoint()
        profile = profile_path()
        profile.mkdir(parents=True, exist_ok=True)
        try:
            profile.chmod(0o700)
        except OSError:
            pass
        log_path = profile.parent / "chrome.log"
        with log_path.open("ab") as log:
            process = subprocess.Popen(
                [
                    str(chrome_path()),
                    "--user-data-dir=" + str(profile),
                    "--remote-debugging-address=" + HOST,
                    "--remote-debugging-port=" + str(port()),
                    "--no-first-run",
                    "--no-default-browser-check",
                    "about:blank",
                ],
                stdout=log,
                stderr=log,
                start_new_session=platform.system() != "Windows",
            )
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise DomainError(
                    "BROWSER_START_FAILED",
                    "映序专用 Chrome 启动失败",
                    503,
                    "browser",
                    "查看工作区 data/chrome.log",
                )
            if _managed_process():
                _version()
                return endpoint()
            time.sleep(0.25)
        raise DomainError(
            "BROWSER_START_TIMEOUT",
            "映序专用 Chrome 尚未就绪",
            503,
            "browser",
            "在接入向导重新检测",
        )


def _close_via_cdp() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as error:
        candidates = [
            root / relative
            for root in (ROOT, PROJECT_ROOT)
            for relative in (
                Path(".venv-topics/bin/python"),
                Path(".venv-topics/Scripts/python.exe"),
            )
        ]
        python = next((path for path in candidates if path.is_file()), None)
        if not python:
            raise DomainError(
                "BROWSER_RUNTIME_MISSING",
                "缺少安全关闭 Chrome 所需的 Playwright",
                503,
                "browser",
                "先在接入向导完成浏览器运行环境安装",
            ) from error
        script = (
            "import sys;"
            "from playwright.sync_api import sync_playwright;"
            "p=sync_playwright().start();"
            "b=p.chromium.connect_over_cdp(sys.argv[1]);"
            "b.new_browser_cdp_session().send('Browser.close');"
            "p.stop()"
        )
        result = subprocess.run(
            [str(python), "-c", script, endpoint()],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
        if result.returncode:
            raise DomainError(
                "BROWSER_STOP_FAILED", "映序专用 Chrome 未能正常关闭", 503
            )
        return
    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(endpoint())
        browser.new_browser_cdp_session().send("Browser.close")


def stop() -> dict:
    process = _managed_process()
    if process:
        _version()
        _close_via_cdp()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if not _managed_process():
                break
            time.sleep(0.25)
        else:
            raise DomainError("BROWSER_STOP_TIMEOUT", "映序专用 Chrome 尚未关闭", 503)
    return {"stopped": bool(process), **status()}


def enabled() -> bool:
    return (
        os.environ.get("CONTENT_AGENT_DESKTOP") == "1"
        or os.environ.get("YINGXU_DEDICATED_CHROME") == "1"
    )
