#!/usr/bin/env python3
import math
import wave
from array import array
from pathlib import Path

from content_workbench.domain.errors import DomainError


def synthesize(score: dict, output: Path) -> dict:
    duration = score.get("duration_seconds")
    notes = score.get("notes")
    if (
        isinstance(duration, bool)
        or not isinstance(duration, (int, float))
        or not 0.1 <= duration <= 600
    ):
        raise DomainError(
            "MUSIC_DURATION_INVALID", "Kimi 配乐时长须为 0.1～600 秒", 502
        )
    if not isinstance(notes, list) or not 1 <= len(notes) <= 512:
        raise DomainError("MUSIC_NOTES_INVALID", "Kimi 配乐必须包含 1～512 个音符", 502)
    sample_rate = 22050
    samples = array("f", [0.0]) * round(duration * sample_rate)
    for note in notes:
        if not isinstance(note, dict):
            raise DomainError("MUSIC_NOTE_INVALID", "Kimi 返回了无效音符", 502)
        frequency = note.get("frequency")
        start = note.get("start")
        length = note.get("duration")
        volume = note.get("volume", 0.2)
        kind = note.get("wave", "sine")
        values = (frequency, start, length, volume)
        if any(
            isinstance(value, bool) or not isinstance(value, (int, float))
            for value in values
        ):
            raise DomainError(
                "MUSIC_NOTE_INVALID", "音符频率、时间和音量必须是数字", 502
            )
        if (
            not 20 <= frequency <= 5000
            or start < 0
            or length <= 0
            or start + length > duration + 0.001
        ):
            raise DomainError("MUSIC_NOTE_INVALID", "音符频率或时间超出当前配乐", 502)
        if not 0 < volume <= 1 or kind not in ("sine", "triangle", "square"):
            raise DomainError("MUSIC_NOTE_INVALID", "音符音量或波形无效", 502)
        first = round(start * sample_rate)
        count = min(round(length * sample_rate), len(samples) - first)
        for index in range(max(0, count)):
            position = index / sample_rate
            envelope = min(1.0, position / 0.02, (length - position) / 0.04)
            phase = 2 * math.pi * frequency * position
            if kind == "triangle":
                signal = 2 / math.pi * math.asin(math.sin(phase))
            elif kind == "square":
                signal = 1.0 if math.sin(phase) >= 0 else -1.0
            else:
                signal = math.sin(phase)
            samples[first + index] += signal * volume * max(0.0, envelope)
    peak = max((abs(value) for value in samples), default=0.0)
    if peak <= 0:
        raise DomainError("MUSIC_EMPTY", "Kimi 配乐没有产生有效声音", 502)
    scale = min(1.0, 0.9 / peak)
    pcm = array(
        "h", (round(max(-1.0, min(1.0, value * scale)) * 32767) for value in samples)
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(sample_rate)
        stream.writeframes(pcm.tobytes())
    return {
        "duration_seconds": round(duration, 3),
        "sample_rate": sample_rate,
        "note_count": len(notes),
    }
