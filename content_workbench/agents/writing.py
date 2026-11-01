import json
from pathlib import Path

from content_workbench.media.versioning import payload_hash

SCRIPT_KEYS = ("master", "douyin", "wechat_channels", "xiaohongshu", "wechat_official_account")
DEFAULT_SKILLS = ("skills/writing/de-ai/SKILL.md", "skills/writing/techniques/SKILL.md")


def initial_script_meta(scripts, previous=None):
    previous = previous or {}
    result = {}
    for key in SCRIPT_KEYS:
        old = previous.get(key, {})
        revision = int(old.get("revision_no", 0)) if isinstance(old, dict) else 0
        text = scripts.get(key, "")
        result[key] = {
            **(old if isinstance(old, dict) else {}),
            "origin": old.get("origin", "manual") if text else "empty",
            "revision_no": revision,
            "content_hash": payload_hash(text) if text else "",
        }
    return result


def merge_manual_scripts(current_scripts, current_meta, incoming):
    scripts = dict(current_scripts)
    metadata = initial_script_meta(scripts, current_meta)
    for key, value in incoming.items():
        if key not in SCRIPT_KEYS or not isinstance(value, str):
            continue
        if value == scripts.get(key, ""):
            continue
        old = metadata[key]
        old["revision_no"] = int(old.get("revision_no", 0)) + 1
        old["origin"] = "edited" if old.get("origin") == "agent" else "manual"
        old["content_hash"] = payload_hash(value) if value else ""
        old.pop("candidate", None)
        scripts[key] = value
    return scripts, metadata


def missing_script_fields(scripts, requested=None):
    if requested is not None:
        return [key for key in requested if key in SCRIPT_KEYS and not scripts.get(key, "").strip()]
    return [key for key in ("douyin",) if not scripts.get(key, "").strip()]


def validate_generated_scripts(payload, fields):
    if not isinstance(payload, dict) or set(payload) != set(fields):
        raise ValueError("写作 Agent 必须只返回请求的字段")
    if any(not isinstance(payload.get(key), str) or not payload[key].strip() for key in fields):
        raise ValueError("写作 Agent 返回了空文稿")
    if set(payload) - set(SCRIPT_KEYS):
        raise ValueError("写作 Agent 返回了未知字段")
    return {key: payload[key] for key in fields}


def apply_generated_scripts(scripts, metadata, generated, request_id, agent_snapshot, base_revisions=None):
    updated = dict(scripts)
    meta = json.loads(json.dumps(metadata))
    base_revisions = base_revisions or {}
    conflicts = []
    for key, text in generated.items():
        current = meta.get(key) or initial_script_meta(updated, meta)[key]
        if int(current.get("revision_no", 0)) != int(base_revisions.get(key, 0)):
            current["candidate"] = {
                "text": text, "request_id": request_id, "base_revision": current.get("revision_no", 0),
                "agent_snapshot": agent_snapshot,
            }
            conflicts.append(key)
        else:
            current["revision_no"] = int(current.get("revision_no", 0)) + 1
            current["origin"] = "agent"
            current["content_hash"] = payload_hash(text)
            current["agent_snapshot"] = agent_snapshot
            current.pop("candidate", None)
            updated[key] = text
        meta[key] = current
    return updated, meta, conflicts


def load_writing_skills(project_root, configured=None):
    project_root = Path(project_root).resolve()
    references = configured or DEFAULT_SKILLS
    if not isinstance(references, (list, tuple)) or len(references) > 6:
        raise ValueError("写作 Skills 配置无效")
    documents = []
    for reference in references:
        if not isinstance(reference, str) or not reference.strip():
            raise ValueError("写作 Skill 路径无效")
        path = (project_root / reference.strip()).resolve()
        allowed = [project_root / "skills", project_root / ".agents" / "skills"]
        if not any(root.resolve() in path.parents for root in allowed) or path.suffix.lower() != ".md" or not path.is_file():
            raise ValueError("写作 Skill 不存在或不在允许目录：{}".format(reference))
        if path.stat().st_size > 200000:
            raise ValueError("写作 Skill 文件过大：{}".format(reference))
        documents.append({"path": path.relative_to(project_root).as_posix(), "version": payload_hash(path.read_text(encoding="utf-8"))[:12],
                          "text": path.read_text(encoding="utf-8")})
    return documents


def writing_context(config, project_root):
    skills = load_writing_skills(project_root, config.get("custom", {}).get("skills"))
    snapshot = {"model": config.get("model"), "skills": [{"path": item["path"], "version": item["version"]} for item in skills]}
    prompt = "\n\n".join(item["text"] for item in skills)
    return prompt, snapshot
