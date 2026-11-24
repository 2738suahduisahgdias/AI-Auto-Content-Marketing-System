"""Start the isolated migration API and the original-workspace Vite preview."""
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from content_workbench.accounts.setup import playwright_python

APFS_PREVIEW = Path("/Volumes/EXTERNAL_USB/kimi/storage/YingxuPreviewWorkspace/migration-preview")


def preview_root(repo: Path, environ: Mapping[str, str], apfs_preview: Path = APFS_PREVIEW) -> Path:
    configured = environ.get("YINGXU_PREVIEW_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    if (apfs_preview / "data/content-agent.db").is_file():
        return apfs_preview.resolve()
    return (repo.parents[1] / "runtime/migration-preview").resolve()


def preview_python(repo: Path) -> str:
    binary = playwright_python(repo)
    if binary is None:
        raise SystemExit("预览登录需要 Playwright 隔离环境，请先运行项目安装脚本")
    return str(binary)


def preview_environment(preview: Path, environ: Mapping[str, str]) -> dict[str, str]:
    database = preview / "data/content-agent.db"
    env = {
        **environ,
        "CONTENT_AGENT_ROOT": str(preview),
        "CONTENT_AGENT_DB": str(database),
        "CONTENT_AGENT_MEDIA_BASE_URL": "http://127.0.0.1:8876",
        "YINGXU_DEDICATED_CHROME": "1",
    }
    if (preview / "license/public-keys.json").is_file():
        env["CONTENT_AGENT_LICENSE_MODE"] = "required"
    return env


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    preview = preview_root(repo, os.environ)
    database = preview / "data/content-agent.db"
    if not database.is_file():
        raise SystemExit("找不到隔离演示数据库；请先准备副本。不会自动使用正式数据库。")

    def ready(url: str) -> bool:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                return response.status == 200
        except Exception:
            return False

    if not ready("http://127.0.0.1:8876/"):
        env = preview_environment(preview, os.environ)
        with (preview / "server.log").open("ab") as log:
            process = subprocess.Popen(
                [preview_python(repo), str(repo / "scripts/run-migration-preview.py")],
                cwd=repo,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
        (preview / "server.pid").write_text(str(process.pid))
        for _ in range(40):
            if ready("http://127.0.0.1:8876/"):
                break
            if process.poll() is not None:
                raise SystemExit("预览 API 启动失败，请查看隔离目录 server.log")
            time.sleep(0.25)
        else:
            raise SystemExit("预览 API 未就绪，请查看 server.log")
    subprocess.run(["python3", str(repo / "scripts/start-yingxu-preview.py")], cwd=repo, check=True)


if __name__ == "__main__":
    main()
