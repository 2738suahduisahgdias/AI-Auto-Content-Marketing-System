import argparse
import json
import mimetypes
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .db import PROJECT_ROOT, connect, dumps, expand_schema, file_hash, immediate, loads, payload_hash, utcnow

PLATFORMS = {
    "douyin": ("video", "douyin"),
    "wechat_channels": ("video", "wechat_channels"),
    "xiaohongshu": ("video", "xiaohongshu"),
    "wechat_official_account": ("article", "wechat_official_account"),
}


def utc(value):
    if not value:
        return utcnow()
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    except ValueError:
        return utcnow()


def insert(conn, sql, values):
    cursor = conn.execute("INSERT OR IGNORE " + sql, values)
    return cursor.rowcount > 0


def link(conn, batch, source_type, source_id, target_type, target_id, resolution):
    return insert(conn, "INTO wb_legacy_links VALUES (?,?,?,?,?,?)", (batch, source_type, str(source_id), target_type, target_id, resolution))


def add_revision(conn, item_id, kind, payload, created_at, revision_id, source_audio=None, depends=None):
    changed = insert(conn, """INTO wb_revisions
        (id,item_id,kind,revision_no,parent_id,payload_json,payload_hash,validity,source_audio_asset_id,created_by,created_at)
        VALUES (?,?,?,1,NULL,?,?, 'valid',?,?,?)""",
        (revision_id, item_id, kind, dumps(payload), payload_hash(payload), source_audio, "migration", utc(created_at)))
    if depends:
        insert(conn, "INTO wb_revision_dependencies(revision_id,depends_revision_id,depends_asset_id) VALUES (?,?,NULL)", (revision_id, depends))
    return changed


def migrate(source_path, target_path, batch_id="legacy-v1", apply=False):
    source_path = Path(source_path).resolve()
    target_path = Path(target_path).resolve()
    if source_path == target_path and not apply:
        raise ValueError("源库与目标库相同；原库迁移必须显式使用 --apply")
    source = connect(source_path, readonly=True)
    target = connect(target_path)
    expand_schema(target)
    tasks = [dict(row) for row in source.execute("SELECT * FROM tasks ORDER BY content_id")]
    files = [dict(row) for row in source.execute("SELECT * FROM files ORDER BY id")]
    events = [dict(row) for row in source.execute("SELECT * FROM events ORDER BY id")]
    source_checksum = payload_hash({"tasks": tasks, "files": files, "events": events})
    report = {"version": "workbench-v2", "batch_id": batch_id, "source_checksum": source_checksum,
              "changed": 0, "skipped": 0, "blocked": [], "tasks": [], "files": []}

    def track(changed):
        report["changed" if changed else "skipped"] += 1
        return changed

    with immediate(target):
        for task in tasks:
            legacy_id = task["content_id"]
            campaign_id = "cmp_legacy_" + legacy_id
            scripts = loads(task["scripts_json"], {})
            brief = {
                "title": task["title"], "pillar": task["pillar"], "audience": task["audience"],
                "pain_point": task["pain_point"], "angle": task["angle"], "source": loads(task["source_json"], {}),
                "legacy_state": task["state"], "master": scripts.get("master", ""),
            }
            track(insert(target, "INTO wb_campaigns(id,title,brief_json,version,created_at,updated_at) VALUES (?,?,?,1,?,?)",
                         (campaign_id, task["title"], dumps(brief), utc(task["created_at"]), utc(task["updated_at"]))))
            track(link(target, batch_id, "task", legacy_id, "campaign", campaign_id, "mapped"))
            item_ids = {}
            article_id = "item_legacy_{}_article".format(legacy_id)
            item_ids["wechat_official_account"] = article_id
            track(insert(target, """INTO wb_content_items
                (id,campaign_id,content_type,platform,state,version,active_revisions_json,legacy_task_id,created_at,updated_at)
                VALUES (?,?,'article','wechat_official_account','needs_review',1,'{}',?,?,?)""",
                (article_id, campaign_id, legacy_id, utc(task["created_at"]), utc(task["updated_at"]))))
            track(link(target, batch_id, "task", legacy_id, "content_item", article_id, "needs_review"))
            for key, (content_type, platform) in PLATFORMS.items():
                if key == "wechat_official_account" or not str(scripts.get(key, "")).strip():
                    continue
                item_id = "item_legacy_{}_{}".format(legacy_id, platform)
                item_ids[key] = item_id
                track(insert(target, """INTO wb_content_items
                    (id,campaign_id,content_type,platform,state,version,active_revisions_json,legacy_task_id,created_at,updated_at)
                    VALUES (?,?,?,?,'needs_review',1,'{}',?,?,?)""",
                    (item_id, campaign_id, content_type, platform, legacy_id, utc(task["created_at"]), utc(task["updated_at"]))))
                track(link(target, batch_id, "task", legacy_id, "content_item", item_id, "needs_review"))
            anchor = article_id
            brief_revision = "rev_legacy_{}_brief_1".format(legacy_id)
            has_brief = bool(str(scripts.get("master", "")).strip())
            if has_brief:
                track(add_revision(target, anchor, "brief", {"text": scripts["master"], "title": task["title"]}, task["updated_at"], brief_revision))
                active = target.execute("SELECT active_revisions_json FROM wb_content_items WHERE id=?", (anchor,)).fetchone()[0]
                active_map = loads(active, {})
                active_map["brief"] = brief_revision
                target.execute("UPDATE wb_content_items SET active_revisions_json=? WHERE id=?", (dumps(active_map), anchor))
            for key, item_id in item_ids.items():
                text = str(scripts.get(key, "")).strip()
                if not text:
                    continue
                kind = "draft" if key == "wechat_official_account" else "script"
                revision_id = "rev_legacy_{}_{}_1".format(legacy_id, key)
                track(add_revision(target, item_id, kind, {"text": text, "format": "markdown" if kind == "draft" else "plain"}, task["updated_at"], revision_id,
                                   depends=brief_revision if has_brief else None))
                active_map = loads(target.execute("SELECT active_revisions_json FROM wb_content_items WHERE id=?", (item_id,)).fetchone()[0], {})
                active_map[kind] = revision_id
                target.execute("UPDATE wb_content_items SET active_revisions_json=? WHERE id=?", (dumps(active_map), item_id))
                track(link(target, batch_id, "script", legacy_id + ":" + key, "revision", revision_id, "needs_platform_review"))
            task_result = {"task_id": legacy_id, "campaign_id": campaign_id, "items": list(item_ids.values()), "blocked": []}
            for field in ("publications_json", "metrics_json"):
                value = loads(task[field], {})
                if value:
                    task_result["blocked"].append(field + " retained_in_legacy_only")
                    report["blocked"].append({"source": legacy_id, "reason": field + " requires explicit legacy publication mapping"})
            report["tasks"].append(task_result)

        canonical_assets = {}
        for file in files:
            relative = file["relative_path"]
            path = (PROJECT_ROOT / relative).resolve()
            if not path.is_file():
                report["blocked"].append({"source": "file:" + str(file["id"]), "reason": "missing_file", "path": relative})
                track(link(target, batch_id, "file", file["id"], "asset", "missing", "blocked_missing_file"))
                continue
            digest = file_hash(path)
            size = path.stat().st_size
            key = (digest, size)
            mime_type = "application/x-subrip" if file["kind"] == "srt" else mimetypes.guess_type(file["original_name"])[0] or "application/octet-stream"
            asset_id = canonical_assets.get(key)
            if not asset_id:
                asset_id = "asset_legacy_file_{}".format(file["id"])
                canonical_assets[key] = asset_id
                media = loads(file["media_info_json"], {})
                source_info = {"legacy_file_id": file["id"], "legacy_task_id": file["content_id"],
                               "kind": file["kind"], "original_name": file["original_name"]}
                track(insert(target, """INTO wb_assets
                    (id,sha256,byte_size,storage_key,mime_type,media_info_json,source_json,privacy_class,rights_status,retention_class,created_at)
                    VALUES (?,?,?,?,?,?,?,'local_only','legacy_unverified','referenced',?)""",
                    (asset_id, digest, size, relative, mime_type, dumps(media), dumps(source_info), utc(file["created_at"]))))
            target.execute("UPDATE wb_assets SET mime_type=? WHERE id=?", (mime_type, asset_id))
            campaign_id = "cmp_legacy_" + file["content_id"]
            track(insert(target, "INTO wb_asset_links(id,asset_id,owner_type,owner_id,purpose,license_id,created_at) VALUES (?,?, 'campaign',?,?,NULL,?)",
                         ("assetlink_legacy_file_{}".format(file["id"]), asset_id, campaign_id, "legacy_file_{}".format(file["id"]), utc(file["created_at"]))))
            track(link(target, batch_id, "file", file["id"], "asset", asset_id, "registered_unassigned"))
            media_info = loads(file["media_info_json"], {})
            if file["kind"] == "srt" and not media_info.get("source_audio_file_id"):
                report["blocked"].append({"source": "file:" + str(file["id"]), "reason": "subtitle_source_confirmation_required", "asset_id": asset_id})
            report["files"].append({"legacy_file_id": file["id"], "asset_id": asset_id, "sha256": digest, "size": size})

        for event in events:
            event_id = "legacy-event-{}".format(event["id"])
            campaign_id = "cmp_legacy_" + event["content_id"]
            payload = {"legacy_event_id": event["id"], "event": event["event"], "detail": event["detail"], "legacy_created_at": event["created_at"]}
            track(insert(target, """INTO wb_events
                (event_id,aggregate_type,aggregate_id,event_type,schema_version,actor,trace_id,payload_json,created_at)
                VALUES (?, 'campaign',?,'legacy.event',1,'migration',NULL,?,?)""",
                (event_id, campaign_id, dumps(payload), utc(event["created_at"]))))

        integrity = target.execute("PRAGMA integrity_check").fetchone()[0]
        foreign = target.execute("PRAGMA foreign_key_check").fetchall()
        campaign_count = target.execute("SELECT COUNT(*) FROM wb_campaigns WHERE id LIKE 'cmp_legacy_%'").fetchone()[0]
        file_links = target.execute("SELECT COUNT(DISTINCT source_id) FROM wb_legacy_links WHERE batch_id=? AND source_type='file'", (batch_id,)).fetchone()[0]
        report["verification"] = {
            "integrity_check": integrity, "foreign_key_errors": [tuple(row) for row in foreign],
            "source_tasks": len(tasks), "mapped_campaigns": campaign_count,
            "source_files": len(files), "mapped_file_links": file_links,
            "content_items": target.execute("SELECT COUNT(*) FROM wb_content_items").fetchone()[0],
            "revisions": target.execute("SELECT COUNT(*) FROM wb_revisions").fetchone()[0],
            "events": target.execute("SELECT COUNT(*) FROM wb_events").fetchone()[0],
        }
        if integrity != "ok" or foreign or campaign_count != len(tasks):
            raise RuntimeError("迁移验证失败：{}".format(report["verification"]))
        target.execute("INSERT OR REPLACE INTO wb_migrations VALUES (?,?,?,?,?)",
                       ("workbench-v2", batch_id, source_checksum, utcnow(), dumps(report)))
    source.close()
    target.close()
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Workbench v2 idempotent migration")
    parser.add_argument("--source", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--batch-id", default="legacy-v1")
    parser.add_argument("--report")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    result = migrate(args.source, args.target, args.batch_id, args.apply)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.report:
        Path(args.report).write_text(text + "\n", encoding="utf-8")
    print(json.dumps({"changed": result["changed"], "skipped": result["skipped"], "blocked": len(result["blocked"]), "verification": result["verification"]}, ensure_ascii=False))
