#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from faster_whisper import WhisperModel


def srt_timestamp(seconds):
    milliseconds = max(0, round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3600000)
    minutes, milliseconds = divmod(milliseconds, 60000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", default="base")
    parser.add_argument("--language", default="zh")
    parser.add_argument("--chunk-seconds", type=int, default=30)
    args = parser.parse_args()

    audio_path = Path(args.audio).resolve()
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    model = WhisperModel(args.model, device="cpu", compute_type="int8", cpu_threads=2)
    segments, _ = model.transcribe(
        str(audio_path),
        language=args.language,
        beam_size=1,
        vad_filter=False,
        condition_on_previous_text=False,
    )
    lines = []
    count = 0
    for index, segment in enumerate(segments, 1):
        text = segment.text.strip()
        if not text:
            continue
        count += 1
        lines.extend([
            str(count),
            f"{srt_timestamp(segment.start)} --> {srt_timestamp(segment.end)}",
            text,
            "",
        ])
    if not lines:
        raise RuntimeError("WhisperX 未识别出字幕内容")
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"output": str(output_path), "segments": count, "model": args.model}, ensure_ascii=False))


if __name__ == "__main__":
    main()
