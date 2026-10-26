import json
import mimetypes
import shutil
import subprocess
from pathlib import Path

from content_workbench.domain.errors import DomainError


def probe(path, mime_type=None):
    path = Path(path)
    mime = mime_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    info = {"mime_type": mime}
    if mime == "application/x-subrip" or path.suffix.lower() == ".srt":
        text = path.read_text(encoding="utf-8-sig")
        if "-->" not in text:
            raise DomainError("INVALID_SRT", "SRT 缺少有效时间轴", 422, "file", "上传包含序号、起止时间和文本的 UTF-8 SRT")
        return {**info, "format": "SRT", "characters": len(text)}
    if not (mime.startswith("audio/") or mime.startswith("video/") or path.suffix.lower() in (".wav", ".mp3", ".m4a", ".mp4", ".mov", ".webm")):
        return info
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise DomainError("FFPROBE_MISSING", "未找到 FFprobe", 503, "settings", "安装并配置 FFprobe 后重试")
    result = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate", "-of", "json", str(path)], capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise DomainError("INVALID_MEDIA", "媒体无法解码", 422, "file", "重新导出有效媒体后上传")
    data = json.loads(result.stdout or "{}")
    duration = float(data.get("format", {}).get("duration", 0) or 0)
    if duration <= 0:
        raise DomainError("INVALID_MEDIA_DURATION", "媒体时长必须大于 0", 422, "file", "重新上传完整媒体")
    return {**info, "duration_seconds": duration, "streams": data.get("streams", [])}
