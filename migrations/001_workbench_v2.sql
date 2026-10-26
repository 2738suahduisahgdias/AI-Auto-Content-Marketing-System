-- 本地 AI 内容营销工作台 v2 独立参考结构，2026-10-26
-- 仅用于空参考数据库与 contract tests；不可直接当作原项目迁移脚本。
-- 与开发文档第11节配套。JSON schema、跨表类型匹配、状态迁移由领域服务校验。
PRAGMA foreign_keys = ON;
BEGIN;
CREATE TABLE wb_campaigns (
 id TEXT PRIMARY KEY, title TEXT NOT NULL, brief_json TEXT NOT NULL DEFAULT '{}',
 version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE wb_content_items (
 id TEXT PRIMARY KEY, campaign_id TEXT REFERENCES wb_campaigns(id),
 content_type TEXT NOT NULL CHECK(content_type IN ('article','video')),
 platform TEXT NOT NULL, state TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1,
 active_revisions_json TEXT NOT NULL DEFAULT '{}', legacy_task_id TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 CHECK(platform <> 'wechat_official_account' OR content_type = 'article')
);
CREATE TABLE wb_assets (
 id TEXT PRIMARY KEY, sha256 TEXT NOT NULL, byte_size INTEGER NOT NULL CHECK(byte_size >= 0),
 storage_key TEXT NOT NULL, mime_type TEXT NOT NULL, media_info_json TEXT NOT NULL DEFAULT '{}',
 source_json TEXT NOT NULL DEFAULT '{}', privacy_class TEXT NOT NULL,
 rights_status TEXT NOT NULL DEFAULT 'research_only', retention_class TEXT NOT NULL DEFAULT 'referenced',
 created_at TEXT NOT NULL, UNIQUE(sha256, byte_size)
);
CREATE TABLE wb_licenses (
 id TEXT PRIMARY KEY, asset_id TEXT NOT NULL REFERENCES wb_assets(id),
 holder TEXT, allowed_uses_json TEXT NOT NULL, platform_scope_json TEXT NOT NULL,
 evidence_asset_id TEXT REFERENCES wb_assets(id), valid_until TEXT,
 declared_by TEXT NOT NULL, declared_at TEXT NOT NULL, status TEXT NOT NULL
);
CREATE TABLE wb_revisions (
 id TEXT PRIMARY KEY, item_id TEXT NOT NULL REFERENCES wb_content_items(id),
 kind TEXT NOT NULL, revision_no INTEGER NOT NULL CHECK(revision_no > 0),
 parent_id TEXT REFERENCES wb_revisions(id), payload_json TEXT NOT NULL,
 payload_hash TEXT NOT NULL, validity TEXT NOT NULL DEFAULT 'valid',
 source_audio_asset_id TEXT REFERENCES wb_assets(id), created_by TEXT NOT NULL, created_at TEXT NOT NULL,
 UNIQUE(item_id,kind,revision_no)
);
CREATE TABLE wb_revision_dependencies (
 revision_id TEXT NOT NULL REFERENCES wb_revisions(id),
 depends_revision_id TEXT REFERENCES wb_revisions(id), depends_asset_id TEXT REFERENCES wb_assets(id),
 CHECK((depends_revision_id IS NOT NULL) <> (depends_asset_id IS NOT NULL))
);
CREATE UNIQUE INDEX wb_dep_revision ON wb_revision_dependencies(revision_id,depends_revision_id) WHERE depends_revision_id IS NOT NULL;
CREATE UNIQUE INDEX wb_dep_asset ON wb_revision_dependencies(revision_id,depends_asset_id) WHERE depends_asset_id IS NOT NULL;
CREATE TABLE wb_asset_links (
 id TEXT PRIMARY KEY, asset_id TEXT NOT NULL REFERENCES wb_assets(id),
 owner_type TEXT NOT NULL, owner_id TEXT NOT NULL, purpose TEXT NOT NULL,
 license_id TEXT REFERENCES wb_licenses(id), created_at TEXT NOT NULL,
 UNIQUE(asset_id,owner_type,owner_id,purpose)
); -- owner_type/owner_id 存在性与引用保护必须在服务事务中校验。
CREATE TABLE wb_source_accounts (
 id TEXT PRIMARY KEY, platform TEXT NOT NULL, external_account_id TEXT NOT NULL,
 browser_profile_ref TEXT NOT NULL, connection_status TEXT NOT NULL,
 created_at TEXT NOT NULL, UNIQUE(platform, external_account_id)
);
CREATE TABLE wb_collections (
 id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES wb_source_accounts(id),
 external_collection_id TEXT NOT NULL, title TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)),
 UNIQUE(account_id, external_collection_id)
);
CREATE TABLE wb_research_items (
 id TEXT PRIMARY KEY, platform TEXT NOT NULL, platform_item_id TEXT,
 canonical_url TEXT NOT NULL, canonical_url_hash TEXT NOT NULL, metadata_json TEXT NOT NULL,
 first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL, observed_at TEXT NOT NULL
);
CREATE UNIQUE INDEX wb_research_external ON wb_research_items(platform,platform_item_id) WHERE platform_item_id IS NOT NULL;
CREATE UNIQUE INDEX wb_research_url ON wb_research_items(platform,canonical_url_hash);
CREATE TABLE wb_research_aliases (
 platform TEXT NOT NULL, alias_url_hash TEXT NOT NULL, item_id TEXT NOT NULL REFERENCES wb_research_items(id),
 PRIMARY KEY(platform,alias_url_hash)
);
CREATE TABLE wb_memberships (
 collection_id TEXT NOT NULL REFERENCES wb_collections(id), item_id TEXT NOT NULL REFERENCES wb_research_items(id),
 status TEXT NOT NULL DEFAULT 'present', last_seen_run_id TEXT,
 consecutive_full_scan_misses INTEGER NOT NULL DEFAULT 0 CHECK(consecutive_full_scan_misses >= 0),
 PRIMARY KEY(collection_id,item_id)
);
CREATE TABLE wb_sync_runs (
 id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES wb_source_accounts(id),
 mode TEXT NOT NULL CHECK(mode IN ('incremental','full')), scope_json TEXT NOT NULL,
 status TEXT NOT NULL, checkpoint_json TEXT NOT NULL DEFAULT '{}', selector_version TEXT NOT NULL,
 complete INTEGER NOT NULL DEFAULT 0 CHECK(complete IN (0,1)), started_at TEXT NOT NULL, finished_at TEXT,
 stats_json TEXT NOT NULL DEFAULT '{}', error_json TEXT
);
CREATE TABLE wb_sync_pages (
 run_id TEXT NOT NULL REFERENCES wb_sync_runs(id), page_key TEXT NOT NULL,
 collection_id TEXT NOT NULL REFERENCES wb_collections(id), receipt_json TEXT NOT NULL,
 committed_at TEXT NOT NULL, PRIMARY KEY(run_id,page_key)
);
CREATE TABLE wb_analyses (
 id TEXT PRIMARY KEY, item_id TEXT NOT NULL REFERENCES wb_research_items(id),
 source_asset_id TEXT REFERENCES wb_assets(id), pipeline_version TEXT NOT NULL,
 model_manifest_json TEXT NOT NULL, prompt_hash TEXT NOT NULL,
 cache_key TEXT NOT NULL UNIQUE, report_json TEXT NOT NULL,
 status TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE wb_evidence (
 id TEXT PRIMARY KEY, analysis_id TEXT NOT NULL REFERENCES wb_analyses(id),
 asset_id TEXT REFERENCES wb_assets(id), evidence_type TEXT NOT NULL,
 start_ms INTEGER, end_ms INTEGER, text_content TEXT, metadata_json TEXT NOT NULL DEFAULT '{}',
 CHECK(start_ms IS NULL OR start_ms >= 0),
 CHECK(end_ms IS NULL OR (start_ms IS NOT NULL AND end_ms >= start_ms))
);
CREATE TABLE wb_topic_candidates (
 id TEXT PRIMARY KEY, payload_json TEXT NOT NULL, scores_json TEXT NOT NULL,
 evidence_ids_json TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE wb_feedback (
 id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL REFERENCES wb_topic_candidates(id),
 decision TEXT NOT NULL CHECK(decision IN ('accept','reject')), reason TEXT,
 actor TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE wb_providers (
 id TEXT PRIMARY KEY, adapter_type TEXT NOT NULL, endpoint TEXT, region TEXT,
 secret_ref TEXT, enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0,1)),
 verification_status TEXT NOT NULL DEFAULT 'unverified', verified_at TEXT,
 config_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE wb_models (
 id TEXT PRIMARY KEY, provider_id TEXT NOT NULL REFERENCES wb_providers(id),
 model_id TEXT NOT NULL, capability_manifest_json TEXT NOT NULL,
 lifecycle TEXT NOT NULL DEFAULT 'unverified', source_url TEXT, checked_at TEXT,
 UNIQUE(provider_id,model_id)
);
CREATE TABLE wb_route_revisions (
 id TEXT PRIMARY KEY, version INTEGER NOT NULL UNIQUE, config_json TEXT NOT NULL,
 config_hash TEXT NOT NULL, activated_at TEXT, created_by TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE wb_price_revisions (
 id TEXT PRIMARY KEY, provider_id TEXT NOT NULL REFERENCES wb_providers(id),
 model_id TEXT NOT NULL, currency TEXT NOT NULL, units_json TEXT NOT NULL,
 source_url TEXT, verified_at TEXT NOT NULL, valid_until TEXT
);
CREATE TABLE wb_jobs (
 id TEXT PRIMARY KEY, kind TEXT NOT NULL, aggregate_id TEXT,
 status TEXT NOT NULL CHECK(status IN ('queued','leased','running','retry_wait','blocked','unknown_remote','cancel_requested','cancelled','failed','succeeded')),
 stage TEXT, progress REAL CHECK(progress IS NULL OR (progress >= 0 AND progress <= 1)),
 input_json TEXT NOT NULL, input_hash TEXT NOT NULL, route_revision_id TEXT REFERENCES wb_route_revisions(id),
 idempotency_scope TEXT NOT NULL, idempotency_key TEXT NOT NULL,
 priority INTEGER NOT NULL DEFAULT 0, available_at TEXT NOT NULL,
 lease_owner TEXT, lease_expires_at TEXT, fencing_token INTEGER NOT NULL DEFAULT 0,
 attempt_count INTEGER NOT NULL DEFAULT 0, max_attempts INTEGER NOT NULL DEFAULT 3,
 resource_key TEXT, blocked_reason TEXT, error_json TEXT, result_json TEXT,
 cancel_requested_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 UNIQUE(idempotency_scope,idempotency_key)
);
CREATE INDEX wb_jobs_due ON wb_jobs(status,available_at,priority);
CREATE TABLE wb_attempts (
 id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES wb_jobs(id), attempt_no INTEGER NOT NULL,
 fencing_token INTEGER NOT NULL, status TEXT NOT NULL,
 provider_id TEXT REFERENCES wb_providers(id), model_id TEXT,
 submission_intent_json TEXT, provider_request_id TEXT, provider_job_id TEXT,
 request_fingerprint TEXT, usage_json TEXT, started_at TEXT NOT NULL, finished_at TEXT,
 error_json TEXT, UNIQUE(job_id,attempt_no)
);
CREATE TABLE wb_job_dependencies (
 job_id TEXT NOT NULL REFERENCES wb_jobs(id), dependency_job_id TEXT NOT NULL REFERENCES wb_jobs(id),
 PRIMARY KEY(job_id,dependency_job_id), CHECK(job_id <> dependency_job_id)
); -- 环检测在提交依赖的事务中执行。
CREATE TABLE wb_resource_leases (
 resource_key TEXT NOT NULL, slot INTEGER NOT NULL, job_id TEXT NOT NULL REFERENCES wb_jobs(id),
 lease_owner TEXT NOT NULL, expires_at TEXT NOT NULL, fencing_token INTEGER NOT NULL,
 PRIMARY KEY(resource_key,slot)
);
CREATE TABLE wb_schedules (
 id TEXT PRIMARY KEY, kind TEXT NOT NULL, expression TEXT NOT NULL, timezone TEXT NOT NULL,
 next_due_at TEXT NOT NULL, misfire_policy TEXT NOT NULL, payload_json TEXT NOT NULL,
 enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)), version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE wb_schedule_runs (
 schedule_id TEXT NOT NULL REFERENCES wb_schedules(id), due_at TEXT NOT NULL,
 job_id TEXT NOT NULL REFERENCES wb_jobs(id), created_at TEXT NOT NULL,
 PRIMARY KEY(schedule_id,due_at)
);
CREATE TABLE wb_approvals (
 id TEXT PRIMARY KEY, item_id TEXT NOT NULL REFERENCES wb_content_items(id),
 revision_id TEXT NOT NULL REFERENCES wb_revisions(id), manifest_hash TEXT NOT NULL,
 decision TEXT NOT NULL CHECK(decision IN ('approve','reject')), check_results_json TEXT NOT NULL,
 actor TEXT NOT NULL, created_at TEXT NOT NULL, revoked_at TEXT
);
CREATE TABLE wb_publications (
 id TEXT PRIMARY KEY, item_id TEXT NOT NULL REFERENCES wb_content_items(id),
 revision_id TEXT NOT NULL REFERENCES wb_revisions(id), approval_id TEXT NOT NULL REFERENCES wb_approvals(id),
 artifact_asset_id TEXT REFERENCES wb_assets(id), manifest_json TEXT NOT NULL,
 platform TEXT NOT NULL, url TEXT NOT NULL, published_at TEXT NOT NULL,
 recorded_by TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE wb_metric_samples (
 id TEXT PRIMARY KEY, publication_id TEXT NOT NULL REFERENCES wb_publications(id),
 window_key TEXT NOT NULL, metric_key TEXT NOT NULL, value REAL, missing_reason TEXT,
 source TEXT NOT NULL, observed_at TEXT NOT NULL, scheduled_for TEXT,
 CHECK(value IS NOT NULL OR missing_reason IS NOT NULL),
 UNIQUE(publication_id,window_key,metric_key,observed_at,source)
);
CREATE TABLE wb_retrospectives (
 id TEXT PRIMARY KEY, publication_ids_json TEXT NOT NULL, revision_no INTEGER NOT NULL,
 evidence_json TEXT NOT NULL, conclusion TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE wb_cost_entries (
 id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES wb_jobs(id),
 attempt_id TEXT REFERENCES wb_attempts(id), price_revision_id TEXT REFERENCES wb_price_revisions(id),
 entry_type TEXT NOT NULL CHECK(entry_type IN ('estimate','reserve','release','reported','adjustment')),
 amount_microunits INTEGER, currency TEXT NOT NULL, is_unknown INTEGER NOT NULL DEFAULT 0 CHECK(is_unknown IN (0,1)),
 usage_json TEXT NOT NULL DEFAULT '{}', fx_json TEXT, created_at TEXT NOT NULL,
 CHECK((is_unknown = 1 AND amount_microunits IS NULL) OR (is_unknown = 0 AND amount_microunits IS NOT NULL))
); -- reserve/release 为追加分录；总可用额必须在同一写事务内检查。
CREATE TABLE wb_events (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE,
 aggregate_type TEXT NOT NULL, aggregate_id TEXT NOT NULL, event_type TEXT NOT NULL,
 schema_version INTEGER NOT NULL DEFAULT 1, actor TEXT NOT NULL, trace_id TEXT,
 payload_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX wb_events_aggregate ON wb_events(aggregate_id,sequence);
CREATE TABLE wb_migrations (
 version TEXT PRIMARY KEY, batch_id TEXT NOT NULL, source_checksum TEXT NOT NULL,
 applied_at TEXT NOT NULL, report_json TEXT NOT NULL
);
CREATE TABLE wb_legacy_links (
 batch_id TEXT NOT NULL, source_type TEXT NOT NULL, source_id TEXT NOT NULL,
 target_type TEXT NOT NULL, target_id TEXT NOT NULL, resolution TEXT NOT NULL,
 PRIMARY KEY(batch_id,source_type,source_id,target_type,target_id)
);
COMMIT;
