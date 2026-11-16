#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

from content_workbench.storage.db import PROJECT_ROOT

_ITEMS = (
    {"id": "python", "label": "媒体 Python 与 AI 运行库", "estimate": "约 3.4 GB"},
    {"id": "system_tools", "label": "Node、FFmpeg 与 FFprobe", "estimate": "约 250 MB"},
    {"id": "remotion", "label": "Remotion 视频渲染依赖", "estimate": "约 550 MB"},
    {"id": "browser_main", "label": "工作台浏览器", "estimate": "约 1.2 GB"},
    {"id": "browser_media", "label": "媒体工具浏览器", "estimate": "约 1.3 GB"},
    {
        "id": "whisper",
        "label": "Whisper 字幕模型（base + small）",
        "estimate": "约 1.2 GB",
    },
    {"id": "openvoice", "label": "OpenVoice 与中文语音模型", "estimate": "约 540 MB"},
    {"id": "text_models", "label": "多语言文本模型", "estimate": "约 700 MB"},
    {"id": "audio_tools", "label": "声音分离与语言数据", "estimate": "约 130 MB"},
)
_LOCK = threading.Lock()
_WORKER = None


def is_slim() -> bool:
    return (
        os.environ.get("CONTENT_AGENT_SLIM") == "1"
        or (PROJECT_ROOT / "slim-build.json").is_file()
    )


def _has(root: Path, pattern: str) -> bool:
    return any(root.glob(pattern))


def _ready(root: Path, item_id: str) -> bool:
    if item_id == "python":
        return (root / "tools/python/bin/python3").is_file() and all(
            (root / "tools/python-packages" / name).exists()
            for name in (
                "torch",
                "faster_whisper",
                "rapidocr_onnxruntime",
                "demucs",
                "melo",
                "playwright",
            )
        )
    if item_id == "system_tools":
        return all(
            path.is_file()
            for path in (
                root / "tools/node/bin/node",
                root / "tools/node/bin/npm",
                root / "tools/bin/ffmpeg",
                root / "tools/bin/ffprobe",
            )
        )
    if item_id == "remotion":
        return (
            root / "runtime/remotion-0.1.1/node_modules/remotion/package.json"
        ).is_file()
    if item_id == "browser_main":
        return _has(
            root, "tools/playwright-browsers/chromium-*/INSTALLATION_COMPLETE"
        ) and _has(
            root,
            "tools/playwright-browsers/chromium_headless_shell-*/INSTALLATION_COMPLETE",
        )
    if item_id == "browser_media":
        return (
            root / "tools/playwright-browsers/chromium-1140/INSTALLATION_COMPLETE"
        ).is_file()
    if item_id == "whisper":
        return all(
            _has(
                root,
                f"cache/huggingface/hub/models--Systran--faster-whisper-{model}/snapshots/*/model.bin",
            )
            for model in ("base", "small")
        )
    if item_id == "openvoice":
        return all(
            (
                _has(
                    root,
                    "cache/huggingface/hub/models--myshell-ai--MeloTTS-Chinese/snapshots/*/checkpoint.pth",
                ),
                _has(
                    root,
                    "cache/huggingface/hub/models--M4869--WavMark/snapshots/*/*.model.pkl",
                ),
                (
                    root / "tools/OpenVoice/checkpoints_v2/converter/checkpoint.pth"
                ).is_file(),
                (
                    root / "tools/OpenVoice/checkpoints_v2/converter/config.json"
                ).is_file(),
                (
                    root / "tools/OpenVoice/checkpoints_v2/base_speakers/ses/zh.pth"
                ).is_file(),
            )
        )
    if item_id == "text_models":
        return _has(
            root,
            "cache/huggingface/models--bert-base-multilingual-uncased/snapshots/*/pytorch_model.bin",
        )
    if item_id == "audio_tools":
        return all(
            (
                (root / "cache/torch/hub/checkpoints/955717e8-8726e21a.th").is_file(),
                (root / "cache/nltk/corpora/cmudict/cmudict").is_file(),
                _has(root, "cache/nltk/taggers/averaged_perceptron_tagger/*.pickle"),
                (root / "cache/torch/hub/snakers4_silero-vad_master").is_dir(),
            )
        )
    raise ValueError("未知精简资源：" + item_id)


def _state_path(root: Path) -> Path:
    return root / "cache/slim-dependencies.json"


def _read_state(root: Path) -> dict:
    path = _state_path(root)
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_state(root: Path, state: dict) -> None:
    path = _state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(temporary, path)


def status(root: Path) -> dict:
    root = Path(root)
    running = _WORKER is not None and _WORKER.is_alive()
    saved = _read_state(root) if is_slim() else {}
    items = []
    for definition in _ITEMS:
        item_state = saved.get("items", {}).get(definition["id"], {})
        ready = _ready(root, definition["id"])
        current = (
            "succeeded"
            if ready
            else "running"
            if running and saved.get("active") == definition["id"]
            else item_state.get("status", "pending")
        )
        if current == "running" and (
            not running or saved.get("active") != definition["id"]
        ):
            current = "pending"
        items.append(
            {**definition, "status": current, "error": item_state.get("error")}
        )
    complete = all(_ready(root, definition["id"]) for definition in _ITEMS)
    return {
        "slim": is_slim(),
        "edition": "精简版" if is_slim() else "全量离线版",
        "required": is_slim() and not complete,
        "complete": complete,
        "running": running,
        "active": saved.get("active") if running else None,
        "items": items,
        "completed": sum(_ready(root, definition["id"]) for definition in _ITEMS),
        "total": len(_ITEMS),
        "error": saved.get("error"),
    }


def _command(root: Path, resources: Path, item_id: str) -> list[str]:
    script = [
        str(resources / "slim_download.py"),
        "--root",
        str(root),
        "--resources",
        str(resources),
        "--action",
        item_id,
    ]
    if item_id in ("python", "system_tools"):
        return [sys.executable, *script]
    if item_id == "browser_main":
        return [sys.executable, "-m", "playwright", "install", "chromium"]
    python = root / "tools/python/bin/python3"
    if item_id == "browser_media":
        return [str(python), "-m", "playwright", "install", "chromium"]
    return [str(python), *script]


def _tail(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")[-1800:]


def _run(root: Path, resources: Path) -> None:
    state = {"active": None, "items": {}, "error": None}
    _write_state(root, state)
    environment = os.environ.copy()
    environment.update(
        PLAYWRIGHT_BROWSERS_PATH=str(root / "tools/playwright-browsers"),
        PLAYWRIGHT_DOWNLOAD_HOST="https://playwright-akamai.azureedge.net",
        HF_HOME=str(root / "cache/huggingface"),
        TRANSFORMERS_CACHE=str(root / "cache/huggingface"),
        TORCH_HOME=str(root / "cache/torch"),
        NLTK_DATA=str(root / "cache/nltk"),
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=str(root / "tools/python-packages"),
        HF_HUB_OFFLINE="0",
        PATH=os.pathsep.join(
            (
                str(root / "tools/node/bin"),
                str(root / "tools/bin"),
                environment.get("PATH", "/usr/bin:/bin"),
            )
        ),
    )
    for definition in _ITEMS:
        item_id = definition["id"]
        if _ready(root, item_id):
            state["items"][item_id] = {"status": "succeeded", "error": None}
            _write_state(root, state)
            continue
        state["active"] = item_id
        state["items"][item_id] = {"status": "running", "error": None}
        state["error"] = None
        _write_state(root, state)
        log = root / "logs" / f"slim-download-{item_id}.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        try:
            with log.open("w", encoding="utf-8") as output:
                subprocess.run(
                    _command(root, resources, item_id),
                    check=True,
                    env=environment,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    timeout=7200,
                )
            if not _ready(root, item_id):
                raise RuntimeError("下载命令已结束，但所需文件仍不完整")
            state["items"][item_id] = {"status": "succeeded", "error": None}
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            RuntimeError,
            OSError,
        ) as error:
            detail = _tail(log) or str(error)
            state["items"][item_id] = {"status": "failed", "error": detail}
            state["error"] = f"{definition['label']}下载失败：{detail}"
            state["active"] = None
            _write_state(root, state)
            return
    state["active"] = None
    state["error"] = None
    _write_state(root, state)


def start(root: Path, resources: Path) -> dict:
    global _WORKER
    if not is_slim():
        return status(root)
    if status(root)["complete"]:
        return status(root)
    with _LOCK:
        if _WORKER is None or not _WORKER.is_alive():
            _WORKER = threading.Thread(
                target=_run, args=(Path(root), Path(resources)), daemon=True
            )
            _WORKER.start()
    return status(root)
