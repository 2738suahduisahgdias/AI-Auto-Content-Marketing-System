import json


def preview_dict(row):
    if not row:
        return None
    item = dict(row)
    for source, target in (
        ("request_json", "request"), ("storyboard_json", "storyboard"),
        ("input_snapshot_json", "input_snapshot"),
    ):
        item[target] = json.loads(item.pop(source)) if item.get(source) else ({} if source != "storyboard_json" else None)
    item.pop("props_json", None)
    item["progress"] = float(item.get("progress") or 0)
    item["is_current"] = bool(item.get("is_current"))
    item["approved"] = bool(item.get("approved_at"))
    item["video_url"] = "/api/files/{}/media".format(item["video_file_id"]) if item.get("video_file_id") else None
    item["cover_url"] = "/api/files/{}/media".format(item["cover_file_id"]) if item.get("cover_file_id") else None
    return item


def get_preview(conn, content_id, preview_id):
    return conn.execute("SELECT * FROM visual_previews WHERE id=? AND content_id=?",
                        (preview_id, content_id)).fetchone()


def list_previews(conn, content_id):
    return [preview_dict(row) for row in conn.execute(
        "SELECT * FROM visual_previews WHERE content_id=? ORDER BY is_current DESC,created_at DESC,rowid DESC",
        (content_id,))]


def approved_preview(conn, content_id, template_key, fingerprint):
    return conn.execute("""SELECT * FROM visual_previews
                           WHERE content_id=? AND template_key=? AND fingerprint=?
                             AND status='succeeded' AND approved_at IS NOT NULL
                           ORDER BY approved_at DESC LIMIT 1""",
                        (content_id, template_key, fingerprint)).fetchone()


def set_current(conn, content_id, preview_id):
    conn.execute("UPDATE visual_previews SET is_current=0 WHERE content_id=?", (content_id,))
    conn.execute("UPDATE visual_previews SET is_current=1 WHERE id=? AND content_id=?",
                 (preview_id, content_id))
