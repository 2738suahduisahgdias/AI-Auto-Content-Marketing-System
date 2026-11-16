#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Callable, Optional, TextIO

from faster_whisper import WhisperModel


def srt_timestamp(seconds):
    milliseconds = max(0, round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3600000)
    minutes, milliseconds = divmod(milliseconds, 60000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def emit(stream: TextIO, event_type: str, payload: dict) -> None:
    stream.write(json.dumps({"type": event_type, **payload}, ensure_ascii=False) + "\n")
    stream.flush()


def transcribe_audio_file(
    model: object,
    audio_path: Path,
    output_path: Path,
    progress: Optional[Callable[[str, dict], None]] = None,
) -> None:
    if progress:
        progress("transcribing", {"completed_seconds": 0.0})
    segments, _ = model.transcribe(
        str(audio_path),
        language="zh",
        beam_size=1,
        vad_filter=False,
        word_timestamps=True,
        condition_on_previous_text=False,
    )
    lines = []
    words = []
    count = 0
    for index, segment in enumerate(segments, 1):
        text = segment.text.strip()
        if not text:
            continue
        count += 1
        lines.extend(
            [
                str(count),
                f"{srt_timestamp(segment.start)} --> {srt_timestamp(segment.end)}",
                text,
                "",
            ]
        )
        for word in segment.words:
            value = word.word.strip()
            if value:
                words.append(
                    {
                        "text": value,
                        "start": round(word.start, 3),
                        "end": round(word.end, 3),
                    }
                )
        if progress:
            progress("transcribing", {"completed_seconds": round(segment.end, 3)})
    if not lines:
        raise RuntimeError("WhisperX 未识别出字幕内容")
    output_path.write_text("\n".join(lines), encoding="utf-8")
    output_path.with_suffix(".words.json").write_text(
        json.dumps(words, ensure_ascii=False), encoding="utf-8"
    )


def serve(model_name: str, input_stream: TextIO, output_stream: TextIO) -> None:
    emit(output_stream, "progress", {"stage": "model_loading"})
    model = WhisperModel(model_name, device="cpu", compute_type="int8", cpu_threads=2)
    emit(output_stream, "progress", {"stage": "model_ready"})
    for line in input_stream:
        if not line.strip():
            continue
        request = json.loads(line)
        output_path = Path(request["output"]).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            transcribe_audio_file(
                model,
                Path(request["audio"]).resolve(),
                output_path,
                lambda stage, payload: emit(
                    output_stream, "progress", {"stage": stage, **payload}
                ),
            )
            emit(output_stream, "progress", {"stage": "writing"})
            emit(
                output_stream,
                "result",
                {"output": str(output_path), "model": model_name},
            )
        except Exception as error:
            emit(output_stream, "error", {"message": str(error)[:500]})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio")
    parser.add_argument("--output")
    parser.add_argument("--model", default="base")
    parser.add_argument("--language", default="zh")
    parser.add_argument("--chunk-seconds", type=int, default=30)
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args()
    if args.serve:
        serve(args.model, __import__("sys").stdin, __import__("sys").stdout)
        return
    if not args.audio or not args.output:
        parser.error("--audio and --output are required unless --serve is used")
    audio_path = Path(args.audio).resolve()
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    model = WhisperModel(args.model, device="cpu", compute_type="int8", cpu_threads=2)
    segments, _ = model.transcribe(
        str(audio_path),
        language=args.language,
        beam_size=1,
        vad_filter=False,
        word_timestamps=True,
        condition_on_previous_text=False,
    )
    lines = []
    words = []
    count = 0
    for index, segment in enumerate(segments, 1):
        text = segment.text.strip()
        if not text:
            continue
        count += 1
        lines.extend(
            [
                str(count),
                f"{srt_timestamp(segment.start)} --> {srt_timestamp(segment.end)}",
                text,
                "",
            ]
        )
        for word in segment.words:
            value = word.word.strip()
            if value:
                words.append(
                    {
                        "text": value,
                        "start": round(word.start, 3),
                        "end": round(word.end, 3),
                    }
                )
    if not lines:
        raise RuntimeError("WhisperX 未识别出字幕内容")
    output_path.write_text("\n".join(lines), encoding="utf-8")
    output_path.with_suffix(".words.json").write_text(
        json.dumps(words, ensure_ascii=False), encoding="utf-8"
    )
    print(
        json.dumps(
            {"output": str(output_path), "segments": count, "model": args.model},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
