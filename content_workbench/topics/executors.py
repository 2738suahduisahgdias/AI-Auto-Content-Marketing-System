import json
import shutil
import tempfile
from pathlib import Path

from content_workbench.agents.registry import require_agent_enabled
from content_workbench.domain.errors import DomainError
from content_workbench.domain.services import Workbench
from content_workbench.topics.industry_connector import fetch_industry
from content_workbench.topics.media_analysis import analyze_video


class TopicExecutors:
    def __init__(self, service):
        self.service = service
        self.root = service.root
        self.workbench = Workbench(service.db_path, self.root)

    def mapping(self):
        return {"topics.login": self.login, "topics.sync": self.sync, "topics.industry": self.industry,
                "topics.recommend": self.recommend, "research.analyze": self.analyze}

    def browser(self, context, action, stage, collection=None, url=None, output=None, wait_seconds=30):
        config = require_agent_enabled(self.service.db_path, "hotspot_agent")
        arguments = [str(self.root / ".venv-topics/bin/python"), str(self.root / "content_workbench/topics/browser_worker.py"),
                     "--action", action, "--profile", str(self.root / "data/topic-browser-profile"),
                     "--wait-seconds", str(wait_seconds)]
        if collection:
            arguments += ["--collection", collection]
        if url:
            arguments += ["--url", url]
        if output:
            arguments += ["--output", str(output)]
        stdout, _ = context.run_process(arguments, timeout=min(config["timeout_seconds"], max(120, wait_seconds + 120)), stage=stage, cwd=self.root)
        try:
            result = json.loads(stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            raise DomainError("BROWSER_PROTOCOL_ERROR", "采集浏览器没有返回有效结果", 502, "browser", "检查 Chrome 是否可用以及页面是否改版")
        if result.get("status") == "login_required":
            raise DomainError("LOGIN_REQUIRED", "采集窗口需要完成抖音登录", 409, "browser", "点击“连接采集窗口”，登录后重新同步")
        if result.get("status") == "error":
            message = result.get("error", "未知采集错误")
            code = "COLLECTION_NOT_FOUND" if message.startswith("COLLECTION_NOT_FOUND") else "BROWSER_SYNC_FAILED"
            raise DomainError(code, "页面采集失败：" + message, 502, "browser", "确认收藏夹名称和页面结构；不要重复刷新")
        return result

    def login(self, job, context):
        result = self.browser(context, "login", "waiting_for_user_login", wait_seconds=1800)
        self.service.ensure_account()
        with self.service.conn() as conn:
            conn.execute("UPDATE wb_source_accounts SET connection_status='ready' WHERE id='source_douyin_main'")
        return result

    def sync(self, job, context):
        run_id = self.service.start_sync("full", {"sources": ["hot", "featured", "competitor", "high_praise"]})
        settings = self.service.settings()
        stats = {"hot": 0, "featured": 0, "competitor": 0, "high_praise": 0, "errors": [], "media_downloaded": 0}
        complete = True
        try:
            try:
                result = self.browser(context, "hot", "douyin_hot_top20")
                for item in result["items"]:
                    self.service.upsert_item(item, "hot", run_id=run_id)
                stats["hot"] = len(result["items"])
                stats["hot_complete"] = len(result["items"]) >= 20
                complete = complete and stats["hot_complete"]
            except DomainError as error:
                stats["errors"].append({"source": "hot", "code": error.code, "message": error.message})
                complete = False
            for key, setting in (("featured", "featured_collection"), ("competitor", "competitor_collection"), ("high_praise", "high_praise_collection")):
                try:
                    title = settings[setting]
                    result = self.browser(context, "favorites", "favorite_" + key, collection=title)
                    item_ids = [self.service.upsert_item(item, key, collection_title=title, run_id=run_id) for item in result["items"]]
                    self.service.reconcile_collection(title, item_ids, run_id, complete=True)
                    stats[key] = len(result["items"])
                except DomainError as error:
                    stats["errors"].append({"source": key, "code": error.code, "message": error.message})
                    complete = False
            status = "succeeded" if complete else "partial"
            self.service.finish_sync(run_id, status, stats, complete)
            return {"sync_run_id": run_id, "status": status, "stats": stats}
        except Exception as error:
            self.service.finish_sync(run_id, "failed", stats, False, {"message": str(error)[:500]})
            raise

    def industry(self, job, context):
        require_agent_enabled(self.service.db_path, "industry_topic_agent")
        settings = self.service.settings()
        context.progress("industry_public_metadata", 0.15)
        items = fetch_industry(settings["industry_scope"])
        for item in items:
            self.service.upsert_item(item, "industry")
        recommendation = self.recommend({**job, "input": {**job["input"], "agent": "industry"}}, context)
        return {"items": len(items), "media_downloaded": 0, "recommendation": recommendation}

    def kimi_json(self, context, agent_name, prompt, timeout=600):
        binary = shutil.which("kimi") or str(Path.home() / ".kimi-code/bin/kimi")
        if not Path(binary).is_file():
            raise DomainError("KIMI_NOT_FOUND", "未找到 Kimi CLI", 503, "provider", "先安装并登录 Kimi CLI")
        agent = self.root / "agents" / (agent_name + ".md")
        stdout, _ = context.run_process([binary, "--agent-file", str(agent), "-p", prompt, "--output-format", "stream-json"],
                                        timeout=timeout, stage=agent_name, cwd=self.root)
        contents = []
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") != "assistant" and event.get("role") != "assistant":
                continue
            content = event.get("content")
            if isinstance(content, list):
                content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
            elif isinstance(content, dict):
                content = content.get("text", "")
            if isinstance(content, str) and content.strip():
                contents.append(content.strip())
        if not contents:
            raise DomainError("MODEL_EMPTY_RESPONSE", "选题Agent未返回内容", 502, "provider", "检查 Kimi CLI 登录状态")
        try:
            payload = json.loads(contents[-1])
        except json.JSONDecodeError:
            raise DomainError("MODEL_SCHEMA_INVALID", "选题Agent返回的不是合法JSON数组", 502, "provider", "重试一次或调整提示词")
        if not isinstance(payload, list) or not 1 <= len(payload) <= 6:
            raise DomainError("MODEL_SCHEMA_INVALID", "选题Agent必须返回1～6个推荐", 502, "provider", "重试或调整提示词")
        for index, item in enumerate(payload):
            if not isinstance(item, dict) or not item.get("title") or not item.get("reason") or not item.get("angle"):
                raise DomainError("MODEL_SCHEMA_INVALID", "第{}个推荐缺少标题、理由或切入".format(index + 1), 502)
            if item.get("audience") not in ("business_owners", "practitioners", "fde"):
                item["audience"] = "business_owners"
            if item.get("pillar") not in ("enterprise_ai", "ai_learning", "ai_marketing", "personal_thinking"):
                item["pillar"] = "enterprise_ai"
        return payload

    def recommend(self, job, context):
        agent = job["input"].get("agent", "douyin")
        if agent not in ("douyin", "industry"):
            raise DomainError("INVALID_TOPIC_AGENT", "推荐Agent类型无效", 422, "agent", "选择 industry 或 douyin")
        config = require_agent_enabled(self.service.db_path, agent + "_topic_agent")
        data = self.service.bootstrap()
        settings = data["settings"]
        sources = data["sources"] if agent == "douyin" else {"industry": data["sources"]["industry"]}
        if not any(sources.values()):
            raise DomainError("NO_TOPIC_SNAPSHOT", "当前没有可分析的真实快照", 409, "snapshot", "先同步热点、收藏或行业资讯")
        context.progress(agent + "_topic_analysis", 0.4)
        prompt = json.dumps({"agent": agent, "industry_scope": settings["industry_scope"],
                             "custom_prompt": settings[agent + "_prompt"] + "\n" + config["prompt"], "sources": sources}, ensure_ascii=False)
        candidates = self.kimi_json(context, agent + "-topic-agent", prompt, config["timeout_seconds"])
        ids = self.service.save_candidates(agent, candidates)
        return {"agent": agent, "candidates": len(ids), "candidate_ids": ids}

    def analyze(self, job, context):
        item_id = job["aggregate_id"]
        item = self.service.get_item(item_id)
        if item["analysis_status"] == "succeeded":
            return {"analysis_id": item["analysis_id"], "cache_hit": True}
        with tempfile.TemporaryDirectory(prefix="topic-analysis-") as directory:
            video = Path(directory) / "source.mp4"
            result = self.browser(context, "download", "download_selected_video", url=item["url"], output=video, wait_seconds=120)
            if result.get("needs_upload"):
                raise DomainError("NEEDS_UPLOAD", "当前页面未能取得可解码视频", 409, "file", "在原链接观看后手动下载，再上传本地视频；其他条目不受影响")
            return analyze_video(self.workbench, self.service, item_id, video, context)
