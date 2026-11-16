#!/usr/bin/env python3

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path


def run(command: list[str], environment: dict[str, str], timeout: int = 1800) -> None:
    subprocess.run(command, check=True, env=environment, timeout=timeout)


def probe(executable: Path, path: Path) -> dict:
    output = subprocess.check_output(
        [
            str(executable),
            "-v",
            "error",
            "-show_entries",
            "format=duration,size",
            "-of",
            "json",
            str(path),
        ],
        text=True,
    )
    return json.loads(output)["format"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--sample", type=Path, required=True)
    parser.add_argument("--frame", type=Path, required=True)
    args = parser.parse_args()
    app = args.app.resolve()
    root = args.root.resolve()
    resources = app / "Contents/Resources/engine/_internal"
    engine = app / "Contents/Resources/engine/YingxuService"
    slim = (resources / "slim-build.json").is_file()
    python = (
        root / "tools/python/bin/python3"
        if slim
        else resources / "python/bin/python3.9"
    )
    ffprobe = root / "tools/bin/ffprobe" if slim else resources / "bin/ffprobe"
    runtime_binaries = (
        [root / "tools/node/bin", root / "tools/bin"] if slim else [resources / "bin"]
    )
    browsers = (
        root / "tools/playwright-browsers"
        if slim
        else resources / "playwright-browsers"
    )
    openvoice = root / "tools/OpenVoice" if slim else resources / "OpenVoice"
    output = root / "acceptance"
    output.mkdir(parents=True, exist_ok=True)
    frames = output / "frames"
    frames.mkdir(exist_ok=True)
    shutil.copy2(args.frame.resolve(), frames / f"frame-{args.frame.name}")
    environment = os.environ.copy()
    environment.update(
        CONTENT_AGENT_DESKTOP="1",
        CONTENT_AGENT_ROOT=str(root),
        CONTENT_AGENT_DB=str(root / "data/content-agent.db"),
        HOME=str(root / "cache/home"),
        KIMI_CODE_HOME=str(Path.home() / ".kimi-code"),
        HF_HOME=str(root / "cache/huggingface"),
        TRANSFORMERS_CACHE=str(root / "cache/huggingface"),
        TORCH_HOME=str(root / "cache/torch"),
        XDG_CACHE_HOME=str(root / "cache/xdg"),
        NLTK_DATA=str(root / "cache/nltk"),
        PLAYWRIGHT_BROWSERS_PATH=str(browsers),
        HF_HUB_OFFLINE="1",
        PYTHONDONTWRITEBYTECODE="1",
        PATH=os.pathsep.join(
            (
                *(str(path) for path in runtime_binaries),
                str(Path.home() / ".kimi-code/bin"),
                environment["PATH"],
            )
        ),
    )
    if slim:
        environment["CONTENT_AGENT_SLIM"] = "1"
        environment["PYTHONPATH"] = str(root / "tools/python-packages")
    subtitle = output / "whisper.srt"
    run(
        [
            str(python),
            str(resources / "workers/whisperx_worker.py"),
            "--audio",
            str(args.sample.resolve()),
            "--output",
            str(subtitle),
            "--model",
            "base",
        ],
        environment,
    )
    ocr = subprocess.check_output(
        [
            str(python),
            str(resources / "content_workbench/topics/ocr_worker.py"),
            "--frames",
            str(frames),
        ],
        text=True,
        env=environment,
    )
    if "真实" not in ocr:
        raise RuntimeError("OCR 没有识别出测试帧中的中文")
    run(
        [
            str(python),
            "-m",
            "demucs",
            "--two-stems",
            "vocals",
            "-n",
            "htdemucs",
            "-o",
            str(output / "demucs"),
            str(args.sample.resolve()),
        ],
        environment,
    )
    voice = output / "openvoice.wav"
    run(
        [
            str(python),
            str(resources / "workers/openvoice_worker.py"),
            "--openvoice-root",
            str(openvoice),
            "--ref",
            str(openvoice / "resources/example_reference.mp3"),
            "--text",
            "自包含客户端真实媒体验收。",
            "--output",
            str(voice),
            "--work-dir",
            str(output / "openvoice-work"),
        ],
        environment,
    )
    model_code = """
import json
import subprocess
from content_workbench.agents.registry import require_agent_enabled
from content_workbench.providers.system import provider_for
from content_workbench.storage.db import DB_PATH, PROJECT_ROOT
class Context:
    def run_process(self, arguments, timeout, stage, cwd):
        result = subprocess.run(arguments, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        if result.returncode:
            raise RuntimeError(result.stderr[-500:])
        return result.stdout, result.stderr
config = require_agent_enabled(DB_PATH, 'article_image_agent')
result = provider_for(PROJECT_ROOT, config['engine']).complete_json(
    '只返回 {\"ok\": true}', Context(), PROJECT_ROOT / 'agents/model-connection-agent.md',
    timeout=180, model=config['model'])
print(json.dumps({'engine': config['engine'], 'model': config['model'], 'result': result}, ensure_ascii=False))
"""
    model_result = subprocess.check_output(
        [str(engine), "-c", model_code], text=True, env=environment, timeout=240
    )
    stems = output / "demucs/htdemucs" / args.sample.stem
    report = {
        "whisper": subtitle.with_suffix(".words.json").is_file()
        and bool(subtitle.read_text().strip()),
        "ocr": json.loads(ocr),
        "demucs": {
            role: probe(ffprobe, stems / filename)
            for role, filename in (
                ("vocals", "vocals.wav"),
                ("accompaniment", "no_vocals.wav"),
            )
        },
        "openvoice": probe(ffprobe, voice),
        "model_cli": json.loads(model_result.strip().splitlines()[-1]),
    }
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
