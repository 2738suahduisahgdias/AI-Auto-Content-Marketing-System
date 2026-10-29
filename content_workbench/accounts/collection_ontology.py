from content_workbench.publishing.knowledge import publish_knowledge


def publishing_fields(platform, content_kind):
    content = publish_knowledge(platform=platform, content_kind=content_kind)["platforms"][0]["content_types"][0]
    return {field["name"]: {"type": field["control"], "required": field["required"], "max_length": field["max_length"],
                            "sync_status": field["sync_status"], "verification": field["verification"]}
            for field in content["fields"]}


CATEGORY_LABELS = {
    "identity_access": "身份与权限", "account_profile": "账号资料", "content_management": "内容管理",
    "analytics": "数据分析", "interaction": "评论与私信", "research": "热点与收藏",
    "publishing": "发布任务", "scheduling": "定时任务", "assets": "素材与媒体", "export": "数据导出",
}

COMMON_ERRORS = ["LOGIN_REQUIRED", "PERMISSION_DENIED", "STRUCTURE_CHANGED", "RATE_LIMITED", "PARSING_FAILED", "VALIDATION_FAILED", "NETWORK_ERROR"]


def entity(platform, category, title, url, fields, status, usage, write=False, errors=None, refresh="按内容 ID 去重，指标按采集时间追加"):
    return {"id": f"{platform}:{category}", "platform": platform, "category": category, "category_name": CATEGORY_LABELS[category],
            "title": title, "url": url, "status": status, "verification": "已验证" if status == "verified" else "待验证" if status == "unverified" else "待接入",
            "capabilities": {"read": True, "write": write}, "fields": fields, "agent_usage": usage,
            "errors": errors or COMMON_ERRORS, "refresh": refresh, "version": "2026-10-29"}


def base_entities(platform):
    return [
        entity(platform, "identity_access", "账号登录与权限", "平台登录页", {"login_url": "string", "logged_in": "boolean", "verification_required": "boolean"}, "verified", ["login", "session_check"], errors=["LOGIN_REQUIRED", "PERMISSION_DENIED", "NETWORK_ERROR"], refresh="仅在登录失效时由本人重新验证"),
        entity(platform, "account_profile", "账号资料与累计指标", "账号主页/创作者首页", {"account_name": "string|null", "fans": "number|null", "likes": "number|null", "works_count": "number|null", "captured_at": "datetime"}, "verified" if platform == "douyin" else "unverified", ["account_daily", "profile_analysis"]),
        entity(platform, "scheduling", "账号每日增量任务", "accounts.daily", {"schedule_id": "accounts.daily", "expression": "09:30", "timezone": "Asia/Shanghai", "mode": "initial|incremental"}, "verified", ["scheduler", "account_daily"], refresh="首次基线，之后仅增量；失败不自动重试"),
        entity(platform, "assets", "素材与媒体文件", "内容媒体与封面", {"cover_url": "string|null", "source_url": "string|null", "media_type": "video|article|image|audio", "local_path": "string|null"}, "unverified", ["asset_plan", "render", "review"]),
        entity(platform, "export", "官方数据导出", "平台导出能力（未验证）", {"export_supported": "boolean|null", "file_format": "csv|xlsx|null", "file_path": "string|null", "imported_at": "datetime|null", "record_count": "number|null"}, "unverified", ["export", "import", "validation"], errors=["EXPORT_NOT_FOUND", "VALIDATION_FAILED", "PERMISSION_DENIED"], refresh="仅用户发起的一次导出与导入，文件只存本机"),
    ]


def douyin_entities():
    return base_entities("douyin") + [
        entity("douyin", "content_management", "账号作品与公开指标", "https://www.douyin.com/user/self", {"title": "string", "canonical_url": "string", "cover_url": "string|null", "like_count": "number|null", "published_at": "datetime|null"}, "verified", ["account_daily", "content_review"]),
        entity("douyin", "analytics", "创作者数据中心", "https://creator.douyin.com/creator-micro/content/manage", {"views": "number|null", "likes": "number|null", "comments": "number|null", "shares": "number|null", "favorites": "number|null", "retention": "object|null"}, "unverified", ["account_daily", "quality_analysis"]),
        entity("douyin", "interaction", "评论与私信", "创作者互动管理（待验证）", {"comment_id": "string|null", "message_text": "string|null", "author_alias": "string|null", "occurred_at": "datetime|null"}, "unverified", ["lead_review", "comment_analysis"]),
        entity("douyin", "research", "抖音热榜", "https://www.douyin.com/hot", {"rank": "number", "title": "string", "heat": "string|null", "canonical_url": "string", "captured_at": "datetime"}, "verified", ["topic_research", "hotspot_agent"], refresh="每日热点快照，归档保留"),
        entity("douyin", "research", "收藏夹精选/竞品/高赞", "https://www.douyin.com/user/self?showSubTab=favorite_folder&showTab=favorite_collection", {"collection": "string", "title": "string", "author": "string|null", "likes": "number|null", "cover_url": "string|null", "archived": "boolean"}, "verified", ["topic_research", "competitor_analysis"]),
        entity("douyin", "publishing", "视频发布与核验", "https://creator.douyin.com/creator-micro/content/upload", publishing_fields("douyin", "video"), "verified", ["publish_preview", "publish_verify"], write=True),
    ]


def xhs_entities():
    return base_entities("xiaohongshu") + [
        entity("xiaohongshu", "content_management", "笔记管理与笔记 ID", "https://creator.xiaohongshu.com/new/note-manager", {"noteId": "string", "title": "string", "published_at": "datetime", "cover_url": "string|null", "visible_metrics": "array", "visible_text": "string"}, "verified", ["account_daily", "content_review"]),
        entity("xiaohongshu", "analytics", "笔记数据看板", "创作者数据看板（待验证）", {"views": "number|null", "likes": "number|null", "comments": "number|null", "shares": "number|null", "favorites": "number|null", "search_rate": "number|null"}, "unverified", ["account_daily", "search_analysis"]),
        entity("xiaohongshu", "interaction", "笔记评论与私信", "创作者互动管理（待验证）", {"comment_id": "string|null", "message_text": "string|null", "author_alias": "string|null", "occurred_at": "datetime|null"}, "unverified", ["lead_review", "comment_analysis"]),
        entity("xiaohongshu", "research", "近期笔记研究快照", "https://creator.xiaohongshu.com/new/note-manager", {"noteId": "string", "title": "string", "cover_url": "string|null", "published_at": "datetime", "visible_metrics": "array"}, "verified", ["topic_research", "content_review"]),
        entity("xiaohongshu", "publishing", "笔记发布与核验", "小红书创作者发布页", {**publishing_fields("xiaohongshu", "video"), **publishing_fields("xiaohongshu", "article")}, "verified", ["publish_preview", "publish_verify"], write=True),
    ]


def channels_entities():
    return base_entities("wechat_channels") + [
        entity("wechat_channels", "content_management", "视频内容管理与微前端指标", "https://channels.weixin.qq.com/platform/post/list", {"title": "string", "published_at": "datetime", "cover_url": "string|null", "views": "number|null", "likes": "number|null", "comments": "number|null", "shares": "number|null", "favorites": "number|null"}, "verified", ["account_daily", "quality_analysis"]),
        entity("wechat_channels", "analytics", "视频号数据中心", "视频号数据中心（待验证）", {"views": "number|null", "likes": "number|null", "comments": "number|null", "shares": "number|null", "followers": "number|null", "retention": "object|null"}, "unverified", ["account_daily", "quality_analysis"]),
        entity("wechat_channels", "interaction", "评论、弹幕与私信", "互动管理（待验证）", {"comment_id": "string|null", "message_text": "string|null", "author_alias": "string|null", "occurred_at": "datetime|null"}, "unverified", ["lead_review", "comment_analysis"]),
        entity("wechat_channels", "research", "微信消息选题收件箱", "本地微信消息快照", {"tag": "精选|竞品|高赞|行业", "text": "string", "original_url": "string|null", "created_at": "datetime", "archived": "boolean"}, "verified", ["topic_research", "wechat_inbox"], refresh="手动入库，不回写微信"),
        entity("wechat_channels", "publishing", "视频号发表与核验", "https://channels.weixin.qq.com/platform/post/create", publishing_fields("wechat_channels", "video"), "verified", ["publish_preview", "publish_verify"], write=True),
    ]


def official_entities():
    return base_entities("wechat_official_account") + [
        entity("wechat_official_account", "content_management", "公众号文章列表", "https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_list&action=list", {"title": "string", "canonical_url": "string", "published_at": "datetime|null", "readers": "number|null", "likes": "number|null", "comments": "number|null", "shares": "number|null"}, "verified", ["account_daily", "content_review"]),
        entity("wechat_official_account", "analytics", "阅读与关注数据", "公众号数据分析（待验证）", {"readers": "number|null", "completion_rate": "number|null", "shares": "number|null", "new_followers": "number|null", "read_source": "object|null"}, "unverified", ["account_daily", "quality_analysis"]),
        entity("wechat_official_account", "interaction", "留言与关注者消息", "公众号互动管理（待验证）", {"message_id": "string|null", "message_text": "string|null", "author_alias": "string|null", "occurred_at": "datetime|null"}, "unverified", ["lead_review", "comment_analysis"]),
        entity("wechat_official_account", "research", "公众号历史内容研究", "公众号文章列表", {"title": "string", "canonical_url": "string", "published_at": "datetime|null", "content_kind": "article", "visible_text": "string"}, "verified", ["topic_research", "content_review"]),
        entity("wechat_official_account", "publishing", "公众号文章发表与核验", "https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit_v2", publishing_fields("wechat_official_account", "article"), "verified", ["publish_preview", "publish_verify"], write=True),
    ]


def collection_ontology(platform=None, category=None, usage=None):
    entities = douyin_entities() + xhs_entities() + channels_entities() + official_entities()
    if platform:
        entities = [item for item in entities if item["platform"] == platform]
    if category:
        entities = [item for item in entities if item["category"] == category]
    if usage:
        entities = [item for item in entities if usage in item["agent_usage"]]
    return {"entities": entities, "categories": [{"id": key, "name": value} for key, value in CATEGORY_LABELS.items()],
            "boundary": "结构、字段与用途供 Agent 只读调用；verified 为已验证，unverified 为待验证，planned 为待接入。凭据和私信原文不进入 Ontology。"}
