from .contracts import publishing_contract
from .schemas import ARTICLE_PLATFORMS, PLATFORM_NAMES, VIDEO_PLATFORMS, prepare_supported


def publish_knowledge(platform=None, content_kind=None):
    result = []
    for key, name in PLATFORM_NAMES.items():
        if platform and key != platform:
            continue
        kinds = []
        for kind in ("article", "video"):
            if content_kind and kind != content_kind:
                continue
            if (kind == "article" and key not in ARTICLE_PLATFORMS) or (kind == "video" and key not in VIDEO_PLATFORMS):
                continue
            contract = publishing_contract(key, kind)
            approval = "必须完成机器预审与人工终审" if kind == "video" else "正文必须人工批准"
            media = {**contract["media"], "required": kind == "video" or key == "wechat_official_account",
                     "format": "已批准视频" if kind == "video" else "正文封面/排版图片", "approval": approval}
            kinds.append({"content_kind": kind, "fields": contract["fields"], "media": media, "approval": approval})
        result.append({"platform": key, "platform_name": name, "prepare_supported": prepare_supported(key),
                       "verification": "基础字段已接入；扩展字段按同步状态执行",
                       "content_types": kinds,
                       "workflow": ["生成字段", "保存发布批次", "创建发布预览", "人工确认当前版本", "执行发布", "后台核验"],
                       "boundary": "connected 为已接入写入，stored 为仅保存待接入；非默认 stored 字段未写入时不能通过预览。"})
    return {"contract_version": "2026-10-29", "platforms": result,
            "boundary": "字段与限制来自同一平台契约。平台改版或账号权限差异必须重新核验；生成、填写、预览和发布是不同状态。"}
