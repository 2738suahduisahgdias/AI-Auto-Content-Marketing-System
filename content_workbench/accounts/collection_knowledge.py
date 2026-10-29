from content_workbench.accounts.collection_ontology import collection_ontology

ERROR_TYPES = [
    "LOGIN_REQUIRED", "PERMISSION_DENIED", "STRUCTURE_CHANGED", "RATE_LIMITED", "EMPTY_RESULT",
    "PARSING_FAILED", "VALIDATION_FAILED", "NETWORK_ERROR", "EXPORT_NOT_FOUND",
]

COLLECTION_KNOWLEDGE = [
    {
        "platform": "douyin", "name": "抖音", "version": "2026-10-29",
        "page": "账号作品列表", "url": "https://www.douyin.com/user/self",
        "login_check": {"url_contains": "login", "text_contains": "登录后查看"},
        "selectors": {"container": "a[href*='/video/']:has(img)", "title": "作品链接最长文本", "cover": "img", "published_at": "作品元数据", "metrics": "like_count"},
        "validation": {"required": ["title", "canonical_url"], "allow_empty_metrics": True},
        "incremental": {"cursor": "platform_item_id + published_at", "overlap": 20, "history": "仅首次全量，后续按 ID 去重与指标追加"},
        "export": {"priority": ["official_export", "official_api", "dom"], "status": "unverified"},
    },
    {
        "platform": "xiaohongshu", "name": "小红书", "version": "2026-10-29",
        "page": "笔记管理", "url": "https://creator.xiaohongshu.com/new/note-manager",
        "login_check": {"url_contains": "login", "cookies": ["web_session", "webId", "a1", "web_sessionid"]},
        "selectors": {"container": ".note-card", "title": ".note-card__title", "cover": ".note-card__media", "published_at": "卡片日期", "note_id": "data-impression.noteTarget.value.noteId"},
        "validation": {"required": ["title", "noteId"], "allow_empty_metrics": True, "unlabeled_numbers": "visible_metrics_only"},
        "incremental": {"cursor": "noteId + published_at", "overlap": 20, "history": "仅首次全量，后续按 ID 去重与指标追加"},
        "export": {"priority": ["official_export", "official_api", "dom"], "status": "unverified"},
    },
    {
        "platform": "wechat_channels", "name": "视频号", "version": "2026-10-29",
        "page": "视频内容管理", "url": "https://channels.weixin.qq.com/platform/post/list",
        "login_check": {"url_contains": "login", "text_contains": "登录视频号助手"},
        "selectors": {"container": ".post-feed-item", "title": "日期与操作项之后的首个标题", "cover": "img.thumb", "published_at": ".time-label", "metrics": ".post-data .data-item .count"},
        "metric_map": {"views": 0, "likes": 1, "comments": 2, "shares": 3, "favorites": 4},
        "validation": {"required": ["title", "published_at"], "allow_empty_metrics": True, "body": "读取文本最完整的微前端节点"},
        "incremental": {"cursor": "platform_item_id + published_at", "overlap": 20, "history": "仅首次全量，后续按 ID 去重与指标追加"},
        "export": {"priority": ["official_export", "official_api", "dom"], "status": "unverified"},
    },
    {
        "platform": "wechat_official_account", "name": "公众号", "version": "2026-10-29",
        "page": "文章列表", "url": "https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_list&action=list",
        "login_check": {"text_contains": ["使用账号登录", "扫码登录"], "token_query": "token"},
        "selectors": {"container": "a[href]", "title": "文章链接最长文本", "cover": "img", "published_at": "文章元数据", "metrics": "带明确标签的阅读/点赞/评论/分享"},
        "validation": {"required": ["title", "canonical_url"], "allow_empty_metrics": True},
        "incremental": {"cursor": "platform_item_id + published_at", "overlap": 50, "history": "仅首次全量，后续按 ID 去重与指标追加"},
        "export": {"priority": ["official_export", "official_api", "dom"], "status": "unverified"},
    },
]


def collection_bootstrap():
    ontology = collection_ontology()
    return {"platforms": COLLECTION_KNOWLEDGE, "error_types": ERROR_TYPES,
            "entities": ontology["entities"], "categories": ontology["categories"],
            "boundary": "只保存页面结构、字段口径与适配版本；不保存 Cookie、Token、密码或私信。原始导出文件仅本机保存。"}


def error_type(error, default="PARSING_FAILED"):
    text = str(error).lower()
    if "login" in text or "登录" in text or "扫码" in text:
        return "LOGIN_REQUIRED"
    if "permission" in text or "权限" in text:
        return "PERMISSION_DENIED"
    if "rate" in text or "频繁" in text or "风控" in text:
        return "RATE_LIMITED"
    if "strict mode" in text or "structure" in text or "结构" in text or "selector" in text:
        return "STRUCTURE_CHANGED"
    if "network" in text or "connection" in text or "timeout" in text:
        return "NETWORK_ERROR"
    return default
