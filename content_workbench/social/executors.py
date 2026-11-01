import json
import re
import shutil
import tempfile
import time
from pathlib import Path
from urllib.parse import quote

from content_workbench.accounts.existing_browser import body
from content_workbench.domain.errors import DomainError
from content_workbench.publishing.webbridge_worker import Bridge
from content_workbench.social.catalog import get_operation
from content_workbench.storage.db import utcnow
from content_workbench.topics.executors import TopicExecutors
from content_workbench.topics.link_snapshot import validate_public_url

SEARCH_URLS = {
    "douyin": lambda keyword: "https://www.douyin.com/search/" + quote(keyword) + "?type=video",
    "xhs": lambda keyword: "https://www.xiaohongshu.com/search_result?keyword=" + quote(keyword),
    "bilibili": lambda keyword: "https://search.bilibili.com/video?keyword=" + quote(keyword),
    "weibo": lambda keyword: "https://s.weibo.com/weibo?q=" + quote(keyword),
}


def srt_milliseconds(value):
    hours, minutes, rest = value.split(":")
    seconds, milliseconds = rest.split(",")
    return ((int(hours) * 60 + int(minutes)) * 60 + int(seconds)) * 1000 + int(milliseconds)


def parse_srt(text):
    segments = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3 or "-->" not in lines[1]:
            continue
        start, end = [srt_milliseconds(value.strip()) for value in lines[1].split("-->")]
        content = " ".join(lines[2:]).strip()
        if content:
            segments.append({"start_ms": start, "end_ms": end, "text": content})
    return segments


def model_result(payload, operation, source_url, provider_id):
    items = payload.get("items") or []
    if not isinstance(items, list):
        raise DomainError("MODEL_SCHEMA_INVALID", "模型返回的 items 必须是数组", 502, "provider", "重试结构化整理")
    normalized = []
    for item in items[:200]:
        if not isinstance(item, dict):
            continue
        value = {
            "title": str(item.get("title") or "")[:1000],
            "text": str(item.get("text") or "")[:12000],
            "canonical_url": str(item.get("canonical_url") or "")[:4000],
            "author": str(item.get("author") or "")[:500],
            "published_at": item.get("published_at"),
            "metrics": item.get("metrics") if isinstance(item.get("metrics"), dict) else {},
        }
        if any((value["title"], value["text"], value["canonical_url"], value["author"])):
            normalized.append(value)
    return {
        "operation_id": operation["id"],
        "platform": operation["platform"],
        "kind": operation["kind"],
        "source_url": source_url,
        "captured_at": utcnow(),
        "items": normalized,
        "profile": payload.get("profile") if isinstance(payload.get("profile"), dict) else {},
        "metrics": payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {},
        "text": str(payload.get("text") or "")[:30000],
        "evidence": payload.get("evidence") if isinstance(payload.get("evidence"), list) else [],
        "provider": provider_id,
    }


class SocialExecutors:
    def __init__(self, service, topics):
        self.service = service
        self.topics = topics
        self.root = Path(service.root).resolve()

    def mapping(self):
        return {"social.execute": self.execute}

    def execute(self, job, context):
        run_id = job["aggregate_id"]
        run = self.service.get_run(run_id)
        operation = get_operation(run["operation_id"])
        self.service.start_run(run_id)
        try:
            if operation["executor"] == "douyin_hot":
                result = self.douyin_hot(context)
            elif operation["executor"] == "browser_model":
                result = self.browser_model(run, operation, context)
            elif operation["executor"] == "local_download":
                result = self.local_download(run["input"], context)
            elif operation["executor"] == "local_transcript":
                result = self.local_transcript(run["input"], context)
            else:
                raise DomainError("SOCIAL_ADAPTER_REQUIRED", "本地适配器尚未完成", 501)
            self.service.finish_run(run_id, result)
            return {"run_id": run_id, "status": "succeeded", "items": len(result.get("items") or [])}
        except DomainError as error:
            self.service.fail_run(run_id, error.as_dict()["error"])
            raise
        except Exception as error:
            self.service.fail_run(run_id, {"code": "WORKER_ERROR", "message": str(error)[:1000]})
            raise

    def douyin_hot(self, context):
        result = TopicExecutors(self.topics).browser(context, "hot", "social_douyin_hot")
        items = result.get("items") or []
        for item in items:
            self.topics.upsert_item(item, "hot")
        return {"operation_id": "douyin:hot/search/list", "platform": "douyin", "kind": "hot_list",
                "items": items, "captured_at": utcnow(), "provider": "playwright"}

    def source_url(self, operation, data):
        if operation["kind"] == "search":
            builder = SEARCH_URLS.get(operation["platform"])
            if not builder:
                raise DomainError("SOCIAL_SEARCH_ADAPTER_REQUIRED", "该平台搜索适配器尚未完成", 501, "url", "改用公开结果页链接或其他 supported 能力")
            return builder(str(data["keyword"]).strip())
        return data.get("url") or data.get("note_url") or data.get("profile_url")

    def browser_model(self, run, operation, context):
        source_url = self.source_url(operation, run["input"])
        validate_public_url(source_url)
        context.progress("browser_read", 0.15)
        bridge = Bridge()
        bridge.goto(source_url)
        time.sleep(4)
        text = body(bridge)
        if len(text) < 3000 and any(marker in text for marker in ("扫码登录", "登录后查看", "验证码", "访问验证")):
            raise DomainError("SOCIAL_LOGIN_REQUIRED", "公开页面需要登录或完成平台验证", 409, "url", "在现有浏览器完成登录或验证后重试")
        raw = bridge.evaluate("""() => ({
          title: document.title || '',
          canonical_url: location.href,
          cover_url: document.querySelector('meta[property="og:image"]')?.content || document.querySelector('video')?.poster || '',
          links: Array.from(document.querySelectorAll('a[href]')).slice(0,200).map(a => ({
            url: a.href, text: (a.innerText || '').trim().slice(0,500)
          })).filter(x => x.text)
        })""") or {}
        final_url = bridge.snapshot().get("url") or source_url
        raw_links = {item.get("url") for item in raw.get("links") or []}
        evidence = {"text": text[:40000], "document": raw}
        context.progress("model_structure", 0.45)
        prompt = json.dumps({"operation": {"platform": operation["platform"], "kind": operation["kind"]},
                             "source_url": final_url, "page_evidence": evidence}, ensure_ascii=False)
        provider = self.service.providers.get(run["provider"])
        payload = provider.complete_json(prompt, context, self.root / "agents/social-data-extractor.md", stage="social_model")
        result = model_result(payload, operation, final_url, run["provider"])
        for item in result["items"]:
            candidate = item.get("canonical_url")
            if candidate and candidate != final_url and candidate not in raw_links:
                item["canonical_url"] = ""
        if operation["kind"] == "detail" and result["items"]:
            item = result["items"][0]
            platform = "wechat_official_account" if operation["path"].startswith("mp/") else operation["platform"]
            self.topics.upsert_item({"title": item["title"] or raw.get("title") or "未读取标题",
                                     "canonical_url": item["canonical_url"] or final_url,
                                     "author": item["author"], "published_at": item["published_at"],
                                     "metadata": {**item["metrics"], "cover_url": raw.get("cover_url"),
                                                  "source": "local_browser_model", "text": item["text"]}},
                                    "competitor", collection_title=self.topics.settings()["competitor_collection"], platform=platform)
        return result

    def local_download(self, data, context):
        validate_public_url(data["url"])
        binary = shutil.which("yt-dlp")
        if not binary:
            raise DomainError("YTDLP_NOT_FOUND", "未找到本机 yt-dlp", 503, "provider", "安装 yt-dlp 后重试")
        stdout, _ = context.run_process([binary, "-J", "--no-playlist", "--no-warnings", data["url"]],
                                        timeout=180, stage="local_video_probe", cwd=self.root)
        payload = json.loads(stdout)
        tracks = []
        for item in payload.get("formats") or []:
            if not item.get("url"):
                continue
            tracks.append({key: item.get(key) for key in ("format_id", "url", "ext", "vcodec", "acodec", "width", "height",
                                                          "filesize", "filesize_approx", "tbr", "format_note")})
        if not tracks:
            raise DomainError("VIDEO_TRACKS_EMPTY", "本地解析器没有返回可下载轨道", 502, "url", "检查公开链接和 yt-dlp 版本")
        return {"operation_id": "bilibili:video/download-links", "platform": "bilibili", "title": payload.get("title"),
                "content_id": payload.get("id"), "webpage_url": payload.get("webpage_url") or data["url"],
                "headers": payload.get("http_headers") or {}, "download_manifest": {"tracks": tracks},
                "provider": "yt_dlp", "captured_at": utcnow()}

    def local_transcript(self, data, context):
        media = Path(data["media_path"]).expanduser()
        if not media.is_absolute():
            media = self.root / media
        media = media.resolve()
        if self.root not in media.parents or not media.is_file():
            raise DomainError("SOCIAL_MEDIA_INVALID", "媒体文件必须位于项目目录内", 422, "media_path", "选择项目目录内仍存在的音视频文件")
        python = self.root / ".venv-faster-whisper/bin/python"
        worker = self.root / "workers/whisperx_worker.py"
        ffmpeg = shutil.which("ffmpeg")
        if not python.is_file() or not worker.is_file() or not ffmpeg:
            raise DomainError("LOCAL_ASR_NOT_CONFIGURED", "本地 faster-whisper 转写环境未完成", 503, "provider", "先安装本地转写依赖")
        with tempfile.TemporaryDirectory(prefix="social-asr-") as directory:
            work = Path(directory)
            audio = work / "audio.wav"
            subtitle = work / "subtitle.srt"
            context.run_process([ffmpeg, "-v", "error", "-y", "-i", str(media), "-vn", "-ac", "1", "-ar", "16000", str(audio)],
                                timeout=600, stage="local_audio_extract", cwd=self.root)
            stdout, _ = context.run_process([str(python), str(worker), "--audio", str(audio), "--model", data.get("model", "base"),
                                             "--language", "zh", "--output", str(subtitle)], timeout=3600,
                                            stage="local_faster_whisper", cwd=self.root)
            segments = parse_srt(subtitle.read_text(encoding="utf-8"))
        if not segments:
            raise DomainError("LOCAL_ASR_EMPTY", "本地转写没有生成有效字幕", 502, "media_path", "检查音轨后重试")
        return {"operation_id": "media_transcript:media/video-speech-text/submit", "status": "succeeded",
                "transcript": {"text": "\n".join(item["text"] for item in segments), "segments": segments},
                "provider": "faster_whisper", "model": data.get("model", "base"), "worker_result": json.loads(stdout)}
