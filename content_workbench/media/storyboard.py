import copy
import hashlib
import re


SCHEMA_VERSION = "1.0.0"
ENGINE_VERSION = "content-scenes-1.1.0"
SCENE_TYPES = {
    "hook", "key_point", "metric", "process", "comparison", "timeline",
    "architecture", "map", "media", "quote", "cta",
}

KEYWORDS = (
    "客户", "任务", "数据", "增长", "效率", "风险", "成本", "团队", "流程",
    "目标", "方案", "留言", "沟通", "店铺", "老板", "安全", "完成", "搜索",
    "文档", "AI", "系统", "平台", "Agent", "时间", "情绪", "睡眠", "身体",
)

LOCATIONS = (
    "北京", "上海", "广州", "深圳", "杭州", "成都", "重庆", "武汉", "南京",
    "苏州", "西安", "华东", "华南", "华北", "华中", "西南", "西北", "东北",
)


SEMANTIC_TRANSLATION = str.maketrans({
    "華": "华", "東": "东", "擴": "扩", "體": "体", "統": "统", "傳": "传", "對": "对",
    "現": "现", "業": "业", "務": "务", "復": "复", "複": "复", "過": "过", "來": "来",
    "時": "时", "間": "间", "點": "点", "數": "数", "據": "据", "開": "开",
    "發": "发", "關": "关", "鍵": "键", "題": "题", "戶": "户", "團": "团",
    "隊": "队", "長": "长", "風": "风", "險": "险", "錢": "钱", "預": "预",
    "選": "选", "擇": "择", "驗": "验", "證": "证", "書": "书", "記": "记",
    "錄": "录", "認": "认", "識": "识", "說": "说", "話": "话", "語": "语",
    "讀": "读", "寫": "写", "運": "运", "營": "营", "應": "应", "該": "该",
    "這": "这", "個": "个", "條": "条", "種": "种", "類": "类", "與": "与",
    "為": "为", "還": "还", "沒": "没", "萬": "万", "億": "亿", "後": "后",
    "總": "总", "結": "结",
})


def semantic_text(value):
    return str(value or "").translate(SEMANTIC_TRANSLATION)


def _text(scene):
    return str(scene.get("narration") or scene.get("description") or scene.get("name") or "").strip()


def _metric(text):
    match = re.search(r"(\d+(?:\.\d+)?)\s*(%|％|个|条|家|倍|万|元|分钟|小时|天|周|月|年|步|类|次)?", text)
    if not match:
        return None
    value = float(match.group(1))
    return {
        "value": int(value) if value.is_integer() else value,
        "unit": "％" if match.group(2) == "%" else (match.group(2) or ""),
        "direction": "down" if re.search(r"减少|降低|节省|下降|压缩", text) else "up",
    }


def _items(text):
    parts = [part.strip(" ，。；：、\n\t") for part in re.split(
        r"首先|第一步|第二步|第三步|其次|然后|接着|最后|一是|二是|三是|\d+[、.]", text,
    ) if part.strip(" ，。；：、\n\t")]
    if len(parts) < 2:
        parts = [part.strip() for part in re.split(r"[，；。]", text) if part.strip()]
    return [part[:28] for part in parts[:4]] or [text[:28]]


def _scene_type(scene, index, total):
    text = semantic_text(_text(scene))
    if scene.get("media"):
        return "media"
    if re.search(r"地图|路线|华东|华南|华北|华中|西南|西北|东北|扩展到|布局", text):
        return "map"
    if re.search(r"对比|相比|传统|以前|之前|之后|而不是|VS|vs|前后", text):
        return "comparison"
    if re.search(r"步骤|流程|首先|第一步|第二步|第三步|其次|然后|接着|最后|一是|二是|三是|\d+\s*个?(?:步骤|步|类)", text):
        return "process"
    if _metric(text):
        return "metric"
    if re.search(r"\d{4}\s*年|时间线|阶段|曾经|后来|历年", text):
        return "timeline"
    if re.search(r"架构|系统|平台|Agent|智能体|节点|数据流", text, re.I):
        return "architecture"
    if index == total - 1 and total > 2 and re.search(r"关注|咨询|了解|试试|开始|留言|行动|总结", text):
        return "cta"
    if re.search(r"情绪|焦虑|睡眠|身体|陪伴|感受|自己|更年期|温柔|人生|故事", text):
        return "quote"
    if index == 0:
        return "hook"
    return "key_point"


def _beat_actions(scene_type):
    return {
        "metric": ["scene_enter", "metric_grow", "result_emphasis"],
        "process": ["scene_enter", "process_advance", "path_draw"],
        "comparison": ["scene_enter", "comparison_reveal", "result_emphasis"],
        "timeline": ["scene_enter", "timeline_advance", "result_emphasis"],
        "architecture": ["scene_enter", "node_activate", "path_draw"],
        "map": ["scene_enter", "route_draw", "camera_move"],
        "media": ["scene_enter", "camera_move", "media_emphasis"],
        "quote": ["scene_enter", "quote_reveal", "camera_move"],
        "cta": ["scene_enter", "result_emphasis", "cta_reveal"],
    }.get(scene_type, ["scene_enter", "keyword_reveal", "layout_shift"])


def enrich_scene(scene, index, total):
    result = copy.deepcopy(scene)
    text = _text(result)
    scene_type = result.get("type") if result.get("type") in SCENE_TYPES else _scene_type(result, index, total)
    start = float(result["start_seconds"])
    end = float(result["end_seconds"])
    duration = max(0.1, end - start)
    actions = _beat_actions(scene_type)
    beats = []
    offsets = [0.0]
    while offsets[-1] + 2.8 < duration - 0.25:
        offsets.append(offsets[-1] + 2.8)
    for beat_index, offset in enumerate(offsets):
        beats.append({
            "at": round(start + offset, 3),
            "offset_seconds": round(offset, 3),
            "action": actions[beat_index % len(actions)],
        })
    normalized = semantic_text(text)
    result.update({
        "type": scene_type,
        "narration": text,
        "headline": result.get("name") or text[:24],
        "keywords": [word for word in KEYWORDS if word.lower() in normalized.lower()][:5],
        "locations": [word for word in LOCATIONS if word in normalized],
        "data": {
            "metric": _metric(normalized),
            "items": _items(text),
        },
        "visualBeats": beats,
    })
    return result


def build_storyboard(props, content_id):
    result = copy.deepcopy(props)
    scenes = result.get("scenes") or []
    if not scenes:
        raise ValueError("Storyboard 至少需要一个有效场景")
    enriched = [enrich_scene(scene, index, len(scenes)) for index, scene in enumerate(scenes)]
    seed = int(hashlib.sha256(content_id.encode("utf-8")).hexdigest()[:8], 16)
    result["scenes"] = enriched
    result["storyboard"] = {
        "schema_version": SCHEMA_VERSION,
        "engine_version": ENGINE_VERSION,
        "seed": seed,
        "planner": "deterministic-semantic-rules",
        "scenes": enriched,
    }
    return result


def _caption_window(captions, source_start, source_end, shift):
    result = []
    for caption in captions:
        start = max(source_start, caption["startMs"] / 1000)
        end = min(source_end, caption["endMs"] / 1000)
        if end <= start:
            continue
        result.append({
            **caption,
            "startMs": round((start + shift) * 1000),
            "endMs": round((end + shift) * 1000),
        })
    return result


def build_preview_props(props, duration_seconds=10.0):
    source_duration = float(props["durationSeconds"])
    target = min(float(duration_seconds), source_duration)
    priorities = {
        "metric": 0, "process": 0, "comparison": 0, "map": 0, "media": 0,
        "architecture": 0, "timeline": 1, "key_point": 1, "quote": 1,
        "hook": 2, "cta": 2,
    }
    scenes = props["scenes"]
    ranked = sorted(scenes, key=lambda scene: (priorities.get(scene.get("type"), 1), scene["start_seconds"]))
    selected = sorted(ranked[:min(3, len(ranked))], key=lambda scene: scene["start_seconds"])
    takes = [min(float(scene["end_seconds"]) - float(scene["start_seconds"]), target / len(selected)) for scene in selected]
    remaining = target - sum(takes)
    for index, scene in enumerate(selected):
        available = float(scene["end_seconds"]) - float(scene["start_seconds"]) - takes[index]
        extra = min(remaining, max(0.0, available))
        takes[index] += extra
        remaining -= extra
    for scene in scenes:
        if remaining <= 0.001:
            break
        if scene in selected:
            continue
        take = min(remaining, float(scene["end_seconds"]) - float(scene["start_seconds"]))
        if take > 0:
            selected.append(scene)
            takes.append(take)
            remaining -= take
    selected = sorted(selected, key=lambda scene: scene["start_seconds"])
    takes = [min(float(scene["end_seconds"]) - float(scene["start_seconds"]), target / len(selected)) for scene in selected]
    remaining = target - sum(takes)
    for index, scene in enumerate(selected):
        available = float(scene["end_seconds"]) - float(scene["start_seconds"]) - takes[index]
        extra = min(remaining, max(0.0, available))
        takes[index] += extra
        remaining -= extra

    result = copy.deepcopy(props)
    preview_scenes = []
    preview_captions = []
    audio_segments = []
    timeline = 0.0
    for index, (scene, take) in enumerate(zip(selected, takes)):
        if take <= 0:
            continue
        source_start = float(scene["start_seconds"])
        source_end = source_start + take
        shift = timeline - source_start
        preview_scene = copy.deepcopy(scene)
        preview_scene["id"] = "preview-{}-{}".format(index, scene["id"])
        preview_scene["start_seconds"] = round(timeline, 3)
        preview_scene["end_seconds"] = round(timeline + take, 3)
        preview_scene["source_start_seconds"] = source_start
        preview_scene["source_end_seconds"] = source_end
        preview_scene["visualBeats"] = [
            {**beat, "at": round(beat["at"] + shift, 3), "offset_seconds": round(beat["at"] + shift - timeline, 3)}
            for beat in scene.get("visualBeats", []) if source_start <= beat["at"] < source_end
        ]
        preview_scenes.append(preview_scene)
        preview_captions.extend(_caption_window(props.get("captions", []), source_start, source_end, shift))
        if props.get("audio"):
            audio_segments.append({
                "src": props["audio"],
                "start_seconds": source_start,
                "end_seconds": source_end,
                "timeline_start_seconds": round(timeline, 3),
            })
        timeline += take
    result.update({
        "scenes": preview_scenes,
        "captions": preview_captions,
        "durationSeconds": round(timeline, 3),
        "audioSegments": audio_segments,
        "preview": True,
    })
    result.pop("audio", None)
    result["previewManifest"] = {
        "duration_seconds": round(timeline, 3),
        "segments": [{"scene_id": scene["id"], "source_start": scene["source_start_seconds"],
                      "source_end": scene["source_end_seconds"]} for scene in preview_scenes],
    }
    return result
