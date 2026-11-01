#!/usr/bin/env python3
import argparse
import json
import subprocess


def main():
    parser = argparse.ArgumentParser(description="Check rendered visual changes outside the subtitle area")
    parser.add_argument("video")
    parser.add_argument("--fps", type=float, default=2)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--max-static", type=float, default=4.0)
    args = parser.parse_args()
    width, height = 80, 100
    command = [
        "ffmpeg", "-v", "error", "-i", args.video,
        "-vf", f"fps={args.fps},crop=iw:ih*0.72:0:0,scale={width}:{height},format=gray",
        "-f", "rawvideo", "-",
    ]
    raw = subprocess.run(command, check=True, capture_output=True).stdout
    size = width * height
    frames = [raw[index:index + size] for index in range(0, len(raw), size) if len(raw[index:index + size]) == size]
    differences = []
    for index in range(1, len(frames)):
        difference = sum(abs(a - b) for a, b in zip(frames[index - 1], frames[index])) / size
        differences.append({"time": round(index / args.fps, 3), "mean_absolute_difference": round(difference, 4),
                            "changed": difference >= args.threshold})
    longest = 0.0
    current = 0.0
    for item in differences:
        current = 0.0 if item["changed"] else current + 1 / args.fps
        longest = max(longest, current)
    result = {"video": args.video, "sampled_frames": len(frames), "subtitle_area_excluded": "bottom 28%",
              "threshold": args.threshold, "longest_static_seconds": round(longest, 3),
              "passed": longest <= args.max_static, "differences": differences}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
