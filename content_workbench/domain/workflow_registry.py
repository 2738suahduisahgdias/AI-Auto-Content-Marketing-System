ARTICLE_STAGES = [
    {"id": "brief", "label": "内容 brief", "states": ["brief_ready"]},
    {"id": "outline", "label": "大纲", "states": ["outline_draft"]},
    {"id": "draft", "label": "正文与引用", "states": ["draft", "needs_review"]},
    {"id": "review", "label": "人工终审", "states": ["in_review", "approved"]},
    {"id": "export", "label": "导出", "states": ["exported"]},
    {"id": "publish", "label": "人工发布", "states": ["published"]},
    {"id": "retro", "label": "复盘", "states": ["reviewed"]},
]

VIDEO_STAGES = [
    {"id": "brief", "label": "内容 brief", "states": ["brief_ready"]},
    {"id": "script", "label": "本平台口播稿", "states": ["script_draft", "script_approved", "needs_review"]},
    {"id": "audio", "label": "活动音频", "states": ["audio_ready"]},
    {"id": "subtitle", "label": "匹配字幕", "states": ["subtitles_ready"]},
    {"id": "storyboard", "label": "分镜与素材", "states": ["storyboard_ready", "assets_approved"]},
    {"id": "render", "label": "渲染", "states": ["rendered"]},
    {"id": "qc", "label": "质检与终审", "states": ["qc_passed", "approved"]},
    {"id": "publish", "label": "人工发布", "states": ["published"]},
    {"id": "retro", "label": "复盘", "states": ["reviewed"]},
]

PLATFORM_PROFILES = {
    "douyin": {"content_type": "video", "width": 1080, "height": 1920, "fps": 30,
               "video_codec": "h264", "audio_codec": "aac", "render_modes": ["remotion"]},
    "wechat_official_account": {"content_type": "article", "formats": ["markdown", "safe_html"]},
}

REVISION_KINDS = {
    "article": {"brief", "outline", "draft", "export"},
    "video": {"brief", "script", "audio", "subtitle", "storyboard", "render"},
}

DOWNSTREAM = {
    "brief": {"outline", "draft", "script", "audio", "subtitle", "storyboard", "render", "export"},
    "outline": {"draft", "export"}, "draft": {"export"},
    "script": {"audio", "subtitle", "storyboard", "render"},
    "audio": {"subtitle", "storyboard", "render"},
    "subtitle": {"storyboard", "render"}, "storyboard": {"render"},
    "render": set(), "export": set(),
}


def workflow_bootstrap():
    return {
        "article": {"states": ["brief_ready", "outline_draft", "draft", "in_review", "approved", "exported", "published", "reviewed", "needs_review"], "stages": ARTICLE_STAGES},
        "video": {"states": ["brief_ready", "script_draft", "script_approved", "audio_ready", "subtitles_ready", "storyboard_ready", "assets_approved", "rendered", "qc_passed", "approved", "published", "reviewed", "needs_review"], "stages": VIDEO_STAGES},
    }
