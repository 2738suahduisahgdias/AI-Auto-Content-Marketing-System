#!/usr/bin/env python3
import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = PROJECT_ROOT / "templates" / "content-card.yaml"
BASE_DIRECTORIES = (
    "content_cards",
    "narration",
    "voice",
    "subtitles",
    "assets",
    "renders",
    "covers",
    "analytics",
    "reports",
)
CONTENT_DIRECTORIES = (
    "narration/{content_id}",
    "voice/{content_id}",
    "assets/{content_id}/source",
    "assets/{content_id}/generated",
    "assets/{content_id}/approved",
    "renders/{content_id}",
    "covers/{content_id}",
    "analytics/{content_id}",
    "reports/{content_id}",
)
PILLARS = ("enterprise_ai", "ai_learning", "ai_marketing", "personal_thinking")
AUDIENCES = ("business_owners", "practitioners", "fde")


def yaml_string(value):
    return json.dumps(value, ensure_ascii=False)


def next_sequence(cards_dir, date_prefix):
    pattern = re.compile(r"^" + re.escape(date_prefix) + r"-(\d{3})\.yaml$")
    sequences = []
    for path in cards_dir.glob(date_prefix + "-*.yaml"):
        match = pattern.match(path.name)
        if match:
            sequences.append(int(match.group(1)))
    return max(sequences, default=0) + 1


def create_content(root, args):
    for directory in BASE_DIRECTORIES:
        (root / directory).mkdir(parents=True, exist_ok=True)

    now = datetime.now().astimezone()
    date_prefix = now.strftime("%Y%m%d")
    cards_dir = root / "content_cards"
    sequence = next_sequence(cards_dir, date_prefix)
    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    while True:
        if sequence > 999:
            raise RuntimeError("当天任务编号已超过 999，请检查 content_cards 目录")
        content_id = "{}-{:03d}".format(date_prefix, sequence)
        card_path = cards_dir / (content_id + ".yaml")
        replacements = {
            "{{content_id}}": content_id,
            "{{created_at}}": now.isoformat(timespec="seconds"),
            "{{updated_at}}": now.isoformat(timespec="seconds"),
            "{{title}}": yaml_string(args.title)[1:-1],
            "{{pillar}}": args.pillar,
            "{{audience}}": args.audience,
            "{{pain_point}}": yaml_string(args.pain_point)[1:-1],
            "{{angle}}": yaml_string(args.angle)[1:-1],
        }
        card = template
        for placeholder, value in replacements.items():
            card = card.replace(placeholder, value)
        if "{{" in card or "}}" in card:
            raise RuntimeError("任务卡模板仍有未替换的占位符")

        try:
            with card_path.open("x", encoding="utf-8") as handle:
                handle.write(card)
            break
        except FileExistsError:
            sequence += 1

    for directory in CONTENT_DIRECTORIES:
        path = directory.format(content_id=content_id)
        (root / path).mkdir(parents=True, exist_ok=True)

    return content_id, card_path


def main():
    parser = argparse.ArgumentParser(description="创建一条自媒体内容任务")
    parser.add_argument("--title", required=True, help="选题标题")
    parser.add_argument("--pillar", choices=PILLARS, default="enterprise_ai")
    parser.add_argument("--audience", choices=AUDIENCES, default="business_owners")
    parser.add_argument("--pain-point", default="", help="这条内容解决的核心痛点")
    parser.add_argument("--angle", default="", help="内容切入角度")
    args = parser.parse_args()

    root = Path(os.environ.get("CONTENT_AGENT_ROOT", str(PROJECT_ROOT))).expanduser().resolve()
    content_id, card_path = create_content(root, args)
    print("已创建内容任务：" + content_id)
    print("任务卡：" + str(card_path))
    print("初始状态：idea（等待选题确认）")
    print("录音位置：" + str(root / "voice" / content_id / "source.wav"))


if __name__ == "__main__":
    main()
