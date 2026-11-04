"""Shared text-model selection for local workflows."""
import json
import os
import sqlite3
import tempfile
import sys
from pathlib import Path

from content_workbench.domain.errors import DomainError
from content_workbench.storage.db import connect, dumps, loads

ENGINES = ("codex_cli", "kimi_cli", "model_api")


def model_settings(db_path):
    if not Path(db_path).is_file():
        return {"engine": "codex_cli"}
    try:
        with connect(db_path, readonly=True) as conn:
            row = conn.execute("SELECT value FROM settings WHERE key='system_text_model'").fetchone()
    except sqlite3.OperationalError as error:
        if "no such table: settings" not in str(error):
            raise
        row = None
    return loads(row[0], {}) if row else {"engine": "codex_cli"}


def public_settings(db_path):
    data = dict(model_settings(db_path))
    secret = Path(db_path).parent.parent / "config/text-model-secret.json"
    data["key_configured"] = secret.is_file()
    return data


def save_settings(db_path, values):
    current = model_settings(db_path)
    updated = {**current, **{k: values[k] for k in ("engine", "base_url", "model") if k in values}}
    if updated.get("engine") not in ENGINES:
        raise DomainError("INVALID_MODEL", "请选择支持的文本模型服务", 422)
    if updated["engine"] == "model_api":
        from urllib.parse import urlsplit
        url = urlsplit(updated.get("base_url", ""))
        if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password:
            raise DomainError("INVALID_MODEL_URL", "请填写有效的 API 地址", 422)
        if url.scheme == "http" and url.hostname not in ("127.0.0.1", "localhost", "::1"):
            raise DomainError("INVALID_MODEL_URL", "远程模型 API 请使用 HTTPS", 422)
        if not str(updated.get("model", "")).strip():
            raise DomainError("MODEL_REQUIRED", "请填写 API 模型名称", 422)
    key = values.get("api_key")
    if key:
        if not isinstance(key, str) or len(key) > 4096:
            raise DomainError("INVALID_MODEL_KEY", "API Key 格式无效", 422)
        secret = Path(db_path).parent.parent / "config/text-model-secret.json"
        secret.parent.mkdir(parents=True, exist_ok=True)
        temporary = secret.with_suffix(".tmp")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump({"api_key": key}, stream)
        temporary.replace(secret)
    with connect(db_path) as conn:
        conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES ('system_text_model',?)", (dumps(updated),))
    return public_settings(db_path)


class ModelAPIProvider:
    provider_id = "model_api"

    def __init__(self, root):
        self.root = Path(root)

    def status(self):
        config = model_settings(self.root / "data/content-agent.db")
        available = bool(config.get("base_url") and config.get("model"))
        return {"id": self.provider_id, "label": "模型 API", "available": available,
                "reason": None if available else "请配置模型 API 地址和模型"}

    def complete_text(self, prompt, context, agent_path, timeout=600, stage="model_api"):
        settings = model_settings(self.root / "data/content-agent.db")
        secret = self.root / "config/text-model-secret.json"
        key = json.loads(secret.read_text()).get("api_key") if secret.is_file() else None
        if not settings.get("base_url") or not settings.get("model"):
            raise DomainError("MODEL_API_UNCONFIGURED", "请在模型连接中配置 API 地址和模型", 503)
        body = {"model": settings["model"], "messages": [
            {"role": "system", "content": Path(agent_path).read_text(encoding="utf-8")},
            {"role": "user", "content": prompt}]}
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = "Bearer " + key
        from content_workbench.storage.db import PROJECT_ROOT
        worker = PROJECT_ROOT / "workers/text_api_worker.py"
        request = {"url": settings["base_url"].rstrip("/") + "/chat/completions",
                   "body": body, "headers": headers, "timeout": timeout}
        with tempfile.TemporaryDirectory(prefix="yingxu-model-api-") as directory:
            path = Path(directory) / "request.json"
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as stream:
                json.dump(request, stream)
            stdout, _ = context.run_process([sys.executable, str(worker), str(path)],
                                            timeout=timeout, stage=stage, cwd=self.root)
        try:
            result = json.loads(stdout)
            if result.get("error"):
                raise DomainError("MODEL_API_FAILED", result["error"], 502)
            return result["text"]
        except (ValueError, KeyError, TypeError):
            raise DomainError("MODEL_API_FAILED", "模型 API 返回格式无效", 502) from None

    def complete_json(self, prompt, context, agent_path, timeout=600, stage="model_api"):
        from content_workbench.providers.text import json_object
        return json_object(self.complete_text(prompt, context, agent_path, timeout, stage))


def provider_for(root, engine):
    from content_workbench.providers.text import CodexCLIProvider, KimiCLIProvider
    providers = {"codex_cli": CodexCLIProvider, "kimi_cli": lambda: KimiCLIProvider(root),
                 "model_api": lambda: ModelAPIProvider(root)}
    if engine not in providers:
        raise DomainError("INVALID_TEXT_ENGINE", "该引擎不支持文本生成", 422)
    return providers[engine]()


def test_connection(db_path):
    import subprocess
    root = Path(db_path).parent.parent
    config = model_settings(db_path)
    engine = config.get("engine", "codex_cli")

    class TestContext:
        def run_process(self, arguments, timeout=90, stage=None, cwd=None):
            try:
                result = subprocess.run(arguments, cwd=cwd, capture_output=True, text=True, timeout=timeout)
            except subprocess.TimeoutExpired:
                raise DomainError("MODEL_TEST_TIMEOUT", "模型连接测试超时，请检查登录和网络", 504) from None
            if result.returncode:
                raise DomainError("MODEL_TEST_FAILED", "模型连接失败，请检查所选 CLI 的登录、网络和额度", 502)
            return result.stdout, result.stderr

    from content_workbench.storage.db import PROJECT_ROOT
    result = provider_for(root, engine).complete_json(
        '连接验收。只返回 {"ok": true}，不要使用工具或读取资料。',
        TestContext(), PROJECT_ROOT / "agents/model-connection-agent.md", timeout=90)
    if result.get("ok") is not True:
        raise DomainError("MODEL_TEST_SCHEMA", "模型返回内容未通过连接验收", 502)
    return {"ok": True, "engine": engine}
