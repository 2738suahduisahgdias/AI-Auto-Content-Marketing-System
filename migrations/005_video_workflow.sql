CREATE TABLE IF NOT EXISTS stage_revisions (
 id TEXT PRIMARY KEY, content_id TEXT NOT NULL, stage TEXT NOT NULL,
 revision_no INTEGER NOT NULL, payload_json TEXT NOT NULL, payload_hash TEXT NOT NULL,
 status TEXT NOT NULL, created_at TEXT NOT NULL,
 UNIQUE(content_id,stage,revision_no),
 FOREIGN KEY(content_id) REFERENCES tasks(content_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS video_variants (
 id TEXT PRIMARY KEY, content_id TEXT NOT NULL,
 template_id TEXT NOT NULL, template_version TEXT NOT NULL,
 file_id INTEGER NOT NULL UNIQUE, file_sha256 TEXT NOT NULL DEFAULT '',
 quality_json TEXT NOT NULL DEFAULT '{}', approved_at TEXT, published_json TEXT NOT NULL DEFAULT '{}',
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 FOREIGN KEY(content_id) REFERENCES tasks(content_id) ON DELETE CASCADE,
 FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS video_variants_task ON video_variants(content_id,created_at);
