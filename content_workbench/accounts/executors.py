import json
from pathlib import Path

from content_workbench.accounts.collection_knowledge import error_type
from content_workbench.accounts.existing_browser import run as run_existing_browser
from content_workbench.agents.registry import require_agent_enabled
from content_workbench.domain.errors import DomainError
from content_workbench.storage.db import utcnow
from content_workbench.topics.executors import TopicExecutors


class AccountExecutors:
    def __init__(self, service):
        self.service = service
        self.topics = service.topics
        self.root = self.topics.root.resolve()

    def mapping(self):
        return {"accounts.sync": self.sync, "accounts.recommend": self.recommend, "accounts.daily": self.daily,
                "accounts.login": self.login, "publish.douyin": self.publish_preview}

    def login(self, job, context):
        platform = job["input"].get("platform")
        actions = {"xiaohongshu": "xiaohongshu_login", "douyin_publish": "douyin_publish_login",
                   "wechat_channels": "channels_login", "wechat_official_account": "official_login"}
        if platform not in actions:
            raise DomainError("ACCOUNT_BROWSER_PLATFORM_INVALID", "登录平台无效", 422, "platform", "重新选择登录入口")
        result = self.platform(context, actions[platform], platform + "_login")
        if not result.get("login_verified"):
            return result
        snapshot = self.sync(job, context)
        return {**result, "sync": snapshot, "refresh": "all_account_data"}

    def platform(self, context, action, stage, **kwargs):
        result = run_existing_browser(action)
        if result.get("status") == "login_required":
            raise DomainError("LOGIN_REQUIRED", result.get("error") or "平台创作者后台需要登录", 409, "browser", result.get("action") or "请重新发起登录并完成扫码")
        if result.get("status") == "error":
            raise DomainError("PLATFORM_SYNC_FAILED", "平台采集失败：" + result.get("error", "未知错误"), 502, "browser", result.get("action") or "检查现有浏览器连接后手动重试，不会自动新建浏览器或重复拉取")
        return result

    def sync(self, job, context):
        result = {"accounts": {}, "media_downloaded": 0, "errors": []}
        sources = [("xiaohongshu", "xhs_notes"), ("douyin", "douyin_account"),
                   ("wechat_channels", "channels_account"), ("wechat_official_account", "official_account")]
        for platform, action in sources:
            try:
                snapshot = self.platform(context, action, platform)
                items = snapshot.get("items", [])
                if platform == "xiaohongshu":
                    for item in items:
                        item_id = self.topics.upsert_item(item, "xhs_notes", platform="xiaohongshu")
                        try:
                            self.topics.cache_cover(item_id)
                        except Exception:
                            pass
                profile = {**(snapshot.get("profile") or {}), "connection": "ready" if items else "empty"}
                self.service.save_snapshot(platform, profile, items)
                result["accounts"][platform] = len(items)
                if not items:
                    result["accounts"][platform + "_warning"] = "已打开后台但未读取到内容；账号可能无内容，也可能页面结构已变化，请检查后台列表"
                    result["errors"].append({"platform": platform, "type": "EMPTY_RESULT", "message": "未读取到内容，需确认账号无内容还是结构变化", "action": "检查后台列表，不自动重试", "captured_at": utcnow()})
            except DomainError as error:
                result["accounts"][platform + "_error"] = error.message
                result["errors"].append({"platform": platform, "type": error_type(error.message), "message": error.message, "action": error.action or "按错误类型处理后手动重试", "captured_at": utcnow()})
        errors = [key for key in result["accounts"] if key.endswith("_error")]
        if len(errors) == len(sources):
            details = "；".join("{}：{}".format(key, result["accounts"][key]) for key in errors)
            raise DomainError("ACCOUNTS_UNAVAILABLE", details, 409, "browser", "在接入向导分别登录对应平台后重试；已登录平台检查页面结构")
        return result

    def recommend(self, job, context):
        config = require_agent_enabled(self.topics.db_path, "account_analysis_agent")
        data = self.service.bootstrap()
        if not data["accounts"]:
            raise DomainError("NO_ACCOUNT_SNAPSHOT", "还没有账号日报数据", 409, "accounts", "先同步账号快照，再运行账号分析Agent")
        helper = TopicExecutors(self.topics)
        prompt = json.dumps({"operation": "账号日报分析，输出事实、推断、下一步实验和今日推荐，不得编造指标或稳定规律",
                             "accounts": data["accounts"], "agent_supplement": config["prompt"]}, ensure_ascii=False)
        candidates = helper.kimi_json(context, "douyin-topic-agent", prompt, config["timeout_seconds"])
        ids = self.topics.save_candidates("account_analysis", candidates)
        return {"candidates": len(ids), "candidate_ids": ids}

    def daily(self, job, context):
        snapshot = self.sync(job, context)
        recommendation = self.recommend(job, context)
        return {"snapshot": snapshot, "recommendation": recommendation}

    def publish_preview(self, job, context):
        require_agent_enabled(self.topics.db_path, "publish_agent")
        data = job["input"]
        relative = str(data.get("video_path", "")).replace("\\", "/")
        if not relative or relative.startswith("/") or ".." in Path(relative).parts:
            raise DomainError("PUBLISH_VIDEO_INVALID", "发布视频路径无效", 422, "video_path", "从已人工批准的视频任务中选择成片")
        video = (self.root / relative).resolve()
        with self.topics.conn(readonly=True) as conn:
            approved = conn.execute("""SELECT 1 FROM files f JOIN tasks t ON t.content_id=f.content_id
                WHERE f.relative_path=? AND f.kind='video' AND t.state='approved'""", (relative,)).fetchone()
        if not approved or self.root not in video.parents or video.suffix.lower() != ".mp4" or not video.is_file():
            raise DomainError("PUBLISH_VIDEO_NOT_APPROVED", "只能选择已人工批准且仍存在的 MP4 成片", 409, "video_path", "在视频任务完成人工最终审核后，从发布页重新选择")
        title = str(data.get("title", "")).strip()
        description = str(data.get("description", "")).strip()
        if not title or not description:
            raise DomainError("PUBLISH_TEXT_MISSING", "发布标题和简介不能为空", 422, "title", "填写实际发布标题和简介")
        result = self.platform(context, "publish_preview", "douyin_publish_preview", video=str(video), title=title, description=description)
        return {**result, "final_confirmation": "user_required", "auto_published": False}
