import copy
import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = PROJECT_ROOT / "config" / "video_templates.json"
STATUSES = {"draft", "stable", "deprecated"}


class TemplateError(ValueError):
    pass


def template_key(template):
    return "{}@{}".format(template["id"], template["version"])


def load_templates(path=TEMPLATE_PATH):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise TemplateError("模板注册表必须是数组")
    templates = []
    seen = set()
    for item in data:
        if not isinstance(item, dict):
            raise TemplateError("模板定义必须是对象")
        for field in ("id", "version", "composition_id", "status", "name", "category", "description"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise TemplateError("模板缺少有效字段：{}".format(field))
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", item["id"]):
            raise TemplateError("模板 ID 格式无效：{}".format(item["id"]))
        if not re.fullmatch(r"\d+\.\d+\.\d+", item["version"]):
            raise TemplateError("模板版本格式无效：{}".format(item["version"]))
        if not re.fullmatch(r"[A-Za-z0-9-]+", item["composition_id"]):
            raise TemplateError("Composition ID 格式无效：{}".format(item["composition_id"]))
        if item["status"] not in STATUSES:
            raise TemplateError("模板状态无效：{}".format(item["status"]))
        if not isinstance(item.get("default_props"), dict) or not isinstance(item.get("allowed_props"), list):
            raise TemplateError("模板 Props 定义无效：{}".format(item["id"]))
        key = template_key(item)
        if key in seen:
            raise TemplateError("模板版本重复：{}".format(key))
        seen.add(key)
        allowed = set(item["allowed_props"])
        if not allowed or any(not isinstance(key, str) or not key for key in allowed):
            raise TemplateError("模板 Props 白名单无效：{}".format(item["id"]))
        if not set(item["default_props"]).issubset(allowed):
            raise TemplateError("默认 Props 超出白名单：{}".format(item["id"]))
        normalized = copy.deepcopy(item)
        normalized["key"] = key
        templates.append(normalized)
    return templates


def _with_preview(item):
    preview = PROJECT_ROOT / "remotion-app" / "public-static" / "previews" / "{}-{}.png".format(item["id"], item["version"])
    if preview.is_file():
        item["preview_url"] = "/api/video-templates/{}/preview".format(item["key"])
    return item


def stable_templates():
    return [_with_preview(item) for item in load_templates() if item["status"] == "stable"]


def all_templates():
    return [_with_preview(item) for item in load_templates()]


def set_template_status(reference, status, path=TEMPLATE_PATH):
    if status not in STATUSES:
        raise TemplateError("模板状态无效：{}".format(status))
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    found = False
    for item in data:
        if not isinstance(item, dict) or "{}@{}".format(item.get("id"), item.get("version")) != reference:
            continue
        found = True
        if status == "stable":
            preview = PROJECT_ROOT / "remotion-app" / "public-static" / "previews" / "{}-{}.png".format(item["id"], item["version"])
            if not preview.is_file():
                raise TemplateError("升级为稳定前需要真实渲染预览图：请先运行 remotion-app/scripts/preview-stills.mjs 并确认预览正常")
        item["status"] = status
    if not found:
        raise TemplateError("模板版本不存在：{}".format(reference))
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return all_templates() if path == TEMPLATE_PATH else load_templates(path)


def resolve_template(reference, for_render=False):
    matches = [item for item in load_templates() if item["key"] == reference]
    if not matches:
        raise TemplateError("模板版本不存在：{}".format(reference))
    template = matches[0]
    if for_render and template["status"] != "stable":
        raise TemplateError("只有稳定模板可以用于视频生产：{}".format(reference))
    return template


def merge_dict(base, overrides):
    result = copy.deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_dict(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def template_props(template, overrides=None):
    if overrides is None:
        overrides = {}
    if not isinstance(overrides, dict):
        raise TemplateError("模板 Props 必须是对象")
    unknown = sorted(set(overrides) - set(template["allowed_props"]))
    if unknown:
        raise TemplateError("模板 {} 不允许修改参数：{}".format(template["key"], ", ".join(unknown)))
    return merge_dict(template["default_props"], overrides)
