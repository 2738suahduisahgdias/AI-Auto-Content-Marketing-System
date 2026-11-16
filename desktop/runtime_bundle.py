#!/usr/bin/env python3
"""Copy relocatable local runtimes and model resources into the Mac application."""

import os
import shutil
import subprocess
from pathlib import Path


def find_openssl() -> Path:
    explicit = os.environ.get("YINGXU_OPENSSL")
    candidates: list[Path] = [Path(explicit)] if explicit else []
    if not explicit:
        brew = shutil.which("brew")
        if brew:
            result = subprocess.run(
                [brew, "--prefix", "openssl@3"],
                check=False,
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode == 0:
                candidates.append(Path(result.stdout.strip()) / "bin/openssl")
        ambient = shutil.which("openssl")
        if ambient:
            candidates.append(Path(ambient))
    for candidate in candidates:
        if not candidate.is_file():
            continue
        result = subprocess.run(
            [str(candidate), "version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout.startswith("OpenSSL 3."):
            return candidate.resolve()
    raise RuntimeError(
        "打包需要支持 Ed25519 的 OpenSSL 3+，请安装 openssl@3 或设置 YINGXU_OPENSSL"
    )


def prepare_openssl_runtime(destination: Path) -> list[Path]:
    source = find_openssl()
    destination.mkdir(parents=True, exist_ok=True)
    dependencies: dict[str, Path] = {}
    inspection = subprocess.check_output(
        ["/usr/bin/otool", "-L", str(source)], text=True
    )
    for line in inspection.splitlines()[1:]:
        library = Path(line.strip().split(" ", 1)[0])
        if library.name in ("libcrypto.3.dylib", "libssl.3.dylib"):
            dependencies[str(library)] = library
    if not any(path.name == "libcrypto.3.dylib" for path in dependencies.values()):
        raise RuntimeError("OpenSSL 3 缺少 libcrypto.3.dylib，无法制作自包含客户端")
    executable = destination / "openssl"
    executable.unlink(missing_ok=True)
    shutil.copy2(source, executable)
    bundled = [executable]
    for library in dependencies.values():
        target = destination / library.name
        target.unlink(missing_ok=True)
        shutil.copy2(library, target)
        bundled.append(target)
    for binary in bundled:
        for original, library in dependencies.items():
            prefix = "executable" if binary == executable else "loader"
            subprocess.run(
                [
                    "/usr/bin/install_name_tool",
                    "-change",
                    original,
                    f"@{prefix}_path/{library.name}",
                    str(binary),
                ],
                check=True,
                capture_output=True,
            )
    result = subprocess.run(
        [str(executable), "version"],
        check=True,
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin"},
    )
    if not result.stdout.startswith("OpenSSL 3."):
        raise RuntimeError("随包 OpenSSL 3 独立运行校验失败")
    return bundled


def copy_python_runtime(environment: Path, destination: Path) -> None:
    environment = environment.resolve()
    executable = Path(
        subprocess.check_output(
            [
                str(environment / "bin/python"),
                "-c",
                "import sys; print(sys._base_executable)",
            ],
            text=True,
        ).strip()
    ).resolve()
    base = executable.parent.parent
    if not (base / "lib/python3.9/os.py").is_file():
        raise RuntimeError("客户端 Python 不是可迁移的独立运行环境")
    shutil.copytree(base, destination, dirs_exist_ok=True)
    packages = environment / "lib/python3.9/site-packages"
    if not packages.is_dir():
        raise RuntimeError("客户端 Python 缺少统一媒体依赖")
    shutil.copytree(
        packages, destination / "lib/python3.9/site-packages", dirs_exist_ok=True
    )


def validate_python_runtime(resources: Path, models: Path) -> None:
    environment = os.environ.copy()
    environment.update(
        HOME=str(resources / ".runtime-home"),
        HF_HOME=str(models / "huggingface"),
        TRANSFORMERS_CACHE=str(models / "huggingface"),
        TORCH_HOME=str(models / "torch"),
        XDG_CACHE_HOME=str(models / "xdg"),
        NLTK_DATA=str(models / "nltk"),
        HF_HUB_OFFLINE="1",
    )
    command = [
        str(resources / "python/bin/python3.9"),
        "-c",
        "import torch,faster_whisper,rapidocr_onnxruntime,demucs,melo.api,av,playwright; print('runtime imports ok')",
    ]
    subprocess.run(command, check=True, env=environment)


def remove_apple_double(root: Path) -> None:
    for path in root.rglob("._*"):
        if path.is_file() or path.is_symlink():
            path.unlink()


def replace_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def prepare_shared_resources(
    python_environment: Path,
    models: Path,
    browsers: Path,
    openvoice: Path,
    stage: Path,
    slim: bool = False,
) -> None:
    if not slim:
        copy_python_runtime(python_environment, stage / "python")
        for name in ("huggingface", "torch", "nltk"):
            source = models / name
            if not source.is_dir():
                raise RuntimeError("缺少客户端模型目录：" + str(source))
            shutil.copytree(source, stage / "models" / name, dirs_exist_ok=True)
        if not any(browsers.glob("chromium-*")):
            raise RuntimeError("缺少客户端 Chromium：" + str(browsers))
        replace_tree(browsers, stage / "playwright-browsers")
    ignored = [".git", "__pycache__", "*.pyc"]
    if slim:
        ignored.append("checkpoints_v2")
    shutil.copytree(
        openvoice,
        stage / "OpenVoice",
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(*ignored),
    )
    if not slim:
        validate_python_runtime(stage, models)
