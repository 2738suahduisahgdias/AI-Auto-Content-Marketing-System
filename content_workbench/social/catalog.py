CATALOG_VERSION = "local-social-v1"

PLATFORMS = {
    "account": "账号",
    "xhs": "小红书",
    "douyin": "抖音",
    "tiktok": "TikTok",
    "kuaishou": "快手",
    "bilibili": "B站",
    "weibo": "微博",
    "haokan": "好看视频",
    "toutiao": "今日头条",
    "baidu-tieba": "百度贴吧",
    "wechat": "微信",
    "zhihu": "知乎",
    "instagram": "Instagram",
    "x": "X / Twitter",
    "youtube": "YouTube",
    "media_transcript": "视频口播转文字",
}

OPERATION_PATHS = {
    "account": """
points/balance
""",
    "xhs": """
hot/search/list
search/suggestions
note/search
image/search
user/search
product/search
product/detail
product/review/list
product/review/reply/list
product/review/reply/reply/list
note/detail
pgy/note/detail
pgy/creator/profile
pgy/creator/notes/performance
pgy/creator/fans/profile
pgy/creator/fans/summary
pgy/creator/metrics/trend
pgy/creator/commercial/overview
user/id/decrypt
note/share/link
share/info
user/info
user/note/list
note/comment/list
note/comment/sub/list
topic/note/list
""",
    "douyin": """
hot/search/list
search/suggestions
video/search
user/search
product/search
product/detail
video/detail
video/share/link
video/comment/list
video/comment/reply/list
user/info
user/video/list
user/series/list
""",
    "tiktok": """
search/suggestions
user/search
post/search
post/detail
post/comment/list
post/comment/reply/list
user/info
user/post/list
""",
    "kuaishou": """
hot/search/list
search/suggestions
video/search
user/search
video/detail
video/comment/list
video/comment/reply/list
user/info
user/video/list
""",
    "bilibili": """
user/search
search/suggestions
video/search
article/search
content/detail
video/download-links
content/comment/list
content/comment/reply/list
content/like-repost/list
user/info
user/video/list
user/article/list
user/dynamic/list
""",
    "weibo": """
hot/search/list
post/search
post/detail
post/comment/list
post/comment/reply/list
post/liker/list
post/repost/list
user/info
user/post/list
search/suggestions
user/search
user/suggestions
""",
    "haokan": """
video/comment/reply/list
video/comment/list
user/video/list
user/info
video/detail
video/search
user/search
search/suggestions
hot/search/list
""",
    "toutiao": """
user/search
search/suggestions
hot/search/list
post/comment/reply/list
user/info
post/comment/list
user/post/list
post/detail
post/search
""",
    "baidu-tieba": """
forum/post/list
forum/detail
user/followed/forum/list
user/post/list
user/info
search/suggestions
search/users
search/forum/posts
search/general
post/detail
post/comment/reply/list
post/comment/list
post/search
""",
    "wechat": """
hot/search/list
video/search
finder/user/search
video/detail
video/share/url
video/comment/list
video/comment/reply/list
user/info
user/video/list
mp/image_post/search
mp/account/image_post/list
mp/article/search
mp/article/detail
mp/account/info
mp/account/article/list
mp/article/stats
mp/article/comment/list
mp/article/comment/reply/list
""",
    "zhihu": """
user/search
search/suggestions
hot/list
content/search
content/detail
user/info
user/article/list
content/comment/list
content/comment/reply/list
""",
    "instagram": """
user/search
tag/search
post/search
post/detail
post/comment/list
post/comment/reply/list
user/info
user/post/list
""",
    "x": """
user/reply/list
user/search
search/suggestions
post/search
post/detail
post/comment/list
post/comment/reply/list
user/info
user/post/list
""",
    "youtube": """
video/search
video/detail
video/comment/list
video/comment/reply/list
channel/info
user/video/list
search/suggestions
channel/search
""",
    "media_transcript": """
media/video-speech-text/submit
media/video-speech-text/get
""",
}

BROWSER_MODEL_PATHS = {
    "douyin": {"video/search", "video/detail", "video/comment/list", "user/info", "user/video/list"},
    "xhs": {"note/search", "note/detail", "note/comment/list", "user/info", "user/note/list"},
    "bilibili": {"video/search", "content/detail", "content/comment/list", "user/info", "user/video/list"},
    "weibo": {"post/search", "post/detail", "post/comment/list", "user/info", "user/post/list"},
    "wechat": {"video/detail", "video/comment/list", "user/info", "user/video/list", "mp/article/detail",
               "mp/article/comment/list", "mp/account/info", "mp/account/article/list"},
}


def operation_kind(path):
    if "video-speech-text" in path:
        return "transcript"
    if "product" in path or "review" in path:
        return "commerce"
    if "pgy/" in path:
        return "creator_analytics"
    if "comment" in path or "reply/list" in path:
        return "comments"
    if "liker/list" in path or "repost/list" in path or "like-repost/list" in path:
        return "engagement"
    if "download-links" in path:
        return "download_links"
    if "hot/" in path:
        return "hot_list"
    if "share" in path:
        return "share"
    if path.endswith("/info") or path.endswith("/profile"):
        return "profile"
    if "detail" in path or path.endswith("/stats"):
        return "detail"
    if "suggestions" in path:
        return "suggestions"
    if "search" in path:
        return "search"
    if path.endswith("/list"):
        return "user_content"
    return "utility"


def executor_for(platform, path):
    if platform == "douyin" and path == "hot/search/list":
        return "douyin_hot"
    if path in BROWSER_MODEL_PATHS.get(platform, set()):
        return "browser_model"
    if platform == "bilibili" and path == "video/download-links":
        return "local_download"
    if platform == "media_transcript":
        return "local_transcript"
    return None


def operation(platform, path):
    executor = executor_for(platform, path)
    kind = operation_kind(path)
    return {
        "id": platform + ":" + path,
        "platform": platform,
        "platform_label": PLATFORMS[platform],
        "path": path,
        "kind": kind,
        "status": "supported" if executor else "adapter_required",
        "executor": executor,
        "billing": "not_used",
    }


def operations():
    result = []
    for platform, raw_paths in OPERATION_PATHS.items():
        for path in raw_paths.split():
            result.append(operation(platform, path))
    return result


def get_operation(operation_id):
    for item in operations():
        if item["id"] == operation_id:
            return item
    return None


def catalog():
    items = operations()
    supported = sum(item["status"] == "supported" for item in items)
    return {
        "version": CATALOG_VERSION,
        "platforms": [{"id": key, "label": value} for key, value in PLATFORMS.items()],
        "items": items,
        "coverage": {"total": len(items), "supported": supported, "adapter_required": len(items) - supported},
        "runtime": {"external_social_api": False, "billing": "not_used", "default_model_provider": "kimi_cli"},
    }
