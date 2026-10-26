import json
import math
import re
import shutil
import socket
from pathlib import Path

from content_workbench.domain.errors import DomainError
from content_workbench.media.probe import probe
from content_workbench.storage.db import connect


def captions(text):
    result = []
    pattern = r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})[^\r\n]*\r?\n(.*?)(?=\r?\n\s*\r?\n|\Z)"
    for match in re.finditer(pattern, text, re.S):
        values = [int(value) for value in match.groups()[:8]]
        start = ((values[0] * 60 + values[1]) * 60 + values[2]) * 1000 + values[3]
        end = ((values[4] * 60 + values[5]) * 60 + values[6]) * 1000 + values[7]
        value = re.sub(r"\s+", " ", match.group(9)).strip()
        if value and end > start:
            result.append({"text": value, "startMs": start, "endMs": end, "timestampMs": None, "confidence": None})
    return result


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def render_remotion(workbench, item_id, context):
    manifest = workbench.validate_render(item_id, "remotion")
    item = workbench.get_item(item_id)
    root = workbench.root
    remotion_root = root / "remotion-app"
    staging = remotion_root / "public" / "assets" / ("v2-" + context.job_id)
    staging.mkdir(parents=True, exist_ok=False)
    try:
        with workbench.conn(readonly=True) as conn:
            ids = [manifest["audio_asset_id"], manifest["subtitle_asset_id"]]
            rows = {row["id"]: dict(row) for row in conn.execute("SELECT * FROM wb_assets WHERE id IN (?,?)", ids)}
        audio = rows[manifest["audio_asset_id"]]
        subtitle = rows[manifest["subtitle_asset_id"]]
        audio_path = (root / audio["storage_key"]).resolve()
        subtitle_path = (root / subtitle["storage_key"]).resolve()
        for path in (audio_path, subtitle_path):
            if root not in path.parents or not path.is_file():
                raise DomainError("RENDER_ASSET_MISSING", "渲染输入文件不存在或路径无效", 422, "manifest", "重新上传输入资产", item_id)
        duration = float(json.loads(audio["media_info_json"]).get("duration_seconds", 0))
        if duration <= 0:
            raise DomainError("INVALID_AUDIO_DURATION", "活动音频没有有效时长", 422, "audio_asset_id", "重新上传或生成音频", item_id)
        shutil.copyfile(audio_path, staging / "narration.wav")
        srt = subtitle_path.read_text(encoding="utf-8-sig")
        scenes = []
        storyboard_id = item["active_revisions"].get("storyboard")
        if storyboard_id:
            storyboard = workbench.get_revision(storyboard_id)["payload"]
            for index, scene in enumerate(storyboard.get("scenes", [])):
                start = float(scene.get("start_seconds", scene.get("start_ms", 0) / 1000))
                end = float(scene.get("end_seconds", scene.get("end_ms", 0) / 1000))
                if start < 0 or end <= start or end > duration + 0.1:
                    raise DomainError("INVALID_STORYBOARD_TIME", "第 {} 个分镜时间越界".format(index + 1), 422,
                                      "storyboard.scenes[{}]".format(index), "修正分镜时间后重试", item_id)
                scenes.append({"id": str(scene.get("id") or "scene-" + str(index)), "name": str(scene.get("name") or "镜头 " + str(index + 1)),
                               "start_seconds": start, "end_seconds": min(end, duration), "asset_type": scene.get("asset_type", "own"),
                               "description": str(scene.get("description") or scene.get("fallback_text") or item["campaign"]["title"]), "media": None})
        if not scenes:
            descriptions = [item["campaign"]["title"], "真实任务与完整流程", "人工检查每一步", "结果可核验，再进入发布"]
            scenes = [{"id": "text-" + str(index), "name": "文字卡 {:02d}".format(index + 1),
                       "start_seconds": duration * index / 4, "end_seconds": duration * (index + 1) / 4,
                       "asset_type": "own", "description": value, "media": None} for index, value in enumerate(descriptions)]
        props = {"title": item["campaign"]["title"], "audio": "assets/{}/narration.wav".format(staging.name),
                 "captions": captions(srt), "durationSeconds": duration, "scenes": scenes}
        props_path = staging / "props.json"
        props_path.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
        output = staging / "render.mp4"
        context.run_process(["npx", "remotion", "render", "src/index.ts", "TalkingHead", str(output),
                             "--props=" + str(props_path), "--codec=h264", "--port=" + str(free_port())],
                            timeout=1800, stage="remotion_render", cwd=remotion_root)
        info = probe(output, "video/mp4")
        streams = info["streams"]
        if not any(stream.get("codec_type") == "audio" for stream in streams) or not any(stream.get("codec_type") == "video" for stream in streams):
            raise DomainError("RENDER_TRACKS_MISSING", "成片必须包含音频和视频轨", 502, "render", "检查 Remotion 输出")
        video = next(stream for stream in streams if stream["codec_type"] == "video")
        if video.get("width") != 1080 or video.get("height") != 1920:
            raise DomainError("RENDER_SIZE_MISMATCH", "成片不是 1080×1920", 502, "render", "检查平台渲染 profile")
        if abs(info["duration_seconds"] - duration) > max(0.1, 2 / 30):
            raise DomainError("RENDER_DURATION_MISMATCH", "成片时长与活动音频不一致", 502, "render", "检查字幕和分镜时长")
        asset_id = workbench.register_asset(output, {"kind": "render", "item_id": item_id, "manifest": manifest}, "owned")
        return asset_id, info
    finally:
        shutil.rmtree(staging, ignore_errors=True)
