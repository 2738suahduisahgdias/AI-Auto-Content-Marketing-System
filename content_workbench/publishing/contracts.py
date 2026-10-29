from copy import deepcopy

GB = 1024 ** 3


def field(name, label, control="text", group="basic", required=False, maximum=None, default="", agent=False,
          sync="stored", verification="verified", description="", options=None, depends=None, **limits):
    return {"name": name, "label": label, "control": control, "group": group, "required": required,
            "max_length": maximum, "default": default, "agent_generated": agent, "sync_status": sync,
            "verification": verification, "description": description, "source": "发布 Agent" if agent else "人工填写/选择",
            "options": options or [], "depends_on": depends, **limits}


def video_path():
    return field("video_path", "已审核视频", "source", "media", True, sync="connected",
                 description="只读取当前来源中已人工批准的 MP4，不由 Agent 生成")


def chapters():
    return field("chapters_json", "视频章节（JSON）", "json", "advanced", default="[]",
                 description='格式：[{"start_seconds":0,"title":"章节名"}]；时间必须递增且小于视频时长')


def scheduling():
    return field("scheduled_at", "定时发布", "datetime", "settings", description="必须晚于当前时间；空值表示立即发布")


def common_dynamic(include_group=False):
    values = [
        field("collection_name", "合集名称", "text", "settings", description="必须与平台后台已有合集名称完全一致"),
        field("location_name", "位置", "text", "advanced", description="必须与平台位置候选完全一致"),
        field("content_type_declaration", "内容类型声明", "text", "settings",
              description="例如 AI 生成、剧情演绎等；以平台当前候选项为准"),
    ]
    if include_group:
        values.append(field("group_chat_name", "群聊", "text", "advanced", description="必须与平台可关联群聊完全一致"))
    return values


CONTRACTS = {
    ("douyin", "video"): {
        "fields": [
            field("title", "作品标题", required=True, maximum=30, agent=True, sync="connected",
                  description="当前账号真实预览显示最多 30 字"),
            field("description", "作品描述", "textarea", required=True, maximum=1000, agent=True, sync="connected",
                  description="描述与话题文本合计最多 1000 字"),
            field("tags", "话题文本", "textarea", agent=True, sync="connected",
                  description="写入作品描述；平台话题实体仍需在预览中核对", combined_with="description", combined_max=1000),
            video_path(),
            field("cover_asset_id", "竖版封面（3:4）", "asset", "media", sync="stored", aspect_ratio=0.75, aspect_tolerance=0.03),
            field("horizontal_cover_asset_id", "横版封面（4:3）", "asset", "media", sync="stored", aspect_ratio=4 / 3, aspect_tolerance=0.03),
            field("official_activity_name", "官方活动", "text", "settings", description="必须与当前可参与官方活动完全一致"),
            field("collection_name", "合集名称", "text", "settings", description="必须与平台已有合集完全一致"),
            field("self_declaration", "自主声明", "text", "settings", description="例如 AI 生成等；以平台当前候选项为准"),
            chapters(),
            field("location_name", "位置", "text", "advanced", description="必须与平台位置候选完全一致"),
            field("visibility", "可见范围", "select", "settings", default="public", options=["public", "friends", "private"],
                  verification="unverified", description="公开/朋友/私密等，实际选项以当前账号为准"),
            scheduling(),
        ],
        "media": {"formats": [".mp4"], "max_duration_seconds": 3600, "max_size_bytes": 16 * GB,
                  "codecs": [], "aspect_suggestions": ["16:9", "9:16", "3:4", "4:3", "9:19.5"],
                  "evidence": "2026-10-29 当前账号上传页：1 小时以内、16G 以内；支持 4K"},
    },
    ("xiaohongshu", "video"): {
        "fields": [
            field("title", "笔记标题", required=True, maximum=20, agent=True, sync="connected"),
            field("description", "笔记正文", "textarea", required=True, maximum=1000, agent=True, sync="connected",
                  description="正文与话题文本合计最多 1000 字"),
            field("tags", "话题文本", "textarea", agent=True, sync="connected",
                  combined_with="description", combined_max=1000),
            video_path(),
            field("cover_asset_id", "封面", "asset", "media", sync="stored"),
            chapters(),
            *common_dynamic(include_group=True),
            field("original", "原创声明", "boolean", "settings", default=False,
                  description="开启后必须读到平台原创状态；未接入时不能忽略"),
            field("visibility", "可见范围", "select", "settings", default="public", options=["public", "friends", "private"],
                  verification="unverified", description="实际选项以当前账号为准"),
            scheduling(),
        ],
        "media": {"formats": [".mp4", ".mov"], "max_duration_seconds": 4 * 3600, "max_size_bytes": 20 * GB,
                  "codecs": [], "aspect_suggestions": ["超过 1080P 建议使用网页端"],
                  "evidence": "2026-10-29 当前账号上传页：4 小时以内、最大 20GB；推荐 MP4/MOV"},
    },
    ("xiaohongshu", "article"): {
        "fields": [
            field("title", "长文标题", required=True, maximum=20, agent=True, sync="connected"),
            field("body", "长文正文", "textarea", required=True, maximum=6000, agent=True, sync="connected", verification="unverified",
                  description="6000 字为长文功能限制资料，仍需当前账号预览核验"),
            field("description", "发布描述", "textarea", maximum=1000, agent=True, sync="connected",
                  description="这是排版后发布设置页的描述，不是长文正文"),
            field("tags", "话题文本", "textarea", agent=True, sync="connected",
                  combined_with="description", combined_max=1000),
            field("template_name", "排版模板", "text", "media", default="理性现代", sync="connected",
                  description="当前连接器已验证“理性现代”；其他模板需重新验收"),
            field("cover_asset_id", "封面补充图片", "asset", "media", sync="stored",
                  description="长文主要由模板生成笔记图片，不能用普通封面字段冒充生成结果"),
            *common_dynamic(),
            field("original", "原创声明", "boolean", "settings", default=False),
            scheduling(),
        ],
        "media": {"formats": [], "evidence": "长文正文经平台模板生成笔记图片，必须等待图片生成完成"},
    },
    ("wechat_channels", "video"): {
        "fields": [
            field("short_title", "短标题", required=True, maximum=16, agent=True, sync="connected",
                  description="当前连接器按平台 16 字输入限制校验"),
            field("description", "视频描述", "textarea", required=True, maximum=2000, agent=True, sync="connected", verification="unverified",
                  description="2000 字为系统安全上限，平台未显示明确计数时需以预览为准"),
            field("tags", "话题文本", "textarea", agent=True, sync="connected",
                  description="可写入话题；话题实体与数量以平台预览为准"),
            video_path(),
            field("cover_asset_id", "封面（3:4）", "asset", "media", sync="stored", aspect_ratio=0.75, aspect_tolerance=0.03),
            field("location_name", "位置", "text", "settings", description="必须与平台位置候选完全一致"),
            field("collection_name", "合集名称", "text", "settings", description="必须与平台已有合集完全一致"),
            field("link_url", "链接", "url", "settings", description="必须是 https 链接，且属于平台允许关联的链接类型"),
            field("activity_name", "活动", "text", "settings", description="空值表示不参与；填写时必须与已有活动一致"),
            scheduling(),
            field("original", "原创声明", "boolean", "settings", default=False,
                  description="视频短于 5 秒或仅自己可见时不能声明原创"),
            field("video_annotation", "视频标注", "text", "advanced", description="必须与平台支持的标注类型和内容一致"),
            field("visibility", "可见范围", "select", "settings", default="public", options=["public", "private"]),
        ],
        "media": {"formats": [".mp4"], "max_duration_seconds": 8 * 3600, "max_size_bytes": 20 * GB,
                  "codecs": ["h264"], "aspect_suggestions": ["建议 720p 及以上", "建议码率 10Mbps 以内"],
                  "evidence": "当前视频号上传规则与既有连接器：MP4/H.264、8 小时、20GB"},
    },
    ("wechat_official_account", "article"): {
        "fields": [
            field("title", "文章标题", required=True, maximum=64, agent=True, sync="connected"),
            field("author", "作者", maximum=8, default="刘量", agent=True, sync="connected"),
            field("body", "文章正文", "textarea", required=True, agent=True, sync="connected",
                  description="不再使用统一的 200000 字限制；图文混排和 HTML 需以编辑器读回为准"),
            field("summary", "摘要", "textarea", maximum=120, agent=True, sync="connected"),
            field("cover_asset_id", "正文封面", "asset", "media", required=True, sync="connected",
                  min_width=900, min_height=383, aspect_ratio=900 / 383, aspect_tolerance=0.03,
                  description="本账号已验收至少 900×383；比例异常可能无法裁剪"),
            field("original", "原创声明", "boolean", "settings", default=False,
                  description="需要平台资格和额外声明确认，未读到状态前不能发布"),
            field("reward_enabled", "赞赏", "boolean", "settings", default=False, depends={"field": "original", "equals": True}),
            field("paid_enabled", "付费阅读", "boolean", "settings", default=False, depends={"field": "original", "equals": True}),
            field("comments_enabled", "开启留言", "boolean", "settings", default=True),
            field("collection_name", "合集名称", "text", "settings", description="必须与平台已有合集完全一致"),
            field("source_url", "原文链接", "url", "settings", description="必须是有效的 https 链接"),
            field("creation_source", "创作来源", "text", "settings", description="以平台当前创作来源声明选项为准"),
            field("in_article_ads_enabled", "文中广告", "boolean", "settings", default=False),
            field("keyword_ads_enabled", "关键词广告", "boolean", "settings", default=False),
            field("comment_ads_enabled", "留言区广告", "boolean", "settings", default=False),
            scheduling(),
        ],
        "media": {"formats": [], "evidence": "标题 64、作者 8、摘要 120 来自真实编辑器；900×383 封面已验收"},
    },
}


def publishing_contract(platform, content_kind):
    try:
        return deepcopy(CONTRACTS[(platform, content_kind)])
    except KeyError:
        raise ValueError("不支持的平台与内容类型：{} / {}".format(platform, content_kind))


def contract_fields(platform, content_kind):
    return publishing_contract(platform, content_kind)["fields"]
