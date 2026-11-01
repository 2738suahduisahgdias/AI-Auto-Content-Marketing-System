import hashlib
import json
import uuid
from datetime import datetime
from pathlib import Path


def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def payload_hash(value):
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def record_stage_revision(conn, task, stage, status="active"):
    content_id = task["content_id"] if isinstance(task, dict) else task
    if isinstance(task, dict):
        payload = {
            "scripts": task.get("scripts", {}),
            "script_meta": task.get("script_meta", {}),
            "asset_plan": task.get("asset_plan", []),
            "quality": task.get("quality", {}),
            "files": [{key: file.get(key) for key in ("id", "kind", "original_name", "relative_path", "media_info")}
                      for file in task.get("files", [])],
            "render_runs": task.get("render_runs", []),
            "variants": task.get("variants", []),
        }
    else:
        payload = {}
    revision = conn.execute("SELECT COALESCE(MAX(revision_no),0)+1 FROM stage_revisions WHERE content_id=? AND stage=?",
                            (content_id, stage)).fetchone()[0]
    revision_id = "stage_" + uuid.uuid4().hex
    conn.execute("UPDATE stage_revisions SET status='superseded' WHERE content_id=? AND stage=? AND status='active'",
                 (content_id, stage))
    conn.execute("""INSERT INTO stage_revisions(id,content_id,stage,revision_no,payload_json,payload_hash,status,created_at)
                    VALUES (?,?,?,?,?,?,?,?)""",
                 (revision_id, content_id, stage, revision, json.dumps(payload, ensure_ascii=False),
                  payload_hash(payload), status, now()))
    return revision_id


def upsert_variant(conn, task, file_row, template=None, file_path=None):
    file_id = file_row["id"] if isinstance(file_row, dict) else file_row
    if isinstance(file_row, dict):
        path = file_path
        original_name = file_row.get("original_name", "video.mp4")
    else:
        original_name = "video.mp4"
    digest = file_sha256(path) if path else ""
    existing = conn.execute("SELECT id FROM video_variants WHERE file_id=?", (file_id,)).fetchone()
    template = template or {"id": "upload", "version": "1.0.0"}
    if existing:
        conn.execute("UPDATE video_variants SET file_sha256=?,template_id=?,template_version=?,updated_at=? WHERE id=?",
                     (digest, template["id"], template["version"], now(), existing["id"]))
        return existing["id"]
    variant_id = "variant_" + uuid.uuid4().hex
    conn.execute("""INSERT INTO video_variants(id,content_id,template_id,template_version,file_id,file_sha256,
                    quality_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)""",
                 (variant_id, task["content_id"], template["id"], template["version"], file_id, digest,
                  "{}", now(), now()))
    conn.execute("UPDATE files SET media_info_json=? WHERE id=?",
                 (json.dumps({**json.loads(file_row["media_info_json"]), "variant_id": variant_id,
                              "original_name": original_name}, ensure_ascii=False), file_id))
    return variant_id


def variant_for_file(conn, content_id, file_id):
    return conn.execute("SELECT * FROM video_variants WHERE content_id=? AND file_id=?", (content_id, file_id)).fetchone()


def latest_variant(conn, content_id):
    return conn.execute("SELECT * FROM video_variants WHERE content_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1",
                        (content_id,)).fetchone()


def variant_dict(row):
    if not row:
        return None
    item = dict(row)
    item["quality"] = json.loads(item.pop("quality_json") or "{}")
    item["approved"] = bool(item.get("approved_at"))
    return item
