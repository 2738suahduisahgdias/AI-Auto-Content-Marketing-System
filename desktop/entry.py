#!/usr/bin/env python3
"""Mac entry point for the existing workbench, not a replacement application."""

import argparse
import fcntl
import json
import os
import runpy
import shlex
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path


def configure_readonly_runtime() -> None:
    sys.dont_write_bytecode = True
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"


def refresh_renderer_code(resources, runtime):
    """Refresh shipped code on upgrade without touching media, caches or templates."""
    source = resources / "remotion-app"
    for name in ("src", "scripts"):
        directory = source / name
        if not directory.is_dir():
            continue
        for item in directory.rglob("*"):
            if not item.is_file():
                continue
            target = runtime / name / item.relative_to(directory)
            target.parent.mkdir(parents=True, exist_ok=True)
            content = item.read_bytes()
            if target.is_file() and target.read_bytes() == content:
                continue
            temporary = target.with_name(target.name + ".upgrade-tmp")
            temporary.write_bytes(content)
            temporary.replace(target)
    for name in (
        "package.json",
        "package-lock.json",
        "remotion.config.ts",
        "tsconfig.json",
    ):
        item = source / name
        if item.is_file():
            target = runtime / name
            temporary = target.with_name(target.name + ".upgrade-tmp")
            temporary.write_bytes(item.read_bytes())
            temporary.replace(target)


def prepare_shared_cache(resources: Path, root: Path) -> None:
    for name in ("huggingface", "torch", "nltk", "home"):
        source = resources / "models" / name
        if not source.is_dir():
            continue
        destination = root / "cache" / name
        destination.mkdir(parents=True, exist_ok=True)
        for item in source.rglob("*"):
            target = destination / item.relative_to(source)
            if target.exists() or target.is_symlink():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if item.is_symlink():
                target.symlink_to(os.readlink(item), target_is_directory=item.is_dir())
            elif item.is_dir():
                target.mkdir(exist_ok=True)
            elif item.is_file():
                temporary = target.with_name(target.name + ".upgrade-tmp")
                shutil.copy2(item, temporary)
                temporary.replace(target)
    browsers = (
        root / "tools/playwright-browsers"
        if os.environ.get("CONTENT_AGENT_SLIM") == "1"
        else resources / "playwright-browsers"
    )
    os.environ.update(
        CONTENT_AGENT_DESKTOP="1",
        PLAYWRIGHT_BROWSERS_PATH=str(browsers),
        HOME=str(root / "cache/home"),
        HF_HOME=str(root / "cache/huggingface"),
        TRANSFORMERS_CACHE=str(root / "cache/huggingface"),
        TORCH_HOME=str(root / "cache/torch"),
        XDG_CACHE_HOME=str(root / "cache/xdg"),
        NLTK_DATA=str(root / "cache/nltk"),
        HF_HUB_DISABLE_TELEMETRY="1",
    )
    torch_link = root / "cache/home/.cache/torch"
    if not torch_link.exists() and not torch_link.is_symlink():
        torch_link.parent.mkdir(parents=True, exist_ok=True)
        torch_link.symlink_to(Path("../../torch"), target_is_directory=True)


def prepare_slim_workspace(resources: Path, root: Path) -> None:
    if not (resources / "slim-build.json").is_file():
        return
    os.environ["CONTENT_AGENT_SLIM"] = "1"
    for directory in (
        root / "cache/huggingface/hub",
        root / "cache/torch",
        root / "cache/nltk",
        root / "tools/playwright-browsers",
        root / "logs",
    ):
        directory.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        resources / "OpenVoice",
        root / "tools/OpenVoice",
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("checkpoints_v2", "__pycache__", "*.pyc"),
    )


def runtime_binary_directories(resources: Path, root: Path, slim: bool) -> list[Path]:
    if slim:
        return [resources / "bin", root / "tools/node/bin", root / "tools/bin"]
    return [resources / "bin"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root")
    parser.add_argument("--port", type=int, default=8848)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()
    resources = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    pointer = Path.home() / "Library/Application Support/Yingxu/workspace.json"
    root = args.root or os.environ.get("CONTENT_AGENT_ROOT")
    if not root and pointer.is_file():
        previous = json.loads(pointer.read_text())["root"]
        root = previous
    if not root:
        choice = subprocess.run(
            [
                "/usr/bin/osascript",
                "-e",
                'POSIX path of (choose folder with prompt "选择新的空工作区文件夹，或已有恢复目录（建议外置硬盘）")',
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if choice.returncode:
            return 0
        root = str(Path(choice.stdout.strip()))
        pointer.parent.mkdir(parents=True, exist_ok=True)
        pointer.write_text(json.dumps({"root": root}))
    root = Path(root).expanduser().resolve()
    if (
        str(root).startswith("/Volumes/")
        and not Path("/Volumes", root.parts[2]).is_mount()
    ):
        raise RuntimeError("外置硬盘未连接，请连接后重启；不会在系统盘创建替代工作区")
    root.mkdir(parents=True, exist_ok=True)
    user_home = Path.home()
    prepare_slim_workspace(resources, root)
    prepare_shared_cache(resources, root)
    os.environ.setdefault("KIMI_CODE_HOME", str(user_home / ".kimi-code"))
    os.environ.setdefault("CODEX_HOME", str(user_home / ".codex"))
    os.environ.setdefault("YINGXU_KIMI_CLI", str(resources / "bin/kimi"))
    os.environ.update(
        CONTENT_AGENT_ROOT=str(root),
        CONTENT_AGENT_DB=str(root / "data/content-agent.db"),
        CONTENT_AGENT_LICENSE_MODE="required",
        CONTENT_AGENT_MEDIA_BASE_URL=f"http://127.0.0.1:{args.port}",
    )
    slim = (resources / "slim-build.json").is_file()
    if slim:
        os.environ["PYTHONPATH"] = str(root / "tools/python-packages")
    runtime_binaries = runtime_binary_directories(resources, root, slim)
    os.environ["PATH"] = os.pathsep.join(
        [
            *(str(path) for path in runtime_binaries),
            str(user_home / ".local/bin"),
            str(user_home / ".kimi-code/bin"),
            "/opt/homebrew/bin",
            "/usr/local/bin",
            os.environ.get("PATH", "/usr/bin:/bin"),
        ]
    )
    temporary = root / "cache/tmp"
    temporary.mkdir(parents=True, exist_ok=True)
    os.environ["TMPDIR"] = str(temporary)
    import tempfile

    tempfile.tempdir = str(temporary)
    if not args.smoke_test:
        (root / "logs").mkdir(exist_ok=True)
        sys.stdout = (root / "logs/desktop.log").open("a", buffering=1)
        sys.stderr = sys.stdout
    lock = (root / ".desktop.lock").open("a")
    try:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        # First launch can still be preparing dependencies. Do not use a stale session.
        from desktop.browser import open_workbench

        for attempt in range(120):
            try:
                current = json.loads((root / "data/desktop-session.json").read_text())
                os.kill(int(current["pid"]), 0)
                with urllib.request.urlopen(
                    "http://127.0.0.1:{}/demo/".format(int(current["port"])), timeout=1
                ) as response:
                    if response.status != 200:
                        raise ValueError("not ready")
                if not args.no_browser:
                    open_workbench(current["port"])
                return 0
            except (OSError, ValueError, KeyError):
                time.sleep(0.5)
        raise RuntimeError("工作台仍在启动或服务无响应，请稍后再试；未新开网页")
    # Only the local inbox credential and sender allowlist are loaded, never shell code.
    inbox_env = root / "config/wechat-inbox.env"
    if inbox_env.is_file():
        for line in inbox_env.read_text().splitlines():
            key, sep, value = line.partition("=")
            if sep and key in (
                "CONTENT_AGENT_WECHAT_TOKEN",
                "CONTENT_AGENT_WECHAT_SENDER_ID",
            ):
                parts = shlex.split(value)
                os.environ[key] = parts[0] if parts else ""
    # Writable build/cache directory stays with user data, not inside signed application.
    runtime = root / "runtime/remotion-0.1.1"
    if not runtime.exists():
        if not args.no_browser:
            subprocess.run(
                [
                    "/usr/bin/osascript",
                    "-e",
                    'display notification "首次启动正在准备本地视频运行依赖，请勿拔出硬盘。完成后将打开工作台。" with title "映序工作台"',
                ],
                check=False,
            )
        required_space = 12 if slim else 4
        if shutil.disk_usage(root).free < required_space * 1024**3:
            raise RuntimeError(
                f"首次运行需要至少 {required_space} GB 可用空间，请选择空间充足的工作区"
            )
        runtime.parent.mkdir(parents=True, exist_ok=True)
        stage = runtime.with_name(runtime.name + ".partial")
        if stage.exists():
            shutil.rmtree(stage)
        stage.mkdir()
        for item in (resources / "remotion-app").iterdir():
            if item.name == "node_modules":
                continue
            if item.is_dir():
                shutil.copytree(item, stage / item.name)
            else:
                shutil.copyfile(item, stage / item.name)
        if not slim:
            (stage / "node_modules").symlink_to(
                resources / "remotion-app/node_modules", target_is_directory=True
            )
        stage.rename(runtime)
    refresh_renderer_code(resources, runtime)
    dependency = runtime / "node_modules"
    if not slim and dependency.is_symlink():
        dependency.unlink()
        dependency.symlink_to(
            resources / "remotion-app/node_modules", target_is_directory=True
        )
    keys = resources / "license/public-keys.json"
    if keys.is_file() and not (root / "license/public-keys.json").exists():
        (root / "license").mkdir(exist_ok=True)
        shutil.copyfile(keys, root / "license/public-keys.json")
    (root / "config").mkdir(exist_ok=True)
    template_path = root / "config/video_templates.json"
    if not template_path.exists():
        shutil.copyfile(resources / "config/video_templates.json", template_path)
    os.environ["CONTENT_AGENT_TEMPLATE_PATH"] = str(template_path)
    import app
    from content_workbench.api.v2 import V2Application

    app.REMOTION_APP = runtime
    app.REMOTION_PUBLIC = runtime / "public"
    app.init_db()
    app.V2 = V2Application(
        app.DB_PATH,
        app.ROOT,
        app.create_task,
        {
            "video.produce": app.produce_video_task,
            "video.preview": app.produce_visual_preview,
        },
    )
    # Delivery stops at platform prefill. Final platform publish remains a human action.
    app.V2.publishing_execution_enabled = False
    app.V2.worker.allowed_kinds = [
        key for key in app.V2.worker.executors if key != "publish.execute"
    ]
    try:
        server = app.ThreadingHTTPServer(("127.0.0.1", args.port), app.Handler)
    except OSError:
        server = app.ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    next_workspace = []

    def select_workspace(destination):
        from content_workbench.domain.errors import DomainError
        from content_workbench.storage.activity import ACTIVITY
        from content_workbench.storage.db import connect, immediate
        from content_workbench.storage.workspace_selection import (
            select_workspace as select,
        )

        def prepare():
            with connect(app.DB_PATH) as conn, immediate(conn):
                if conn.execute(
                    "SELECT 1 FROM wb_jobs WHERE status IN ('queued','leased','running','retry_wait','cancel_requested') LIMIT 1"
                ).fetchone():
                    raise DomainError(
                        "WORKSPACE_BUSY",
                        "仍有后台任务进行中，请等待完成或取消后再切换",
                        409,
                    )
                return select(root, destination, pointer)

        try:
            result = ACTIVITY.switch(prepare)
        except DomainError as error:
            raise app.ApiError(error.status, error.message)
        next_workspace.append(result["path"])
        threading.Timer(1, server.shutdown).start()
        return result

    app.DESKTOP_SELECT_WORKSPACE = select_workspace
    args.port = server.server_port
    os.environ["CONTENT_AGENT_MEDIA_BASE_URL"] = f"http://127.0.0.1:{args.port}"
    (root / "data/desktop-session.json").write_text(
        json.dumps({"port": args.port, "pid": os.getpid()})
    )
    if args.smoke_test:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        import http.cookiejar

        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )
        with opener.open(f"http://127.0.0.1:{server.server_port}/demo/") as response:
            assert response.status == 200
        with opener.open(
            f"http://127.0.0.1:{server.server_port}/api/v2/license"
        ) as response:
            license_state = json.load(response)
            assert license_state["mode"] == "required" and license_state["configured"]
        with opener.open(
            f"http://127.0.0.1:{server.server_port}/yingxu-original/assets/scene-0.jpg"
        ) as response:
            assert response.headers["Content-Type"].startswith("image/")
        slim = (resources / "slim-build.json").is_file()
        openssl = shutil.which("openssl")
        if (
            openssl is None
            or Path(openssl).resolve() != (resources / "bin/openssl").resolve()
        ):
            raise RuntimeError(
                "客户端没有优先使用随包 OpenSSL，当前解析为：" + str(openssl)
            )
        slim_status = None
        if slim:
            with opener.open(
                f"http://127.0.0.1:{server.server_port}/api/slim-dependencies"
            ) as response:
                slim_status = json.load(response)
            assert slim_status["slim"] and slim_status["edition"] == "精简版"
        required = [root / "cache/huggingface/hub", root / "cache/torch"]
        if slim:
            required += [
                resources / "slim_download.py",
                resources / "slim-requirements.txt",
                resources / "bin/openssl",
                root / "tools/playwright-browsers",
            ]
        else:
            required += [
                resources / "python/bin/python3.9",
                resources / "OpenVoice/checkpoints_v2/converter/checkpoint.pth",
                resources / "playwright-browsers",
            ]
        missing = [str(path) for path in required if not path.exists()]
        if missing:
            raise RuntimeError("客户端本地运行资源不完整：" + ", ".join(missing))
        binaries = {
            "node": resources / "bin/node",
            "ffmpeg": resources / "bin/ffmpeg",
            "ffprobe": resources / "bin/ffprobe",
            "openssl": resources / "bin/openssl",
        }
        if slim:
            binaries.update(
                node=root / "tools/node/bin/node",
                ffmpeg=root / "tools/bin/ffmpeg",
                ffprobe=root / "tools/bin/ffprobe",
            )
        if not slim or slim_status["complete"]:
            for name, path in binaries.items():
                result = subprocess.run(
                    [
                        str(path),
                        "-version"
                        if name.startswith("ff")
                        else "--version"
                        if name == "node"
                        else "version",
                    ],
                    check=False,
                    capture_output=True,
                )
                if result.returncode:
                    raise RuntimeError(name + " runtime failed")
            media_python = (
                root / "tools/python/bin/python3"
                if slim
                else resources / "python/bin/python3.9"
            )
            subprocess.run(
                [
                    str(media_python),
                    "-c",
                    "import torch,faster_whisper,rapidocr_onnxruntime,demucs,melo.api,av",
                ],
                check=True,
                env={**os.environ, "HF_HUB_OFFLINE": "1"},
                timeout=600,
            )
        if not slim or slim_status["complete"]:
            subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch(headless=True); b.close(); p.stop()",
                ],
                check=True,
                timeout=300,
            )
        with opener.open(
            f"http://127.0.0.1:{server.server_port}/api/agents/config"
        ) as response:
            agents = json.load(response)["agents"]
        for agent_id in (
            "article_image_agent",
            "music_composer_agent",
            "visual_analysis_agent",
            "audio_separation_agent",
            "remotion_director_agent",
            "remotion_code_agent",
            "social_data_agent",
        ):
            if agent_id not in agents:
                raise RuntimeError("客户端缺少 Agent：" + agent_id)
        print(
            json.dumps(
                {
                    "status": "ok",
                    "root": str(root),
                    "port": server.server_port,
                    "license": app.V2.license.status()["status"],
                    "local_media": True if not slim else slim_status["complete"],
                    "browser": True if not slim else slim_status["complete"],
                    "agents": len(agents),
                    "edition": "精简版" if slim else "全量离线版",
                }
            )
        )
        server.shutdown()
        server.server_close()
        return 0
    app.V2.worker.before_execute = app.V2.license.require_active
    app.V2.topic_api.wechat_client.start()
    app.V2.worker.start()
    app.V2.topic_scheduler.start()
    if not args.no_browser:
        from desktop.browser import open_workbench

        try:
            open_workbench(args.port)
        except (RuntimeError, subprocess.TimeoutExpired) as error:
            print(str(error), file=sys.stderr)
            subprocess.run(
                [
                    "/usr/bin/osascript",
                    "-e",
                    'on run argv\ndisplay alert "工作台已启动" message (item 1 of argv)\nend run',
                    str(error),
                ],
                check=False,
            )
    try:
        server.serve_forever()
    finally:
        app.V2.stop()
        app.stop_whisper_servers()
        server.server_close()
        lock.close()
    if next_workspace:
        if getattr(sys, "frozen", False):
            command = [
                sys.executable,
                "--root",
                next_workspace[-1],
                "--port",
                str(args.port),
            ]
        else:
            bootstrap = (
                "import sys; sys._MEIPASS="
                + repr(str(resources))
                + "; from desktop.entry import main; raise SystemExit(main())"
            )
            command = [
                sys.executable,
                "-c",
                bootstrap,
                "--root",
                next_workspace[-1],
                "--port",
                str(args.port),
            ]
        os.execv(sys.executable, command)
    return 0


if __name__ == "__main__":
    configure_readonly_runtime()
    # Existing subprocess workers can use the bundled runtime like Python.
    if len(sys.argv) > 2 and sys.argv[1] == "-c":
        exec(sys.argv[2], {"__name__": "__main__"})  # noqa: S102
        raise SystemExit(0)
    if len(sys.argv) > 2 and sys.argv[1] == "-m":
        module = sys.argv[2]
        sys.argv = sys.argv[2:]
        runpy.run_module(module, run_name="__main__")
        raise SystemExit(0)
    if len(sys.argv) > 1 and sys.argv[1].endswith(".py"):
        script = Path(sys.argv[1]).resolve()
        resources = Path(
            getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1])
        ).resolve()
        if resources not in script.parents:
            raise SystemExit("只运行随应用分发的工作脚本")
        sys.argv = sys.argv[1:]
        runpy.run_path(str(script), run_name="__main__")
        raise SystemExit(0)
    try:
        raise SystemExit(main())
    except Exception as error:
        print(str(error), file=sys.stderr)
        if "--no-browser" not in sys.argv:
            subprocess.run(
                [
                    "/usr/bin/osascript",
                    "-e",
                    'on run argv\ndisplay alert "映序启动失败" message (item 1 of argv)\nend run',
                    str(error),
                ],
                check=False,
            )
        raise
