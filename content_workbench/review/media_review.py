import hashlib
import json
import math
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OCR_PYTHON = PROJECT_ROOT / ".venv-topics/bin/python"

_OCR_WORKER = r'''
import json
import sys
from rapidocr_onnxruntime import RapidOCR

with open(sys.argv[1], encoding="utf-8") as handle:
    frames = json.load(handle)
engine = RapidOCR()
results = []
for frame in frames:
    output, _ = engine(frame["path"])
    lines = []
    for item in output or []:
        if len(item) < 3 or float(item[2]) < 0.2:
            continue
        lines.append({"box": item[0], "text": str(item[1]), "confidence": float(item[2])})
    results.append({"timestamp_seconds": frame["timestamp_seconds"], "lines": lines})
print(json.dumps(results, ensure_ascii=False))
'''


class MediaToolError(Exception):
    pass


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tail(value, limit=1200):
    return (value or "").strip()[-limit:]


def build_safe_transcode_command(source, output, width=1080, height=1920):
    source = Path(source)
    output = Path(output)
    if source.resolve() == output.resolve():
        raise ValueError("转码输出不能覆盖原文件")
    if output.suffix.lower() != ".mp4":
        raise ValueError("安全转码候选仅支持 MP4 输出")
    if width <= 0 or height <= 0 or width % 2 or height % 2:
        raise ValueError("转码宽高必须是正偶数")
    return [
        shutil.which("ffmpeg") or "ffmpeg", "-n", "-i", str(source),
        "-map", "0:v:0", "-map", "0:a:0",
        "-vf", "scale={}:{}:force_original_aspect_ratio=decrease,"
               "pad={}:{}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p".format(width, height, width, height),
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", str(output),
    ]


def _faststart(path):
    try:
        with Path(path).open("rb") as handle:
            saw_mdat = False
            while True:
                header = handle.read(8)
                if not header:
                    return None
                if len(header) != 8:
                    return None
                size = int.from_bytes(header[:4], "big")
                kind = header[4:8]
                header_size = 8
                if size == 1:
                    extended = handle.read(8)
                    if len(extended) != 8:
                        return None
                    size = int.from_bytes(extended, "big")
                    header_size = 16
                elif size == 0:
                    size = path.stat().st_size - handle.tell() + 8
                if size < header_size:
                    return None
                if kind == b"moov":
                    return not saw_mdat
                if kind == b"mdat":
                    saw_mdat = True
                handle.seek(size - header_size, 1)
    except (OSError, ValueError):
        return None


class MediaReviewer:
    def __init__(self, ffmpeg=None, ffprobe=None, ocr_python=None,
                 target_width=1080, target_height=1920, min_duration=1.0,
                 max_duration=900.0, min_width=360, min_height=640,
                 aspect_tolerance=0.02, black_min_duration=0.25,
                 silence_min_duration=0.5, silence_noise_db=-45.0,
                 low_mean_volume_db=-35.0, high_mean_volume_db=-8.0,
                 clipping_peak_db=-0.1, ocr_interval=2.0, ocr_max_frames=60,
                 subtitle_safe_area=(0.05, 0.05, 0.95, 0.95),
                 command_timeout=120, ocr_timeout=300):
        self.ffmpeg = ffmpeg or "ffmpeg"
        self.ffprobe = ffprobe or "ffprobe"
        self.ocr_python = str(ocr_python or DEFAULT_OCR_PYTHON)
        self.target_width = int(target_width)
        self.target_height = int(target_height)
        self.min_duration = float(min_duration)
        self.max_duration = float(max_duration)
        self.min_width = int(min_width)
        self.min_height = int(min_height)
        self.aspect_tolerance = float(aspect_tolerance)
        self.black_min_duration = float(black_min_duration)
        self.silence_min_duration = float(silence_min_duration)
        self.silence_noise_db = float(silence_noise_db)
        self.low_mean_volume_db = float(low_mean_volume_db)
        self.high_mean_volume_db = float(high_mean_volume_db)
        self.clipping_peak_db = float(clipping_peak_db)
        self.ocr_interval = float(ocr_interval)
        self.ocr_max_frames = int(ocr_max_frames)
        self.subtitle_safe_area = tuple(float(value) for value in subtitle_safe_area)
        self.command_timeout = int(command_timeout)
        self.ocr_timeout = int(ocr_timeout)
        if len(self.subtitle_safe_area) != 4:
            raise ValueError("subtitle_safe_area 必须是 left, top, right, bottom")
        left, top, right, bottom = self.subtitle_safe_area
        if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
            raise ValueError("subtitle_safe_area 必须是画面内的有效归一化区域")
        if self.ocr_interval <= 0 or self.ocr_max_frames <= 0:
            raise ValueError("OCR 抽帧间隔和帧数上限必须大于 0")

    def review(self, path, check_ocr=True):
        path = Path(path).resolve()
        issues = []
        checks = {name: "pending" for name in (
            "probe", "duration", "aspect_ratio", "resolution", "video_codec",
            "pixel_format", "audio_track", "audio_codec", "faststart",
            "black_frames", "silence", "volume", "subtitle_bounds",
        )}

        def mark(check, status):
            rank = {"pending": 0, "skipped": 1, "not_applicable": 1, "passed": 2,
                    "warning": 3, "unavailable": 4, "failed": 5}
            if rank[status] > rank[checks[check]]:
                checks[check] = status

        def issue(kind, severity, check, recommendation, evidence=None,
                  timestamp=None, end=None):
            issues.append({
                "type": kind, "severity": severity,
                "timestamp_seconds": timestamp, "end_seconds": end,
                "evidence": evidence or {}, "recommendation": recommendation,
                "auto_fixable": False,
            })
            mark(check, {"error": "failed", "warning": "warning"}.get(severity, "passed"))

        if not path.is_file():
            issue("source_not_found", "error", "probe", "确认上传文件完整且路径可读取",
                  {"path": str(path)})
            return self._result(path, None, issues, checks, None, False)

        before = _sha256(path)
        ffmpeg = shutil.which(self.ffmpeg)
        ffprobe = shutil.which(self.ffprobe)
        if not ffmpeg:
            issue("ffmpeg_unavailable", "error", "probe", "安装并配置 FFmpeg 后重新预审",
                  {"executable": self.ffmpeg})
        if not ffprobe:
            issue("ffprobe_unavailable", "error", "probe", "安装并配置 FFprobe 后重新预审",
                  {"executable": self.ffprobe})
        if not ffmpeg or not ffprobe:
            return self._result(path, None, issues, checks, before, before == _sha256(path))

        try:
            data = self._probe(ffprobe, path)
        except MediaToolError as exc:
            issue("media_probe_failed", "error", "probe", "重新导出可完整解码的媒体后上传",
                  {"detail": str(exc)})
            return self._result(path, None, issues, checks, before, before == _sha256(path))
        mark("probe", "passed")
        streams = data.get("streams", [])
        video = next((item for item in streams if item.get("codec_type") == "video"), None)
        audio = next((item for item in streams if item.get("codec_type") == "audio"), None)
        duration = self._duration(data, video, audio)
        metadata = {
            "duration_seconds": duration,
            "format_name": data.get("format", {}).get("format_name"),
            "video": video,
            "audio": audio,
            "stream_count": len(streams),
        }
        if duration is None or duration <= 0:
            issue("invalid_duration", "error", "duration", "重新导出具有有效时长的完整视频",
                  {"duration_seconds": duration})
        elif duration < self.min_duration or duration > self.max_duration:
            issue("duration_out_of_range", "error", "duration", "按平台时长要求重新剪辑后人工复审",
                  {"duration_seconds": duration, "minimum_seconds": self.min_duration,
                   "maximum_seconds": self.max_duration}, timestamp=0.0)
        else:
            mark("duration", "passed")

        if not video:
            issue("video_track_missing", "error", "video_codec", "上传包含画面和声音的完整视频")
            for name in ("aspect_ratio", "resolution", "pixel_format", "black_frames", "subtitle_bounds"):
                mark(name, "not_applicable")
        else:
            self._review_video_shape(video, issue, mark)
            if (video.get("codec_name") or "").lower() not in ("h264", "avc1"):
                issue("unsupported_video_codec", "error", "video_codec",
                      "使用安全转码候选转为 H264，输出后重新完整预审",
                      {"codec_name": video.get("codec_name")})
            else:
                mark("video_codec", "passed")
            if video.get("pix_fmt") != "yuv420p":
                issue("unsupported_pixel_format", "error", "pixel_format",
                      "使用安全转码候选转为 yuv420p，输出后重新完整预审",
                      {"pix_fmt": video.get("pix_fmt")})
            else:
                mark("pixel_format", "passed")

        if not audio:
            issue("audio_track_missing", "error", "audio_track", "补回音轨后重新导出；不要自动填充静音",
                  timestamp=0.0)
            mark("audio_codec", "not_applicable")
            for name in ("silence", "volume"):
                mark(name, "not_applicable")
        else:
            mark("audio_track", "passed")
            if (audio.get("codec_name") or "").lower() != "aac":
                issue("unsupported_audio_codec", "error", "audio_codec",
                      "使用安全转码候选转为 AAC，输出后重新完整预审",
                      {"codec_name": audio.get("codec_name")})
            else:
                mark("audio_codec", "passed")

        faststart = _faststart(path)
        metadata["faststart"] = faststart
        if faststart is False:
            issue("faststart_missing", "warning", "faststart",
                  "使用安全转码候选将 moov 元数据前置，输出后重新预审",
                  {"container": metadata["format_name"]})
        elif faststart is None:
            issue("faststart_unknown", "warning", "faststart",
                  "封装为 MP4 并启用 faststart 后重新预审",
                  {"container": metadata["format_name"]})
        else:
            mark("faststart", "passed")

        if video:
            try:
                intervals = self._black_frames(ffmpeg, path)
                for start, end, black_duration in intervals:
                    issue("black_frames", "warning", "black_frames",
                          "人工确认黑帧是否有意；如需删除请重新剪辑，预审不会自动剪除",
                          {"start_seconds": start, "end_seconds": end,
                           "duration_seconds": black_duration}, start, end)
                if not intervals:
                    mark("black_frames", "passed")
            except MediaToolError as exc:
                issue("black_frame_check_failed", "error", "black_frames",
                      "检查视频解码和 FFmpeg blackdetect 后重试", {"detail": str(exc)})
        if audio:
            try:
                intervals = self._silence(ffmpeg, path, duration)
                for start, end, silence_duration in intervals:
                    issue("silence", "warning", "silence",
                          "人工确认静音是否有意；如需删除请重新剪辑，预审不会自动剪除",
                          {"start_seconds": start, "end_seconds": end,
                           "duration_seconds": silence_duration}, start, end)
                if not intervals:
                    mark("silence", "passed")
            except MediaToolError as exc:
                issue("silence_check_failed", "error", "silence",
                      "检查音轨解码和 FFmpeg silencedetect 后重试", {"detail": str(exc)})
            try:
                self._volume(ffmpeg, path, issue, mark)
            except MediaToolError as exc:
                issue("volume_check_failed", "error", "volume",
                      "检查音轨解码和 FFmpeg volumedetect 后重试", {"detail": str(exc)})

        limitations = [
            "机器预审只提供风险线索，发布前仍须人工终审",
            "黑帧和静音仅报告，不自动剪除",
            "OCR 抽帧识别不能证明未抽到的画面没有字幕或越界文字",
        ]
        if video and check_ocr:
            try:
                with tempfile.TemporaryDirectory(prefix="media-review-") as temp:
                    ocr, truncated = self._ocr(ffmpeg, path, Path(temp), duration, video)
                for item in ocr:
                    self._subtitle_issues(item, video, issue)
                if not any(item["type"] == "subtitle_out_of_bounds" for item in issues):
                    mark("subtitle_bounds", "passed")
                if truncated:
                    issue("ocr_sample_truncated", "warning", "subtitle_bounds",
                          "提高抽帧上限或分段复审，避免漏检长视频中的字幕",
                          {"max_frames": self.ocr_max_frames, "interval_seconds": self.ocr_interval})
                    limitations.append("OCR 达到抽帧上限，本次未覆盖全部视频")
            except MediaToolError as exc:
                issue("ocr_unavailable", "error", "subtitle_bounds",
                      "配置可用的 RapidOCR 隔离环境后重试；OCR 未执行不能视为字幕检查通过",
                      {"detail": str(exc), "engine": "rapidocr_onnxruntime"})
        elif not check_ocr:
            mark("subtitle_bounds", "skipped")
            limitations.append("本次按调用方要求跳过 OCR，字幕越界检查未执行")

        unchanged = before == _sha256(path)
        if not unchanged:
            issue("source_changed_during_review", "error", "probe",
                  "源文件在审核期间发生变化，停止使用本次结果并重新上传",
                  {"sha256_before": before, "sha256_after": _sha256(path)})
        return self._result(path, metadata, issues, checks, before, unchanged, limitations)

    def _run(self, command, timeout=None):
        try:
            result = subprocess.run(command, capture_output=True, text=True,
                                    timeout=timeout or self.command_timeout)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise MediaToolError(str(exc))
        if result.returncode:
            raise MediaToolError(_tail(result.stderr) or "进程退出码 {}".format(result.returncode))
        return result

    def _probe(self, executable, path):
        command = [executable, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]
        result = self._run(command, min(self.command_timeout, 60))
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise MediaToolError("FFprobe 返回无效 JSON: {}".format(exc))

    @staticmethod
    def _duration(data, video, audio):
        values = [data.get("format", {}).get("duration")]
        values.extend(item.get("duration") for item in (video, audio) if item)
        for value in values:
            try:
                number = float(value)
                if math.isfinite(number) and number > 0:
                    return number
            except (TypeError, ValueError):
                pass
        return None

    def _review_video_shape(self, video, issue, mark):
        width = int(video.get("width") or 0)
        height = int(video.get("height") or 0)
        if width <= 0 or height <= 0:
            issue("invalid_resolution", "error", "resolution", "重新导出具有有效宽高的视频",
                  {"width": width, "height": height})
            mark("aspect_ratio", "not_applicable")
            return
        display_ratio = video.get("display_aspect_ratio")
        try:
            numerator, denominator = display_ratio.split(":")
            ratio = float(numerator) / float(denominator)
        except (AttributeError, ValueError, ZeroDivisionError):
            ratio = width / height
        target_ratio = self.target_width / self.target_height
        evidence = {"width": width, "height": height, "display_aspect_ratio": ratio,
                    "target_width": self.target_width, "target_height": self.target_height,
                    "target_aspect_ratio": target_ratio}
        if abs(ratio - target_ratio) > self.aspect_tolerance:
            issue("aspect_ratio_mismatch", "warning", "aspect_ratio",
                  "使用等比缩放加留白的安全候选，或人工重新构图；不要直接拉伸画面", evidence)
        else:
            mark("aspect_ratio", "passed")
        if width < self.min_width or height < self.min_height:
            issue("resolution_too_low", "error", "resolution",
                  "换用更高质量的源视频；放大低清源不会恢复细节",
                  {**evidence, "minimum_width": self.min_width, "minimum_height": self.min_height})
        elif width != self.target_width or height != self.target_height:
            issue("resolution_mismatch", "warning", "resolution",
                  "使用等比缩放加留白的安全候选，输出后检查清晰度和构图", evidence)
        else:
            mark("resolution", "passed")

    def _black_frames(self, executable, path):
        graph = "blackdetect=d={}:pix_th=0.10:pic_th=0.98".format(self.black_min_duration)
        result = self._run([executable, "-hide_banner", "-nostats", "-i", str(path),
                            "-map", "0:v:0", "-vf", graph, "-an", "-f", "null", "-"])
        pattern = re.compile(r"black_start:([0-9.]+)\s+black_end:([0-9.]+)\s+black_duration:([0-9.]+)")
        return [tuple(float(value) for value in match.groups()) for match in pattern.finditer(result.stderr)]

    def _silence(self, executable, path, duration):
        graph = "silencedetect=noise={}dB:d={}".format(self.silence_noise_db, self.silence_min_duration)
        result = self._run([executable, "-hide_banner", "-nostats", "-i", str(path),
                            "-map", "0:a:0", "-af", graph, "-vn", "-f", "null", "-"])
        intervals = []
        start = None
        for line in result.stderr.splitlines():
            found = re.search(r"silence_start:\s*([0-9.]+)", line)
            if found:
                start = float(found.group(1))
            found = re.search(r"silence_end:\s*([0-9.]+)\s*\|\s*silence_duration:\s*([0-9.]+)", line)
            if found and start is not None:
                intervals.append((start, float(found.group(1)), float(found.group(2))))
                start = None
        if start is not None and duration:
            intervals.append((start, duration, max(0.0, duration - start)))
        return intervals

    def _volume(self, executable, path, issue, mark):
        result = self._run([executable, "-hide_banner", "-nostats", "-i", str(path),
                            "-map", "0:a:0", "-af", "volumedetect", "-vn", "-f", "null", "-"])
        values = {}
        for name in ("mean_volume", "max_volume"):
            found = re.search(name + r":\s*(-?(?:[0-9.]+|inf))\s*dB", result.stderr)
            if found:
                value = float(found.group(1))
                values[name] = value if math.isfinite(value) else None
        if "mean_volume" not in values or "max_volume" not in values:
            raise MediaToolError("volumedetect 未返回 mean_volume/max_volume")
        mean = values["mean_volume"]
        peak = values["max_volume"]
        if mean is not None and mean < self.low_mean_volume_db:
            issue("volume_too_low", "warning", "volume", "人工试听并重新混音；不要只靠放大峰值修复",
                  {**values, "threshold_db": self.low_mean_volume_db}, 0.0)
        elif mean is not None and mean > self.high_mean_volume_db:
            issue("volume_too_high", "warning", "volume", "人工试听并降低整体响度，避免失真",
                  {**values, "threshold_db": self.high_mean_volume_db}, 0.0)
        if peak is not None and peak >= self.clipping_peak_db:
            issue("audio_clipping_risk", "warning", "volume", "人工检查爆音并保留峰值余量后重新混音",
                  {**values, "threshold_db": self.clipping_peak_db}, 0.0)
        mark("volume", "passed")

    def _ocr(self, executable, path, temp, duration, video):
        frames = temp / "frames"
        frames.mkdir()
        output = frames / "frame-%04d.png"
        fps = 1.0 / self.ocr_interval
        self._run([executable, "-v", "error", "-i", str(path), "-map", "0:v:0",
                   "-vf", "fps={}".format(fps), "-frames:v", str(self.ocr_max_frames),
                   str(output)], self.command_timeout)
        paths = sorted(frames.glob("frame-*.png"))
        if not paths:
            raise MediaToolError("FFmpeg 没有抽出可供 OCR 的视频帧")
        manifest = [{"path": str(frame), "timestamp_seconds": min(index * self.ocr_interval, duration or 0)
                     } for index, frame in enumerate(paths)]
        manifest_path = temp / "frames.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        ocr_python = shutil.which(self.ocr_python)
        if not ocr_python:
            raise MediaToolError("未找到 RapidOCR Python: {}".format(self.ocr_python))
        result = self._run([ocr_python, "-c", _OCR_WORKER, str(manifest_path)], self.ocr_timeout)
        try:
            lines = [line for line in result.stdout.splitlines() if line.strip()]
            data = json.loads(lines[-1])
            if not isinstance(data, list) or len(data) != len(paths):
                raise ValueError("OCR 帧数不一致")
            return data, bool(duration and duration / self.ocr_interval > self.ocr_max_frames)
        except (ValueError, IndexError, json.JSONDecodeError) as exc:
            raise MediaToolError("RapidOCR 返回无效结果: {}".format(exc))

    def _subtitle_issues(self, frame, video, issue):
        width = int(video.get("width") or 0)
        height = int(video.get("height") or 0)
        left, top, right, bottom = self.subtitle_safe_area
        safe = {"left": left * width, "top": top * height,
                "right": right * width, "bottom": bottom * height}
        for line in frame.get("lines", []):
            try:
                xs = [float(point[0]) for point in line["box"]]
                ys = [float(point[1]) for point in line["box"]]
                box = {"left": min(xs), "top": min(ys), "right": max(xs), "bottom": max(ys)}
            except (KeyError, TypeError, ValueError, IndexError):
                continue
            outside = (box["left"] < safe["left"] or box["top"] < safe["top"] or
                       box["right"] > safe["right"] or box["bottom"] > safe["bottom"])
            if outside:
                issue("subtitle_out_of_bounds", "warning", "subtitle_bounds",
                      "人工核对文字是否为目的性版式；字幕应移入安全区后重新导出",
                      {"text": line.get("text", ""), "confidence": line.get("confidence"),
                       "box_pixels": box, "safe_area_pixels": safe,
                       "note": "OCR 无法可靠区分字幕与其他画面文字"},
                      frame.get("timestamp_seconds"))

    def _result(self, path, metadata, issues, checks, sha256, unchanged, limitations=None):
        for name, status in checks.items():
            if status == "pending":
                checks[name] = "passed" if metadata is not None else "unavailable"
        failed = any(item["severity"] == "error" for item in issues)
        warned = any(item["severity"] == "warning" for item in issues)
        transcode = {"eligible": False, "required": False, "command": None,
                     "output_contract": {"container": "mp4", "video_codec": "h264",
                                         "audio_codec": "aac", "pixel_format": "yuv420p",
                                         "faststart": True},
                     "preserves_source": True, "automatically_applied": False}
        if metadata and metadata.get("video") and metadata.get("audio") and metadata.get("duration_seconds"):
            video = metadata["video"]
            audio = metadata["audio"]
            required = (
                video.get("codec_name") not in ("h264", "avc1") or video.get("pix_fmt") != "yuv420p" or
                audio.get("codec_name") != "aac" or not metadata.get("faststart") or
                video.get("width") != self.target_width or video.get("height") != self.target_height
            )
            command = build_safe_transcode_command(path, "media-review-output.mp4",
                                                   self.target_width, self.target_height)
            transcode.update({"eligible": True, "required": required, "command": command})
        return {
            "schema_version": 1,
            "source": {"path": str(path), "sha256": sha256, "unchanged": unchanged},
            "status": "failed" if failed else "needs_review" if warned else "passed",
            "machine_checks_passed": not failed and not warned,
            "human_review_required": True,
            "checks": checks,
            "issues": issues,
            "media": metadata,
            "safe_transcode_candidate": transcode,
            "automatic_repairs_applied": [],
            "limitations": limitations or [],
        }


def review_media(path, check_ocr=True, **options):
    return MediaReviewer(**options).review(path, check_ocr=check_ocr)
