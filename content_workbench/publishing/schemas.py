import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from content_workbench.domain.errors import DomainError
from .contracts import contract_fields, publishing_contract

ARTICLE_PLATFORMS = ("wechat_official_account", "xiaohongshu")
VIDEO_PLATFORMS = ("douyin", "xiaohongshu", "wechat_channels")
SUPPORTED_PREPARE = {"wechat_official_account", "xiaohongshu", "douyin", "wechat_channels"}
PLATFORM_NAMES = {
    "wechat_official_account": "公众号",
    "xiaohongshu": "小红书",
    "douyin": "抖音",
    "wechat_channels": "视频号",
}


def invalid(code, message, field, action):
    raise DomainError(code, message, 422, field, action)


def dependency_active(payload, definition):
    dependency = definition.get("depends_on")
    return not dependency or payload.get(dependency["field"]) == dependency["equals"]


def validate_datetime(value, name):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        invalid("PUBLISH_DATETIME_INVALID", "定时时间格式无效", name, "使用日期时间选择器重新填写")
    now = datetime.now(timezone.utc) if parsed.tzinfo else datetime.now()
    if parsed <= now:
        invalid("PUBLISH_DATETIME_PAST", "定时发布时间必须晚于当前时间", name, "选择未来时间，或清空后立即发布")


def validate_chapters(value, name):
    try:
        chapters = json.loads(value)
    except json.JSONDecodeError:
        invalid("PUBLISH_CHAPTERS_INVALID", "视频章节不是合法 JSON", name, '使用 [{"start_seconds":0,"title":"章节名"}] 格式')
    if not isinstance(chapters, list):
        invalid("PUBLISH_CHAPTERS_INVALID", "视频章节必须是数组", name, "填写章节数组，没有章节时保留 []")
    previous = -1
    for chapter in chapters:
        if not isinstance(chapter, dict) or isinstance(chapter.get("start_seconds"), bool) \
                or not isinstance(chapter.get("start_seconds"), (int, float)) or chapter["start_seconds"] < 0 \
                or not str(chapter.get("title", "")).strip():
            invalid("PUBLISH_CHAPTERS_INVALID", "每个章节都需要非负 start_seconds 和标题", name, "修正章节时间和标题")
        if chapter["start_seconds"] <= previous:
            invalid("PUBLISH_CHAPTERS_ORDER", "章节时间必须严格递增", name, "按时间先后排列章节")
        if len(str(chapter["title"]).strip()) > 100:
            invalid("PUBLISH_CHAPTERS_TOO_LONG", "单个章节标题不能超过 100 字", name, "缩短章节标题")
        previous = chapter["start_seconds"]


def validate_payload(kind, platform, payload):
    if not isinstance(payload, dict):
        raise DomainError("PUBLISH_PAYLOAD_INVALID", "发布内容必须是对象", 422, "payload", "按平台表单填写")
    allowed = ARTICLE_PLATFORMS if kind == "article" else VIDEO_PLATFORMS if kind == "video" else ()
    if platform not in allowed:
        raise DomainError("PUBLISH_CONTENT_PLATFORM_MISMATCH", "内容类型与发布平台不匹配", 422, "platform", "文章选择公众号或小红书长文；视频选择抖音、小红书或视频号")
    raw = dict(payload)
    if platform == "wechat_channels" and kind == "video" and not raw.get("short_title") and raw.get("title"):
        raw["short_title"] = raw["title"]
    try:
        definitions = contract_fields(platform, kind)
    except ValueError:
        raise DomainError("PUBLISH_CONTENT_PLATFORM_MISMATCH", "内容类型与发布平台不匹配", 422, "platform", "使用页面提供的平台")
    result = {}
    for definition in definitions:
        name = definition["name"]
        control = definition["control"]
        if control == "source":
            if raw.get(name):
                result[name] = raw[name]
            continue
        value = raw.get(name, definition["default"])
        if control == "boolean":
            if not isinstance(value, bool):
                invalid("PUBLISH_FIELD_TYPE_INVALID", definition["label"] + "必须是开启或关闭状态", name, "使用页面开关重新选择")
        else:
            if value is None:
                value = ""
            if not isinstance(value, str):
                invalid("PUBLISH_FIELD_TYPE_INVALID", definition["label"] + "必须是文本", name, "重新填写该字段")
            value = value.strip()
        active = dependency_active(raw, definition)
        if definition["required"] and active and not value:
            invalid("PUBLISH_FIELD_REQUIRED", definition["label"] + "不能为空", name, "填写" + definition["label"])
        if isinstance(value, str) and definition["max_length"] and len(value) > definition["max_length"]:
            invalid("PUBLISH_FIELD_TOO_LONG", "{}不能超过{}字，当前{}字".format(definition["label"], definition["max_length"], len(value)),
                    name, "缩短" + definition["label"])
        if definition["options"] and value and value not in definition["options"]:
            invalid("PUBLISH_OPTION_INVALID", definition["label"] + "不在允许选项中", name, "使用页面提供的选项")
        if control == "url" and value:
            parsed = urlparse(value)
            if parsed.scheme != "https" or not parsed.netloc:
                invalid("PUBLISH_URL_INVALID", definition["label"] + "必须是有效的 https 链接", name, "填写完整 https:// 地址")
        if control == "datetime" and value:
            validate_datetime(value, name)
        if control == "json" and value:
            validate_chapters(value, name)
        if definition.get("depends_on") and not active and value != definition["default"]:
            dependency = definition["depends_on"]
            invalid("PUBLISH_FIELD_DEPENDENCY", definition["label"] + "依赖" + dependency["field"], name,
                    "先开启" + dependency["field"] + "，或恢复该字段默认状态")
        result[name] = value
    for definition in definitions:
        if definition.get("combined_with"):
            field_name = definition["name"]
            left = str(result.get(definition["combined_with"], ""))
            right = str(result.get(field_name, ""))
            total = len(left) + len(right) + (1 if left and right else 0)
            if total > definition["combined_max"]:
                invalid("PUBLISH_COMBINED_TOO_LONG", "描述与话题合计不能超过{}字，当前{}字".format(definition["combined_max"], total),
                        field_name, "缩短描述或话题文本")
    if platform == "wechat_channels" and kind == "video":
        if result.get("original") and result.get("visibility") == "private":
            invalid("PUBLISH_ORIGINAL_VISIBILITY_CONFLICT", "仅自己可见的视频不能声明原创", "original", "改为公开可见或关闭原创声明")
        result["title"] = result["short_title"]
    return result


def validate_video_source(platform, source, payload=None):
    path = Path(source["absolute_video_path"])
    rules = publishing_contract(platform, "video")["media"]
    if path.suffix.lower() not in rules["formats"]:
        invalid("PUBLISH_VIDEO_FORMAT_INVALID", PLATFORM_NAMES[platform] + "不支持此视频格式", "video_path",
                "转换为 " + "/".join(rules["formats"]) + " 后重新审核")
    if path.stat().st_size > rules["max_size_bytes"]:
        invalid("PUBLISH_VIDEO_TOO_LARGE", PLATFORM_NAMES[platform] + "视频超过大小限制", "video_path",
                "压缩到 {}GB 以内".format(rules["max_size_bytes"] // 1024 ** 3))
    try:
        process = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                  "-show_entries", "stream=codec_name:format=duration", "-of", "json", str(path)],
                                 capture_output=True, text=True, timeout=30)
        metadata = json.loads(process.stdout or "{}") if process.returncode == 0 else {}
        duration = float(metadata.get("format", {}).get("duration", 0))
        codec = (metadata.get("streams") or [{}])[0].get("codec_name")
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError):
        invalid("PUBLISH_VIDEO_PROBE_FAILED", "无法读取视频编码或时长", "video_path", "重新转码并审核 MP4")
    if not 0 < duration <= rules["max_duration_seconds"]:
        invalid("PUBLISH_VIDEO_DURATION_INVALID", PLATFORM_NAMES[platform] + "视频时长超出限制", "video_path",
                "时长需在 0～{} 小时之间".format(rules["max_duration_seconds"] // 3600))
    if rules["codecs"] and codec not in rules["codecs"]:
        invalid("PUBLISH_VIDEO_CODEC_INVALID", PLATFORM_NAMES[platform] + "要求 " + "/".join(rules["codecs"]) + " 编码",
                "video_path", "重新转码并审核视频")
    if platform == "wechat_channels" and (payload or {}).get("original") and duration < 5:
        invalid("PUBLISH_ORIGINAL_DURATION_CONFLICT", "短于 5 秒的视频不能声明原创", "original", "关闭原创声明，或使用至少 5 秒的视频")
    chapters = json.loads((payload or {}).get("chapters_json", "[]") or "[]")
    if chapters and chapters[-1]["start_seconds"] >= duration:
        invalid("PUBLISH_CHAPTERS_DURATION", "章节开始时间不能超过视频时长", "chapters_json", "删除或调整超出视频时长的章节")


def prepare_supported(platform):
    return platform in SUPPORTED_PREPARE
