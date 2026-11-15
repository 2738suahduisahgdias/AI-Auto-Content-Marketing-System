"""Kimi CLI browser collection with explicit login and structured evidence."""

import json
import time
from pathlib import Path

from content_workbench.domain.errors import DomainError
from content_workbench.providers.text import KimiCLIProvider
from content_workbench.storage.db import PROJECT_ROOT

PROFILE_URL = "https://www.douyin.com/user/self?showSubTab=favorite_folder&showTab=favorite_collection"
HOT_URL = "https://www.douyin.com/hot"
AGENT_PATH = PROJECT_ROOT / "agents/douyin-collection-agent.md"


class KimiBrowserCollector:
    def __init__(self, root: Path, context, timeout_seconds: int = 600):
        self.root = Path(root)
        self.context = context
        self.timeout_seconds = timeout_seconds
        self.provider = KimiCLIProvider(self.root)
        self.platform = "douyin"
        self.platform_label = "抖音"
        self.agent_path = AGENT_PATH
        self.profile_url = PROFILE_URL

    def _request(self, action: str, **payload) -> dict:
        wait_seconds = int(payload.get("wait_seconds", 0))
        request = {"action": action, "platform": self.platform, **payload}
        for attempt in range(2):
            result = self.provider.complete_json(
                json.dumps(request, ensure_ascii=False),
                self.context,
                self.agent_path,
                timeout=max(120, wait_seconds + 120)
                if wait_seconds
                else self.timeout_seconds,
                stage="kimi_browser_" + action,
            )
            if result.get("status") not in ("ok", "partial", "login_required", "error"):
                raise DomainError(
                    "BROWSER_PROTOCOL_ERROR", "Kimi 采集未返回有效状态", 502, "browser"
                )
            if not isinstance(result.get("items"), list) or not isinstance(
                result.get("errors"), list
            ):
                raise DomainError(
                    "BROWSER_PROTOCOL_ERROR",
                    "Kimi 采集未返回条目和错误列表",
                    502,
                    "browser",
                )
            if result["status"] != "error" or attempt == 1:
                return result
            error_code = str(
                result["errors"][0].get("code", "") if result["errors"] else ""
            )
            if error_code.lower() not in (
                "browser_unavailable",
                "browser_disconnected",
                "mcp_unavailable",
            ):
                return result
            self.context.progress("browser_reconnecting", 0.08)
            time.sleep(1)
        return result

    def ensure_login(self, wait_seconds: int = 300) -> dict:
        self.context.progress("checking_login", 0.05)
        result = self._request(
            "check_login",
            wait_seconds=wait_seconds,
            profile_url=self.profile_url,
        )
        if result["status"] == "error":
            first = result["errors"][0] if result["errors"] else {}
            raise DomainError(
                first.get("code") or "BROWSER_SYNC_FAILED",
                first.get("message") or "Kimi 浏览器连接失败",
                502,
                "browser",
                first.get("action") or "检查固定 Chrome 和 chrome-persistent 后重试",
            )
        if result.get("login_verified") is not True or result["status"] != "ok":
            raise DomainError(
                "LOGIN_REQUIRED",
                self.platform_label + "登录尚未确认，5 分钟内未完成本人登录或验证",
                409,
                "browser",
                "在已打开的固定 Chrome 窗口完成登录；5 分钟超时后重试，窗口和旧数据保留",
            )
        self.context.progress("login_verified", 0.1)
        return {**result, "provider": "kimi_cli"}

    def collect(self, action: str, collection=None, url=None) -> dict:
        login = self.ensure_login()
        if action == "login":
            return {**login, "status": "ok", "login_verified": True}
        requests = {
            "hot": ("collect_hot", {"url": HOT_URL}),
            "favorites": (
                "collect_favorites",
                {"url": PROFILE_URL, "collection": collection},
            ),
            "details": ("collect_details", {"url": url}),
        }
        if action not in requests:
            raise DomainError(
                "BROWSER_ACTION_INVALID", "不支持的抖音采集动作：" + action, 422
            )
        stage = {
            "hot": "douyin_hot_top20",
            "favorites": "favorite_collection",
            "details": "research_metadata",
        }[action]
        self.context.progress(stage, 0.3)
        kimi_action, payload = requests[action]
        result = self._request(kimi_action, **payload)
        if result["status"] == "error":
            first = result["errors"][0] if result["errors"] else {}
            raise DomainError(
                first.get("code") or "BROWSER_SYNC_FAILED",
                first.get("message") or "Kimi 浏览器采集失败",
                502,
                "browser",
                first.get("action") or "检查固定 Chrome 和平台页面后手动重试",
            )
        if action == "details":
            if result.get("details") is None and result["items"]:
                result["details"] = result["items"][0].get("details")
            if not isinstance(result.get("details"), dict):
                raise DomainError(
                    "BROWSER_PROTOCOL_ERROR",
                    "Kimi 未返回作者和互动详情",
                    502,
                    "browser",
                    "重新打开真实作品页读取作者、粉丝、点赞和评论",
                )
        if action == "hot":
            result["items"] = result["items"][:20]
            for index, item in enumerate(result["items"], 1):
                item["rank"] = index
                item["metadata"]["rank"] = index
        self.context.progress(stage + "_completed", 0.9)
        return {
            **result,
            "login_verified": True,
            "provider": "kimi_cli",
        }

    def collect_details_batch(self, urls: list[str]) -> dict:
        if not urls or len(urls) > 4:
            raise DomainError(
                "BROWSER_BATCH_INVALID",
                "每批详情采集必须包含 1～4 个真实作品链接",
                422,
                "url",
            )
        self.ensure_login()
        self.context.progress("research_metadata_batch", 0.3)
        result = self._request("collect_details_batch", urls=urls)
        if result["status"] == "error":
            first = result["errors"][0] if result["errors"] else {}
            raise DomainError(
                first.get("code") or "BROWSER_SYNC_FAILED",
                first.get("message") or "Kimi 批量作品详情采集失败",
                502,
                "browser",
                first.get("action") or "检查固定 Chrome 和平台页面后重试",
            )
        if "results" in result:
            raw_results = result.pop("results")
            if not isinstance(raw_results, list):
                raise DomainError(
                    "BROWSER_PROTOCOL_ERROR",
                    "Kimi 批量详情 results 必须是数组",
                    502,
                    "browser",
                )
            snapshots = {
                item.get("canonical_url"): item
                for item in result["items"]
                if item.get("canonical_url")
            }
            result["items"] = [
                {**snapshots.get(item.get("canonical_url"), {}), **item}
                for item in raw_results
            ]
        for item in result["items"]:
            if not item.get("canonical_url") or not isinstance(
                item.get("details"), dict
            ):
                result["errors"].append(
                    {
                        "code": "METADATA_NOT_FOUND",
                        "message": "作品缺少可核对的作者或互动数据",
                        "action": "打开真实作品页确认后再补全，不猜数字",
                        "item": item,
                    }
                )
        if result["errors"] and result["status"] == "ok":
            result["status"] = "partial"
        self.context.progress("research_metadata_batch_completed", 0.9)
        return {**result, "login_verified": True, "provider": "kimi_cli"}
