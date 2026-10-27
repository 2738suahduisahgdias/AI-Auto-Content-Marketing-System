#!/usr/bin/env python3
import json
import math
import mimetypes
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import threading
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit

from content_workbench.agents.registry import agent_config

os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "30")

PROJECT_ROOT = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("CONTENT_AGENT_ROOT", PROJECT_ROOT)).expanduser().resolve()
DB_PATH = Path(os.environ.get("CONTENT_AGENT_DB", ROOT / "data" / "content-agent.db")).expanduser().resolve()
SEED_PATH = PROJECT_ROOT / "data" / "seed.json"
if not SEED_PATH.is_file():
    SEED_PATH = PROJECT_ROOT / "data" / "seed.example.json"
WEB_ROOT = PROJECT_ROOT / "web"
SCRIPT_AGENT_PATH = PROJECT_ROOT / "agents" / "script-agent.md"
ASSET_AGENT_PATH = PROJECT_ROOT / "agents" / "asset-planning-agent.md"
ASSET_TYPES = ("own", "screen_record", "stock", "ai_image", "ai_video")
WHISPERX_PATH = PROJECT_ROOT / ".venv-whisperx" / "bin" / "whisperx"
WHISPERX_PYTHON = PROJECT_ROOT / ".venv-faster-whisper" / "bin" / "python"
WHISPERX_WORKER = PROJECT_ROOT / "workers" / "whisperx_worker.py"
OPENVOICE_ROOT = PROJECT_ROOT / "vendor" / "OpenVoice"
OPENVOICE_PYTHON = PROJECT_ROOT / "vendor" / "openvoice-venv" / "bin" / "python"
OPENVOICE_WORKER = PROJECT_ROOT / "workers" / "openvoice_worker.py"
OPENVOICE_REFERENCE = OPENVOICE_ROOT / "resources" / "example_reference.mp3"
REMOTION_APP = PROJECT_ROOT / "remotion-app"
REMOTION_PUBLIC = REMOTION_APP / "public"
MAX_JSON = 2 * 1024 * 1024
MAX_UPLOAD = 500 * 1024 * 1024
MAX_CLI_OUTPUT = 2 * 1024 * 1024
MAX_PROMPT = 24000
MAX_ASSET_PROMPT = 60000
DB_LOCK = threading.RLock()
GENERATING = set()
SCRIPT_KEYS = ("master", "douyin", "wechat_channels", "xiaohongshu", "wechat_official_account")
PLATFORMS = ("douyin", "wechat_channels", "xiaohongshu", "wechat_official_account")
V2 = None
QUALITY_KEYS = ("subtitles", "audio", "visual", "copyright", "platform")
PERIODS = ("2h", "1d", "3d", "7d")
SYSTEM_VOICES = (
    ("system-tingting", "Tingting", "婷婷（Tingting）", "清晰自然的 macOS 中文系统音色"),
    ("system-meijia", "Meijia", "美佳（Meijia）", "适合口播的 macOS 中文系统音色"),
    ("system-sinji", "Sinji", "Sinji（中文音色）", "macOS 自带中文系统音色"),
    ("system-eddy", "Eddy (中文（中国大陆）)", "Eddy（中文音色）", "macOS 自带中文（中国大陆）音色"),
    ("system-flo", "Flo (中文（中国大陆）)", "Flo（中文音色）", "macOS 自带中文（中国大陆）音色"),
    ("system-reed", "Reed (中文（中国大陆）)", "Reed（中文音色）", "macOS 自带中文（中国大陆）音色"),
)
STATES = (
    "idea", "topic_approved", "script_drafted", "script_approved", "waiting_audio",
    "transcribed", "assets_planned", "assets_approved", "rendered", "quality_checked",
    "review_required", "approved", "published", "analyzed",
)
UPLOADS = {
    "audio": (("voice",), {".wav", ".mp3", ".m4a", ".aac"}),
    "srt": (("subtitles",), {".srt"}),
    "asset": (("assets", "source"), {".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".mov", ".mp3", ".wav", ".m4a", ".pdf", ".txt"}),
    "video": (("renders",), {".mp4", ".mov", ".webm"}),
}


class ApiError(Exception):
    def __init__(self, status, message, field=None, action=None, item=None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.field = field
        self.action = action
        self.item = item


def infer_error_details(error):
    message = getattr(error, "message", "") or "服务器未能完成此操作，请修正后重试"
    field = getattr(error, "field", None)
    action = getattr(error, "action", None)
    if field and action:
        return message, field, action, getattr(error, "item", None)
    rules = [
        (("授权", "licensed"), "licensed", "逐项上传真实素材、填写来源、关联文件并勾选本人授权；AI建议不能代替授权。"),
        (("母稿", "脚本版本", "五个版本", "脚本"), "scripts", "在脚本页补齐母稿、抖音、视频号、小红书和公众号版本，保存后再确认。"),
        (("SRT", "字幕", "srt"), "srt", "上传或编辑有效 SRT，检查序号、起止时间格式和字幕文本后重试。"),
        (("分镜", "素材清单", "素材类型"), "asset_plan", "在素材页逐项修正时间、类型、来源和文件关联，保存后重试。"),
        (("录音", "音频", "媒体时长", "音频轨道"), "audio", "选择当前任务的有效音频；损坏文件请重新录制或转换后上传。"),
        (("音色", "voice_id", "声音样本"), "voice_id", "选择可用系统音色，或先保存本人授权样本并完成 OpenVoice 真实测试。"),
        (("发布链接", "发布状态", "发布记录", "平台"), "publications", "在发布页核对各平台状态；已发布平台填写真实 http(s) URL，未发布不要虚报。"),
        (("指标", "复盘", "播放/阅读"), "metrics", "在复盘页按 2h/1d/3d/7d 填写非负数字；未读取的单项留空。"),
        (("文本", "TTS"), "text", "编辑非空文本并缩短到限制长度后重试。"),
        (("链接", "URL", "url"), "url", "填写以 http:// 或 https:// 开头的真实链接。"),
        (("文件", "上传", "文件名", "路径", "扩展名"), "file", "重新选择当前步骤允许的有效文件和安全文件名；不要输入目录或路径。"),
        (("Kimi", "WhisperX", "OpenVoice", "CLI", "Agent", "连接"), "settings", "到设置页检查安装与登录状态，完成对应真实连接测试后重试。"),
        (("当前步骤", "前置", "状态"), "workflow", "回到任务当前步骤，先完成页面标出的前置条件和人工确认，不要跳步。"),
    ]
    if not field or not action:
        for keywords, inferred_field, inferred_action in rules:
            if any(keyword.lower() in message.lower() for keyword in keywords):
                field = field or inferred_field
                action = action or inferred_action
                break
    return message, field or "workflow", action or "返回当前页面核对必填项和任务状态，修正后重试；仍失败时查看本地服务日志。", getattr(error, "item", None)


def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    with connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY, title TEXT NOT NULL, pillar TEXT, audience TEXT,
            duration TEXT, rank INTEGER, evidence_json TEXT NOT NULL,
            experiment TEXT, script_angle TEXT, used_at TEXT
        );
        CREATE TABLE IF NOT EXISTS accounts (
            platform TEXT PRIMARY KEY, snapshot_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS hotspot_snapshots (
            platform TEXT PRIMARY KEY, snapshot_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY, value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS voice_profiles (
            id TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT NOT NULL,
            voice_name TEXT, language TEXT NOT NULL, description TEXT NOT NULL,
            sample_path TEXT, sample_name TEXT, duration_seconds REAL,
            authorized INTEGER NOT NULL DEFAULT 0, last_used_at TEXT,
            use_count INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tasks (
            content_id TEXT PRIMARY KEY, topic_id INTEGER, title TEXT NOT NULL,
            pillar TEXT NOT NULL, audience TEXT NOT NULL, pain_point TEXT NOT NULL DEFAULT '',
            angle TEXT NOT NULL DEFAULT '', state TEXT NOT NULL, source_json TEXT NOT NULL DEFAULT '{}',
            scripts_json TEXT NOT NULL DEFAULT '{}', asset_plan_json TEXT NOT NULL DEFAULT '[]',
            quality_json TEXT NOT NULL DEFAULT '{}', publications_json TEXT NOT NULL DEFAULT '{}',
            metrics_json TEXT NOT NULL DEFAULT '{}', retrospective TEXT NOT NULL DEFAULT '',
            script_approved_at TEXT, assets_approved_at TEXT, final_approved_at TEXT,
            published_at TEXT, completed_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT, content_id TEXT NOT NULL,
            kind TEXT NOT NULL, original_name TEXT NOT NULL, relative_path TEXT NOT NULL UNIQUE,
            size INTEGER NOT NULL, media_info_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL,
            FOREIGN KEY(content_id) REFERENCES tasks(content_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, content_id TEXT NOT NULL,
            event TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
            FOREIGN KEY(content_id) REFERENCES tasks(content_id) ON DELETE CASCADE
        );
        """)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
        if "source_json" not in columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN source_json TEXT NOT NULL DEFAULT '{}'")
        if conn.execute("SELECT COUNT(*) FROM topics").fetchone()[0] == 0:
            for topic in seed["topics"]:
                conn.execute(
                    "INSERT INTO topics VALUES (?,?,?,?,?,?,?,?,?,NULL)",
                    (topic["id"], topic["title"], topic.get("pillar", ""), topic.get("audience", ""),
                     topic.get("recommended_duration", ""), topic.get("recommendation_rank", 0),
                     json.dumps(topic.get("evidence", []), ensure_ascii=False), topic.get("experiment", ""),
                     topic.get("script_angle", "")),
                )
        if conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 0:
            for account in seed["accounts"]:
                conn.execute("INSERT INTO accounts VALUES (?,?)", (account["platform"], json.dumps(account, ensure_ascii=False)))
        hotspot_snapshot = seed["douyin_hotspots"]
        conn.execute("INSERT OR IGNORE INTO hotspot_snapshots VALUES (?,?)",
                     ("douyin", json.dumps(hotspot_snapshot, ensure_ascii=False)))
        for voice_id, voice_name, name, description in SYSTEM_VOICES:
            conn.execute("""INSERT OR IGNORE INTO voice_profiles
                            (id,kind,name,voice_name,language,description,sample_path,sample_name,duration_seconds,authorized,last_used_at,use_count,created_at)
                            VALUES (?,?,?,?,?,?,NULL,NULL,NULL,0,NULL,0,?)""",
                         (voice_id, "system", name, voice_name, "中文（中国大陆）", description, now()))
            conn.execute("UPDATE voice_profiles SET voice_name=? WHERE id=? AND kind='system'", (voice_name, voice_id))


def run_process(arguments, timeout, output_limit=MAX_CLI_OUTPUT, label="Kimi CLI", cwd=None):
    process = subprocess.Popen(arguments, cwd=str(cwd or ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8", errors="replace")
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        raise ApiError(504, "{} 调用超过 {} 秒，已终止".format(label, timeout))
    if len(stdout) + len(stderr) > output_limit:
        raise ApiError(502, "{} 输出超过安全限制".format(label))
    if process.returncode:
        message = " ".join(stderr.strip().split())[:500]
        raise ApiError(502, "{} 调用失败".format(label) + ("：{}".format(message) if message else "，请检查本机配置"))
    return stdout, stderr


def agent_runtime(agent_id):
    config = agent_config(DB_PATH, agent_id)
    if not config["enabled"]:
        raise ApiError(409, "该 Agent 已停用，不能创建新任务", "enabled", "到设置页的 Agent 配置中心启用后再试。")
    return config


def find_kimi():
    discovered = shutil.which("kimi")
    candidate = Path(discovered).expanduser() if discovered else Path.home() / ".kimi-code" / "bin" / "kimi"
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return candidate.resolve()
    return None


def detect_kimi():
    binary = find_kimi()
    if not binary:
        return {"installed": False, "version": None, "binary": None, "detection_error": "未找到 Kimi CLI"}
    try:
        stdout, _ = run_process([str(binary), "--version"], 10, 65536)
        lines = [line.strip() for line in stdout.splitlines() if line.strip()]
        version = lines[-1][:100] if lines else None
        if not version:
            raise ApiError(502, "Kimi CLI 未返回版本号")
        return {"installed": True, "version": version, "binary": str(binary), "detection_error": None}
    except ApiError as error:
        return {"installed": True, "version": None, "binary": str(binary), "detection_error": error.message}


def ai_settings():
    with connect() as conn:
        return {row[0]: row[1] for row in conn.execute("SELECT key,value FROM settings")}


def write_ai_settings(values):
    with DB_LOCK, connect() as conn:
        conn.executemany("INSERT OR REPLACE INTO settings(key,value) VALUES (?,?)",
                         [(key, str(value)) for key, value in values.items()])


def record_ai_result(detection, error=None):
    values = {"ai_ready": "0", "ai_last_error": error or ""}
    if detection.get("version"):
        values["ai_version"] = detection["version"]
    if error is None:
        values.update({"ai_ready": "1", "ai_last_success": now(),
                       "ai_ready_version": detection.get("version") or "",
                       "ai_ready_binary": detection.get("binary") or ""})
    write_ai_settings(values)


def get_ai_status():
    detection = detect_kimi()
    settings = ai_settings()
    ready = (detection["installed"] and detection["version"] and settings.get("ai_ready") == "1"
             and settings.get("ai_ready_version") == detection["version"]
             and settings.get("ai_ready_binary") == detection["binary"])
    return {"installed": detection["installed"], "version": detection["version"], "ready": bool(ready),
            "last_success": settings.get("ai_last_success") or None,
            "model": "使用 Kimi CLI 当前默认模型，不固定模型 ID",
            "last_error": detection["detection_error"] or settings.get("ai_last_error") or None,
            "oauth_status": "真实连接已验证" if ready else "尚未通过真实连接测试"}


def parse_kimi_json(stdout, agent_name="Agent"):
    assistant_contents = []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or not (event.get("type") == "assistant" or event.get("role") == "assistant"):
            continue
        content = event.get("content")
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        elif isinstance(content, dict):
            content = content.get("text", "")
        if isinstance(content, str) and content.strip():
            assistant_contents.append(content.strip())
    if not assistant_contents:
        raise ApiError(502, "Kimi CLI 未返回助手内容")
    try:
        return json.loads(assistant_contents[-1])
    except json.JSONDecodeError:
        raise ApiError(502, "{}返回内容不是合法 JSON".format(agent_name))


def validate_scripts_payload(payload):
    if not isinstance(payload, dict) or set(payload) != set(SCRIPT_KEYS):
        raise ApiError(502, "脚本Agent必须恰好返回五个指定字段")
    if any(not isinstance(payload.get(key), str) or not payload[key].strip() for key in SCRIPT_KEYS):
        raise ApiError(502, "脚本Agent返回的五个版本都必须是非空字符串")
    if sum(len(payload[key]) for key in SCRIPT_KEYS) > 1000000:
        raise ApiError(502, "脚本Agent返回内容超过长度限制")
    return {key: payload[key] for key in SCRIPT_KEYS}


def parse_kimi_output(stdout):
    return validate_scripts_payload(parse_kimi_json(stdout, "脚本Agent"))


def run_kimi_agent_json(agent_path, prompt, timeout=600, detection=None):
    detection = detection or detect_kimi()
    if not detection["installed"]:
        raise ApiError(503, "未找到 Kimi CLI，请先安装并登录")
    if detection["detection_error"]:
        raise ApiError(503, detection["detection_error"])
    if not agent_path.is_file():
        raise ApiError(500, "缺少 {}".format(agent_path.name))
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > MAX_ASSET_PROMPT:
        raise ApiError(400, "Agent 输入为空或超过 60000 字符限制")
    stdout, _ = run_process([detection["binary"], "--agent-file", str(agent_path), "-p", prompt,
                             "--output-format", "stream-json"], timeout)
    return parse_kimi_json(stdout, agent_path.stem)


def run_kimi_prompt(prompt, timeout, detection=None):
    return validate_scripts_payload(run_kimi_agent_json(SCRIPT_AGENT_PATH, prompt, timeout, detection))


def test_ai_connection():
    detection = detect_kimi()
    try:
        prompt = "连接测试。只返回五个指定 JSON 字符串字段，每个字段的值都填写“连接成功”，不要添加其他内容。"
        run_kimi_prompt(prompt, 90, detection)
        record_ai_result(detection)
    except ApiError as error:
        record_ai_result(detection, error.message)
        raise
    return get_ai_status()


def get_asset_ai_status():
    settings = ai_settings()
    ready = get_ai_status()["ready"] and settings.get("asset_ai_ready") == "1"
    return {"ready": bool(ready), "status": "已连接" if ready else "未测试",
            "last_success": settings.get("asset_ai_last_success") or None,
            "last_error": settings.get("asset_ai_last_error") or None}


def record_asset_ai_result(error=None):
    values = {"asset_ai_ready": "0" if error else "1", "asset_ai_last_error": error or ""}
    if not error:
        values["asset_ai_last_success"] = now()
    write_ai_settings(values)


def get_render_ai_status():
    settings = ai_settings()
    ready = settings.get("render_ai_ready") == "1" and (REMOTION_APP / "package.json").is_file()
    return {"ready": bool(ready), "status": "已连接" if ready else "未测试",
            "last_success": settings.get("render_last_success") or None,
            "last_error": settings.get("render_last_error") or None}


def record_render_result(error=None):
    values = {"render_ai_ready": "0" if error else "1", "render_last_error": error or ""}
    if not error:
        values["render_last_success"] = now()
    write_ai_settings(values)


def voice_profile_dict(row):
    item = dict(row)
    item["authorized"] = bool(item["authorized"])
    item["clone_status"] = "样本已保存，克隆生成未接入" if item["kind"] == "clone" else None
    return item


def get_voices():
    with connect() as conn:
        systems = [voice_profile_dict(row) for row in conn.execute(
            "SELECT * FROM voice_profiles WHERE kind='system' ORDER BY rowid")]
        clones = [voice_profile_dict(row) for row in conn.execute(
            "SELECT * FROM voice_profiles WHERE kind='clone' ORDER BY created_at DESC")]
    settings = ai_settings()
    media = media_ai_status()
    clone_ready = media["openvoice"]["ready"]
    for profile in clones:
        sample_valid = profile["authorized"] and profile["sample_path"] and (ROOT / profile["sample_path"]).is_file()
        profile["clone_status"] = "可生成克隆录音" if clone_ready and sample_valid else "样本已保存，等待 OpenVoice 真实测试" if sample_valid else "样本或授权无效"
    binaries_ready = Path("/usr/bin/say").is_file() and shutil.which("ffmpeg") and shutil.which("ffprobe")
    ready = bool(binaries_ready and settings.get("tts_ready") == "1")
    return {"system_voices": systems, "clone_profiles": clones,
            "last_used_id": settings.get("last_voice_id") or None,
            "last_success": settings.get("tts_last_success") or None,
            "last_error": settings.get("tts_last_error") or None,
            "capabilities": {"system_ready": ready, "system_status": "已连接" if ready else "未测试",
                             "clone_ready": clone_ready, "clone_status": media["openvoice"]["status"],
                             "synthesis": "macOS say + FFmpeg + OpenVoice V2",
                             "sample_storage": "独立保存于 voice_profiles/{profile_id}/"}}


def record_tts_result(error=None):
    values = {"tts_ready": "0" if error else "1", "tts_last_error": error or ""}
    if not error:
        values["tts_last_success"] = now()
    write_ai_settings(values)


def openvoice_missing_files():
    required = [OPENVOICE_PYTHON, OPENVOICE_WORKER, OPENVOICE_REFERENCE,
                OPENVOICE_ROOT / "checkpoints_v2" / "converter" / "config.json",
                OPENVOICE_ROOT / "checkpoints_v2" / "converter" / "checkpoint.pth",
                OPENVOICE_ROOT / "checkpoints_v2" / "base_speakers" / "ses" / "zh.pth"]
    return [path for path in required if not path.is_file()]


def path_label(path):
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def media_ai_status():
    settings = ai_settings()
    whisperx_installed = WHISPERX_PATH.is_file() and os.access(WHISPERX_PATH, os.X_OK)
    missing = openvoice_missing_files()
    whisperx_ready = whisperx_installed and settings.get("whisperx_ready") == "1"
    clone_ready = not missing and settings.get("clone_ready") == "1"
    return {"whisperx": {"installed": whisperx_installed, "ready": bool(whisperx_ready),
                         "status": "已连接" if whisperx_ready else "未测试" if whisperx_installed else "未就绪",
                         "last_success": settings.get("whisperx_last_success") or None,
                         "last_error": settings.get("whisperx_last_error") or None, "default_model": "small"},
            "openvoice": {"installed": not missing, "ready": bool(clone_ready),
                          "status": "已连接" if clone_ready else "未测试" if not missing else "未就绪",
                          "last_success": settings.get("clone_last_success") or None,
                          "last_error": settings.get("clone_last_error") or None,
                          "missing_files": [path_label(path) for path in missing]}}


def record_media_result(kind, error=None):
    prefix = "whisperx" if kind == "whisperx" else "clone"
    values = {prefix + "_ready": "0" if error else "1", prefix + "_last_error": error or ""}
    if not error:
        values[prefix + "_last_success"] = now()
    write_ai_settings(values)


def parse_json(value, default):
    try:
        return json.loads(value) if value else default
    except (TypeError, json.JSONDecodeError):
        return default


def task_dict(row, conn):
    item = dict(row)
    for key, target, default in (
        ("scripts_json", "scripts", {}), ("asset_plan_json", "asset_plan", []),
        ("quality_json", "quality", {}), ("publications_json", "publications", {}),
        ("metrics_json", "metrics", {}), ("source_json", "source", {}),
    ):
        item[target] = parse_json(item.pop(key), default)
    item["files"] = [file_dict(row) for row in conn.execute(
        "SELECT * FROM files WHERE content_id=? ORDER BY id DESC", (item["content_id"],))]
    item["events"] = [dict(row) for row in conn.execute(
        "SELECT event,detail,created_at FROM events WHERE content_id=? ORDER BY id DESC LIMIT 30",
        (item["content_id"],))]
    return item


def file_dict(row):
    item = dict(row)
    item["media_info"] = parse_json(item.pop("media_info_json"), {})
    item["url"] = "/api/files/{}/media".format(item["id"])
    item["download_url"] = item["url"] + "?download=1"
    return item


def get_task_file(conn, content_id, file_id, kind):
    if not isinstance(file_id, int):
        raise ApiError(400, "文件 ID 无效", "file_id", "从当前任务的文件列表中选择有效文件，不要手工填写其他任务的 ID。")
    row = conn.execute("SELECT * FROM files WHERE id=? AND content_id=? AND kind=?",
                       (file_id, content_id, kind)).fetchone()
    if not row:
        raise ApiError(404, "该任务没有指定的{}文件".format("音频" if kind == "audio" else "字幕"), "file_id",
                       "在下拉列表中重新选择属于当前任务的{}文件。".format("音频" if kind == "audio" else "SRT 字幕"))
    return row


def task_file_path(row):
    path = (ROOT / row["relative_path"]).resolve()
    expected = ROOT / ("subtitles" if row["kind"] == "srt" else "voice") / row["content_id"]
    if expected.resolve() not in path.parents or not path.is_file():
        raise ApiError(404, "任务文件不存在或路径无效", "file",
                       "回到任务文件列表重新上传该文件；不要手工修改相对路径或引用其他任务目录。")
    return path


def get_task(conn, content_id):
    if not re.fullmatch(r"\d{8}-\d{3}", content_id or ""):
        raise ApiError(404, "任务不存在")
    row = conn.execute("SELECT * FROM tasks WHERE content_id=?", (content_id,)).fetchone()
    if not row:
        raise ApiError(404, "任务不存在")
    return task_dict(row, conn)


def add_event(conn, content_id, event, detail=""):
    conn.execute("INSERT INTO events(content_id,event,detail,created_at) VALUES (?,?,?,?)",
                 (content_id, event, detail, now()))


def require_state(task, *states):
    if task["state"] not in states:
        raise ApiError(409, "当前状态为 {}，不能执行此操作".format(task["state"]), "workflow",
                       "回到任务步骤条，先完成当前步骤的文件和人工确认；不要跳过前置步骤或重复已完成操作。")


def update_task(conn, content_id, **fields):
    fields["updated_at"] = now()
    columns = ",".join("{}=?".format(key) for key in fields)
    conn.execute("UPDATE tasks SET {} WHERE content_id=?".format(columns), (*fields.values(), content_id))


def make_directories(content_id):
    paths = [ROOT / "narration" / content_id, ROOT / "voice" / content_id, ROOT / "subtitles",
             ROOT / "assets" / content_id / "source", ROOT / "assets" / content_id / "generated",
             ROOT / "assets" / content_id / "approved", ROOT / "renders" / content_id,
             ROOT / "covers" / content_id, ROOT / "analytics" / content_id, ROOT / "reports" / content_id]
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def create_task(payload):
    title = str(payload.get("title", "")).strip()
    topic_id = payload.get("topic_id")
    hotspot_rank = payload.get("hotspot_rank")
    favorite_collection = payload.get("favorite_collection") or None
    source_count = sum(value is not None for value in (topic_id, hotspot_rank, favorite_collection))
    if source_count > 1:
        raise ApiError(400, "候选选题、热点和收藏夹分类只能选择一个任务来源")
    source = {"type": "manual"}
    with DB_LOCK, connect() as conn:
        if topic_id is not None:
            topic = conn.execute("SELECT * FROM topics WHERE id=?", (topic_id,)).fetchone()
            if not topic:
                raise ApiError(404, "候选选题不存在")
            title = topic["title"]
            pillar, audience, angle = topic["pillar"], topic["audience"], topic["script_angle"]
            pain_point = str(payload.get("pain_point", "")).strip()
            source = {"type": "topic_candidate", "id": topic_id}
        elif hotspot_rank is not None:
            row = conn.execute("SELECT snapshot_json FROM hotspot_snapshots WHERE platform='douyin'").fetchone()
            snapshot = parse_json(row[0], {}) if row else {}
            hotspot = next((item for item in snapshot.get("items", []) if item.get("rank") == hotspot_rank), None)
            if not hotspot:
                raise ApiError(404, "热点快照中不存在该排名")
            title = hotspot["task_title"]
            pillar, audience, angle = hotspot["pillar"], hotspot["audience"], hotspot["angle"]
            pain_point = ""
            source = {"type": "douyin_hotspot", "rank": hotspot["rank"], "title": hotspot["title"],
                      "heat": hotspot["heat"], "relevance": hotspot["relevance"], "url": snapshot["source"],
                      "captured_at": snapshot["captured_at"]}
        else:
            pillar = str(payload.get("pillar", "enterprise_ai"))
            audience = str(payload.get("audience", "business_owners"))
            angle = str(payload.get("angle", "")).strip()
            pain_point = str(payload.get("pain_point", "")).strip()
            if favorite_collection:
                seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
                snapshot = seed["douyin_favorite_collections"]
                collection = next((item for item in snapshot["items"] if item["name"] == favorite_collection), None)
                if not collection or not collection["enabled"]:
                    raise ApiError(400, "该收藏夹分类不纳入当前内容定位")
                source = {"type": "douyin_favorite_collection", "name": collection["name"],
                          "usage": collection["usage"], "url": snapshot["source"],
                          "captured_at": snapshot["captured_at"]}
        if not title or len(title) > 200:
            raise ApiError(400, "请输入 1～200 字的选题标题")
        if pillar not in ("enterprise_ai", "ai_learning", "ai_marketing", "personal_thinking"):
            raise ApiError(400, "内容支柱无效")
        if audience not in ("business_owners", "practitioners", "fde"):
            raise ApiError(400, "目标人群无效")
        prefix = datetime.now().strftime("%Y%m%d")
        rows = conn.execute("SELECT content_id FROM tasks WHERE content_id LIKE ?", (prefix + "-%",)).fetchall()
        sequence = max([int(row[0].split("-")[1]) for row in rows] or [0]) + 1
        if sequence > 999:
            raise ApiError(409, "当天任务编号已满")
        content_id = "{}-{:03d}".format(prefix, sequence)
        timestamp = now()
        conn.execute("""INSERT INTO tasks(content_id,topic_id,title,pillar,audience,pain_point,angle,state,source_json,created_at,updated_at)
                        VALUES (?,?,?,?,?,?,?,'topic_approved',?,?,?)""",
                     (content_id, topic_id, title, pillar, audience, pain_point, angle,
                      json.dumps(source, ensure_ascii=False), timestamp, timestamp))
        if topic_id is not None:
            conn.execute("UPDATE topics SET used_at=? WHERE id=?", (timestamp, topic_id))
        detail = "任务已创建，等待编辑五个脚本版本"
        if source["type"] == "douyin_hotspot":
            detail += "；来源：抖音热点 #{}，{}".format(source["rank"], source["captured_at"])
        elif source["type"] == "douyin_favorite_collection":
            detail += "；来源：抖音收藏夹「{}」".format(source["name"])
        add_event(conn, content_id, "确认选题", detail)
    make_directories(content_id)
    with connect() as conn:
        return get_task(conn, content_id)


def save_scripts(task, payload):
    require_state(task, "topic_approved", "script_drafted")
    scripts = payload.get("scripts")
    if not isinstance(scripts, dict):
        raise ApiError(400, "脚本数据格式无效", "scripts", "在脚本页分别编辑五个文本框后再保存。")
    labels = {"master": "母稿", "douyin": "抖音版", "wechat_channels": "视频号版", "xiaohongshu": "小红书版", "wechat_official_account": "公众号文章版"}
    for key in SCRIPT_KEYS:
        if not isinstance(scripts.get(key), str):
            raise ApiError(400, "缺少{}文本".format(labels[key]), "scripts." + key,
                           "在脚本页的“{}”文本框补齐内容，并保留其他四个版本后保存。".format(labels[key]))
        if len(scripts[key]) > 200000:
            raise ApiError(400, "{}超过 20 万字符".format(labels[key]), "scripts." + key,
                           "精简{}到 20 万字符以内后重新保存。".format(labels[key]))
    with DB_LOCK, connect() as conn:
        update_task(conn, task["content_id"], scripts_json=json.dumps(scripts, ensure_ascii=False), state="script_drafted")
        add_event(conn, task["content_id"], "保存脚本", "母稿与四个平台版本已保存")


def build_script_prompt(task):
    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    strategy = seed["strategy"]
    platform_requirements = {}
    for key, value in seed["platforms"]["platforms"].items():
        platform_requirements[key] = {field: value[field] for field in
                                      ("role", "short_video_duration", "long_video_duration", "content_focus") if field in value}
    evidence = []
    if task.get("topic_id") is not None:
        with connect() as conn:
            row = conn.execute("SELECT evidence_json,experiment FROM topics WHERE id=?", (task["topic_id"],)).fetchone()
        if row:
            evidence = parse_json(row[0], [])[:5]
    context = {
        "task": {key: task.get(key) for key in ("content_id", "title", "pillar", "audience", "pain_point", "angle")},
        "source": task.get("source", {}), "candidate_evidence": evidence,
        "account_positioning": strategy["brand"], "audience": strategy["audiences"].get(task["audience"], {}),
        "editorial_rules": strategy["editorial_rules"], "platform_requirements": platform_requirements,
        "publish_defaults": {"master_short_video_duration": seed["platforms"]["publish_defaults"]["master_short_video_duration"],
                             "human_review_required": True, "auto_publish": False},
    }
    prompt = ("请根据且仅根据以下资料生成五个独立的中文草稿。不要补造证据，不要把单次数据写成稳定规律。"
              "最终只输出符合 agent 约束的五字段 JSON，不执行工具或发布操作。\n" +
              json.dumps(context, ensure_ascii=False, separators=(",", ":")))
    if len(prompt) > MAX_PROMPT:
        raise ApiError(400, "生成资料超过 24000 字符，请缩短痛点或内容切入")
    return prompt


def generate_scripts(task):
    require_state(task, "topic_approved", "script_drafted")
    content_id = task["content_id"]
    with DB_LOCK:
        if content_id in GENERATING:
            raise ApiError(409, "脚本Agent正在为此任务生成，请等待完成")
        GENERATING.add(content_id)
    try:
        status = get_ai_status()
        if not status["ready"]:
            raise ApiError(409, "请先在设置页完成 Kimi 真实连接测试")
        config = agent_runtime("script_agent")
        prompt = config["prompt"] + "\n" + build_script_prompt(task)
        detection = detect_kimi()
        try:
            scripts = run_kimi_prompt(prompt, config["timeout_seconds"], detection)
        except ApiError as error:
            record_ai_result(detection, error.message)
            raise
        with DB_LOCK, connect() as conn:
            current = get_task(conn, content_id)
            require_state(current, "topic_approved", "script_drafted")
            update_task(conn, content_id, scripts_json=json.dumps(scripts, ensure_ascii=False),
                        state="script_drafted", script_approved_at=None)
            add_event(conn, content_id, "脚本Agent生成五版草稿", "Kimi CLI 真实调用成功；等待人工确认，未自动批准")
        record_ai_result(detection)
        with connect() as conn:
            return get_task(conn, content_id)
    finally:
        with DB_LOCK:
            GENERATING.discard(content_id)


def srt_end_seconds(text):
    end = 0.0
    for match in re.finditer(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})", text):
        value = int(match.group(1)) * 3600 + int(match.group(2)) * 60 + int(match.group(3)) + int(match.group(4)) / 1000
        end = max(end, value)
    return end


def asset_audio_duration(task, srt_row, srt_text):
    media_info = parse_json(srt_row["media_info_json"], {})
    with connect() as conn:
        if media_info.get("source_audio_file_id"):
            audio = get_task_file(conn, task["content_id"], media_info["source_audio_file_id"], "audio")
            duration = parse_json(audio["media_info_json"], {}).get("duration_seconds")
            if isinstance(duration, (int, float)) and duration > 0:
                return float(duration)
    for file in task["files"]:
        if file["kind"] == "audio" and isinstance(file["media_info"].get("duration_seconds"), (int, float)) and file["media_info"]["duration_seconds"] > 0:
            return float(file["media_info"]["duration_seconds"])
    subtitle_end = srt_end_seconds(srt_text)
    if subtitle_end <= 0:
        raise ApiError(400, "无法从音频或字幕末尾确定分镜时长")
    return subtitle_end


def validate_asset_plan(payload, duration, allowed_types):
    if not isinstance(payload, list) or not 4 <= len(payload) <= 10:
        raise ApiError(502, "素材规划Agent必须返回 4～10 个分镜")
    required = {"id", "name", "start_seconds", "end_seconds", "asset_type", "description",
                "source", "search_query", "generation_prompt", "license_risk"}
    clean = []
    previous_end = 0.0
    ids = set()
    for index, item in enumerate(payload):
        if not isinstance(item, dict) or not required.issubset(item):
            raise ApiError(502, "第 {} 个分镜字段不完整".format(index + 1))
        if any(not isinstance(item.get(key), str) for key in required - {"start_seconds", "end_seconds"}):
            raise ApiError(502, "第 {} 个分镜文本字段类型无效".format(index + 1))
        if not item["id"].strip() or not item["name"].strip() or item["id"] in ids:
            raise ApiError(502, "分镜 ID 为空或重复")
        ids.add(item["id"])
        start, end = item["start_seconds"], item["end_seconds"]
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in (start, end)):
            raise ApiError(502, "第 {} 个分镜时间必须是数字".format(index + 1))
        if start < 0 or end <= start or start < previous_end or end > duration + 0.2:
            raise ApiError(502, "第 {} 个分镜时间越界、重叠或顺序无效".format(index + 1))
        if item["asset_type"] not in allowed_types:
            raise ApiError(502, "第 {} 个分镜使用了未允许的素材类型".format(index + 1))
        previous_end = end
        clean.append({"id": item["id"].strip() or uuid.uuid4().hex, "name": item["name"].strip()[:300],
                      "source": item["source"].strip()[:1000], "licensed": False, "file_id": None, "note": "",
                      "order": index, "start_seconds": round(float(start), 3), "end_seconds": round(float(end), 3),
                      "asset_type": item["asset_type"], "description": item["description"].strip()[:3000],
                      "search_query": item["search_query"].strip()[:1000],
                      "generation_prompt": item["generation_prompt"].strip()[:3000],
                      "license_risk": item["license_risk"].strip()[:2000]})
    return clean


def allowed_asset_types(value):
    if not isinstance(value, list) or not value:
        raise ApiError(400, "请至少允许一种素材类型", "allowed_types", "勾选自有素材、屏幕录制、合法素材库、AI 图像或 AI 视频中的至少一项。")
    if any(item not in ASSET_TYPES for item in value):
        raise ApiError(400, "素材类型无效", "allowed_types", "只使用页面提供的五种素材类型，移除无效值后重试。")
    return tuple(dict.fromkeys(value))


def generate_asset_plan(task, payload):
    require_state(task, "transcribed", "assets_planned")
    allowed = allowed_asset_types(payload.get("allowed_types"))
    with connect() as conn:
        if payload.get("file_id") is not None:
            srt_row = get_task_file(conn, task["content_id"], payload["file_id"], "srt")
        else:
            srt_row = conn.execute("SELECT * FROM files WHERE content_id=? AND kind='srt' ORDER BY id DESC LIMIT 1",
                                   (task["content_id"],)).fetchone()
    if not srt_row:
        raise ApiError(409, "请先准备当前任务的 SRT 字幕")
    srt_path = task_file_path(srt_row)
    srt_text = srt_path.read_text(encoding="utf-8-sig")
    if len(srt_text) > 5 * 1024 * 1024:
        raise ApiError(400, "SRT 超过 5MB，无法用于分镜")
    duration = asset_audio_duration(task, srt_row, srt_text)
    master = task["scripts"].get("master", "").strip()
    if not master:
        raise ApiError(409, "母稿为空，无法生成分镜")
    context = {"title": task["title"], "master_script": master, "srt": srt_text,
               "audio_duration_seconds": duration, "allowed_asset_types": allowed,
               "requirements": "返回4～10个不重叠分镜；end_seconds不得超过音频+0.2秒；只给建议，不下载、不生成媒体、不代表授权"}
    config = agent_runtime("asset_planning_agent")
    prompt = config["prompt"] + "\n根据当前任务的母稿、SRT和音频时长生成分镜建议，严格遵守agent JSON协议。\n" + json.dumps(context, ensure_ascii=False, separators=(",", ":"))
    if len(prompt) > MAX_ASSET_PROMPT:
        raise ApiError(400, "分镜输入超过 60000 字符，请使用较短母稿或字幕")
    content_id = task["content_id"]
    with DB_LOCK:
        if content_id in GENERATING:
            raise ApiError(409, "当前任务已有生成操作进行中")
        GENERATING.add(content_id)
    try:
        if not get_ai_status()["ready"]:
            raise ApiError(409, "请先完成 Kimi 真实连接测试")
        detection = detect_kimi()
        try:
            raw = run_kimi_agent_json(ASSET_AGENT_PATH, prompt, config["timeout_seconds"], detection)
            plan = validate_asset_plan(raw, duration, set(allowed))
        except ApiError as error:
            record_asset_ai_result(error.message)
            raise
        with DB_LOCK, connect() as conn:
            current = get_task(conn, content_id)
            require_state(current, "transcribed", "assets_planned")
            update_task(conn, content_id, asset_plan_json=json.dumps(plan, ensure_ascii=False),
                        state="assets_planned", assets_approved_at=None)
            add_event(conn, content_id, "素材规划Agent生成分镜",
                      "{} 条建议 · 尚未下载素材或确认授权".format(len(plan)))
        record_asset_ai_result()
        with connect() as conn:
            return get_task(conn, content_id)
    finally:
        with DB_LOCK:
            GENERATING.discard(content_id)


def test_asset_agent():
    prompt = json.dumps({"title": "分镜连接测试", "master_script": "选一个真实任务，明确交付结果。",
                         "srt": "1\n00:00:00,000 --> 00:00:04,000\n选一个真实任务\n2\n00:00:04,000 --> 00:00:08,000\n明确交付结果\n",
                         "audio_duration_seconds": 8, "allowed_asset_types": ["own", "screen_record"],
                         "requirements": "用4个分镜覆盖8秒，只返回建议，不代表素材已下载或授权"}, ensure_ascii=False)
    try:
        raw = run_kimi_agent_json(ASSET_AGENT_PATH, prompt, 600)
        plan = validate_asset_plan(raw, 8, {"own", "screen_record"})
        record_asset_ai_result()
    except ApiError as error:
        record_asset_ai_result(error.message)
        raise
    result = get_asset_ai_status()
    result["validated_shots"] = len(plan)
    return result


def save_assets(task, payload):
    require_state(task, "transcribed", "assets_planned")
    plan = payload.get("asset_plan")
    if not isinstance(plan, list) or len(plan) > 100:
        raise ApiError(400, "素材清单格式无效", "asset_plan", "在素材页保留 1～100 个有效分镜条目后重新保存。")
    clean = []
    for index, item in enumerate(plan):
        if not isinstance(item, dict):
            raise ApiError(400, "第 {} 个分镜格式无效".format(index + 1), "asset_plan[{}]".format(index),
                           "将第 {} 项填写为完整分镜，或移除该项后保存。".format(index + 1))
        start, end = item.get("start_seconds"), item.get("end_seconds")
        if start is None and end is None:
            start = end = None
        else:
            invalid_start = isinstance(start, bool) or not isinstance(start, (int, float)) or not math.isfinite(start)
            invalid_end = isinstance(end, bool) or not isinstance(end, (int, float)) or not math.isfinite(end)
            if invalid_start or invalid_end:
                field = "start_seconds" if invalid_start else "end_seconds"
                raise ApiError(400, "第 {} 项时间必须是数字".format(index + 1), "asset_plan[{}].{}".format(index, field),
                               "把第 {} 项的{}改为非负数字，并保证开始时间小于结束时间。".format(index + 1, "开始秒" if invalid_start else "结束秒"))
            if start < 0:
                raise ApiError(400, "第 {} 项开始秒不能小于 0".format(index + 1), "asset_plan[{}].start_seconds".format(index),
                               "把第 {} 项开始秒改为 0 或更大的数字。".format(index + 1))
            if end <= start:
                raise ApiError(400, "第 {} 项结束秒必须大于开始秒".format(index + 1), "asset_plan[{}].end_seconds".format(index),
                               "把第 {} 项结束秒调到开始秒之后，并与前后镜头保持不重叠。".format(index + 1))
        asset_type = item.get("asset_type") or "own"
        if asset_type not in ASSET_TYPES:
            raise ApiError(400, "第 {} 项素材类型无效".format(index + 1), "asset_plan[{}].asset_type".format(index),
                           "把第 {} 项类型改为 own、screen_record、stock、ai_image 或 ai_video。".format(index + 1))
        clean.append({
            "id": str(item.get("id") or uuid.uuid4().hex), "name": str(item.get("name", "")).strip()[:300],
            "source": str(item.get("source", "")).strip()[:1000], "licensed": bool(item.get("licensed")),
            "file_id": item.get("file_id") if isinstance(item.get("file_id"), int) else None,
            "note": str(item.get("note", "")).strip()[:1000], "order": index,
            "start_seconds": start, "end_seconds": end, "asset_type": asset_type,
            "description": str(item.get("description") or "").strip()[:3000],
            "search_query": str(item.get("search_query") or "").strip()[:1000],
            "generation_prompt": str(item.get("generation_prompt") or "").strip()[:3000],
            "license_risk": str(item.get("license_risk") or "").strip()[:2000],
        })
    with DB_LOCK, connect() as conn:
        update_task(conn, task["content_id"], asset_plan_json=json.dumps(clean, ensure_ascii=False), state="assets_planned")
        add_event(conn, task["content_id"], "保存素材清单", "{} 项素材".format(len(clean)))


def save_quality(task, payload):
    require_state(task, "rendered", "quality_checked")
    checks = payload.get("checks")
    if not isinstance(checks, dict):
        raise ApiError(400, "质检数据格式无效", "quality", "在质检页逐项检查字幕、声音、画面、版权和平台规格后保存。")
    labels = {"subtitles": "字幕准确", "audio": "声音清晰", "visual": "画面完整", "copyright": "版权合规", "platform": "平台规格"}
    for key in QUALITY_KEYS:
        if not isinstance(checks.get(key), bool):
            raise ApiError(400, "缺少质检项“{}”的真实检查结果".format(labels[key]), "quality." + key,
                           "在质检页检查“{}”，勾选通过，或取消勾选并填写返修原因后保存。".format(labels[key]))
    quality = {"checks": {k: checks[k] for k in QUALITY_KEYS}, "passed": all(checks[k] for k in QUALITY_KEYS),
               "note": str(payload.get("note", "")).strip()[:3000], "checked_at": now()}
    with DB_LOCK, connect() as conn:
        update_task(conn, task["content_id"], quality_json=json.dumps(quality, ensure_ascii=False), state="quality_checked")
        add_event(conn, task["content_id"], "完成质检", "通过" if quality["passed"] else "未通过，需返修")


def save_publications(task, payload):
    require_state(task, "approved", "published")
    records = payload.get("publications")
    if not isinstance(records, dict):
        raise ApiError(400, "发布记录格式无效", "publications", "在发布页分别填写四个平台的状态和链接后保存。")
    clean = {}
    labels = {"douyin": "抖音", "wechat_channels": "视频号", "xiaohongshu": "小红书", "wechat_official_account": "公众号"}
    for platform in PLATFORMS:
        record = records.get(platform, {})
        if not isinstance(record, dict):
            raise ApiError(400, "{}发布记录格式无效".format(labels[platform]), "publications." + platform,
                           "在{}发布卡片中重新填写状态、标题、简介、标签和链接。".format(labels[platform]))
        status = record.get("status", "unpublished")
        if status not in ("unpublished", "published", "skipped"):
            raise ApiError(400, "{}发布状态无效".format(labels[platform]), "publications.{}.status".format(platform),
                           "把{}状态改为未发布、已发布或本次不发；不要虚报已发布。".format(labels[platform]))
        url = str(record.get("url", "")).strip()[:2000]
        if url and not re.match(r"^https?://", url):
            raise ApiError(400, "{}链接必须以 http:// 或 https:// 开头".format(labels[platform]), "publications.{}.url".format(platform),
                           "把{}链接改为实际作品页的完整 http(s) URL。".format(labels[platform]))
        if status == "published" and not url:
            raise ApiError(400, "{}已标记为已发布，但缺少真实链接".format(labels[platform]), "publications.{}.url".format(platform),
                           "粘贴{}实际作品链接；若尚未发布，把状态改回未发布，不要虚假确认。".format(labels[platform]))
        clean[platform] = {"status": status, "url": url,
                           "title": str(record.get("title", "")).strip()[:300],
                           "description": str(record.get("description", "")).strip()[:10000],
                           "tags": str(record.get("tags", "")).strip()[:1000],
                           "note": str(record.get("note", "")).strip()[:1000],
                           "recorded_at": record.get("recorded_at") if status == "published" else None}
        if status == "published" and not clean[platform]["recorded_at"]:
            clean[platform]["recorded_at"] = now()
    with DB_LOCK, connect() as conn:
        update_task(conn, task["content_id"], publications_json=json.dumps(clean, ensure_ascii=False))
        add_event(conn, task["content_id"], "保存发布记录")


def save_metrics(task, payload):
    require_state(task, "published", "analyzed")
    metrics = payload.get("metrics")
    if not isinstance(metrics, dict):
        raise ApiError(400, "复盘指标格式无效", "metrics", "按 2 小时、1 天、3 天、7 天分别填写指标后保存。")
    clean = {}
    period_labels = {"2h": "2 小时", "1d": "1 天", "3d": "3 天", "7d": "7 天"}
    field_labels = {"views": "播放/阅读", "likes": "点赞", "comments": "评论", "shares": "分享", "followers": "新增关注", "leads": "有效咨询"}
    for period in PERIODS:
        record = metrics.get(period, {})
        if not isinstance(record, dict):
            raise ApiError(400, "{}指标格式无效".format(period_labels[period]), "metrics." + period,
                           "在{}这一行填写各项指标；未读取的项留空，不要填文字。".format(period_labels[period]))
        clean[period] = {}
        for field in ("views", "likes", "comments", "shares", "followers", "leads"):
            value = record.get(field)
            if value in (None, ""):
                clean[period][field] = None
            elif isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0:
                clean[period][field] = value
            else:
                raise ApiError(400, "{}{}必须是非负数字".format(period_labels[period], field_labels[field]),
                               "metrics.{}.{}".format(period, field),
                               "把{}{}改为 0 或更大的数字；若未读取，清空该输入框，不要填负数或文字。".format(period_labels[period], field_labels[field]))
    retrospective = str(payload.get("retrospective", "")).strip()
    if len(retrospective) > 20000:
        raise ApiError(400, "复盘结论超过 2 万字符", "retrospective", "精简复盘结论到 2 万字符以内后保存。")
    with DB_LOCK, connect() as conn:
        update_task(conn, task["content_id"], metrics_json=json.dumps(clean, ensure_ascii=False), retrospective=retrospective)
        add_event(conn, task["content_id"], "保存复盘数据")


def task_action(task, payload):
    action = payload.get("action")
    content_id = task["content_id"]
    with DB_LOCK, connect() as conn:
        current = get_task(conn, content_id)
        if action == "approve_script":
            require_state(current, "script_drafted")
            labels = {"master": "母稿", "douyin": "抖音版", "wechat_channels": "视频号版", "xiaohongshu": "小红书版", "wechat_official_account": "公众号文章版"}
            missing = next((key for key in SCRIPT_KEYS if not current["scripts"].get(key, "").strip()), None)
            if missing:
                raise ApiError(409, "缺少{}，不能确认脚本".format(labels[missing]), "scripts." + missing,
                               "在脚本页补齐“{}”，检查其余四个版本后保存，再点击人工确认。".format(labels[missing]))
            update_task(conn, content_id, state="script_approved", script_approved_at=now())
            add_event(conn, content_id, "人工确认脚本")
        elif action == "revise_script":
            require_state(current, "script_approved", "waiting_audio", "review_required")
            update_task(conn, content_id, state="script_drafted", script_approved_at=None, assets_approved_at=None,
                        final_approved_at=None, published_at=None, quality_json="{}")
            add_event(conn, content_id, "脚本返修", "后续审批已清除，需重新确认")
        elif action == "confirm_audio":
            require_state(current, "script_approved", "waiting_audio")
            kinds = {f["kind"] for f in current["files"]}
            if "audio" not in kinds:
                raise ApiError(409, "缺少有效录音，不能确认", "audio", "上传真人录音或生成系统/克隆音频，确认文件有时长后再继续。")
            if "srt" not in kinds:
                raise ApiError(409, "缺少 SRT 字幕，不能确认", "srt", "上传有效 SRT 或使用 WhisperX 生成，完成人工校对后再确认。")
            update_task(conn, content_id, state="transcribed")
            add_event(conn, content_id, "人工确认录音与字幕")
        elif action == "approve_assets":
            require_state(current, "assets_planned")
            plan = current["asset_plan"]
            if not plan:
                update_task(conn, content_id, state="assets_approved", assets_approved_at=now())
                add_event(conn, content_id, "空素材计划", "无上传素材，允许使用全部 Remotion 文字卡渲染")
                return get_task(conn, content_id)
            file_ids = {f["id"] for f in current["files"] if f["kind"] == "asset"}
            issues = []
            for index, item in enumerate(plan):
                missing = []
                if item["file_id"] not in file_ids:
                    missing.append("未关联素材文件")
                if not item["source"]:
                    missing.append("未填写来源")
                if not item["licensed"]:
                    missing.append("未确认授权")
                if not item["name"]:
                    missing.append("未填写名称")
                if missing:
                    issues.append((index, item.get("name") or "未命名分镜", missing))
            if issues:
                index, name, missing = issues[0]
                first_field = "file_id" if "未关联素材文件" in missing else "source" if "未填写来源" in missing else "licensed" if "未确认授权" in missing else "name"
                message = "素材授权未完成：第 {} 项「{}」{}；共 {} 项待完成".format(index + 1, name, "且".join(missing), len(plan))
                guidance = "先处理第 {} 项：上传真实素材文件→关联→填写来源→勾选授权；其余 {} 项同样完成。也可点击“跳过未完成项并继续”，仅保留已授权场景；全部跳过后使用全部 Remotion。".format(index + 1, len(plan) - 1)
                raise ApiError(409, message, "asset_plan[{}].{}".format(index, first_field), guidance,
                               {"index": index + 1, "name": name, "missing": missing, "total": len(plan), "incomplete": len(issues)})
            update_task(conn, content_id, state="assets_approved", assets_approved_at=now())
            add_event(conn, content_id, "人工确认素材与授权")
        elif action == "skip_incomplete_assets":
            require_state(current, "assets_planned")
            file_ids = {f["id"] for f in current["files"] if f["kind"] == "asset"}
            original_count = len(current["asset_plan"])
            complete_plan = [item for item in current["asset_plan"]
                             if item.get("licensed") and item.get("file_id") in file_ids and item.get("name") and item.get("source")]
            update_task(conn, content_id, asset_plan_json=json.dumps(complete_plan, ensure_ascii=False),
                        state="assets_approved", assets_approved_at=now())
            add_event(conn, content_id, "跳过未完成分镜",
                      "跳过 {} 项，保留 {} 项；空计划使用全部 Remotion".format(original_count - len(complete_plan), len(complete_plan)))
        elif action == "revise_assets":
            require_state(current, "assets_approved", "quality_checked", "review_required")
            update_task(conn, content_id, state="assets_planned", assets_approved_at=None, final_approved_at=None,
                        published_at=None, quality_json="{}")
            add_event(conn, content_id, "素材返修", "素材与后续审批需重新确认")
        elif action == "revise_render":
            require_state(current, "quality_checked")
            update_task(conn, content_id, state="assets_approved", final_approved_at=None, published_at=None, quality_json="{}")
            add_event(conn, content_id, "成片返修", "保留素材审批，等待重新上传成片")
        elif action == "submit_review":
            require_state(current, "quality_checked")
            if not current["quality"].get("passed"):
                raise ApiError(409, "质检未通过，请先返修")
            update_task(conn, content_id, state="review_required")
            add_event(conn, content_id, "提交人工审核")
        elif action == "approve_final":
            require_state(current, "review_required")
            update_task(conn, content_id, state="approved", final_approved_at=now())
            add_event(conn, content_id, "人工最终审核通过", "与发布确认分开记录")
        elif action == "confirm_publish":
            require_state(current, "approved")
            records = current["publications"]
            if not any(records.get(p, {}).get("status") == "published" and records[p].get("url") for p in PLATFORMS):
                raise ApiError(409, "至少一个已发布平台缺少真实链接", "publications",
                               "先在平台手动发布，再把对应平台状态设为已发布并粘贴作品 URL；不要自动或虚假发布。")
            update_task(conn, content_id, state="published", published_at=now())
            add_event(conn, content_id, "人工确认发布", "未进行任何自动发布")
        elif action == "complete_retro":
            require_state(current, "published")
            missing_period = next((period for period in PERIODS if current["metrics"].get(period, {}).get("views") is None), None)
            if missing_period:
                raise ApiError(409, "缺少 {} 的播放/阅读数据".format(missing_period), "metrics.{}.views".format(missing_period),
                               "在复盘页补上 {} 的播放/阅读非负数字；其他未读取指标可留空，然后保存再完成复盘。".format(missing_period))
            if not current["retrospective"]:
                raise ApiError(409, "复盘结论为空", "retrospective", "填写本次内容的真实表现、保留或调整方向，保存后再完成复盘。")
            update_task(conn, content_id, state="analyzed", completed_at=now())
            add_event(conn, content_id, "完成复盘", "结论可回到后续选题")
        else:
            raise ApiError(400, "未知操作")
    with connect() as conn:
        return get_task(conn, content_id)


def safe_filename(name):
    name = unquote(name or "").strip()
    if not name or "\x00" in name or "/" in name or "\\" in name or Path(name).name != name:
        raise ApiError(400, "文件名不能包含路径", "file", "只保留文件名和扩展名，删除目录、../ 和反斜杠后重新选择文件。")
    stem, suffix = Path(name).stem, Path(name).suffix.lower()
    stem = re.sub(r"[^\w\-.\u4e00-\u9fff]+", "-", stem, flags=re.UNICODE).strip("-.")[:100]
    if not stem or not re.fullmatch(r"\.[a-z0-9]{1,8}", suffix):
        raise ApiError(400, "文件名或扩展名无效", "file", "使用普通中英文、数字文件名和当前步骤允许的扩展名后重试。")
    return stem + suffix


def probe_media(path, kind):
    if kind == "srt":
        text = path.read_text(encoding="utf-8-sig")
        if len(text) > 5 * 1024 * 1024 or not re.search(r"\d+\s*\r?\n\s*\d{2}:\d{2}:\d{2}[,.]\d{3}\s*-->", text):
            raise ApiError(400, "SRT 字幕格式无效", "srt",
                           "按“序号 + HH:MM:SS,mmm --> HH:MM:SS,mmm + 文本”修正时间轴，并保存为 UTF-8 SRT 后重试。")
        return {"format": "SRT", "characters": len(text)}
    if kind not in ("audio", "video"):
        return {}
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise ApiError(503, "未找到 FFprobe，无法检查媒体文件", "settings", "安装并确认 FFprobe 在 PATH 中可用，然后重新上传或生成媒体。")
    result = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height",
                             "-of", "json", str(path)], capture_output=True, text=True, timeout=30)
    field = "audio" if kind == "audio" else "file"
    if result.returncode:
        raise ApiError(400, "媒体文件无法读取，请上传有效文件", field,
                       "用 FFmpeg 重新导出有效的{}文件后重试；不要仅修改扩展名。".format("音频" if kind == "audio" else "视频"))
    info = json.loads(result.stdout or "{}")
    streams = info.get("streams", [])
    expected = "audio" if kind == "audio" else "video"
    if not any(s.get("codec_type") == expected for s in streams):
        raise ApiError(400, "文件中没有有效的{}轨道".format("音频" if kind == "audio" else "视频"), field,
                       "重新导出包含{}轨道的文件后重试。".format("音频" if kind == "audio" else "视频"))
    try:
        duration = float(info.get("format", {}).get("duration", 0))
    except (TypeError, ValueError):
        duration = 0
    if duration <= 0:
        raise ApiError(400, "媒体时长无效", field, "确认文件完整且时长大于 0；重新录制或导出后重试。")
    return {"duration_seconds": round(duration, 3), "streams": streams}


def run_whisperx(audio_path, model, directory, timeout=3600):
    if not WHISPERX_PATH.is_file() or not os.access(WHISPERX_PATH, os.X_OK):
        raise ApiError(503, "WhisperX 尚未安装完成：缺少 .venv-whisperx/bin/whisperx")
    if not WHISPERX_WORKER.is_file():
        raise ApiError(503, "WhisperX 工作脚本缺失")
    output = directory / "whisperx.srt"
    run_process([str(WHISPERX_PYTHON), str(WHISPERX_WORKER), "--audio", str(audio_path),
                 "--model", model, "--language", "zh", "--output", str(output)],
                timeout, MAX_CLI_OUTPUT, "WhisperX")
    info = probe_media(output, "srt")
    return output, info


def test_whisperx():
    try:
        with tempfile.TemporaryDirectory(prefix="whisperx-test-") as directory:
            work = Path(directory)
            audio, _ = synthesize_system_wav("Tingting", "自动字幕连接测试", work)
            run_whisperx(audio, "base", work)
        record_media_result("whisperx")
    except ApiError as error:
        record_media_result("whisperx", error.message)
        raise
    return media_ai_status()


def transcribe_audio(task, payload):
    config = agent_runtime("caption_agent")
    require_state(task, "script_approved", "waiting_audio")
    model = payload.get("model") or config["model"]
    if model not in ("small", "base"):
        raise ApiError(400, "WhisperX 仅支持 small 或 base", "model", "在转写模型下拉框中改选 small 或 base 后重试。")
    with connect() as conn:
        audio_row = get_task_file(conn, task["content_id"], payload.get("file_id"), "audio")
    audio_path = task_file_path(audio_row)
    try:
        with tempfile.TemporaryDirectory(prefix="whisperx-task-") as directory:
            srt, info = run_whisperx(audio_path, model, Path(directory), config["timeout_seconds"])
            timestamp = now()
            final_directory = ROOT / "subtitles" / task["content_id"]
            final_directory.mkdir(parents=True, exist_ok=True)
            final_path = (final_directory / ("whisperx-{}-{}.srt".format(model, uuid.uuid4().hex[:12]))).resolve()
            if final_directory.resolve() not in final_path.parents:
                raise ApiError(400, "字幕保存路径无效")
            try:
                shutil.copyfile(srt, final_path)
                info.update({"whisperx": True, "model": model, "source_audio_file_id": audio_row["id"]})
                with DB_LOCK, connect() as conn:
                    current = get_task(conn, task["content_id"])
                    require_state(current, "script_approved", "waiting_audio")
                    conn.execute("""INSERT INTO files(content_id,kind,original_name,relative_path,size,media_info_json,created_at)
                                    VALUES (?,?,?,?,?,?,?)""",
                                 (task["content_id"], "srt", "WhisperX-{}-{}.srt".format(model, audio_row["original_name"]),
                                  final_path.relative_to(ROOT).as_posix(), final_path.stat().st_size,
                                  json.dumps(info, ensure_ascii=False), timestamp))
                    update_task(conn, task["content_id"], state="waiting_audio")
                    add_event(conn, task["content_id"], "WhisperX生成字幕",
                              "{} · 源文件 {} · 仍需人工校对确认".format(model, audio_row["original_name"]))
            except Exception:
                final_path.unlink(missing_ok=True)
                raise
    except ApiError as error:
        record_media_result("whisperx", error.message)
        raise
    record_media_result("whisperx")
    with connect() as conn:
        return get_task(conn, task["content_id"])


def synthesize_system_wav(voice_name, text, directory):
    if not Path("/usr/bin/say").is_file():
        raise ApiError(503, "未找到 macOS /usr/bin/say")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ApiError(503, "未找到 FFmpeg，无法转换 WAV")
    source = directory / "speech.aiff"
    target = directory / "speech.wav"
    timeout = min(300, max(60, len(text) // 3))
    run_process(["/usr/bin/say", "-v", voice_name, "-o", str(source), text], timeout, 65536, "macOS say")
    run_process([ffmpeg, "-v", "error", "-y", "-i", str(source), "-ac", "1", "-ar", "44100",
                 "-c:a", "pcm_s16le", str(target)], 120, 65536, "FFmpeg")
    info = probe_media(target, "audio")
    if info["duration_seconds"] < 0.05:
        raise ApiError(400, "生成语音为空或该音色不可用，请更换系统音色")
    return target, info


def test_system_voice():
    try:
        with tempfile.TemporaryDirectory(prefix="content-voice-test-") as directory:
            synthesize_system_wav("Tingting", "系统语音生成连接测试", Path(directory))
        record_tts_result()
    except ApiError as error:
        record_tts_result(error.message)
        raise
    return get_voices()


def generate_audio(task, payload):
    agent_runtime("voice_agent")
    require_state(task, "script_approved", "waiting_audio")
    script_key = payload.get("script_key", "master")
    if script_key not in SCRIPT_KEYS:
        raise ApiError(400, "脚本版本无效", "script_key", "从母稿、抖音、视频号、小红书或公众号版本中重新选择。")
    text = payload.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ApiError(400, "用于 AI 录音的文本不能为空", "text", "在 TTS 文本框输入或粘贴要朗读的内容后重试。")
    if len(text) > 50000:
        raise ApiError(400, "TTS 文本不能超过 5 万字符", "text", "把 TTS 文本精简到 5 万字符以内，或分段生成。")
    voice_id = str(payload.get("voice_id", ""))
    with connect() as conn:
        voice = conn.execute("SELECT * FROM voice_profiles WHERE id=? AND kind='system'", (voice_id,)).fetchone()
    if not voice:
        raise ApiError(404, "系统音色不存在", "voice_id", "从系统音色列表重新选择；使用本人克隆时改选已授权档案和克隆生成入口。")
    try:
        with tempfile.TemporaryDirectory(prefix="content-tts-") as directory:
            wav, info = synthesize_system_wav(voice["voice_name"], text.strip(), Path(directory))
            timestamp = now()
            final_directory = ROOT / "voice" / task["content_id"]
            final_directory.mkdir(parents=True, exist_ok=True)
            filename = "AI-{}-{}.wav".format(voice["voice_name"], uuid.uuid4().hex[:12])
            final_path = (final_directory / filename).resolve()
            if final_directory.resolve() not in final_path.parents:
                raise ApiError(400, "录音保存路径无效")
            try:
                shutil.copyfile(wav, final_path)
                info.update({"system_tts": True, "voice_id": voice_id, "voice_name": voice["voice_name"],
                             "script_key": script_key})
                with DB_LOCK, connect() as conn:
                    current = get_task(conn, task["content_id"])
                    require_state(current, "script_approved", "waiting_audio")
                    cursor = conn.execute("""INSERT INTO files(content_id,kind,original_name,relative_path,size,media_info_json,created_at)
                                             VALUES (?,?,?,?,?,?,?)""",
                                          (task["content_id"], "audio", "AI录音-{}.wav".format(voice["name"]),
                                           final_path.relative_to(ROOT).as_posix(), final_path.stat().st_size,
                                           json.dumps(info, ensure_ascii=False), timestamp))
                    file_id = cursor.lastrowid
                    update_task(conn, task["content_id"], state="waiting_audio")
                    conn.execute("UPDATE voice_profiles SET last_used_at=?,use_count=use_count+1 WHERE id=?", (timestamp, voice_id))
                    conn.executemany("INSERT OR REPLACE INTO settings(key,value) VALUES (?,?)",
                                     [("last_voice_id", voice_id), ("tts_ready", "1"), ("tts_last_success", timestamp),
                                      ("tts_last_error", "")])
                    add_event(conn, task["content_id"], "AI生成录音",
                              "系统音色 {} · 脚本 {} · 仍需上传 SRT".format(voice["name"], script_key))
                    row = conn.execute("SELECT * FROM files WHERE id=?", (file_id,)).fetchone()
                    generated_file = file_dict(row)
            except Exception:
                final_path.unlink(missing_ok=True)
                raise
    except ApiError as error:
        record_tts_result(error.message)
        raise
    record_tts_result()
    with connect() as conn:
        result = get_task(conn, task["content_id"])
        result["generated_file"] = generated_file
        return result


def run_openvoice(reference, text, directory, timeout=3600):
    missing = openvoice_missing_files()
    if missing:
        raise ApiError(503, "OpenVoice 尚未就绪，缺少：" + "、".join(path_label(path) for path in missing))
    output = directory / "clone.wav"
    run_process([str(OPENVOICE_PYTHON), str(OPENVOICE_WORKER), "--openvoice-root", str(OPENVOICE_ROOT),
                 "--ref", str(reference), "--text", text, "--output", str(output),
                 "--work-dir", str(directory / "work"), "--speaker", "zh"], timeout, MAX_CLI_OUTPUT, "OpenVoice")
    return output, probe_media(output, "audio")


def test_clone_voice():
    try:
        with tempfile.TemporaryDirectory(prefix="openvoice-test-") as directory:
            run_openvoice(OPENVOICE_REFERENCE, "本人音色克隆连接测试", Path(directory))
        record_media_result("clone")
    except ApiError as error:
        record_media_result("clone", error.message)
        raise
    return media_ai_status()


def generate_clone_audio(task, payload):
    config = agent_runtime("clone_agent")
    require_state(task, "script_approved", "waiting_audio")
    if not media_ai_status()["openvoice"]["ready"]:
        raise ApiError(409, "OpenVoice 尚未通过真实连接测试", "settings", "到设置页检查模型文件并点击“测试 OpenVoice”；成功后再生成克隆录音。")
    script_key = payload.get("script_key", "master")
    if script_key not in SCRIPT_KEYS:
        raise ApiError(400, "脚本版本无效", "script_key", "从五个脚本版本中重新选择用于克隆的文本。")
    text = payload.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ApiError(400, "克隆文本不能为空", "text", "在 TTS 文本框填写要由本人克隆音色朗读的内容。")
    if len(text) > 50000:
        raise ApiError(400, "克隆文本不能超过 5 万字符", "text", "把克隆文本精简到 5 万字符以内，或分段生成。")
    voice_id = str(payload.get("voice_id", ""))
    with connect() as conn:
        voice = conn.execute("SELECT * FROM voice_profiles WHERE id=? AND kind='clone'", (voice_id,)).fetchone()
    if not voice or not voice["authorized"]:
        raise ApiError(403, "本人音色档案不存在或未授权", "voice_id", "选择本人已授权档案；若没有，先上传本人样本并明确勾选授权。")
    sample_path = (ROOT / voice["sample_path"]).resolve() if voice["sample_path"] else None
    expected_directory = (ROOT / "voice_profiles" / voice_id).resolve()
    if not sample_path or expected_directory not in sample_path.parents or not sample_path.is_file():
        raise ApiError(404, "本人语音样本不存在或路径无效", "voice_id", "在本人音色记忆库重新上传有效样本，不要修改样本路径或引用任务目录。")
    try:
        with tempfile.TemporaryDirectory(prefix="openvoice-task-") as directory:
            wav, info = run_openvoice(sample_path, text.strip(), Path(directory), config["timeout_seconds"])
            timestamp = now()
            final_directory = ROOT / "voice" / task["content_id"]
            final_directory.mkdir(parents=True, exist_ok=True)
            final_path = (final_directory / ("Clone-{}-{}.wav".format(voice_id, uuid.uuid4().hex[:12]))).resolve()
            if final_directory.resolve() not in final_path.parents:
                raise ApiError(400, "克隆录音保存路径无效")
            try:
                shutil.copyfile(wav, final_path)
                info.update({"clone_tts": True, "voice_id": voice_id, "script_key": script_key})
                with DB_LOCK, connect() as conn:
                    current = get_task(conn, task["content_id"])
                    require_state(current, "script_approved", "waiting_audio")
                    cursor = conn.execute("""INSERT INTO files(content_id,kind,original_name,relative_path,size,media_info_json,created_at)
                                             VALUES (?,?,?,?,?,?,?)""",
                                          (task["content_id"], "audio", "克隆录音-{}.wav".format(voice["name"]),
                                           final_path.relative_to(ROOT).as_posix(), final_path.stat().st_size,
                                           json.dumps(info, ensure_ascii=False), timestamp))
                    file_id = cursor.lastrowid
                    update_task(conn, task["content_id"], state="waiting_audio")
                    conn.execute("UPDATE voice_profiles SET last_used_at=?,use_count=use_count+1 WHERE id=?", (timestamp, voice_id))
                    conn.executemany("INSERT OR REPLACE INTO settings(key,value) VALUES (?,?)",
                                     [("last_voice_id", voice_id), ("clone_ready", "1"), ("clone_last_success", timestamp),
                                      ("clone_last_error", "")])
                    add_event(conn, task["content_id"], "OpenVoice生成克隆录音",
                              "本人档案 {} · 脚本 {} · 仍需 SRT".format(voice["name"], script_key))
                    row = conn.execute("SELECT * FROM files WHERE id=?", (file_id,)).fetchone()
                    generated_file = file_dict(row)
            except Exception:
                final_path.unlink(missing_ok=True)
                raise
    except ApiError as error:
        record_media_result("clone", error.message)
        raise
    record_media_result("clone")
    with connect() as conn:
        result = get_task(conn, task["content_id"])
        result["generated_file"] = generated_file
        return result


def save_voice_sample(name, filename, authorized, body):
    if authorized is not True:
        raise ApiError(403, "必须确认是本人声音且授权用于音色克隆", "authorized",
                           "仅在样本确为本人声音时，勾选“本人声音且授权用于音色克隆”；否则不要上传该样本。")
    name = str(name or "").strip()
    if not name or len(name) > 100:
        raise ApiError(400, "音色档案名需为 1～100 字", "name", "填写便于识别的档案名，例如“本人安静环境样本”，且不超过 100 字。")
    if not body:
        raise ApiError(400, "语音样本不能为空", "file", "重新选择非空 WAV、MP3、M4A 或 AAC 本人录音样本。")
    filename = safe_filename(filename)
    suffix = Path(filename).suffix
    if suffix not in UPLOADS["audio"][1]:
        raise ApiError(400, "样本仅支持 WAV / MP3 / M4A / AAC", "file", "把本人样本转换为 WAV、MP3、M4A 或 AAC，建议 10 秒到 5 分钟后上传。")
    profile_id = "clone-" + uuid.uuid4().hex[:12]
    base = ROOT / "voice_profiles"
    pending = base / (".pending-" + uuid.uuid4().hex[:12])
    final_directory = base / profile_id
    try:
        pending.mkdir(parents=True, exist_ok=False)
        sample = pending / ("sample" + suffix)
        sample.write_bytes(body)
        info = probe_media(sample, "audio")
        duration = info["duration_seconds"]
        pending.rename(final_directory)
        relative = (final_directory / sample.name).relative_to(ROOT).as_posix()
        with DB_LOCK, connect() as conn:
            conn.execute("""INSERT INTO voice_profiles
                            (id,kind,name,voice_name,language,description,sample_path,sample_name,duration_seconds,authorized,last_used_at,use_count,created_at)
                            VALUES (?,'clone',?,NULL,'本人声音样本','本人授权样本；克隆生成未接入',?,?,?,1,NULL,0,?)""",
                         (profile_id, name, relative, filename, duration, now()))
            row = conn.execute("SELECT * FROM voice_profiles WHERE id=?", (profile_id,)).fetchone()
    except Exception:
        if pending.exists():
            shutil.rmtree(pending)
        if final_directory.exists():
            shutil.rmtree(final_directory)
        raise
    result = voice_profile_dict(row)
    result["sample_recommendation"] = "样本时长符合 10 秒到 5 分钟建议" if 10 <= duration <= 300 else "样本已保存；建议未来使用 10 秒到 5 分钟样本"
    return result


def upload_file(task, kind, filename, body):
    if kind not in UPLOADS:
        raise ApiError(400, "上传类型无效", "file", "从当前页面的上传按钮重新选择文件，不要调用其他类型的上传接口。")
    states = {"audio": ("script_approved", "waiting_audio"), "srt": ("script_approved", "waiting_audio"),
              "asset": ("transcribed", "assets_planned"), "video": ("assets_approved", "rendered")}
    require_state(task, *states[kind])
    if not body:
        raise ApiError(400, "不能上传空文件", "file", "重新选择非空且可读取的文件后上传。")
    filename = safe_filename(filename)
    if Path(filename).suffix not in UPLOADS[kind][1]:
        raise ApiError(400, "该步骤不支持此文件扩展名", "file",
                       "把文件转换为当前步骤支持的格式后重试：{}。".format("、".join(sorted(UPLOADS[kind][1]))))
    parts = UPLOADS[kind][0]
    directory = ROOT.joinpath(parts[0], task["content_id"], *parts[1:])
    directory.mkdir(parents=True, exist_ok=True)
    stored = uuid.uuid4().hex[:12] + "-" + filename
    path = (directory / stored).resolve()
    if directory.resolve() not in path.parents:
        raise ApiError(400, "文件路径无效")
    temporary = path.with_suffix(path.suffix + ".uploading")
    try:
        temporary.write_bytes(body)
        info = probe_media(temporary, kind)
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    relative = path.relative_to(ROOT).as_posix()
    with DB_LOCK, connect() as conn:
        cursor = conn.execute("INSERT INTO files(content_id,kind,original_name,relative_path,size,media_info_json,created_at) VALUES (?,?,?,?,?,?,?)",
                              (task["content_id"], kind, filename, relative, len(body), json.dumps(info), now()))
        file_id = cursor.lastrowid
        if kind in ("audio", "srt"):
            update_task(conn, task["content_id"], state="waiting_audio")
        elif kind == "video":
            update_task(conn, task["content_id"], state="rendered", quality_json="{}", final_approved_at=None, published_at=None)
        add_event(conn, task["content_id"], "上传文件", "{} · {}".format(kind, filename))
        row = conn.execute("SELECT * FROM files WHERE id=?", (file_id,)).fetchone()
        return file_dict(row)


def parse_srt_captions(text):
    captions = []
    matches = list(re.finditer(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})[^\r\n]*\r?\n(.*?)(?=\r?\n\s*\r?\n|\Z)", text, re.S))
    for match in matches:
        start = (int(match.group(1)) * 3600 + int(match.group(2)) * 60 + int(match.group(3))) * 1000 + int(match.group(4))
        end = (int(match.group(5)) * 3600 + int(match.group(6)) * 60 + int(match.group(7))) * 1000 + int(match.group(8))
        value = re.sub(r"\s+", " ", match.group(9)).strip()
        if value and end > start:
            captions.append({"text": value, "startMs": start, "endMs": end, "timestampMs": None, "confidence": None})
    return captions


def asset_file_path(row):
    path = (ROOT / row["relative_path"]).resolve()
    expected = ROOT / "assets" / row["content_id"] / "source"
    if expected.resolve() not in path.parents or not path.is_file():
        raise ApiError(404, "素材文件不存在或路径无效", "file", "在素材页重新上传并关联文件，不要修改任务相对路径。")
    return path


def latest_task_file(task, kind):
    return next((file for file in task["files"] if file["kind"] == kind), None)


def render_card_text(value, fallback, limit=48):
    text = re.sub(r"\s+", " ", str(value or "")).strip() or fallback
    return text if len(text) <= limit else text[:limit - 1].rstrip("，。；：、 ") + "…"


def fallback_render_scenes(task, duration):
    descriptions = [render_card_text(task["title"], "企业 AI 落地实战", 36),
                    render_card_text(task.get("angle"), "真实任务与完整流程"),
                    "人工检查每一步", "结果可核验，再进入发布"]
    return [{"id": "text-{}".format(index), "name": "文字卡 {:02d}".format(index + 1),
             "start_seconds": round(duration * index / 4, 3), "end_seconds": round(duration * (index + 1) / 4, 3),
             "asset_type": "own", "description": descriptions[index], "media": None}
            for index, description in enumerate(descriptions)]


def prepare_render_assets(task, mode, platform):
    audio = latest_task_file(task, "audio")
    if not audio:
        raise ApiError(409, "缺少口播音频，无法确定视频时长", "audio", "先上传或生成有效录音，再开始渲染。")
    with connect() as conn:
        audio_row = get_task_file(conn, task["content_id"], audio["id"], "audio")
    audio_path = task_file_path(audio_row)
    duration = audio["media_info"].get("duration_seconds")
    srt = latest_task_file(task, "srt")
    srt_path = None
    captions = []
    if srt:
        with connect() as conn:
            srt_row = get_task_file(conn, task["content_id"], srt["id"], "srt")
        srt_path = task_file_path(srt_row)
        srt_text = srt_path.read_text(encoding="utf-8-sig")
        captions = parse_srt_captions(srt_text)
        if not duration:
            duration = srt_end_seconds(srt_text)
    if not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0:
        raise ApiError(409, "无法从音频或 SRT 确定视频时长", "audio", "重新上传完整音频，或提供带结束时间的有效 SRT。")
    directory = REMOTION_PUBLIC / "assets" / task["content_id"]
    directory.mkdir(parents=True, exist_ok=True)
    if (REMOTION_PUBLIC / "assets").resolve() not in directory.resolve().parents:
        raise ApiError(400, "Remotion 素材目录无效", "file", "重新创建任务后再渲染，不要修改素材目录。")
    audio_target = directory / "narration.wav"
    shutil.copyfile(audio_path, audio_target)
    if srt_path:
        shutil.copyfile(srt_path, directory / "captions.srt")
    asset_rows = {file["id"]: file for file in task["files"] if file["kind"] == "asset"}
    scenes = []
    for index, item in enumerate(task["asset_plan"]):
        start = item.get("start_seconds")
        end = item.get("end_seconds")
        if start is None or end is None:
            start, end = duration * index / max(1, len(task["asset_plan"])), duration * (index + 1) / max(1, len(task["asset_plan"]))
        start, end = max(0, min(float(start), duration)), min(float(end), duration)
        if end <= start:
            continue
        complete = item.get("licensed") and item.get("file_id") in asset_rows and item.get("name") and item.get("source")
        if mode in ("upload", "mixed") and not complete:
            continue
        scene = {"id": item.get("id") or "scene-{}".format(index), "name": item.get("name") or "分镜 {}".format(index + 1),
                 "start_seconds": round(start, 3), "end_seconds": round(end, 3),
                 "asset_type": item.get("asset_type") or "own",
                 "description": render_card_text(item.get("description") or item.get("name"), task["title"]),
                 "media": None}
        if complete:
            row = asset_rows[item["file_id"]]
            source_path = asset_file_path(row)
            suffix = source_path.suffix.lower()
            media_kind = "video" if suffix in (".mp4", ".mov", ".webm") else "image" if suffix in (".png", ".jpg", ".jpeg", ".webp") else None
            if media_kind:
                target = directory / "scene-{}{}".format(index, suffix)
                shutil.copyfile(source_path, target)
                scene["media"] = {"kind": media_kind, "src": "assets/{}/{}".format(task["content_id"], target.name)}
                scene["_local_path"] = str(target)
        scenes.append(scene)
    if mode in ("upload", "mixed"):
        scenes = [scene for scene in scenes if scene.get("_local_path")]
    if not scenes:
        if mode in ("upload", "mixed"):
            raise ApiError(409, "{}至少需要 1 个已关联且授权的视频或图片场景".format("上传模式" if mode == "upload" else "混合模式"),
                           "asset_plan", "为至少一个分镜上传视频/图片、选择关联文件、填写来源并勾选授权；或改用全部 Remotion。")
        scenes = fallback_render_scenes(task, duration)
    if mode in ("upload", "mixed") and not any(scene.get("_local_path") for scene in scenes):
        raise ApiError(409, "已授权场景中没有可渲染的视频或图片", "asset_plan",
                       "至少关联一个 MP4/MOV/WebM 视频或 PNG/JPEG/WebP 图片；其他文件请改作授权凭证，或选择全部 Remotion。")
    props = {"title": render_card_text(task["title"], "企业 AI 落地实战", 42), "audio": "assets/{}/narration.wav".format(task["content_id"]),
             "captions": captions, "durationSeconds": duration,
             "scenes": [{key: value for key, value in scene.items() if not key.startswith("_")} for scene in scenes]}
    return props, scenes, duration


def available_render_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def run_remotion_render(props, output, timeout=1800):
    output = Path(output).resolve()
    npx = shutil.which("npx")
    if not npx or not (REMOTION_APP / "package.json").is_file():
        raise ApiError(503, "Remotion 项目或 npx 不可用", "settings", "确认 remotion-app 已安装依赖且 npx 可用，然后重试。")
    with tempfile.TemporaryDirectory(prefix="remotion-props-") as directory:
        props_path = Path(directory) / "props.json"
        props_path.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
        run_process([npx, "remotion", "render", "src/index.ts", "TalkingHead", str(output),
                     "--props={}".format(props_path), "--codec=h264", "--pixel-format=yuv420p", "--port={}".format(available_render_port())],
                timeout, MAX_CLI_OUTPUT, "Remotion", REMOTION_APP)
    if not output.is_file() or output.stat().st_size == 0:
        raise ApiError(502, "Remotion 命令结束但没有生成有效 MP4", "render", "查看渲染日志和输出路径后重试。")


def caption_overlays(captions, directory):
    if not captions:
        return "", []
    captions_path = Path(directory) / "captions.json"
    captions_path.write_text(json.dumps(captions, ensure_ascii=False), encoding="utf-8")
    worker = PROJECT_ROOT / "workers" / "caption_images.py"
    if not worker.is_file() or not WHISPERX_PYTHON.is_file():
        raise ApiError(503, "字幕图片生成环境不可用", "settings", "安装 Pillow 后重试，或关闭上传模式烧字。")
    stdout, _ = run_process([str(WHISPERX_PYTHON), str(worker), "--captions", str(captions_path),
                             "--output-dir", directory], 120, MAX_CLI_OUTPUT, "字幕图片生成")
    paths = json.loads(stdout)
    filters = []
    for path, caption in zip(paths, captions):
        start = caption["startMs"] / 1000
        end = caption["endMs"] / 1000
        filters.append("overlay=x=(W-w)/2:y=H-300:enable='between(t,{:.3f},{:.3f})'".format(start, end))
    return "".join(filters), paths


def run_upload_render(scenes, props, output, burn_subtitles, timeout=1800):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ApiError(503, "未找到 FFmpeg，无法合成上传素材", "settings", "安装 FFmpeg 后重试，或改用全部 Remotion。")
    command = [ffmpeg, "-v", "error", "-y"]
    filters = []
    for index, scene in enumerate(scenes):
        duration = scene["end_seconds"] - scene["start_seconds"]
        if scene["media"]["kind"] == "image":
            command.extend(["-loop", "1", "-t", "{:.3f}".format(duration), "-i", scene["_local_path"]])
        else:
            command.extend(["-i", scene["_local_path"]])
        filters.append("[{}:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1,format=yuv420p,trim=duration={:.3f},setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration={:.3f}[v{}]".format(index, duration, duration, index))
    command.extend(["-i", str(REMOTION_PUBLIC / "assets" / props["audio"].split("/")[1] / "narration.wav")])
    filters.append("".join("[v{}]".format(index) for index in range(len(scenes))) + "concat=n={}:v=1:a=0[base]".format(len(scenes)))
    with tempfile.TemporaryDirectory(prefix="caption-overlays-") as caption_directory:
        overlay_filter, overlay_paths = caption_overlays(props["captions"], caption_directory) if burn_subtitles else ("", [])
        for path in overlay_paths:
            command.extend(["-i", path])
        filters.append("[base]" + (overlay_filter or "copy") + "[final]")
        command.extend(["-filter_complex_threads", "2", "-filter_complex", ";".join(filters), "-map", "[final]", "-map", "{}:a".format(len(scenes)),
                        "-t", "{:.3f}".format(props["durationSeconds"]), "-r", "30", "-c:v", "libx264", "-preset", "veryfast",
                        "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(output)])
        run_process(command, timeout, MAX_CLI_OUTPUT, "FFmpeg 上传合成")


def validate_rendered_mp4(path):
    info = probe_media(path, "video")
    if not any(stream.get("codec_type") == "audio" for stream in info["streams"]):
        raise ApiError(502, "渲染结果缺少音频流", "render", "检查口播音频和渲染日志后重试；不要发布无声结果。")
    return info


def render_task(task, payload):
    config = agent_runtime("remotion_agent")
    require_state(task, "assets_approved", "rendered")
    mode = payload.get("mode")
    if mode not in ("upload", "remotion", "mixed"):
        raise ApiError(400, "渲染模式无效", "mode", "选择全部上传、全部 Remotion 或混合模式。")
    platform = payload.get("platform") or "douyin"
    if platform not in PLATFORMS:
        raise ApiError(400, "目标平台无效", "platform", "选择抖音、视频号、小红书或公众号。")
    try:
        props, scenes, _ = prepare_render_assets(task, mode, platform)
        with tempfile.TemporaryDirectory(prefix="content-render-") as directory:
            output = Path(directory) / "render.mp4"
            if mode == "upload":
                run_upload_render(scenes, props, output, payload.get("burn_subtitles", True), config["timeout_seconds"])
            else:
                run_remotion_render(props, output, config["timeout_seconds"])
            info = validate_rendered_mp4(output)
            final_directory = ROOT / "renders" / task["content_id"]
            final_directory.mkdir(parents=True, exist_ok=True)
            final_path = (final_directory / "{}-{}-{}.mp4".format(mode, platform, uuid.uuid4().hex[:12])).resolve()
            if final_directory.resolve() not in final_path.parents:
                raise ApiError(400, "成片保存路径无效", "file", "重新创建任务目录后重试，不要修改成片路径。")
            try:
                shutil.copyfile(output, final_path)
                info.update({"mode": mode, "platform": platform})
                with DB_LOCK, connect() as conn:
                    current = get_task(conn, task["content_id"])
                    require_state(current, "assets_approved", "rendered")
                    cursor = conn.execute("""INSERT INTO files(content_id,kind,original_name,relative_path,size,media_info_json,created_at)
                                             VALUES (?,?,?,?,?,?,?)""",
                                          (task["content_id"], "video", "{}-{}.mp4".format(mode, platform),
                                           final_path.relative_to(ROOT).as_posix(), final_path.stat().st_size,
                                           json.dumps(info, ensure_ascii=False), now()))
                    file_id = cursor.lastrowid
                    update_task(conn, task["content_id"], state="rendered", quality_json="{}", final_approved_at=None, published_at=None)
                    add_event(conn, task["content_id"], "视频构建Agent渲染完成",
                              "{} · {} · {:.3f} 秒".format(mode, platform, info["duration_seconds"]))
                    row = conn.execute("SELECT * FROM files WHERE id=?", (file_id,)).fetchone()
                    generated = file_dict(row)
            except Exception:
                final_path.unlink(missing_ok=True)
                raise
    except ApiError as error:
        record_render_result(error.message)
        if not error.field:
            error.field, error.action = "render", "检查渲染模式、素材和本地 Remotion/FFmpeg 日志，修正后重试；旧成片未改变。"
        raise
    record_render_result()
    with connect() as conn:
        result = get_task(conn, task["content_id"])
        result["generated_file"] = generated
        return result


def test_render_agent():
    test_id = "_render_test"
    directory = REMOTION_PUBLIC / "assets" / test_id
    try:
        directory.mkdir(parents=True, exist_ok=True)
        subprocess.run(["/usr/bin/say", "-v", "Tingting", "-o", str(directory / "narration.aiff"), "视频构建连接测试"], check=True, timeout=30)
        subprocess.run([shutil.which("ffmpeg"), "-v", "error", "-y", "-i", str(directory / "narration.aiff"), str(directory / "narration.wav")], check=True, timeout=30)
        props = {"title": "视频构建测试", "audio": "assets/_render_test/narration.wav", "durationSeconds": 2,
                 "captions": [{"text": "视频构建连接测试", "startMs": 0, "endMs": 1800, "timestampMs": None, "confidence": None}],
                 "scenes": [{"id": "test", "name": "文字卡", "start_seconds": 0, "end_seconds": 2,
                             "asset_type": "own", "description": "真实 Remotion 渲染", "media": None}]}
        with tempfile.TemporaryDirectory(prefix="render-test-") as temp:
            output = Path(temp) / "test.mp4"
            run_remotion_render(props, output)
            validate_rendered_mp4(output)
        record_render_result()
    except (ApiError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        record_render_result(getattr(error, "message", "Remotion 自测失败，请检查项目和浏览器渲染环境"))
        if isinstance(error, ApiError):
            raise
        raise ApiError(502, "Remotion 自测失败，请检查项目依赖和 Chrome 渲染环境", "settings", "打开 Remotion Studio 确认 TalkingHead 可预览后重试。")
    finally:
        if directory.exists():
            shutil.rmtree(directory)
    return get_render_ai_status()


def edit_subtitles(task, payload):
    require_state(task, "waiting_audio")
    text = payload.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ApiError(400, "字幕文本不能为空", "srt", "在字幕编辑器中粘贴有效 SRT 文本，包含时间轴和字幕后保存。")
    if len(text.encode("utf-8")) > 5 * 1024 * 1024:
        raise ApiError(400, "字幕文本超过 5MB", "srt", "将当前 SRT 精简到 5MB 以内，或拆分为较短内容后重试。")
    with DB_LOCK, connect() as conn:
        row = get_task_file(conn, task["content_id"], payload.get("file_id"), "srt")
        path = task_file_path(row)
        temporary = path.with_suffix(path.suffix + ".editing")
        try:
            temporary.write_text(text, encoding="utf-8")
            info = probe_media(temporary, "srt")
            temporary.replace(path)
            conn.execute("UPDATE files SET size=?,media_info_json=? WHERE id=?",
                         (path.stat().st_size, json.dumps(info, ensure_ascii=False), row["id"]))
            add_event(conn, task["content_id"], "人工校对字幕", row["original_name"])
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        return get_task(conn, task["content_id"])


class Handler(BaseHTTPRequestHandler):
    server_version = "ContentWorkflow/1.0"

    def log_message(self, fmt, *args):
        print("{} {}".format(self.address_string(), fmt % args), flush=True)

    def json_response(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def error_response(self, error):
        if isinstance(error, ApiError):
            message, field, action, item = infer_error_details(error)
            status = error.status
        else:
            message, field, action, item = "服务器未能完成此操作，请修正后重试", "workflow", "查看本地服务日志定位本次异常，修正后重试；不要重复提交可能产生重复文件的请求。", None
            status = 500
        payload = {"error": message, "field": field, "action": action}
        if item is not None:
            payload["item"] = item
        self.json_response(payload, status)

    def read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ApiError(400, "请求长度无效")
        if length <= 0 or length > MAX_JSON:
            raise ApiError(400, "请求为空或过大")
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ApiError(400, "JSON 格式无效")
        if not isinstance(value, dict):
            raise ApiError(400, "请求格式无效")
        return value

    def serve_static(self, path):
        names = {"/v2": "v2.html", "/v2.js": "v2.js", "/v2.css": "v2.css",
                 "/legacy": "index.html", "/index.html": "index.html", "/styles.css": "styles.css", "/app.js": "app.js",
                 "/workspaces.js": "workspaces.js", "/publishing.js": "publishing.js"}
        react_index = WEB_ROOT / "react-dist" / "index.html"
        react_route = False
        if path == "/" and react_index.is_file():
            target = react_index
            react_route = True
        elif path.startswith("/assets/"):
            target = (WEB_ROOT / "react-dist" / path.lstrip("/")).resolve()
            if (WEB_ROOT / "react-dist") not in target.parents or not target.is_file():
                raise ApiError(404, "静态资源不存在")
        elif path in names:
            target = WEB_ROOT / names[path]
        elif react_index.is_file():
            target = react_index
            react_route = True
        else:
            raise ApiError(404, "页面不存在")
        body = target.read_bytes()
        content_type = "text/html" if target.suffix == ".html" else "text/css" if target.suffix == ".css" else "application/javascript"
        session_header = V2.session_header(self) if V2 and (react_route or path in ("/v2", "/legacy")) else None
        self.send_response(200)
        if session_header:
            self.send_header("Set-Cookie", session_header)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; media-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'")
        self.end_headers()
        self.wfile.write(body)

    def serve_media(self, file_id, download=False):
        with connect() as conn:
            row = conn.execute("SELECT * FROM files WHERE id=?", (file_id,)).fetchone()
        if not row:
            raise ApiError(404, "文件不存在")
        path = (ROOT / row["relative_path"]).resolve()
        expected = ROOT / ("subtitles" if row["kind"] == "srt" else {"audio": "voice", "asset": "assets", "video": "renders"}[row["kind"]]) / row["content_id"]
        if row["kind"] != "srt" and row["kind"] == "asset":
            expected = expected / "source"
        if expected.resolve() not in path.parents or not path.is_file():
            raise ApiError(404, "文件不存在或路径无效")
        size = path.stat().st_size
        start, end = 0, size - 1
        range_header = self.headers.get("Range")
        status = 200
        if range_header:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header)
            if not match:
                raise ApiError(416, "媒体范围无效")
            if match.group(1):
                start = int(match.group(1))
                end = int(match.group(2)) if match.group(2) else end
            else:
                start = max(0, size - int(match.group(2)))
            end = min(end, size - 1)
            if start > end or start >= size:
                raise ApiError(416, "媒体范围无效")
            status = 206
        self.send_response(status)
        content_type = "text/plain; charset=utf-8" if row["kind"] == "srt" else mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_header("Content-Type", content_type)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        disposition = "attachment; filename*=UTF-8''{}".format(quote(row["original_name"])) if download else "inline"
        self.send_header("Content-Disposition", disposition)
        self.send_header("X-Content-Type-Options", "nosniff")
        if status == 206:
            self.send_header("Content-Range", "bytes {}-{}/{}".format(start, end, size))
        self.end_headers()
        with path.open("rb") as handle:
            handle.seek(start)
            remaining = end - start + 1
            while remaining:
                chunk = handle.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def do_GET(self):
        try:
            parsed = urlsplit(self.path)
            path = parsed.path
            if V2 and V2.matches(path):
                return V2.handle(self, "GET", path, parse_qs(parsed.query))
            if path == "/api/ai/status":
                self.json_response(get_ai_status())
            elif path == "/api/voices":
                self.json_response(get_voices())
            elif path == "/api/bootstrap":
                with connect() as conn:
                    tasks = [task_dict(row, conn) for row in conn.execute("SELECT * FROM tasks ORDER BY created_at DESC")]
                    topics = []
                    for row in conn.execute("SELECT * FROM topics ORDER BY rank"):
                        item = dict(row)
                        item["evidence"] = parse_json(item.pop("evidence_json"), [])
                        topics.append(item)
                    accounts = [json.loads(row[0]) for row in conn.execute("SELECT snapshot_json FROM accounts")]
                    hotspot_row = conn.execute("SELECT snapshot_json FROM hotspot_snapshots WHERE platform='douyin'").fetchone()
                    hotspots = parse_json(hotspot_row[0], {}) if hotspot_row else {}
                    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
                    ai = get_ai_status()
                    voices = get_voices()
                    media_ai = media_ai_status()
                    asset_ai = get_asset_ai_status()
                    render_ai = get_render_ai_status()
                    capabilities = [{"name": "账号分析Agent", "status": "已接入"},
                                    {"name": "选题Agent", "status": "已配置"},
                                    {"name": "脚本Agent", "status": "已连接" if ai["ready"] else "未测试" if ai["installed"] else "未配置"},
                                    {"name": "素材规划Agent", "status": asset_ai["status"]},
                                    {"name": "视频构建Agent", "status": render_ai["status"]},
                                    {"name": "质检Agent", "status": "未接入"},
                                    {"name": "发布Agent", "status": "仅预览填充，人工发布"},
                                    {"name": "系统语音生成", "status": voices["capabilities"]["system_status"]},
                                    {"name": "WhisperX自动字幕", "status": media_ai["whisperx"]["status"]},
                                    {"name": "OpenVoice本人克隆", "status": media_ai["openvoice"]["status"]}]
                    self.json_response({"tasks": tasks, "topics": topics, "accounts": accounts, "hotspots": hotspots,
                                        "favorites": seed["douyin_favorite_collections"],
                                        "strategy": seed["strategy"], "platforms": seed["platforms"],
                                        "capabilities": capabilities, "ai": ai, "voices": voices, "media_ai": media_ai,
                                        "asset_ai": asset_ai, "render_ai": render_ai})
            elif re.fullmatch(r"/api/tasks/\d{8}-\d{3}", path):
                with connect() as conn:
                    self.json_response(get_task(conn, path.rsplit("/", 1)[1]))
            elif re.fullmatch(r"/api/files/\d+/media", path):
                self.serve_media(int(path.split("/")[3]), parse_qs(parsed.query).get("download") == ["1"])
            else:
                self.serve_static(path)
        except ApiError as error:
            self.error_response(error)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as error:
            print("GET error:", repr(error), flush=True)
            self.error_response(error)

    def do_POST(self):
        try:
            path = urlsplit(self.path).path
            if V2 and V2.matches(path):
                return V2.handle(self, "POST", path, parse_qs(urlsplit(self.path).query))
            if path == "/api/ai/test":
                self.json_response(test_ai_connection())
                return
            if path == "/api/voices/test":
                self.json_response(test_system_voice())
                return
            if path == "/api/whisperx/test":
                self.json_response(test_whisperx())
                return
            if path == "/api/voices/clone/test":
                self.json_response(test_clone_voice())
                return
            if path == "/api/assets/test":
                self.json_response(test_asset_agent())
                return
            if path == "/api/render/test":
                self.json_response(test_render_agent())
                return
            if path == "/api/voices/samples":
                query = parse_qs(urlsplit(self.path).query)
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    raise ApiError(400, "样本长度无效")
                if length <= 0 or length > MAX_UPLOAD:
                    raise ApiError(413, "样本为空或超过 500MB 限制")
                body = self.rfile.read(length)
                if len(body) != length:
                    raise ApiError(400, "样本上传不完整")
                result = save_voice_sample(query.get("name", [""])[0], query.get("filename", [""])[0],
                                           query.get("authorized", ["false"])[0] == "true", body)
                self.json_response(result, 201)
                return
            generate = re.fullmatch(r"/api/tasks/(\d{8}-\d{3})/generate-scripts", path)
            if generate:
                with connect() as conn:
                    task = get_task(conn, generate.group(1))
                self.json_response(generate_scripts(task))
                return
            generate_audio_match = re.fullmatch(r"/api/tasks/(\d{8}-\d{3})/generate-audio", path)
            if generate_audio_match:
                with connect() as conn:
                    task = get_task(conn, generate_audio_match.group(1))
                self.json_response(generate_audio(task, self.read_json()))
                return
            clone_audio_match = re.fullmatch(r"/api/tasks/(\d{8}-\d{3})/generate-clone-audio", path)
            if clone_audio_match:
                with connect() as conn:
                    task = get_task(conn, clone_audio_match.group(1))
                self.json_response(generate_clone_audio(task, self.read_json()))
                return
            transcribe_match = re.fullmatch(r"/api/tasks/(\d{8}-\d{3})/transcribe", path)
            if transcribe_match:
                with connect() as conn:
                    task = get_task(conn, transcribe_match.group(1))
                self.json_response(transcribe_audio(task, self.read_json()))
                return
            asset_plan_match = re.fullmatch(r"/api/tasks/(\d{8}-\d{3})/generate-asset-plan", path)
            if asset_plan_match:
                with connect() as conn:
                    task = get_task(conn, asset_plan_match.group(1))
                self.json_response(generate_asset_plan(task, self.read_json()))
                return
            render_match = re.fullmatch(r"/api/tasks/(\d{8}-\d{3})/render", path)
            if render_match:
                with connect() as conn:
                    task = get_task(conn, render_match.group(1))
                self.json_response(render_task(task, self.read_json()))
                return
            if path == "/api/tasks":
                self.json_response(create_task(self.read_json()), 201)
                return
            upload = re.fullmatch(r"/api/tasks/(\d{8}-\d{3})/files", path)
            if upload:
                query = parse_qs(urlsplit(self.path).query)
                kind, filename = query.get("kind", [""])[0], query.get("filename", [""])[0]
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    raise ApiError(400, "上传长度无效")
                if length <= 0 or length > MAX_UPLOAD:
                    raise ApiError(413, "文件为空或超过 500MB 限制")
                with connect() as conn:
                    task = get_task(conn, upload.group(1))
                body = self.rfile.read(length)
                if len(body) != length:
                    raise ApiError(400, "文件上传不完整")
                self.json_response(upload_file(task, kind, filename, body), 201)
                return
            action = re.fullmatch(r"/api/tasks/(\d{8}-\d{3})/actions", path)
            if action:
                with connect() as conn:
                    task = get_task(conn, action.group(1))
                self.json_response(task_action(task, self.read_json()))
                return
            raise ApiError(404, "接口不存在")
        except ApiError as error:
            self.error_response(error)
        except Exception as error:
            print("POST error:", repr(error), flush=True)
            self.error_response(error)

    def do_PUT(self):
        try:
            path = urlsplit(self.path).path
            if V2 and V2.matches(path):
                return V2.handle(self, "PUT", path, parse_qs(urlsplit(self.path).query))
            match = re.fullmatch(r"/api/tasks/(\d{8}-\d{3})/(scripts|assets|quality|publications|metrics|subtitles)", path)
            if not match:
                raise ApiError(404, "接口不存在")
            with connect() as conn:
                task = get_task(conn, match.group(1))
            payload = self.read_json()
            handlers = {"scripts": save_scripts, "assets": save_assets, "quality": save_quality,
                        "publications": save_publications, "metrics": save_metrics, "subtitles": edit_subtitles}
            handlers[match.group(2)](task, payload)
            with connect() as conn:
                self.json_response(get_task(conn, match.group(1)))
        except ApiError as error:
            self.error_response(error)
        except Exception as error:
            print("PUT error:", repr(error), flush=True)
            self.error_response(error)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=int(os.environ.get("CONTENT_AGENT_PORT", "8765")))
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        raise SystemExit("端口无效")
    init_db()
    from content_workbench.api.v2 import V2Application
    V2 = V2Application(DB_PATH, ROOT, create_task)
    V2.start()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print("Content Workflow v2: http://127.0.0.1:{}".format(args.port), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        V2.stop()
        server.server_close()
