CREATE TABLE IF NOT EXISTS kb_entities (
 id TEXT PRIMARY KEY,type TEXT NOT NULL,name TEXT NOT NULL,summary TEXT NOT NULL DEFAULT '',
 properties_json TEXT NOT NULL DEFAULT '{}',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
 UNIQUE(type,name)
);
CREATE TABLE IF NOT EXISTS kb_relations (
 id TEXT PRIMARY KEY,source_type TEXT NOT NULL,source_id TEXT NOT NULL,predicate TEXT NOT NULL,
 target_type TEXT NOT NULL,target_id TEXT NOT NULL,properties_json TEXT NOT NULL DEFAULT '{}',
 evidence_json TEXT NOT NULL DEFAULT '{}',confidence REAL NOT NULL DEFAULT 1,created_at TEXT NOT NULL,
 UNIQUE(source_type,source_id,predicate,target_type,target_id,evidence_json)
);
CREATE INDEX IF NOT EXISTS kb_relations_source ON kb_relations(source_type,source_id);
CREATE INDEX IF NOT EXISTS kb_relations_target ON kb_relations(target_type,target_id);
CREATE TABLE IF NOT EXISTS kb_rules (
 id TEXT PRIMARY KEY,name TEXT NOT NULL UNIQUE,definition_json TEXT NOT NULL,created_at TEXT NOT NULL
);
