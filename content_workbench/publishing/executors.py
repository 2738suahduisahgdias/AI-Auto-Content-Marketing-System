import json
import sys
import tempfile
from pathlib import Path

from content_workbench.agents.registry import require_agent_enabled
from content_workbench.domain.errors import DomainError
from content_workbench.jobs.worker import UnknownRemote
from content_workbench.providers.local import LocalExecutors
from .knowledge import publish_knowledge
from .schemas import PLATFORM_NAMES


class PublishingExecutors:
    def __init__(self, service):
        self.service = service
        self.root = service.root

    def mapping(self):
        return {"publish.fields": self.generate_fields, "publish.prepare": self.prepare, "publish.execute": self.execute,
                "publish.login": self.login, "publish.verify": self.verify}

    @staticmethod
    def validate_generated_fields(kind, platforms, payload):
        raw = payload.get("platforms") if isinstance(payload, dict) else None
        if not isinstance(raw, dict):
            raise DomainError("MODEL_SCHEMA_INVALID", "发布 Agent 未返回 platforms 字段对象", 502, "platforms", "重试生成；仍失败时人工填写")
        result = {}
        for platform in platforms:
            fields = raw.get(platform)
            if not isinstance(fields, dict):
                raise DomainError("MODEL_SCHEMA_INVALID", PLATFORM_NAMES[platform] + "缺少字段对象", 502, platform, "重试生成该平台或人工填写")
            contract = publish_knowledge(platform=platform, content_kind=kind)["platforms"][0]["content_types"][0]
            generated_names = {definition["name"] for definition in contract["fields"] if definition["agent_generated"]}
            output = {}
            for definition in contract["fields"]:
                name = definition["name"]
                if name not in generated_names or name not in fields:
                    if name in generated_names and definition["required"]:
                        raise DomainError("PUBLISH_GENERATED_FIELD_REQUIRED", PLATFORM_NAMES[platform] + "缺少必填字段 " + name,
                                          502, platform + "." + name, "重试生成或人工填写该字段")
                    continue
                value = fields[name]
                if not isinstance(value, str):
                    raise DomainError("PUBLISH_GENERATED_FIELD_INVALID", PLATFORM_NAMES[platform] + "的 " + name + " 必须是文本",
                                      502, platform + "." + name, "重试生成或人工填写该字段")
                value = value.strip()
                if definition["required"] and not value:
                    raise DomainError("PUBLISH_GENERATED_FIELD_REQUIRED", PLATFORM_NAMES[platform] + "的 " + name + " 不能为空",
                                      502, platform + "." + name, "重试生成或人工填写该字段")
                if definition["max_length"] and len(value) > definition["max_length"]:
                    raise DomainError("PUBLISH_GENERATED_FIELD_TOO_LONG",
                                      "{}的 {} 不能超过 {} 字，当前 {} 字".format(PLATFORM_NAMES[platform], name, definition["max_length"], len(value)),
                                      502, platform + "." + name, "缩短该字段后保存，或重新生成")
                output[name] = value
            for definition in contract["fields"]:
                if definition.get("combined_with"):
                    total = len(output.get(definition["combined_with"], "")) + len(output.get(definition["name"], "")) + 1
                    if total > definition["combined_max"]:
                        raise DomainError("PUBLISH_GENERATED_FIELD_TOO_LONG", PLATFORM_NAMES[platform] + "的描述与话题合计超长",
                                          502, platform + "." + definition["name"], "缩短描述或话题后重试")
            result[platform] = output
        return result

    @staticmethod
    def model_payload(stdout):
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
            raise DomainError("MODEL_EMPTY_RESPONSE", "发布 Agent 未返回文本", 502, "provider", "检查 Kimi CLI 登录和输出协议")
        try:
            return json.loads(contents[-1])
        except json.JSONDecodeError:
            raise DomainError("MODEL_SCHEMA_INVALID", "发布 Agent 未返回合法 JSON", 502, "provider", "重试生成；仍失败时人工填写")

    def generate_fields(self, job, context):
        config = require_agent_enabled(self.service.db_path, "publish_agent")
        data = job["input"]
        kind = data["content_kind"]
        platforms = data["platforms"]
        source = self.service.source(kind, data["source_id"], data.get("source_file_id"))
        contracts = {platform: publish_knowledge(platform=platform, content_kind=kind)["platforms"][0] for platform in platforms}
        prompt = json.dumps({"operation": "publish.fields", "source": {"title": source["title"],
                             "text": source.get("body") if kind == "article" else source.get("description")},
                             "platforms": platforms, "contracts": contracts, "instructions": data.get("prompt", ""),
                             "agent_supplement": config["prompt"]}, ensure_ascii=False)
        context.progress("model_generate", 0.15)
        agent = self.root / "agents" / "publish-fields-agent.md"
        stdout, _ = context.run_process([LocalExecutors(self.service.workbench).kimi(), "--agent-file", str(agent), "-p", prompt,
                                         "--output-format", "stream-json"], timeout=config["timeout_seconds"], stage="kimi_cli", cwd=self.root)
        fields = self.validate_generated_fields(kind, platforms, self.model_payload(stdout))
        return {"platforms": fields, "provider": "kimi_cli", "model": "unpinned", "auto_saved": False, "auto_published": False}

    def profile(self, platform):
        if platform in ("douyin", "xiaohongshu"):
            return self.root / "data/topic-browser-profile"
        return self.root / "data/publisher-profiles" / platform

    def run(self, context, action, platform, payload=None):
        config = require_agent_enabled(self.service.db_path, "publish_agent")
        with tempfile.TemporaryDirectory(prefix="publishing-job-") as directory:
            use_bridge = platform in ("wechat_channels", "wechat_official_account") and action in ("prepare", "execute")
            worker = "webbridge_worker.py" if use_bridge else "browser_worker.py"
            python = sys.executable if use_bridge else str(self.root / ".venv-topics/bin/python")
            arguments = [python, str(self.root / "content_workbench/publishing" / worker),
                         "--action", action, "--platform", platform]
            if not use_bridge:
                arguments += ["--profile", str(self.profile(platform))]
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
        payload = self.service.resolve_assets(target["payload"], platform, batch["content_kind"])
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
        payload = self.service.resolve_assets(target["payload"], platform, batch["content_kind"])
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

    def verify(self, job, context):
        batch, target = self.service.target(job["input"]["target_id"])
        source = self.service.assert_current(batch)
        platform = target["platform"]
        payload = self.service.resolve_assets(target["payload"], platform, batch["content_kind"])
        result = self.run(context, "verify", platform, {"source": source, "payload": payload, "target_id": target["id"]})
        if result.get("status") == "published" and result.get("published_evidence"):
            self.service.set_target_result(target["id"], "published", result, job_id=job["id"], external_url=result.get("url"))
            return {"target_id": target["id"], "platform": platform, "status": "published", "url": result.get("url")}
        self.service.set_target_result(target["id"], "unknown_remote", result,
                                       {"code": "PUBLISH_NOT_VERIFIED", "message": result.get("error", "后台未核验到发布结果")}, job_id=job["id"])
        return {"target_id": target["id"], "platform": platform, "status": result.get("status", "not_found")}

    def login(self, job, context):
        platform = job["input"].get("platform")
        if platform not in PLATFORM_NAMES:
            raise DomainError("PUBLISH_PLATFORM_INVALID", "发布平台无效", 422, "platform", "使用页面提供的平台登录入口")
        if platform in ("wechat_channels", "wechat_official_account"):
            from .webbridge_worker import Bridge
            url = "https://channels.weixin.qq.com/platform/post/create" if platform == "wechat_channels" else "https://mp.weixin.qq.com/"
            Bridge().call("navigate", {"url": url, "newTab": True, "group_title": "发布预览验证"})
            return {"status": "browser_opened", "transport": "webbridge", "login_verified": False,
                    "next_action": "在 Chrome 的发布预览验证标签组中登录，再重新生成预览"}
        return self.run(context, "login", platform)

    @staticmethod
    def error(platform, stage, result):
        status = result.get("status")
        message = result.get("error") or result.get("message") or "浏览器没有完成发布步骤"
        code = "LOGIN_REQUIRED" if status == "login_required" else "PUBLISH_STEP_FAILED"
        action = result.get("action") or ("在发布中心打开对应平台登录页面，登录后重试" if code == "LOGIN_REQUIRED" else "检查{}、{}和平台页面变化后重试".format(PLATFORM_NAMES[platform], stage))
        return DomainError(code, PLATFORM_NAMES[platform] + "：" + message, 409 if code == "LOGIN_REQUIRED" else 502,
                           result.get("field") or platform, action)
