export type Json = Record<string, any>;
export type ContentKind = "article" | "video";
export interface Job { id: string; kind: string; status: string; stage: string; created_at: string; progress?: number; error?: Json | null; result?: Json | null }
export interface Task { content_id: string; title: string; state: string; pillar: string; audience: string; angle?: string; scripts: Json; files: Json[]; asset_plan: Json[]; quality: Json; publications: Json; metrics: Json; retrospective: string; events: Json[]; render_runs?: Json[]; updated_at: string; published_at?: string }
export interface Article { id: string; state: string; version: number; campaign: Json; active_revisions: Record<string, string>; revisions: Json[]; publications: Json[]; manifest: Json }
export interface TopicItem { id: string; platform: string; title: string; url: string; metadata: Json; source_key: string; analysis_status: string; last_seen_at: string; archived?: boolean }
export interface PublishTarget { id: string; platform: string; platform_name: string; status: string; payload: Json; preview: Json; error?: Json | null; external_url?: string }
export interface PublishBatch { id: string; content_kind: ContentKind; source_id: string; source_hash: string; status: string; confirmed_at?: string; targets: PublishTarget[] }
export interface AppResources {
  core: Json;
  topics: Json;
  agents: Json;
  accounts: Json;
  articles: { items: Article[]; jobs: Job[] };
  knowledge: Json;
}
