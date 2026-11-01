CREATE TABLE IF NOT EXISTS wechat_link_snapshots (
 message_id TEXT PRIMARY KEY REFERENCES wechat_topic_messages(id) ON DELETE CASCADE,
 status TEXT NOT NULL DEFAULT 'not_started',
 snapshot_json TEXT NOT NULL DEFAULT '{}',
 error TEXT,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS wechat_snapshot_status ON wechat_link_snapshots(status,updated_at);
