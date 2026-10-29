from .schemas import ARTICLE_PLATFORMS, PLATFORM_NAMES, VIDEO_PLATFORMS, prepare_supported


def field(name, required, maximum, source, description):
    return {"name": name, "required": required, "max_length": maximum, "source": source, "description": description}


def video_fields():
    return [field("title", True, 300, "当前平台脚本/人工标题", "视频短标题，不能夸大或承诺未验证效果"),
            field("description", True, 5000, "母稿或当前平台口播稿", "发布描述、正文口播与必要背景"),
            field("tags", False, 1000, "平台话题/人工标签", "话题标签，按平台格式填写"),
            field("cover_asset_id", False, 100, "已上传图片资产", "封面资产 ID；平台需要时必须选择"),
            field("video_path", True, None, "已人工批准的 MP4 成片", "本地已批准视频文件，不接受未批准来源")]


def article_fields(platform):
    fields = [field("title", True, 64 if platform == "wechat_official_account" else 200, "文章当前修订标题", "文章标题"),
              field("body", True, 200000, "已人工批准的文章正文", "Markdown/HTML 对应的完整正文")]
    if platform == "wechat_official_account":
        fields += [field("author", False, 8, "人工填写", "作者名"),
                   field("summary", False, 120, "正文摘要/人工编辑", "公众号摘要"),
                   field("cover_asset_id", True, 100, "已上传图片资产", "公众号封面资产，必传"),
                   field("original", False, None, "人工确认", "是否声明原创"),
                   field("comments_enabled", False, None, "人工确认", "是否开启评论")]
    else:
        fields.append(field("cover_asset_id", False, 100, "已上传图片资产", "笔记封面，可选"))
    return fields


def publish_knowledge(platform=None, content_kind=None):
    result = []
    for key, name in PLATFORM_NAMES.items():
        kinds = []
        if key in VIDEO_PLATFORMS:
            kinds.append({"content_kind": "video", "fields": video_fields(),
                          "media": {"required": True, "format": "MP4", "approval": "必须完成机器预审与人工终审"}})
        if key in ARTICLE_PLATFORMS:
            kinds.append({"content_kind": "article", "fields": article_fields(key),
                          "media": {"required": key == "wechat_official_account", "format": "封面图片资产", "approval": "正文必须人工批准"}})
        if platform and key != platform:
            continue
        result.append({"platform": key, "platform_name": name, "prepare_supported": prepare_supported(key),
                       "verification": "已验证发布字段" if prepare_supported(key) else "待验证",
                       "content_types": [item for item in kinds if not content_kind or item["content_kind"] == content_kind],
                       "workflow": ["生成字段", "创建发布预览", "人工确认当前版本", "执行发布", "后台核验"],
                       "boundary": "Agent 只按本定义生成与填充，不代表平台已同步或发布成功；最终状态以后台证据为准。"})
    return {"platforms": result, "boundary": "发布知识来自当前真实校验。未接入平台与未验证字段不得伪造成功。"}
