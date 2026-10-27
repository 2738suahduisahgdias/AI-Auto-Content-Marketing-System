import json
import shutil
import tempfile
from pathlib import Path

from content_workbench.agents.registry import require_agent_enabled
from content_workbench.domain.errors import DomainError
from content_workbench.domain.services import Workbench
from content_workbench.media.probe import probe
from content_workbench.media.render import render_remotion
from content_workbench.storage.db import dumps, immediate, new_id, utcnow


class LocalExecutors:
    def __init__(self, workbench):
        self.workbench = workbench
        self.root = workbench.root

    def mapping(self):
        return {
            "article.outline": self.generate_text,
            "article.draft": self.generate_text,
            "video.script": self.generate_text,
            "audio.synthesize": self.synthesize,
            "voice.clone": self.clone,
            "audio.transcribe": self.transcribe,
            "article.export": self.export,
            "video.render": self.render,
        }

    def kimi(self):
        candidate = shutil.which("kimi")
        path = Path(candidate) if candidate else Path.home() / ".kimi-code" / "bin" / "kimi"
        if not path.is_file():
            raise DomainError("KIMI_NOT_FOUND", "未找到本机 Kimi CLI", 503, "provider", "先安装并登录 Kimi CLI")
        return str(path)

    def save_text_result(self, job, text):
        if not text.strip():
            raise DomainError("EMPTY_GENERATION", "模型返回空文本", 502, "provider", "重试或改为人工编辑")
        item_id = job["aggregate_id"]
        kind = {"article.outline": "outline", "article.draft": "draft", "video.script": "script"}[job["kind"]]
        item = self.workbench.get_item(item_id)
        expected = job["input"].get("expected_version")
        active = expected is None or item["version"] == expected
        revision_id = self.workbench.save_revision(item_id, kind, {"text": text.strip(), "format": "markdown" if kind != "script" else "plain"},
                                                   expected if active else None, activate=active, created_by="kimi_cli")
        return {"revision_id": revision_id, "active": active, "model": "unpinned", "provider": "kimi_cli"}

    def generate_text(self, job, context):
        agent_id = {"article.outline": "article_agent", "article.draft": "article_agent", "video.script": "script_agent"}[job["kind"]]
        config = require_agent_enabled(self.workbench.db_path, agent_id)
        item = self.workbench.get_item(job["aggregate_id"])
        context.progress("model_generate", 0.15)
        prompt = json.dumps({"operation": job["kind"], "campaign": item["campaign"],
                             "brief": item["campaign"]["brief"], "input": job["input"].get("prompt", ""),
                             "agent_supplement": config["prompt"]}, ensure_ascii=False)
        agent = self.root / "agents" / "content-item-agent.md"
        stdout, _ = context.run_process([self.kimi(), "--agent-file", str(agent), "-p", prompt,
                                         "--output-format", "stream-json"], timeout=config["timeout_seconds"], stage="kimi_cli", cwd=self.root)
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
            raise DomainError("MODEL_EMPTY_RESPONSE", "Kimi CLI 未返回文本", 502, "provider", "检查 CLI 登录和输出协议")
        try:
            payload = json.loads(contents[-1])
            text = payload["text"]
        except (json.JSONDecodeError, KeyError, TypeError):
            raise DomainError("MODEL_SCHEMA_INVALID", "模型未返回指定的 text JSON", 502, "provider", "重试一次；仍失败时人工编辑")
        return self.save_text_result(job, text)

    def save_asset_result(self, job, asset_id, kind, source_audio=None, metadata=None):
        item_id = job["aggregate_id"]
        item = self.workbench.get_item(item_id)
        expected = job["input"].get("expected_version")
        active = expected is None or item["version"] == expected
        payload = {"asset_id": asset_id, "metadata": metadata or {}}
        revision_id = self.workbench.save_revision(item_id, kind, payload, expected if active else None,
                                                   source_audio_asset_id=source_audio, activate=active, created_by="local_worker")
        with self.workbench.conn() as conn, immediate(conn):
            conn.execute("INSERT OR IGNORE INTO wb_asset_links VALUES (?,?, 'content_item',?,?,NULL,?)",
                         (new_id("assetlink"), asset_id, item_id, kind, utcnow()))
            Workbench.event(conn, "content_item", item_id, "asset.generated", {"asset_id": asset_id, "kind": kind, "active": active})
        return {"asset_id": asset_id, "revision_id": revision_id, "active": active}

    def synthesize(self, job, context):
        item = self.workbench.get_item(job["aggregate_id"])
        text = str(job["input"].get("text") or "").strip()
        if not text:
            script_id = item["active_revisions"].get("script")
            if not script_id:
                raise DomainError("SCRIPT_REQUIRED", "请先生成并选择口播稿", 409, "script", "完成当前平台口播稿")
            text = self.workbench.get_revision(script_id)["payload"].get("text", "")
        voice_id = job["input"].get("voice_id", "system-tingting")
        with self.workbench.conn(readonly=True) as conn:
            voice = conn.execute("SELECT voice_name FROM voice_profiles WHERE id=? AND kind='system'", (voice_id,)).fetchone()
        if not voice:
            raise DomainError("VOICE_NOT_FOUND", "系统音色不存在", 404, "voice_id", "选择已有系统音色")
        with tempfile.TemporaryDirectory(prefix="v2-tts-") as directory:
            work = Path(directory)
            context.run_process(["/usr/bin/say", "-v", voice["voice_name"], "-o", str(work / "speech.aiff"), text],
                                timeout=min(300, max(60, len(text) // 3)), stage="system_tts")
            context.run_process([shutil.which("ffmpeg"), "-v", "error", "-y", "-i", str(work / "speech.aiff"),
                                 "-ac", "1", "-ar", "44100", "-c:a", "pcm_s16le", str(work / "speech.wav")],
                                timeout=120, stage="audio_convert")
            if probe(work / "speech.wav")["duration_seconds"] < 0.05:
                raise DomainError("EMPTY_AUDIO", "生成语音为空或音色不可用", 502, "voice_id", "更换系统音色")
            asset = self.workbench.register_asset(work / "speech.wav", {"kind": "system_tts", "voice_id": voice_id}, "owned")
        return self.save_asset_result(job, asset, "audio", metadata={"voice_id": voice_id, "provider": "macos_say"})

    def clone(self, job, context):
        voice_id = job["input"].get("voice_id")
        with self.workbench.conn(readonly=True) as conn:
            voice = conn.execute("SELECT * FROM voice_profiles WHERE id=? AND kind='clone' AND authorized=1", (voice_id,)).fetchone()
        if not voice:
            raise DomainError("VOICE_CONSENT_REQUIRED", "本人音色不存在或未授权", 403, "voice_id", "选择本人已授权音色样本")
        item = self.workbench.get_item(job["aggregate_id"])
        text = str(job["input"].get("text") or "").strip()
        if not text:
            text = self.workbench.get_revision(item["active_revisions"]["script"])["payload"]["text"]
        sample = (self.root / voice["sample_path"]).resolve()
        if self.root not in sample.parents or not sample.is_file():
            raise DomainError("VOICE_SAMPLE_MISSING", "本人音色样本不存在", 404, "voice_id", "重新保存本人样本")
        with tempfile.TemporaryDirectory(prefix="v2-clone-") as directory:
            work = Path(directory)
            context.run_process([str(self.root / "vendor/openvoice-venv/bin/python"), str(self.root / "workers/openvoice_worker.py"),
                                 "--openvoice-root", str(self.root / "vendor/OpenVoice"), "--ref", str(sample), "--text", text,
                                 "--output", str(work / "clone.wav"), "--work-dir", str(work / "work"), "--speaker", "zh"],
                                timeout=3600, stage="openvoice_clone")
            asset = self.workbench.register_asset(work / "clone.wav", {"kind": "openvoice_clone", "voice_id": voice_id}, "owned")
        return self.save_asset_result(job, asset, "audio", metadata={"voice_id": voice_id, "provider": "openvoice"})

    def transcribe(self, job, context):
        item = self.workbench.get_item(job["aggregate_id"])
        asset_id = job["input"].get("audio_asset_id") or item["manifest"].get("audio_asset_id")
        if not asset_id or asset_id != item["manifest"].get("audio_asset_id"):
            raise DomainError("AUDIO_NOT_ACTIVE", "只能转写当前活动音频", 409, "audio_asset_id", "先选择要转写的活动音频")
        with self.workbench.conn(readonly=True) as conn:
            asset = conn.execute("SELECT * FROM wb_assets WHERE id=?", (asset_id,)).fetchone()
        path = (self.root / asset["storage_key"]).resolve()
        model = job["input"].get("model", "small")
        if model not in ("small", "base"):
            raise DomainError("INVALID_ASR_MODEL", "本地转写仅支持 small/base", 422, "model", "选择 small 或 base")
        with tempfile.TemporaryDirectory(prefix="v2-asr-") as directory:
            output = Path(directory) / "subtitle.srt"
            context.run_process([str(self.root / ".venv-faster-whisper/bin/python"), str(self.root / "workers/whisperx_worker.py"),
                                 "--audio", str(path), "--model", model, "--language", "zh", "--output", str(output)],
                                timeout=3600, stage="faster_whisper")
            subtitle = self.workbench.register_asset(output, {"kind": "faster_whisper", "model": model, "source_audio_asset_id": asset_id}, "owned")
        return self.save_asset_result(job, subtitle, "subtitle", source_audio=asset_id,
                                      metadata={"provider": "faster_whisper", "model": model})

    def export(self, job, context):
        context.progress("article_export", 0.4)
        item, revision = self.workbench.export_article(job["aggregate_id"], job["input"]["revision_id"], job["input"].get("expected_version"))
        return {"revision_id": revision, "manifest": item["manifest"]}

    def render(self, job, context):
        asset, info = render_remotion(self.workbench, job["aggregate_id"], context)
        return self.save_asset_result(job, asset, "render", metadata={"mode": "remotion", "media_info": info})
