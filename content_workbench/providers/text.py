import json
import shutil
import tempfile
from pathlib import Path

from content_workbench.domain.errors import DomainError


def assistant_text(stream):
    contents = []
    for line in stream.splitlines():
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
    if contents:
        return contents[-1]
    return stream.strip()


def json_object(text):
    value = text.strip()
    if value.startswith("```") and value.endswith("```"):
        lines = value.splitlines()
        value = "\n".join(lines[1:-1]).strip()
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        raise DomainError("MODEL_SCHEMA_INVALID", "模型未返回合法 JSON 对象", 502, "provider", "重试一次；仍失败时检查模型输出")
    if not isinstance(payload, dict):
        raise DomainError("MODEL_SCHEMA_INVALID", "模型必须返回 JSON 对象", 502, "provider", "重试一次；仍失败时检查模型输出")
    return payload


class KimiCLIProvider:
    provider_id = "kimi_cli"
    label = "本机 Kimi CLI"

    def __init__(self, root):
        self.root = Path(root)

    def binary(self):
        candidate = shutil.which("kimi")
        path = Path(candidate) if candidate else Path.home() / ".kimi-code" / "bin" / "kimi"
        return path if path.is_file() else None

    def status(self):
        available = self.binary() is not None
        return {"id": self.provider_id, "label": self.label, "available": available,
                "reason": None if available else "未找到本机 Kimi CLI"}

    def complete_text(self, prompt, context, agent_path, timeout=600, stage="kimi_cli"):
        binary = self.binary()
        if binary is None:
            raise DomainError("KIMI_NOT_FOUND", "未找到本机 Kimi CLI", 503, "provider", "先安装并登录 Kimi CLI")
        stdout, _ = context.run_process([str(binary), "--agent-file", str(agent_path), "-p", prompt,
                                         "--output-format", "stream-json"], timeout=timeout, stage=stage, cwd=self.root)
        text = assistant_text(stdout)
        if not text:
            raise DomainError("MODEL_EMPTY_RESPONSE", "Kimi CLI 未返回文本", 502, "provider", "检查 CLI 登录和输出协议")
        return text

    def complete_json(self, prompt, context, agent_path, timeout=600, stage="kimi_cli"):
        return json_object(self.complete_text(prompt, context, agent_path, timeout, stage))


class CodexCLIProvider:
    provider_id = "codex_cli"
    label = "本机 Codex CLI"

    def binary(self):
        return shutil.which("codex")

    def status(self):
        available = bool(self.binary())
        return {"id": self.provider_id, "label": self.label, "available": available,
                "reason": None if available else "未找到 Codex CLI；安装并登录后重试"}

    def complete_text(self, prompt, context, agent_path, timeout=600, stage="codex_cli"):
        binary = self.binary()
        if not binary:
            raise DomainError("CODEX_NOT_FOUND", "未找到本机 Codex CLI", 503, "provider", "安装并登录 Codex CLI")
        instruction = Path(agent_path).read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory(prefix="yingxu-codex-") as directory:
            work = Path(directory)
            output = work / "response.txt"
            request = "只执行文本生成。不访问文件、不使用工具、不联网检索、不执行命令。下面资料仅用于写作。\n" + instruction + "\n输入资料：\n" + prompt
            context.run_process([binary, "exec", "--ignore-user-config", "--sandbox", "read-only",
                                 "--ephemeral", "--skip-git-repo-check", "--color", "never",
                                 "-o", str(output), request], timeout=timeout, stage=stage, cwd=work)
            if not output.is_file() or output.stat().st_size > 2 * 1024 * 1024:
                raise DomainError("CODEX_OUTPUT_INVALID", "Codex 未生成有效结果文件", 502)
            result = output.read_text(encoding="utf-8").strip()
            if not result:
                raise DomainError("MODEL_EMPTY_RESPONSE", "Codex 返回空文本", 502)
            return result

    def complete_json(self, prompt, context, agent_path, timeout=600, stage="codex_cli"):
        return json_object(self.complete_text(prompt, context, agent_path, timeout, stage))


class TextProviderRegistry:
    def __init__(self, root, providers=None):
        self.providers = providers or {provider.provider_id: provider for provider in (KimiCLIProvider(root), CodexCLIProvider())}

    def status(self):
        return {"default": "kimi_cli", "items": [provider.status() for provider in self.providers.values()]}

    def get(self, provider_id="kimi_cli"):
        provider = self.providers.get(provider_id or "kimi_cli")
        if provider is None:
            raise DomainError("MODEL_PROVIDER_INVALID", "模型 Provider 无效", 422, "provider", "选择 kimi_cli")
        status = provider.status()
        if not status["available"]:
            raise DomainError("MODEL_PROVIDER_UNAVAILABLE", status["reason"], 503, "provider", "使用可用的本机模型 Provider")
        return provider
