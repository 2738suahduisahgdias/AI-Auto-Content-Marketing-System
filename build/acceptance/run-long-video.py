#!/usr/bin/env python3

import json
import tempfile
from pathlib import Path

import app
from content_workbench.agents.registry import save_agent_config

app.init_db()
for agent in ("script_agent", "asset_planning_agent"):
    save_agent_config(app.DB_PATH, agent, {"engine": "kimi_cli"})

task = app.create_task(
    {
        "title": "十二镜长视频压力验收",
        "source_type": "original",
        "target_platforms": ["douyin"],
        "aspect": "1080x1920",
    }
)
text = (
    "。".join(
        f"第{index}个镜头记录真实渲染过程，检查长视频是否稳定" for index in range(1, 13)
    )
    + "。"
)
with tempfile.TemporaryDirectory(prefix="long-video-voice-") as directory:
    audio_path, info = app.synthesize_system_wav("Tingting", text, Path(directory))
    with audio_path.open("rb") as handle:
        audio = app.upload_file(
            task,
            "audio",
            "long-video-narration.wav",
            (handle, audio_path.stat().st_size),
            studio=True,
        )

shots = []
for index in range(12):
    shots.append(
        {
            "id": f"stress-{index + 1:02d}",
            "title": f"真实渲染 {index + 1:02d}",
            "label": "长视频压力验收",
            "text": f"第{index + 1}个镜头记录真实渲染过程，检查长视频是否稳定。",
            "purpose": "验证连续镜头的时间线、文字和转场",
            "desc": f"竖屏中央显示大号数字 {index + 1:02d}，下方为真实渲染和稳定性检查两个信息卡，使用统一深色背景。",
            "motion": "数字与信息卡依次进入，保持清晰阅读后自然退场",
            "duration": 5,
            "source": "Remotion 代码",
            "start_seconds": index * 5,
            "end_seconds": (index + 1) * 5,
        }
    )
snapshot = {
    "workflow_stage": 4,
    "manuscript": {"title": task["title"], "text": text},
    "voiceFileId": audio["id"],
    "voiceDuration": info["duration_seconds"],
    "rhythm": "旁白驱动",
    "captionsEnabled": False,
    "style": "enterprise-explainer@1.0.0",
    "template": "enterprise-explainer@1.0.0",
    "shots": shots,
}
saved = app.save_yingxu(task, {"revision": 0, "snapshot": snapshot})
result = app.render_yingxu(
    saved, {"revision": saved["source"]["yingxu"]["revision"], "preview": False}
)
print(
    json.dumps(
        {
            "content_id": task["content_id"],
            "file_id": result["id"],
            "media_info": result["media_info"],
        },
        ensure_ascii=False,
    )
)
