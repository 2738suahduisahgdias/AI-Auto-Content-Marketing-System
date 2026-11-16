#!/usr/bin/env python3
"""Build an isolated Intel Mac .app and DMG from tracked source + locked dependencies."""

import argparse
import os
import platform
import plistlib
import shutil
import subprocess
from pathlib import Path

from runtime_bundle import prepare_openssl_runtime, remove_apple_double

p = argparse.ArgumentParser()
p.add_argument("--output", required=True)
p.add_argument("--public-keys", required=True)
p.add_argument("--assemble-only", action="store_true")
p.add_argument("--python-runtime", default=os.environ.get("YINGXU_PYTHON_RUNTIME"))
p.add_argument("--models-root", default=os.environ.get("YINGXU_MODELS_ROOT"))
p.add_argument(
    "--playwright-browsers", default=os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
)
p.add_argument("--openvoice-root", default=os.environ.get("YINGXU_OPENVOICE_ROOT"))
p.add_argument("--reuse-runtime", action="store_true")
p.add_argument("--skip-dmg", action="store_true")
p.add_argument("--slim", action="store_true")
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
out = Path(a.output).resolve()
out.mkdir(parents=True, exist_ok=True)
stage = out / "resources"
stage.mkdir(exist_ok=True)
remove_apple_double(stage)
if not a.assemble_only:
    if not all(
        (a.python_runtime, a.models_root, a.playwright_browsers, a.openvoice_root)
    ):
        raise SystemExit(
            "自包含构建需要 --python-runtime、--models-root、--playwright-browsers、--openvoice-root"
        )
    from runtime_bundle import prepare_shared_resources, validate_python_runtime

    if a.reuse_runtime:
        if not a.slim and not (stage / "python/bin/python3.9").is_file():
            raise SystemExit("--reuse-runtime 要求输出目录已有完整的上一版运行时")
        if not a.slim:
            validate_python_runtime(stage, Path(a.models_root))
    else:
        prepare_shared_resources(
            Path(a.python_runtime),
            Path(a.models_root),
            Path(a.playwright_browsers),
            Path(a.openvoice_root),
            stage,
            slim=a.slim,
        )
if a.slim:
    shutil.rmtree(stage / "models", ignore_errors=True)
    shutil.rmtree(stage / "playwright-browsers", ignore_errors=True)
    shutil.rmtree(stage / "OpenVoice/checkpoints_v2", ignore_errors=True)
    shutil.copyfile(repo / "desktop/slim_download.py", stage / "slim_download.py")
    shutil.copyfile(
        repo / "desktop/slim-requirements.txt", stage / "slim-requirements.txt"
    )
    (stage / "slim-build.json").write_text(
        '{"edition":"精简版","downloads":"on-demand"}', encoding="utf-8"
    )
else:
    (stage / "slim-build.json").unlink(missing_ok=True)
for folder in (
    "migrations",
    "agents",
    "workers",
    "templates",
    "content_workbench",
    "config",
    "skills",
):
    if (repo / folder).is_dir():
        shutil.copytree(
            repo / folder,
            stage / folder,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
(stage / "data").mkdir(exist_ok=True)
shutil.copyfile(repo / "data/seed.example.json", stage / "data/seed.example.json")
shutil.copytree(repo / "web/react-dist", stage / "web/react-dist", dirs_exist_ok=True)
shutil.copytree(
    repo / "web",
    stage / "web",
    dirs_exist_ok=True,
    ignore=shutil.ignore_patterns("react-dist"),
)
for name in ("src", "scripts", "public", "public-static"):
    source = repo / "remotion-app" / name
    if source.is_dir():
        shutil.copytree(
            source,
            stage / "remotion-app" / name,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("yingxu-assets"),
        )
renderer = stage / "remotion-app/scripts/render.mjs"
renderer.write_text(
    renderer.read_text().replace("enableCaching: true", "enableCaching: false")
)
for name in (
    "package.json",
    "package-lock.json",
    "remotion.config.ts",
    "tsconfig.json",
):
    if (repo / "remotion-app" / name).exists():
        shutil.copyfile(repo / "remotion-app" / name, stage / "remotion-app" / name)
if a.slim:
    shutil.rmtree(stage / "remotion-app/node_modules", ignore_errors=True)
if not a.slim and not (stage / "dependencies.complete").exists():
    print("Copying locked Remotion runtime", flush=True)
    subprocess.run(
        [
            "/usr/bin/rsync",
            "-a",
            "--exclude=.cache",
            "--exclude=*.map",
            "--exclude=*.tsbuildinfo",
            str((repo / "remotion-app/node_modules").resolve()) + "/",
            str(stage / "remotion-app/node_modules") + "/",
        ],
        check=True,
    )
    for mapping in (stage / "remotion-app/node_modules").rglob("*.map"):
        mapping.unlink()
    shutil.rmtree(stage / "remotion-app/node_modules/.cache", ignore_errors=True)
    (stage / "dependencies.complete").write_text("complete")
if a.public_keys:
    subprocess.run(
        [
            os.sys.executable,
            str(repo / "scripts/configure-license.py"),
            "--root",
            str(stage),
            "--public-keys",
            a.public_keys,
        ],
        check=True,
    )
os.environ["PYINSTALLER_CONFIG_DIR"] = str(out / "pyinstaller-cache")
command = [
    os.sys.executable,
    "-m",
    "PyInstaller",
    "--noconfirm",
    "--onedir",
    "--name",
    "YingxuService",
    "--distpath",
    str(out / "engine"),
    "--workpath",
    str(out / "build"),
    "--specpath",
    str(out),
    "--paths",
    str(repo),
    "--collect-submodules",
    "content_workbench",
    "--hidden-import",
    "app",
    "--collect-submodules",
    "PIL",
    "--collect-submodules",
    "xlrd",
    "--collect-submodules",
    "playwright",
]
# Keep vendor Chromium intact: PyInstaller must not rewrite its Mach-O load commands.
for item in stage.iterdir():
    if item.name in ("dependencies.complete", "python", "playwright-browsers"):
        continue
    if item.name == "remotion-app":
        for child in item.iterdir():
            if child.name != "node_modules":
                command += [
                    "--add-data",
                    str(child)
                    + ":"
                    + (
                        "remotion-app/" + child.name
                        if child.is_dir()
                        else "remotion-app"
                    ),
                ]
    else:
        command += [
            "--add-data",
            str(item) + ":" + (item.name if item.is_dir() else "."),
        ]
for binary in () if a.slim else ("node", "ffmpeg", "ffprobe"):
    path = shutil.which(binary)
    if not path:
        raise SystemExit("缺少打包依赖 " + binary)
    command += ["--add-binary", path + ":bin"]
for path in prepare_openssl_runtime(out / "openssl-runtime"):
    command += ["--add-binary", str(path) + ":bin"]
kimi = os.environ.get("YINGXU_KIMI_CLI")
if not kimi:
    bundled_kimi = Path.home() / ".kimi-code/bin/kimi"
    kimi = str(bundled_kimi) if bundled_kimi.is_file() else shutil.which("kimi")
if not kimi or not Path(kimi).is_file():
    raise SystemExit("缺少打包依赖 Kimi CLI，请安装或设置 YINGXU_KIMI_CLI")
subprocess.run([kimi, "--version"], check=True, capture_output=True, timeout=30)
command += ["--add-binary", kimi + ":bin"]
command.append(str(repo / "desktop/entry.py"))
if not a.assemble_only:
    subprocess.run(command, cwd=repo, check=True)
else:
    for item in (stage / "remotion-app").iterdir():
        if item.name == "node_modules":
            continue
        target = out / "engine/YingxuService/_internal/remotion-app" / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copyfile(item, target)


remove_apple_double(out / "engine")


def clone(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink():
        destination.unlink()
    elif destination.exists():
        shutil.rmtree(destination)
    result = subprocess.run(
        ["/bin/cp", "-cRp", str(source), str(destination)], check=False
    )
    if result.returncode:
        subprocess.run(
            ["/usr/bin/ditto", "--noqtn", str(source), str(destination)], check=True
        )


if a.slim:
    for name in ("python", "playwright-browsers"):
        shutil.rmtree(out / "engine/YingxuService/_internal" / name, ignore_errors=True)
    shutil.rmtree(
        out / "engine/YingxuService/_internal/remotion-app/node_modules",
        ignore_errors=True,
    )
else:
    clone(stage / "python", out / "engine/YingxuService/_internal/python")
    clone(
        stage / "playwright-browsers",
        out / "engine/YingxuService/_internal/playwright-browsers",
    )

if not a.slim and (
    not a.assemble_only
    or (out / "engine/YingxuService/_internal/remotion-app/node_modules").is_symlink()
):
    clone(
        (stage / "remotion-app/node_modules").resolve(),
        out / "engine/YingxuService/_internal/remotion-app/node_modules",
    )
app = out / ("映序工作台·精简版.app" if a.slim else "映序工作台.app")
contents = app / "Contents"
(contents / "MacOS").mkdir(parents=True, exist_ok=True)
clone(out / "engine/YingxuService", contents / "Resources/engine")
# A native launcher can be sealed as a Mac application; shell entry points cannot.
launcher = contents / "MacOS/launcher"
launcher_source = repo / "desktop/launcher.m"
subprocess.run(
    [
        "/usr/bin/clang",
        "-fobjc-arc",
        "-framework",
        "Cocoa",
        "-framework",
        "WebKit",
        "-Os",
        str(launcher_source),
        "-o",
        str(launcher),
    ],
    check=True,
)
shutil.copyfile(repo / "desktop/browser.py", contents / "Resources/open-workbench.py")
shutil.copyfile(
    repo / "desktop/assets/Workbench.icns", contents / "Resources/Workbench.icns"
)
with (contents / "Info.plist").open("wb") as f:
    plistlib.dump(
        {
            "CFBundleExecutable": "launcher",
            "CFBundleIconFile": "Workbench.icns",
            "CFBundleIdentifier": "com.yingxu.workbench.slim"
            if a.slim
            else "com.yingxu.workbench",
            "CFBundleName": "映序工作台·精简版" if a.slim else "映序工作台",
            "CFBundleVersion": "0.3.0.0" if a.slim else "0.2.0.0",
            "CFBundleShortVersionString": "0.3.0" if a.slim else "0.2.0",
            "NSAppleEventsUsageDescription": "用于首次启动选择本地工作区。",
            "CFBundlePackageType": "APPL",
            "LSMinimumSystemVersion": subprocess.check_output(
                ["sw_vers", "-productVersion"], text=True
            )
            .strip()
            .split(".")[0]
            + ".0",
        },
        f,
    )
subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app)], check=True)
if not a.skip_dmg:
    volume = out / "volume"
    volume.mkdir(exist_ok=True)
    clone(app, volume / app.name)
    if not (volume / "Applications").is_symlink():
        (volume / "Applications").symlink_to("/Applications")
    install_text = (
        "将映序工作台·精简版拖入 Applications。首次启动选择新的空工作区，并在下载向导中下载全部本地资源。\n"
        "下载需要网络，资源保存到工作区；下载完成后可离线使用本地媒体能力。\n"
        if a.slim
        else "将映序工作台拖入 Applications。首次启动选择本地或外置硬盘工作区。\n"
    )
    install_text += "本构建为 Intel Mac 测试版，未经过 Apple Developer ID 公证；不是对外正式发布包。\n不包含私钥、客户数据、平台登录或模型密钥。\n"
    (volume / "安装说明.txt").write_text(install_text, encoding="utf-8")
    subprocess.run(
        [
            "hdiutil",
            "create",
            "-volname",
            "映序工作台·精简版" if a.slim else "映序工作台",
            "-srcfolder",
            str(volume),
            "-ov",
            "-format",
            "UDZO",
            str(
                out
                / (
                    "Yingxu-Mac-"
                    + platform.machine()
                    + ("-Slim" if a.slim else "")
                    + ".dmg"
                )
            ),
        ],
        check=True,
    )
print(app)
