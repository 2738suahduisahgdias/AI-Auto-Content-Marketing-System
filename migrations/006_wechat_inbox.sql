CREATE TABLE IF NOT EXISTS wechat_topic_messages (
 id TEXT PRIMARY KEY,
 msgid TEXT NOT NULL UNIQUE,
 research_item_id TEXT NOT NULL REFERENCES wb_research_items(id),
 sender_id TEXT NOT NULL,
 message_type TEXT NOT NULL,
 raw_text TEXT NOT NULL DEFAULT '',
 original_url TEXT,
 raw_payload_json TEXT NOT NULL DEFAULT '{}',
 title_override TEXT NOT NULL DEFAULT '',
 note_override TEXT NOT NULL DEFAULT '',
 category TEXT NOT NULL DEFAULT 'unclassified' CHECK(category IN ('unclassified','featured','competitor','high_praise','industry')),
 ingest_status TEXT NOT NULL DEFAULT 'saved',
 received_at TEXT NOT NULL,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS wechat_messages_category ON wechat_topic_messages(category,received_at);
CREATE INDEX IF NOT EXISTS wechat_messages_research_item ON wechat_topic_messages(research_item_id);
