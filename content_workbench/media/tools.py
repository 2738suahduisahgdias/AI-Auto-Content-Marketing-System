#!/usr/bin/env python3
"""Customer-owned local dependency paths; never assume a developer checkout."""

import json
import os
from pathlib import Path

from content_workbench.domain.errors import DomainError
from content_workbench.storage.db import PROJECT_ROOT

KEYS = {
    "whisper_python",
    "openvoice_python",
    "openvoice_root",
    "ocr_python",
    "demucs_python",
}


def bundled_python() -> Path:
    return PROJECT_ROOT / "python/bin/python3.9"


def openvoice_root(root: Path) -> Path:
    configured = config(root).get("openvoice_root")
    if configured:
        return Path(configured).absolute()
    if os.environ.get("CONTENT_AGENT_SLIM") == "1":
        return Path(root) / "tools/OpenVoice"
    if os.environ.get("CONTENT_AGENT_DESKTOP") == "1":
        return PROJECT_ROOT / "OpenVoice"
    return Path(root) / "tools/OpenVoice"


def local_python(
    root: Path, key: str, development_name: str, workspace_name: str
) -> Path:
    configured = config(root).get(key)
    if configured:
        return Path(configured).absolute()
    if os.environ.get("CONTENT_AGENT_SLIM") == "1":
        return Path(root) / "tools/python/bin/python3"
    if os.environ.get("CONTENT_AGENT_DESKTOP") == "1":
        return bundled_python()
    development = Path(root) / development_name / "bin/python"
    if development.is_file():
        return development
    project = PROJECT_ROOT / development_name / "bin/python"
    if project.is_file():
        return project
    return Path(root) / "tools" / workspace_name / "bin/python"


def ocr_python(root: Path) -> Path:
    return local_python(root, "ocr_python", ".venv-topics", "topics")


def demucs_python(root: Path) -> Path:
    return local_python(root, "demucs_python", ".venv-demucs", "demucs")


def config(root: Path) -> dict:
    path = Path(root) / "config/media-tools.json"
    return json.loads(path.read_text()) if path.is_file() else {}


def save(root: Path, values: dict) -> dict:
    updated = config(root)
    for key, value in values.items():
        if key not in KEYS:
            continue
        if not isinstance(value, str):
            raise DomainError("MEDIA_TOOLS_INVALID", "路径格式无效", 422)
        if not value.strip():
            updated.pop(key, None)
            continue
        path = Path(value).expanduser().absolute()
        if not key.endswith("python"):
            path = path.resolve()
        if key.endswith("python") and (
            not path.is_file() or not os.access(path, os.X_OK)
        ):
            raise DomainError("MEDIA_TOOLS_INVALID", "请选择可执行的 Python 文件", 422)
        if key.endswith("root") and not path.is_dir():
            raise DomainError("MEDIA_TOOLS_INVALID", "请选择 OpenVoice 模型目录", 422)
        updated[key] = str(path)
    path = Path(root) / "config/media-tools.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(updated, ensure_ascii=False))
    os.replace(temporary, path)
    return updated
