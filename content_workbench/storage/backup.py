import argparse
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .db import PROJECT_ROOT, file_hash


def create_backup(root=PROJECT_ROOT, destination=None):
    root = Path(root).resolve()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(destination) if destination else root / "data" / "backups" / ("p0-p1-" + stamp)
    out.mkdir(parents=True, exist_ok=False)
    source = sqlite3.connect(str(root / "data" / "content-agent.db"), timeout=30)
    target = sqlite3.connect(str(out / "source.db"))
    source.backup(target)
    target.close()
    rows = source.execute("SELECT relative_path FROM files UNION SELECT sample_path FROM voice_profiles WHERE sample_path IS NOT NULL").fetchall()
    entries = []
    for (relative,) in rows:
        path = (root / relative).resolve()
        item = {"relative_path": relative, "exists": path.is_file()}
        if path.is_file() and root in path.parents:
            copied = out / "files" / relative
            copied.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, copied)
            item.update({"size": path.stat().st_size, "sha256": file_hash(path)})
        entries.append(item)
    code = {}
    for relative in ("app.py", "web/app.js", "web/index.html", "web/styles.css"):
        path = root / relative
        if path.is_file():
            code[relative] = file_hash(path)
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(), "source_root": str(root),
        "database": "source.db", "task_count": source.execute("SELECT COUNT(*) FROM tasks").fetchone()[0],
        "file_count": source.execute("SELECT COUNT(*) FROM files").fetchone()[0],
        "files": entries, "code_sha256": code,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    check = sqlite3.connect(str(out / "source.db"))
    integrity = check.execute("PRAGMA integrity_check").fetchone()[0]
    foreign = check.execute("PRAGMA foreign_key_check").fetchall()
    check.close()
    source.close()
    if integrity != "ok" or foreign:
        raise RuntimeError("备份数据库校验失败")
    return out, manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(PROJECT_ROOT))
    parser.add_argument("--destination")
    args = parser.parse_args()
    directory, result = create_backup(args.root, args.destination)
    print(json.dumps({"backup": str(directory), "tasks": result["task_count"], "files": len(result["files"]), "missing": sum(not item["exists"] for item in result["files"])}, ensure_ascii=False))
