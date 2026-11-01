import os
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from content_workbench.domain.errors import DomainError
from content_workbench.media.probe import probe

SKILL_NAME = "video-downloader"


def douyin_download_script():
    override = os.environ.get("DOUYIN_DOWNLOAD_SKILL_PATH", "").strip()
    if override:
        configured = Path(override).expanduser()
        return configured / "scripts" / "download.sh" if configured.is_dir() else configured
    return Path.home() / ".kimi-code" / "skills" / SKILL_NAME / "scripts" / "download.sh"


def validate_douyin_url(url):
    parsed = urlparse(str(url or ""))
    host = (parsed.hostname or "").lower().rstrip(".")
    allowed = any(host == suffix or host.endswith("." + suffix) for suffix in ("douyin.com", "iesdouyin.com"))
    if parsed.scheme != "https" or not allowed:
        raise DomainError("INVALID_DOUYIN_URL", "只支持抖音官方 HTTPS 视频链接", 422, "url", "从抖音选题快照中选择官方视频链接")


def download_douyin_video(url, output, context, timeout=1800, script_path=None):
    validate_douyin_url(url)
    script = Path(script_path) if script_path else douyin_download_script()
    if not script.is_file():
        raise DomainError("DOUYIN_SKILL_MISSING", "未安装 video-downloader Skill", 503, "settings",
                          "安装 video-downloader，或设置 DOUYIN_DOWNLOAD_SKILL_PATH 指向其 scripts/download.sh")
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    context.progress("douyin_skill_download", 0.08)
    with tempfile.TemporaryDirectory(prefix="douyin-skill-") as directory:
        library = Path(directory).resolve()
        try:
            context.run_process(["bash", str(script), "compat", str(url), str(library)],
                                timeout=timeout + 120, stage="douyin_skill_download", cwd=script.parent)
        except DomainError as error:
            raise DomainError("DOUYIN_SKILL_DOWNLOAD_FAILED", "video-downloader 执行失败：" + error.message,
                              error.status or 502, "file", "检查链接访问权限、网络和 video-downloader 日志后重试") from error
        candidates = sorted((path for path in library.rglob("*.mp4") if path.is_file()),
                            key=lambda path: path.stat().st_mtime, reverse=True)
        if not candidates:
            raise DomainError("DOUYIN_SKILL_FILE_INVALID", "video-downloader 完成执行但没有生成 MP4", 502, "file",
                              "查看下载日志，确认原视频可播放且当前账号有权访问")
        source = candidates[0].resolve()
        if library not in source.parents or source.stat().st_size < 1024:
            raise DomainError("DOUYIN_SKILL_FILE_INVALID", "video-downloader 返回了无效或越界的媒体文件", 502, "file",
                              "不要修改 Skill 输出路径；检查下载日志后重试")
        info = probe(source, "video/mp4")
        if not any(stream.get("codec_type") == "video" for stream in info.get("streams", [])):
            raise DomainError("DOUYIN_SKILL_FILE_INVALID", "video-downloader 下载结果不包含视频流", 422, "file",
                              "重新下载含画面的 MP4 视频")
        shutil.copyfile(source, output)
    streams = info.get("streams", [])
    video_stream = next(stream for stream in streams if stream.get("codec_type") == "video")
    audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    return {"path": str(output), "bytes": output.stat().st_size, "downloader": SKILL_NAME,
            "skill_script": str(script), "source_kind": "douyin-compat", "duration_seconds": info.get("duration_seconds"),
            "video_codec": video_stream.get("codec_name"), "audio_codec": audio_stream.get("codec_name") if audio_stream else None,
            "width": video_stream.get("width"), "height": video_stream.get("height"), "verification": "ffprobe"}
