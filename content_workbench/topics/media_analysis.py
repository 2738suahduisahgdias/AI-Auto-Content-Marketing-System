import csv
import io
import json
import shutil
from pathlib import Path

from content_workbench.domain.errors import DomainError
from content_workbench.domain.services import Workbench
from content_workbench.media.probe import probe
from content_workbench.storage.db import PROJECT_ROOT, dumps, file_hash, immediate, new_id, payload_hash, utcnow

PIPELINE = "douyin_frame_ocr_v1"


def ocr_tsv(text):
    words = []
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    for row in reader:
        value = (row.get("text") or "").strip()
        try:
            confidence = float(row.get("conf") or -1)
        except ValueError:
            confidence = -1
        if value and confidence >= 20:
            words.append((value, confidence))
    if not words:
        return "", 0
    return " ".join(word for word, _ in words), round(sum(conf for _, conf in words) / len(words), 2)


def analyze_video(workbench, service, item_id, video_path, context):
    video_path = Path(video_path).resolve()
    info = probe(video_path, "video/mp4")
    if not any(stream.get("codec_type") == "video" for stream in info.get("streams", [])):
        raise DomainError("VIDEO_STREAM_MISSING", "下载文件只有音频，没有可抽帧画面", 422, "file", "重新下载含画面的 MP4 视频，不要上传纯音频")
    if info["duration_seconds"] > 900:
        raise DomainError("VIDEO_TOO_LONG", "单条拆解视频不能超过15分钟", 422, "file", "分段后重试或上传短视频")
    digest = file_hash(video_path)
    cache_key = digest + ":" + PIPELINE
    with service.conn(readonly=True) as conn:
        cached = conn.execute("SELECT id FROM wb_analyses WHERE cache_key=?", (cache_key,)).fetchone()
        if cached:
            return {"analysis_id": cached[0], "cache_hit": True}
    source_asset = workbench.register_asset(video_path, {"kind": "research_video", "research_item_id": item_id}, "research_only")
    with workbench.conn() as conn, immediate(conn):
        conn.execute("INSERT OR IGNORE INTO wb_asset_links VALUES (?,?, 'research_item',?,?,NULL,?)",
                     (new_id("assetlink"), source_asset, item_id, "source_video", utcnow()))
    frames_dir = workbench.root / "assets" / "research" / item_id / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    context.progress("extract_frames", 0.25)
    context.run_process([shutil.which("ffmpeg"), "-v", "error", "-y", "-i", str(video_path),
                         "-vf", "fps=30,select='not(mod(n,60))',scale=1280:-2", "-frames:v", "60", str(frames_dir / "frame-%03d.png")],
                        timeout=600, stage="extract_frames")
    frame_paths = sorted(frames_dir.glob("frame-*.png"))
    if not frame_paths:
        raise DomainError("NO_VIDEO_FRAMES", "没有抽到视频帧", 502, "file", "确认视频可解码后重试")
    context.progress("ocr_frames", 0.4)
    ocr_python = PROJECT_ROOT / ".venv-topics/bin/python"
    ocr_worker = PROJECT_ROOT / "content_workbench/topics/ocr_worker.py"
    if not ocr_python.is_file() or not ocr_worker.is_file():
        raise DomainError("OCR_NOT_CONFIGURED", "RapidOCR 本地环境未完成", 503, "settings", "安装隔离 RapidOCR 后重试")
    stdout, _ = context.run_process([str(ocr_python), str(ocr_worker), "--frames", str(frames_dir)], timeout=900, stage="ocr_frames")
    try:
        ocr_results = json.loads(stdout)
    except json.JSONDecodeError:
        raise DomainError("OCR_PROTOCOL_ERROR", "OCR 没有返回有效结果", 502, "file", "检查本地 OCR 环境")
    analysis_id = new_id("analysis")
    evidence = []
    for index, (frame, ocr) in enumerate(zip(frame_paths, ocr_results), 1):
        context.progress("ocr_frames", 0.4 + 0.5 * index / len(frame_paths))
        frame_asset = workbench.register_asset(frame, {"kind": "research_frame", "item_id": item_id, "frame": index}, "research_only")
        evidence.append({"asset_id": frame_asset, "start_ms": (index - 1) * 2000, "end_ms": index * 2000,
                         "text_content": ocr["text"], "metadata": {"confidence": ocr["confidence"], "frame": index}})
    report = {"pipeline": PIPELINE, "duration_seconds": info["duration_seconds"], "frame_count": len(frame_paths),
              "frames_with_text": sum(bool(item["text_content"]) for item in evidence),
              "ocr_engine": "RapidOCR ONNX 中文+英文", "frame_interval_seconds": 2,
              "timeline": [{"start_ms": item["start_ms"], "end_ms": item["end_ms"], "text": item["text_content"],
                            "confidence": item["metadata"]["confidence"], "asset_id": item["asset_id"]} for item in evidence],
              "limitations": ["OCR是画面文字识别，不等同于口播全文", "未识别文字不代表画面没有文字", "未对观点或爆款原因作事实判断"]}
    with workbench.conn() as conn, immediate(conn):
        conn.execute("INSERT INTO wb_analyses VALUES (?,?,?,?,?,?,?,?,'succeeded',?)",
                     (analysis_id, item_id, source_asset, PIPELINE, dumps({"ocr": "rapidocr_onnxruntime", "languages": "zh+en"}),
                      payload_hash({"pipeline": PIPELINE}), cache_key, dumps(report), utcnow()))
        for item in evidence:
            conn.execute("INSERT INTO wb_evidence VALUES (?,?,?,?,?,?,?,?)",
                         (new_id("evidence"), analysis_id, item["asset_id"], "frame_ocr", item["start_ms"], item["end_ms"],
                          item["text_content"], dumps(item["metadata"])))
            conn.execute("INSERT OR IGNORE INTO wb_asset_links VALUES (?,?, 'research_item',?,?,NULL,?)",
                         (new_id("assetlink"), item["asset_id"], item_id, "frame_" + analysis_id, utcnow()))
        Workbench.event(conn, "research_item", item_id, "research.analyzed", {"analysis_id": analysis_id, "frames": len(frame_paths)})
    return {"analysis_id": analysis_id, "cache_hit": False, "frames": len(frame_paths),
            "frames_with_text": report["frames_with_text"]}
