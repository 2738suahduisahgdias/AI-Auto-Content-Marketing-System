from content_workbench.domain.errors import DomainError

ARTICLE_PLATFORMS = ("wechat_official_account", "xiaohongshu")
VIDEO_PLATFORMS = ("douyin", "xiaohongshu", "wechat_channels")
SUPPORTED_PREPARE = {"wechat_official_account", "xiaohongshu", "douyin"}
PLATFORM_NAMES = {
    "wechat_official_account": "公众号",
    "xiaohongshu": "小红书",
    "douyin": "抖音",
    "wechat_channels": "视频号",
}


def text(payload, key, label, maximum, required=True):
    value = str(payload.get(key, "")).strip()
    if required and not value:
        raise DomainError("PUBLISH_FIELD_REQUIRED", label + "不能为空", 422, key, "填写" + label)
    if len(value) > maximum:
        raise DomainError("PUBLISH_FIELD_TOO_LONG", "{}不能超过{}字".format(label, maximum), 422, key, "缩短" + label)
    return value


def validate_payload(kind, platform, payload):
    if not isinstance(payload, dict):
        raise DomainError("PUBLISH_PAYLOAD_INVALID", "发布内容必须是对象", 422, "payload", "按平台表单填写")
    allowed = ARTICLE_PLATFORMS if kind == "article" else VIDEO_PLATFORMS if kind == "video" else ()
    if platform not in allowed:
        raise DomainError("PUBLISH_CONTENT_PLATFORM_MISMATCH", "内容类型与发布平台不匹配", 422, "platform", "文章选择公众号或小红书长文；视频选择抖音、小红书或视频号")
    result = dict(payload)
    if kind == "article":
        result["title"] = text(payload, "title", "标题", 64 if platform == "wechat_official_account" else 200)
        result["body"] = text(payload, "body", "正文", 200000)
        if platform == "wechat_official_account":
            result["author"] = text(payload, "author", "作者", 8, False)
            result["summary"] = text(payload, "summary", "摘要", 120, False)
            result["cover_asset_id"] = text(payload, "cover_asset_id", "封面", 100)
            result["original"] = bool(payload.get("original", False))
            result["comments_enabled"] = bool(payload.get("comments_enabled", True))
    else:
        result["title"] = text(payload, "title", "标题", 300)
        result["description"] = text(payload, "description", "简介", 5000)
        result["tags"] = text(payload, "tags", "标签", 1000, False)
        result["cover_asset_id"] = text(payload, "cover_asset_id", "封面", 100, False)
    return result


def prepare_supported(platform):
    return platform in SUPPORTED_PREPARE
