import json
import tempfile
from pathlib import Path

from content_workbench.agents.registry import require_agent_enabled
from content_workbench.domain.errors import DomainError
from content_workbench.jobs.worker import UnknownRemote
from .schemas import PLATFORM_NAMES


class PublishingExecutors:
    def __init__(self, service):
        self.service = service
        self.root = service.root

    def mapping(self):
        return {"publish.prepare": self.prepare, "publish.execute": self.execute, "publish.login": self.login}

    def profile(self, platform):
        if platform in ("douyin", "xiaohongshu"):
            return self.root / "data/topic-browser-profile"
        return self.root / "data/publisher-profiles" / platform

    def run(self, context, action, platform, payload=None):
        config = require_agent_enabled(self.service.db_path, "publish_agent")
        with tempfile.TemporaryDirectory(prefix="publishing-job-") as directory:
            arguments = [str(self.root / ".venv-topics/bin/python"), str(self.root / "content_workbench/publishing/browser_worker.py"),
                         "--action", action, "--platform", platform, "--profile", str(self.profile(platform))]
            if payload is not None:
                path = Path(directory) / "payload.json"
                path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
                arguments += ["--payload-file", str(path)]
            stdout, _ = context.run_process(arguments, timeout=config["timeout_seconds"], stage=action + ":" + platform, cwd=self.root)
        try:
            return json.loads(stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            raise DomainError("PUBLISH_WORKER_PROTOCOL_ERROR", "发布浏览器没有返回有效结果", 502, platform, "查看 data/server.log 中对应发布阶段")

    def prepare(self, job, context):
        batch, target = self.service.target(job["input"]["target_id"])
        source = self.service.assert_current(batch)
        if target["status"] == "published":
            raise DomainError("PUBLISH_ALREADY_RECORDED", "该平台已经发布，不能重复预览执行", 409, "platform", "核对平台后台")
        platform = target["platform"]
        payload = self.service.resolve_assets(target["payload"])
        result = self.run(context, "prepare", platform, {"source": source, "payload": payload, "target_id": target["id"]})
        if result.get("status") == "preview_ready" and result.get("fields_verified"):
            self.service.set_target_result(target["id"], "ready", result, job_id=job["id"])
            return {"target_id": target["id"], "platform": platform, "status": "ready", "auto_published": False}
        error = self.error(platform, "prepare", result)
        self.service.set_target_result(target["id"], "failed", result, error.as_dict(), job_id=job["id"])
        raise error

    def execute(self, job, context):
        batch, target = self.service.target(job["input"]["target_id"])
        if not batch.get("confirmed_at") or target["status"] != "publishing":
            raise DomainError("PUBLISH_CONFIRMATION_REQUIRED", "缺少有效的一键发布确认", 409, "confirmed_at", "先完成预览并由用户确认")
        source = self.service.assert_current(batch)
        platform = target["platform"]
        payload = self.service.resolve_assets(target["payload"])
        result = self.run(context, "execute", platform, {"source": source, "payload": payload, "target_id": target["id"]})
        if result.get("status") == "published" and result.get("published_evidence"):
            self.service.set_target_result(target["id"], "published", result, job_id=job["id"], external_url=result.get("url"))
            return {"target_id": target["id"], "platform": platform, "status": "published", "url": result.get("url")}
        if result.get("status") == "unknown_remote":
            error = {"code": "UNKNOWN_REMOTE", "message": PLATFORM_NAMES[platform] + "点击后的结果无法确认", "action": "打开平台后台核对，禁止直接重试", "retryable": False}
            self.service.set_target_result(target["id"], "unknown_remote", result, error, job_id=job["id"])
            raise UnknownRemote(error["message"])
        error = self.error(platform, "execute", result)
        self.service.set_target_result(target["id"], "failed", result, error.as_dict(), job_id=job["id"])
        raise error

    def login(self, job, context):
        platform = job["input"].get("platform")
        if platform not in PLATFORM_NAMES:
            raise DomainError("PUBLISH_PLATFORM_INVALID", "发布平台无效", 422, "platform", "使用页面提供的平台登录入口")
        return self.run(context, "login", platform)

    @staticmethod
    def error(platform, stage, result):
        status = result.get("status")
        message = result.get("error") or result.get("message") or "浏览器没有完成发布步骤"
        code = "LOGIN_REQUIRED" if status == "login_required" else "PUBLISH_STEP_FAILED"
        action = "在发布中心打开对应平台专用登录窗口，登录后重试" if code == "LOGIN_REQUIRED" else "检查{}、{}和平台页面变化后重试".format(PLATFORM_NAMES[platform], stage)
        return DomainError(code, PLATFORM_NAMES[platform] + "：" + message, 409 if code == "LOGIN_REQUIRED" else 502,
                           result.get("field") or platform, action)
