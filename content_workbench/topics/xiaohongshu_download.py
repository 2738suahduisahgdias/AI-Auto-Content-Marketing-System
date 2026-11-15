from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

from content_workbench.domain.errors import DomainError
from content_workbench.media.probe import probe
from content_workbench.providers.text import KimiCLIProvider
from content_workbench.storage.db import PROJECT_ROOT
from content_workbench.topics.douyin_download import douyin_download_script

AGENT_PATH = PROJECT_ROOT / "agents" / "xiaohongshu-download-agent.md"
MODES = {"quality", "speed", "compat"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".webm"}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


class JobContext(Protocol):
    def progress(self, stage: str, progress: float | None = None) -> None: ...


def validate_xiaohongshu_url(url: str) -> str:
    parsed = urlparse(str(url or ""))
    host = (parsed.hostname or "").lower().rstrip(".")
    allowed = any(
        host == suffix or host.endswith("." + suffix)
        for suffix in ("xiaohongshu.com", "xhslink.com")
    )
    if parsed.scheme != "https" or not allowed:
        raise DomainError(
            "INVALID_XHS_URL",
            "只支持小红书官方 HTTPS 作品链接",
            422,
            "url",
            "从小红书选题快照中选择真实作品链接",
        )
    return str(url)


def skill_script(name: str) -> Path:
    script = douyin_download_script()
    directory = (
        script.parent if script.name.endswith(".sh") else script.parent / "scripts"
    )
    target = directory / name
    if not target.is_file():
        raise DomainError(
            "XHS_SKILL_MISSING",
            "未安装完整的 video-downloader Skill",
            503,
            "settings",
            "安装 video-downloader，并确认 probe.sh 与 download.sh 均存在",
        )
    return target


def request_xiaohongshu_media(
    action: str, url: str, context: JobContext, **payload: object
) -> dict:
    request = {
        "action": action,
        "platform": "xiaohongshu",
        "url": validate_xiaohongshu_url(url),
        **payload,
    }
    result = KimiCLIProvider(PROJECT_ROOT).complete_json(
        json.dumps(request, ensure_ascii=False),
        context,
        AGENT_PATH,
        timeout=1920,
        stage="kimi_xiaohongshu_" + action,
    )
    if result.get("status") != "ok":
        first = (result.get("errors") or [{}])[0]
        raise DomainError(
            "XHS_DOWNLOAD_FAILED" if action == "download" else "XHS_PROBE_FAILED",
            first.get("message") or "Kimi CLI 未完成小红书素材读取",
            502,
            "file",
            first.get("action") or "检查真实链接、网络和下载日志后重试",
        )
    return result


def probe_xiaohongshu_media(url: str, context: JobContext) -> dict:
    context.progress("kimi_xiaohongshu_probe", 0.08)
    result = request_xiaohongshu_media(
        "probe", url, context, skill_script=str(skill_script("probe.sh"))
    )
    if result.get("media_kind") not in ("video", "image_set") or not isinstance(
        result.get("formats"), list
    ):
        raise DomainError(
            "XHS_PROBE_INVALID",
            "小红书素材探测没有返回类型和真实档位",
            502,
            "file",
            "检查作品页和 probe 输出后重试",
        )
    context.progress("kimi_xiaohongshu_probe_completed", 1)
    return {**result, "provider": "kimi_cli"}


def download_xiaohongshu_media(
    url: str, output_directory: Path, context: JobContext, mode: str
) -> dict:
    if mode not in MODES:
        raise DomainError(
            "XHS_DOWNLOAD_MODE_REQUIRED",
            "请先探测素材并选择画质优先、速度优先或兼容优先",
            422,
            "mode",
            "探测后由用户明确选择下载模式",
        )
    output = Path(output_directory).resolve()
    context.progress("kimi_xiaohongshu_download", 0.08)
    with tempfile.TemporaryDirectory(prefix="xiaohongshu-kimi-download-") as directory:
        library = Path(directory).resolve()
        result = request_xiaohongshu_media(
            "download",
            url,
            context,
            mode=mode,
            skill_script=str(skill_script("download.sh")),
            output_dir=str(library),
        )
        media_kind = result.get("media_kind")
        if media_kind not in ("video", "image_set"):
            raise DomainError(
                "XHS_DOWNLOAD_TYPE_INVALID",
                "下载结果没有明确区分视频或图文素材",
                502,
                "file",
            )
        files = result.get("files")
        if not isinstance(files, list) or not files:
            raise DomainError(
                "XHS_FILE_INVALID", "Kimi CLI 没有返回真实素材文件", 502, "file"
            )
        copied = []
        output.mkdir(parents=True, exist_ok=True)
        for index, item in enumerate(files, 1):
            source = Path(str(item.get("path") or "")).resolve()
            if library not in source.parents or not source.is_file():
                raise DomainError(
                    "XHS_FILE_INVALID", "下载文件不存在或越过任务目录", 502, "file"
                )
            suffix = source.suffix.lower()
            if (
                source.stat().st_size < 100
                or suffix not in VIDEO_SUFFIXES | IMAGE_SUFFIXES
            ):
                raise DomainError(
                    "XHS_FILE_INVALID", "下载文件为空或格式不受支持", 422, "file"
                )
            if media_kind == "image_set" and suffix not in IMAGE_SUFFIXES:
                raise DomainError(
                    "XHS_FILE_TYPE_MISMATCH", "图文结果中包含非图片文件", 422, "file"
                )
            target = output / f"{index:02d}{suffix}"
            shutil.copyfile(source, target)
            copied.append({"path": str(target), "bytes": target.stat().st_size})
        primary = Path(copied[0]["path"])
        info = None
        if media_kind == "video":
            info = probe(primary, "video/mp4")
            if not any(
                stream.get("codec_type") == "video"
                for stream in info.get("streams", [])
            ):
                raise DomainError(
                    "XHS_FILE_INVALID", "下载结果不包含视频流", 422, "file"
                )
        context.progress("kimi_xiaohongshu_download_completed", 1)
        return {
            "path": str(primary),
            "directory": str(output),
            "media_kind": media_kind,
            "file_count": len(copied),
            "files": copied,
            "bytes": sum(item["bytes"] for item in copied),
            "duration_seconds": info.get("duration_seconds") if info else None,
            "downloader": "kimi_cli",
            "mode": mode,
            "verification": "ffprobe" if info else "real_image_files",
        }
