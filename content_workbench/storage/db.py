import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(os.environ.get("CONTENT_AGENT_ROOT", PROJECT_ROOT)).expanduser().resolve()
DB_PATH = Path(os.environ.get("CONTENT_AGENT_DB", ROOT / "data" / "content-agent.db")).expanduser().resolve()
SCHEMA_PATH = PROJECT_ROOT / "migrations" / "001_workbench_v2.sql"


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def new_id(prefix):
    return "{}_{}".format(prefix, uuid.uuid4().hex[:20])


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def loads(value, default=None):
    if value in (None, ""):
        return {} if default is None else default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {} if default is None else default


def payload_hash(value):
    return hashlib.sha256(dumps(value).encode("utf-8")).hexdigest()


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def connect(path=None, readonly=False):
    target = Path(path or DB_PATH).expanduser().resolve()
    if readonly:
        conn = sqlite3.connect("file:{}?mode=ro".format(target.as_posix()), uri=True, timeout=15)
    else:
        conn = sqlite3.connect(str(target), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=15000")
    if not readonly:
        conn.execute("PRAGMA journal_mode=WAL")
    return conn


@contextmanager
def immediate(conn):
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    else:
        conn.commit()


def expand_schema(conn):
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='wb_campaigns'").fetchone()
    if not exists:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def row_dict(row):
    return dict(row) if row is not None else None
