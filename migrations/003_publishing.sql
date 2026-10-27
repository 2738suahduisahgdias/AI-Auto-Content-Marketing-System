CREATE TABLE IF NOT EXISTS publish_batches (
 id TEXT PRIMARY KEY,
 content_kind TEXT NOT NULL,
 source_id TEXT NOT NULL,
 source_hash TEXT NOT NULL,
 status TEXT NOT NULL,
 confirmed_by TEXT,
 confirmed_at TEXT,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS publish_batches_source ON publish_batches(content_kind,source_id,source_hash);
CREATE TABLE IF NOT EXISTS publish_targets (
 id TEXT PRIMARY KEY,
 batch_id TEXT NOT NULL,
 platform TEXT NOT NULL,
 payload_json TEXT NOT NULL,
 status TEXT NOT NULL,
 preview_json TEXT NOT NULL DEFAULT '{}',
 error_json TEXT,
 job_id TEXT,
 external_url TEXT,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 UNIQUE(batch_id,platform),
 FOREIGN KEY(batch_id) REFERENCES publish_batches(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS publish_targets_batch ON publish_targets(batch_id,status);
