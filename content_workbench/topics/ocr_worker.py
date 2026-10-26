import argparse
import json
from pathlib import Path

from rapidocr_onnxruntime import RapidOCR


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", required=True)
    args = parser.parse_args()
    engine = RapidOCR()
    results = []
    for path in sorted(Path(args.frames).glob("frame-*.png")):
        output, _ = engine(str(path))
        lines = output or []
        accepted = [line for line in lines if len(line) >= 3 and float(line[2]) >= 0.2]
        text = " ".join(str(line[1]).strip() for line in accepted if str(line[1]).strip())
        confidence = round(sum(float(line[2]) for line in accepted) / len(accepted) * 100, 2) if accepted else 0
        results.append({"frame": path.name, "text": text, "confidence": confidence})
    print(json.dumps(results, ensure_ascii=False))


if __name__ == "__main__":
    main()
