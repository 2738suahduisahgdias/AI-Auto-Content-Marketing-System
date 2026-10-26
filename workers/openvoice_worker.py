#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--openvoice-root", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--text", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--speaker", default="zh")
    args = parser.parse_args()

    root = Path(args.openvoice_root).resolve()
    checkpoints = root / "checkpoints_v2"
    converter_config = checkpoints / "converter" / "config.json"
    converter_checkpoint = checkpoints / "converter" / "checkpoint.pth"
    reference = Path(args.ref).resolve()
    output = Path(args.output).resolve()
    work_dir = Path(args.work_dir).resolve()
    for required in (converter_config, converter_checkpoint, reference):
        if not required.is_file():
            raise FileNotFoundError(str(required))
    if not args.text.strip():
        raise ValueError("text must not be empty")
    work_dir.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(root))

    import torch
    from melo.api import TTS
    from openvoice import se_extractor
    from openvoice.api import ToneColorConverter

    device = "cpu"
    converter = ToneColorConverter(str(converter_config), device=device)
    converter.watermark_model = None
    converter.load_ckpt(str(converter_checkpoint))
    target_se, _ = se_extractor.get_se(str(reference), converter, target_dir=str(work_dir / "processed"), vad=True)

    model = TTS(language="ZH", device=device)
    speaker_ids = model.hps.data.spk2id
    available_keys = list(speaker_ids.keys())
    requested = args.speaker.lower().replace("_", "-")
    speaker_key = next((key for key in available_keys if key.lower().replace("_", "-") == requested), None)
    if speaker_key is None:
        speaker_key = next((key for key in available_keys if key.lower().replace("_", "-").startswith("zh")), None)
    if speaker_key is None:
        raise RuntimeError("MeloTTS 中未找到中文 speaker")
    normalized = speaker_key.lower().replace("_", "-")
    source_se_path = checkpoints / "base_speakers" / "ses" / (normalized + ".pth")
    if not source_se_path.is_file():
        raise FileNotFoundError(str(source_se_path))
    source_se = torch.load(str(source_se_path), map_location=device)
    if torch.backends.mps.is_available() and device == "cpu":
        torch.backends.mps.is_available = lambda: False

    base_audio = work_dir / "base.wav"
    model.tts_to_file(args.text.strip(), speaker_ids[speaker_key], str(base_audio), speed=1.0)
    converter.convert(audio_src_path=str(base_audio), src_se=source_se, tgt_se=target_se,
                      output_path=str(output), message="@MyShell")
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError("OpenVoice 未生成有效 WAV")
    print(json.dumps({"output": str(output), "speaker": normalized, "language": "ZH", "device": device}, ensure_ascii=False))


if __name__ == "__main__":
    main()
