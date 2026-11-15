from pathlib import Path

from content_workbench.domain.errors import DomainError
from content_workbench.storage.db import PROJECT_ROOT
from content_workbench.topics.kimi_browser import KimiBrowserCollector

PROFILE_URL = "https://www.xiaohongshu.com/explore"
HOT_URL = "https://www.xiaohongshu.com/explore"
AGENT_PATH = PROJECT_ROOT / "agents" / "xiaohongshu-collection-agent.md"


class XHSBrowserCollector(KimiBrowserCollector):
    def __init__(self, root: Path, context, timeout_seconds: int = 900):
        super().__init__(root, context, timeout_seconds)
        self.platform = "xiaohongshu"
        self.platform_label = "小红书"
        self.agent_path = AGENT_PATH
        self.profile_url = PROFILE_URL

    def login(self) -> dict:
        return self.ensure_login(300)

    def collect_hot(self) -> dict:
        self.context.progress("xhs_public_hot", 0.2)
        result = self._request("collect_hot", url=HOT_URL)
        if result["status"] in ("error", "login_required"):
            first = result["errors"][0] if result["errors"] else {}
            raise DomainError(
                first.get("code") or "XHS_HOT_FAILED",
                first.get("message") or "小红书平台热点读取失败",
                502,
                "browser",
                first.get("action") or "检查平台热点入口，不能用推荐feed代替",
            )
        for index, item in enumerate(result["items"], 1):
            item.setdefault("metadata", {})
            item["metadata"].update(source_key="xhs_hot", rank=index)
        self.context.progress("xhs_public_hot_completed", 0.3)
        return result

    def collect_favorites(self, collections: dict[str, str]) -> dict:
        self.ensure_login()
        self.context.progress("xhs_personal_collections", 0.35)
        result = self._request(
            "collect_favorites", profile_url=PROFILE_URL, collections=collections
        )
        if result["status"] in ("error", "login_required"):
            first = result["errors"][0] if result["errors"] else {}
            raise DomainError(
                first.get("code") or "XHS_SYNC_FAILED",
                first.get("message") or "小红书个人收藏夹读取失败",
                502,
                "browser",
                first.get("action") or "核对本人登录、收藏夹名称和页面结构后重试",
            )
        allowed = set(collections)
        for item in result["items"]:
            metadata = item.setdefault("metadata", {})
            if metadata.get("source_key") not in allowed:
                raise DomainError(
                    "XHS_SOURCE_MISMATCH",
                    "收藏作品缺少已配置的精选／竞对／高赞来源归属",
                    502,
                    "browser",
                    "按收藏夹名称重新核对，不把作品归入其他卡片",
                )
        self.context.progress("xhs_personal_collections_completed", 0.7)
        return result
