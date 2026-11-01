-- Approval evidence for individual video files. Existing tasks without a
-- variant continue to use the legacy task-level approval check.
CREATE TABLE IF NOT EXISTS video_variants (
 content_id TEXT NOT NULL,
 file_id INTEGER NOT NULL,
 file_sha256 TEXT NOT NULL,
 approved_at TEXT,
 PRIMARY KEY (content_id, file_id),
 FOREIGN KEY(content_id) REFERENCES tasks(content_id) ON DELETE CASCADE,
 FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE
);
