import json
from pathlib import Path

from content_workbench.agents.registry import require_agent_enabled
from content_workbench.domain.errors import DomainError
from content_workbench.topics.executors import TopicExecutors


class AccountExecutors:
    def __init__(self, service):
        self.service = service
        self.topics = service.topics
        self.root = self.topics.root.resolve()

    def mapping(self):
        return {"accounts.sync": self.sync, "accounts.recommend": self.recommend, "accounts.daily": self.daily,
                "publish.douyin": self.publish_preview}

    def platform(self, context, action, stage, **kwargs):
        config = require_agent_enabled(self.topics.db_path, "hotspot_agent")
        arguments = [str(self.root / ".venv-topics/bin/python"), str(self.root / "content_workbench/accounts/platform_worker.py"),
                     "--action", action, "--profile", str(self.root / "data/topic-browser-profile")]
        for key, value in kwargs.items():
            if value is not None:
                arguments += ["--" + key.replace("_", "-"), str(value)]
        stdout, _ = context.run_process(arguments, timeout=config["timeout_seconds"], stage=stage, cwd=self.root)
        result = json.loads(stdout.strip().splitlines()[-1])
        if result.get("status") == "login_required":
            raise DomainError("LOGIN_REQUIRED", "平台创作者后台需要登录", 409, "browser", "在专用采集窗口登录对应平台后重试")
        if result.get("status") == "error":
            raise DomainError("PLATFORM_SYNC_FAILED", "平台采集失败：" + result.get("error", "未知错误"), 502, "browser", "检查账号会话和页面结构")
        return result

    def sync(self, job, context):
        result = {"accounts": {}, "media_downloaded": 0}
        try:
            xhs = self.platform(context, "xhs_notes", "xiaohongshu_notes")
            items = xhs.get("items", [])
            for item in items:
                item_id = self.topics.upsert_item(item, "xhs_notes", platform="xiaohongshu")
                try:
                    self.topics.cache_cover(item_id)
                except Exception:
                    pass
            self.service.save_snapshot("xiaohongshu", {"connection": "ready"}, items)
            result["accounts"]["xiaohongshu"] = len(items)
        except DomainError as error:
            result["accounts"]["xiaohongshu_error"] = error.message
        try:
            douyin = self.platform(context, "douyin_account", "douyin_account")
            items = douyin.get("items", [])
            self.service.save_snapshot("douyin", douyin.get("profile", {}), items)
            result["accounts"]["douyin"] = len(items)
        except DomainError as error:
            result["accounts"]["douyin_error"] = error.message
        if "xiaohongshu_error" in result["accounts"] and "douyin_error" in result["accounts"]:
            details = "；".join("{}：{}".format(name, result["accounts"][key]) for key, name in (("xiaohongshu_error", "小红书"), ("douyin_error", "抖音")))
            raise DomainError("ACCOUNTS_UNAVAILABLE", details, 409, "browser", "在专用采集窗口分别登录小红书和抖音；若已登录，按上方页面错误检查创作者后台结构")
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
