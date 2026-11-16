#!/usr/bin/env python3
import argparse
import hashlib
import os
import shutil
import subprocess
import tarfile
import urllib.request
from pathlib import Path

PYTHON_URL = "https://github.com/astral-sh/python-build-standalone/releases/download/20261026/cpython-3.11.18%2B20261026-x86_64-apple-darwin-install_only.tar.gz"
PYTHON_SHA256 = "a85474bcc78a98ca6b0070d8d615b0494b912b960239e6f18cc12d648f2dc270"
NODE_URL = "https://nodejs.org/dist/v22.22.0/node-v22.22.0-darwin-x64.tar.gz"
NODE_SHA256 = "5ea50c9d6dea3dfa3abb66b2656f7a4e1c8cef23432b558d45fb538c7b5dedce"


def download(url: str, destination: Path, expected: str) -> None:
    if (
        destination.is_file()
        and hashlib.sha256(destination.read_bytes()).hexdigest() == expected
    ):
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".partial")
    digest = hashlib.sha256()
    with (
        urllib.request.urlopen(url, timeout=90) as response,
        temporary.open("wb") as output,
    ):
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
            digest.update(chunk)
    if digest.hexdigest() != expected:
        temporary.unlink(missing_ok=True)
        raise RuntimeError("下载文件校验失败：" + url)
    temporary.replace(destination)


def extract_tar(archive: Path, destination: Path) -> None:
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".partial")
    shutil.rmtree(partial, ignore_errors=True)
    partial.mkdir(parents=True)
    with tarfile.open(archive) as source:
        for member in source.getmembers():
            target = (partial / member.name).resolve()
            if os.path.commonpath((str(partial.resolve()), str(target))) != str(
                partial.resolve()
            ):
                raise RuntimeError("压缩包包含越界路径")
            if member.issym() or member.islnk():
                linked = (target.parent / member.linkname).resolve()
                if os.path.commonpath((str(partial.resolve()), str(linked))) != str(
                    partial.resolve()
                ):
                    raise RuntimeError("压缩包包含越界链接")
        source.extractall(partial)
    children = list(partial.iterdir())
    if len(children) != 1 or not children[0].is_dir():
        raise RuntimeError("运行时压缩包目录结构无效")
    if destination.exists():
        raise RuntimeError("目标运行目录已存在，未覆盖：" + str(destination))
    children[0].rename(destination)
    shutil.rmtree(partial, ignore_errors=True)


def run(command: list[str], **kwargs) -> None:
    subprocess.run(command, check=True, **kwargs)


def bootstrap_python(root: Path, resources: Path) -> None:
    python = root / "tools/python/bin/python3"
    if not python.is_file():
        archive = root / "cache/downloads/python.tar.gz"
        download(PYTHON_URL, archive, PYTHON_SHA256)
        extract_tar(archive, root / "tools/python")
    run([str(python), "-m", "ensurepip", "--upgrade"])
    run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--target",
            str(root / "tools/python-packages"),
            "-r",
            str(resources / "slim-requirements.txt"),
        ]
    )
    run(
        [
            str(python),
            "-c",
            "import unidic.download; unidic.download.download_version()",
        ]
    )


def bootstrap_tools(root: Path) -> None:
    node = root / "tools/node/bin/node"
    if not node.is_file():
        archive = root / "cache/downloads/node.tar.gz"
        download(NODE_URL, archive, NODE_SHA256)
        extract_tar(archive, root / "tools/node")
    npm = root / "tools/node/bin/npm"
    environment = os.environ.copy()
    environment["PATH"] = os.pathsep.join(
        (str(npm.parent), environment.get("PATH", "/usr/bin:/bin"))
    )
    run(
        [
            str(npm),
            "install",
            "--prefix",
            str(root / "tools/ffmpeg-runtime"),
            "--no-audit",
            "--no-fund",
            "ffmpeg-static@5.2.0",
            "@ffprobe-installer/ffprobe@2.1.2",
        ],
        env=environment,
    )
    binaries = {
        root / "tools/ffmpeg-runtime/node_modules/ffmpeg-static/ffmpeg": root
        / "tools/bin/ffmpeg",
        root
        / "tools/ffmpeg-runtime/node_modules/@ffprobe-installer/darwin-x64/ffprobe": root
        / "tools/bin/ffprobe",
    }
    for source, target in binaries.items():
        if not source.is_file():
            raise RuntimeError("媒体工具下载后缺少文件：" + str(source))
        source.chmod(0o755)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() or target.is_symlink():
            target.unlink()
        target.symlink_to(source)


def bootstrap_remotion(root: Path) -> None:
    runtime = root / "runtime/remotion-0.1.1"
    if not (runtime / "package-lock.json").is_file():
        raise RuntimeError("Remotion 工作目录尚未准备")
    npm = root / "tools/node/bin/npm"
    environment = os.environ.copy()
    environment["PATH"] = os.pathsep.join(
        (str(npm.parent), environment.get("PATH", "/usr/bin:/bin"))
    )
    run(
        [str(npm), "ci", "--prefix", str(runtime), "--no-audit", "--no-fund"],
        env=environment,
    )


def download_silero(root: Path) -> None:
    import zipfile

    archive = root / "cache/downloads/silero-vad-master.zip"
    download(
        "https://codeload.github.com/snakers4/silero-vad/zip/refs/heads/master",
        archive,
        "7bbfa83e32ff29af9144ff73fa62799e30dc6f747289462868bbbf3e617430ff",
    )
    destination = root / "cache/torch/hub/snakers4_silero-vad_master"
    partial = destination.with_name(destination.name + ".partial")
    shutil.rmtree(partial, ignore_errors=True)
    partial.mkdir(parents=True)
    with zipfile.ZipFile(archive) as source:
        for member in source.infolist():
            target = (partial / member.filename).resolve()
            if os.path.commonpath((str(partial.resolve()), str(target))) != str(
                partial.resolve()
            ):
                raise RuntimeError("Silero 压缩包包含越界路径")
        source.extractall(partial)
    children = list(partial.iterdir())
    if len(children) != 1 or not children[0].is_dir():
        raise RuntimeError("Silero 压缩包目录结构无效")
    if destination.exists():
        shutil.rmtree(partial)
    else:
        children[0].rename(destination)
        shutil.rmtree(partial)
    import torch

    torch.hub.load(str(destination), "silero_vad", source="local")


def download_models(root: Path, action: str) -> None:
    os.environ.update(
        HF_HOME=str(root / "cache/huggingface"),
        TRANSFORMERS_CACHE=str(root / "cache/huggingface"),
        TORCH_HOME=str(root / "cache/torch"),
        NLTK_DATA=str(root / "cache/nltk"),
        HF_HUB_OFFLINE="0",
        PYTHONDONTWRITEBYTECODE="1",
    )
    from huggingface_hub import hf_hub_download, snapshot_download

    hub = root / "cache/huggingface/hub"
    if action == "whisper":
        for model in ("base", "small"):
            snapshot_download(f"Systran/faster-whisper-{model}", cache_dir=hub)
        return
    if action == "openvoice":
        snapshot_download("myshell-ai/MeloTTS-Chinese", cache_dir=hub)
        snapshot_download("M4869/WavMark", cache_dir=hub)
        for name in (
            "converter/checkpoint.pth",
            "converter/config.json",
            "base_speakers/ses/zh.pth",
        ):
            hf_hub_download(
                "myshell-ai/OpenVoiceV2",
                name,
                local_dir=root / "tools/OpenVoice/checkpoints_v2",
            )
        return
    if action == "text_models":
        repositories = (
            "bert-base-multilingual-uncased",
            "bert-base-uncased",
            "dbmdz/bert-base-french-europeana-cased",
            "dccuchile/bert-base-spanish-wwm-uncased",
            "kykim/bert-kor-base",
            "tohoku-nlp/bert-base-japanese-v3",
        )
        for repository in repositories:
            snapshot_download(
                repository,
                cache_dir=root / "cache/huggingface",
                allow_patterns=("*.json", "*.txt", "pytorch_model.bin"),
            )
        return
    import nltk

    for package in ("cmudict", "averaged_perceptron_tagger"):
        if not nltk.download(package, download_dir=root / "cache/nltk", quiet=True):
            raise RuntimeError("NLTK 数据下载失败：" + package)
    from demucs.pretrained import get_model

    get_model("htdemucs")
    download_silero(root)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--resources", type=Path, required=True)
    parser.add_argument(
        "--action",
        required=True,
        choices=(
            "python",
            "system_tools",
            "remotion",
            "whisper",
            "openvoice",
            "text_models",
            "audio_tools",
        ),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    resources = args.resources.resolve()
    if args.action == "python":
        bootstrap_python(root, resources)
    elif args.action == "system_tools":
        bootstrap_tools(root)
    elif args.action == "remotion":
        bootstrap_remotion(root)
    else:
        download_models(root, args.action)


if __name__ == "__main__":
    main()
