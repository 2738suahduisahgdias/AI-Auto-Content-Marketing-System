CREATE TABLE IF NOT EXISTS publish_schedules (
 id TEXT PRIMARY KEY,
 first_run_at TEXT NOT NULL,
 interval_minutes INTEGER NOT NULL CHECK(interval_minutes > 0),
 daily_limit INTEGER NOT NULL CHECK(daily_limit > 0),
 status TEXT NOT NULL CHECK(status IN ('active','paused','completed','cancelled')),
 next_run_at TEXT,
 idempotency_key TEXT NOT NULL UNIQUE,
 request_hash TEXT NOT NULL,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS publish_schedules_due ON publish_schedules(status,next_run_at);

CREATE TABLE IF NOT EXISTS publish_queue (
 id TEXT PRIMARY KEY,
 schedule_id TEXT NOT NULL,
 batch_id TEXT NOT NULL,
 target_id TEXT NOT NULL,
 video_id TEXT NOT NULL,
 platform TEXT NOT NULL,
 position INTEGER NOT NULL CHECK(position >= 0),
 scheduled_for TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('queued','running','published','failed','unknown_remote','cancelled')),
 job_id TEXT UNIQUE,
 dispatched_at TEXT,
 dispatch_day TEXT,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 UNIQUE(schedule_id,target_id),
 UNIQUE(schedule_id,video_id,platform),
 UNIQUE(schedule_id,position),
 FOREIGN KEY(schedule_id) REFERENCES publish_schedules(id) ON DELETE CASCADE,
 FOREIGN KEY(batch_id) REFERENCES publish_batches(id),
 FOREIGN KEY(target_id) REFERENCES publish_targets(id),
 FOREIGN KEY(job_id) REFERENCES wb_jobs(id)
);
CREATE INDEX IF NOT EXISTS publish_queue_due ON publish_queue(schedule_id,status,scheduled_for,position);
CREATE INDEX IF NOT EXISTS publish_queue_dispatch_day ON publish_queue(schedule_id,dispatch_day);
CREATE UNIQUE INDEX IF NOT EXISTS publish_queue_active_target ON publish_queue(target_id)
 WHERE status IN ('queued','running','unknown_remote');
