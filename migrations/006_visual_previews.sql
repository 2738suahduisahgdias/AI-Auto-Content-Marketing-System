CREATE TABLE IF NOT EXISTS visual_previews (
 id TEXT PRIMARY KEY, content_id TEXT NOT NULL,
 template_key TEXT NOT NULL, template_id TEXT NOT NULL, template_version TEXT NOT NULL,
 composition_id TEXT NOT NULL, mode TEXT NOT NULL, platform TEXT NOT NULL,
 request_json TEXT NOT NULL, fingerprint TEXT NOT NULL,
 storyboard_json TEXT NOT NULL, props_json TEXT NOT NULL, input_snapshot_json TEXT NOT NULL,
 status TEXT NOT NULL, progress REAL NOT NULL DEFAULT 0,
 video_file_id INTEGER, cover_file_id INTEGER, error TEXT NOT NULL DEFAULT '',
 approved_at TEXT, is_current INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 FOREIGN KEY(content_id) REFERENCES tasks(content_id) ON DELETE CASCADE,
 FOREIGN KEY(video_file_id) REFERENCES files(id) ON DELETE SET NULL,
 FOREIGN KEY(cover_file_id) REFERENCES files(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS visual_previews_lookup
 ON visual_previews(content_id,template_key,fingerprint,status,approved_at);
CREATE INDEX IF NOT EXISTS visual_previews_current ON visual_previews(content_id,is_current,created_at);
