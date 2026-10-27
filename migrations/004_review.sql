CREATE TABLE IF NOT EXISTS review_batches (
 id TEXT PRIMARY KEY,source_folder TEXT NOT NULL,rules_json TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS review_items (
 id TEXT PRIMARY KEY,batch_id TEXT NOT NULL,source_path TEXT NOT NULL,source_sha256 TEXT NOT NULL,
 status TEXT NOT NULL,decision TEXT NOT NULL,report_json TEXT NOT NULL DEFAULT '{}',ai_risk_json TEXT NOT NULL DEFAULT '{}',
 candidate_path TEXT,output_path TEXT,error_json TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
 UNIQUE(batch_id,source_path,source_sha256),FOREIGN KEY(batch_id) REFERENCES review_batches(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS review_items_batch ON review_items(batch_id,status,decision);
