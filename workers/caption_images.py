#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = (
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
)


def font(size):
    for candidate in FONT_CANDIDATES:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default(size)


def wrap_text(draw, text, current_font, max_width):
    lines = []
    current = ""
    for character in text:
        candidate = current + character
        if current and draw.textlength(candidate, font=current_font) > max_width:
            lines.append(current)
            current = character
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [""]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--captions", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    captions = json.loads(Path(args.captions).read_text(encoding="utf-8"))
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    paths = []
    for index, caption in enumerate(captions):
        current_font = font(54)
        probe = Image.new("RGBA", (1, 1))
        draw = ImageDraw.Draw(probe)
        lines = wrap_text(draw, caption["text"], current_font, 820)
        height = 56 + 66 * len(lines)
        image = Image.new("RGBA", (900, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((0, 0, 899, height - 1), radius=22, fill=(0, 0, 0, 176))
        y = 28
        for line in lines:
            width = draw.textlength(line, font=current_font)
            draw.text(((900 - width) / 2, y), line, font=current_font, fill=(255, 255, 255, 255))
            y += 66
        path = output / f"caption-{index:03d}.png"
        image.save(path)
        paths.append(str(path))
    print(json.dumps(paths, ensure_ascii=False))


if __name__ == "__main__":
    main()
