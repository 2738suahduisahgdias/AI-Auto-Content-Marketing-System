import {displayTime} from '@/lib/presentation';
import { useEffect, useState, type FormEvent } from "react";
import { Archive, Download, ExternalLink } from "lucide-react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { useApp } from "@/AppContext";
import { TopicCard } from "@/components/TopicCard";
import DownloadDetail from "@/components/DownloadDetail";
import DownloadProbeModal from "@/components/DownloadProbeModal";
import WechatInbox from "@/components/WechatInbox";
import { Badge, Busy, Button, Card, Empty, ErrorBox, Field, Input, Modal, PageHeader, Progress, Textarea } from "@/components/ui";
import { api, errorText, jsonOptions } from "@/lib/api";
import { audienceNames, jobStatusNames, pillarNames } from "@/lib/names";
import type { Job, Json, Task, TopicItem } from "@/lib/types";
import "./Topics.css";

type TopicSource = "industry" | "douyin" | "wechat" | "xiaohongshu";
type DouyinView = "hot" | "featured" | "competitor" | "high_praise";
type XiaohongshuView = "hot" | "featured" | "competitor" | "high_praise";
type Settings = { industry_scope: string; industry_prompt: string; douyin_prompt: string; xiaohongshu_prompt: string; daily_time: string; daily_enabled: boolean; featured_collection: string; competitor_collection: string; high_praise_collection: string; xhs_hot_collection: string; xhs_featured_collection: string; xhs_competitor_collection: string; xhs_high_praise_collection: string };
const emptySettings: Settings = { industry_scope: "", industry_prompt: "", douyin_prompt: "", xiaohongshu_prompt: "", daily_time: "09:00", daily_enabled: false, featured_collection: "", competitor_collection: "", high_praise_collection: "", xhs_hot_collection: "", xhs_featured_collection: "", xhs_competitor_collection: "", xhs_high_praise_collection: "" };
const sourceCopy: Record<TopicSource, { title: string; eyebrow: string; description: string }> = {
  industry: { title: "行业热点", eyebrow: "INDUSTRY RESEARCH", description: "只分析真实公开资讯，把行业变化转成有证据、可核查的内容方向。" },
  douyin: { title: "抖音选题", eyebrow: "DOUYIN RESEARCH", description: "热榜与收藏夹只是研究快照；选择后才下载，不把热度当作事实。" },
  wechat: { title: "微信选题", eyebrow: "WECHAT INBOX", description: "微信只负责随手记录，标题、想法备注和分类在后台统一整理。" },
  xiaohongshu: { title: "小红书选题", eyebrow: "XIAOHONGSHU RESEARCH", description: "热点来自平台真实热点；精选、竞对和高赞读取个人收藏，保留作者、互动、原链接和素材下载记录。" },
};
const douyinViews: { id: DouyinView; label: string }[] = [{ id: "hot", label: "热点选题" }, { id: "featured", label: "精选选题" }, { id: "competitor", label: "竞对选题" }, { id: "high_praise", label: "高赞选题" }];
const xiaohongshuViews: { id: XiaohongshuView; label: string }[] = [{ id: "hot", label: "热点选题" }, { id: "featured", label: "精选选题" }, { id: "competitor", label: "竞对选题" }, { id: "high_praise", label: "高赞选题" }];
const jobNames: Record<string, string> = { "topics.sync": "同步抖音快照", "topics.cover": "重新获取封面", "topics.xhs_sync": "同步个人小红书收藏夹", "topics.xhs_login": "个人小红书登录", "topics.industry": "同步行业热点与推荐", "topics.recommend": "生成选题推荐", "topics.login": "抖音采集窗口登录", "topics.metadata_backfill": "补全作者与互动", "research.analyze": "下载所选素材", "research.probe": "读取小红书素材与档位", "research.snapshot": "解析微信链接公开快照", "accounts.sync": "同步账号数据", "accounts.login": "平台登录窗口" };
const activeStatuses = ["queued", "leased", "running", "retry_wait"];
const collectionMetadataKeys = ["author_name", "author_followers", "like_count", "comment_count"];

function syncSummary(last: Json | null) {
  if (!last) return "尚未同步，点击同步内容开始。";
  let stats: Json = {};
  try { stats = JSON.parse(last.stats_json || "{}"); } catch { stats = {}; }
  const errors = (stats.errors || []).map((item: Json) => item.code === "LOGIN_REQUIRED" ? "收藏需要登录" : item.code).filter(Boolean);
  return `最近同步 ${displayTime(last.started_at)} · ${last.status === "partial" ? "部分完成" : jobStatusNames[last.status] || last.status} · ${stats.new != null ? `新增 ${stats.new} 条 · 更新 ${stats.updated || 0} 条` : "历史记录未统计新增量"}${errors.length ? " · 有异常，查看同步记录" : ""}`;
}

function xhsSyncSummary(last: Json | null) {
  if (!last) return "尚未同步个人小红书收藏夹。";
  let stats: Json = {};
  try { stats = JSON.parse(last.stats_json || "{}"); } catch { stats = {}; }
  const errors = (stats.errors || []).map((item: Json) => `${item.source || "收藏夹"}：${item.message || item.code}`).filter(Boolean);
  return `最近同步 ${displayTime(last.started_at)} · ${last.status === "partial" ? "部分完成" : jobStatusNames[last.status] || last.status} · ${stats.new != null ? `新增 ${stats.new} 条 · 更新 ${stats.updated || 0} 条` : "历史记录未统计新增量"}${errors.length ? " · 有异常，查看同步记录" : ""}`;
}

const jobStageNames: Record<string, string> = {
  checking_login: "检查抖音登录",
  waiting_for_user_login: "等待本人登录（最多 5 分钟）",
  login_verified: "登录已确认",
  browser_reconnecting: "浏览器连接中断，正在恢复并重试一次",
  douyin_hot_top20: "正在同步抖音热榜",
  douyin_hot_top20_completed: "热榜处理完成",
  kimi_browser_check_login: "Kimi 正在检查抖音登录",
  kimi_browser_collect_hot: "Kimi 正在读取热榜前 20 条",
  kimi_browser_collect_hot_completed: "热榜读取完成",
  kimi_browser_collect_favorites: "Kimi 正在读取指定收藏夹",
  kimi_browser_collect_favorites_completed: "收藏夹读取完成",
  kimi_browser_collect_details: "Kimi 正在补充作品信息",
  kimi_browser_collect_details_batch: "Kimi 正在批量读取作者与互动数据",
  kimi_browser_collect_details_batch_completed: "Kimi 本批作者与互动数据读取完成",
  research_metadata_batch: "Kimi 正在批量读取作者与互动数据",
  research_metadata_batch_completed: "本批作者与互动数据处理完成",
  author_engagement_backfill: "正在补全作者与互动数据",
  author_engagement_backfill_completed: "作者与互动数据补全完成",
  favorite_collection: "正在读取收藏夹",
  favorite_featured_completed: "精选收藏夹处理完成",
  favorite_competitor_completed: "竞对收藏夹处理完成",
  favorite_high_praise_completed: "高赞收藏夹处理完成",
  research_metadata: "正在补充作品信息",
  xhs_public_hot: "正在读取小红书平台热点",
  xhs_public_hot_completed: "平台热点读取完成",
  xhs_personal_collections: "正在读取三类个人收藏夹",
  xhs_personal_collections_completed: "个人收藏夹读取完成",
  kimi_xiaohongshu_probe: "Kimi 正在探测素材与档位",
  kimi_xiaohongshu_probe_completed: "素材探测完成，等待用户选择",
  kimi_xiaohongshu_download: "Kimi 正在下载所选素材",
  kimi_xiaohongshu_download_completed: "素材下载完成",
  failed: "执行失败",
  cancelled: "任务已取消",
  succeeded: "处理完成",
};

function JobList({ jobs, all = false }: { jobs: Job[]; all?: boolean }) {
  if (!jobs.length) return null;
  const active = jobs.filter(job => activeStatuses.includes(job.status));
  const visible = all ? jobs : [...active, ...jobs.filter(job => !activeStatuses.includes(job.status)).slice(0, 1)];
  const sourceNames: Record<string, string> = { hot: "热榜", featured: "精选", competitor: "竞对", high_praise: "高赞" };
  return <div>{visible.map(job => {
    const stats = job.result?.stats ?? (job.result?.provider === "kimi_cli" ? job.result : null);
    const sourceSummary = stats ? Object.entries(sourceNames).map(([key, label]) => `${label} ${Number(stats[key] || 0)} 条`).join(" · ") : "";
    return <article className="topic-job" key={job.id}>
      <div className="topic-job-head"><div><strong>{jobNames[job.kind] || job.kind}</strong><small>{jobStatusNames[job.status] || "处理中"} · {displayTime(job.created_at)}</small></div><Badge tone={job.status === "succeeded" && job.result?.status !== "partial" ? "green" : ["failed", "unknown_remote"].includes(job.status) ? "red" : "orange"}>{job.result?.status === "partial" ? "部分完成" : jobStatusNames[job.status] || job.status}</Badge></div>
      {activeStatuses.includes(job.status) && <Progress value={job.progress ?? 0} />}
      {job.stage && <p><small>当前阶段：{jobStageNames[job.stage] || job.stage}</small></p>}
      {stats?.provider === "kimi_cli" && <p><small>采集执行：Kimi CLI 浏览器操作 · {typeof stats.total === "number" ? `已检查 ${stats.processed ?? stats.succeeded ?? 0}/${stats.total} 个作品 · 四项完整 ${stats.succeeded || 0} 个` : `已处理 ${stats.finished_sources || 0}/${stats.source_total || 4} 个来源${sourceSummary ? ` · ${sourceSummary}` : ""}`}</small></p>}
      {stats?.errors?.map((error: Json, index: number) => <p className="topic-job-error" key={`${error.source || "source"}-${index}`}>{error.source || "来源"}：{error.message || error.code}{error.action ? ` · 怎么改：${error.action}` : ""}</p>)}
      {job.error && Object.keys(job.error).length > 0 && <p className="topic-job-error">{job.error.message || job.error.code}{job.error.action ? `\n怎么改：${job.error.action}` : ""}</p>}
    </article>;
  })}</div>;
}

const recommendationSourceNames: Record<string, string> = { hot: "抖音热点榜", featured: "精选收藏夹", competitor: "竞对收藏夹", high_praise: "高赞收藏夹", industry: "行业公开资讯", xhs_hot: "小红书热点收藏夹", xhs_featured: "小红书精选收藏夹", xhs_competitor: "小红书竞对收藏夹", xhs_high_praise: "小红书高赞收藏夹", xhs_notes: "我的小红书笔记", wechat_inbox: "微信消息" };

export function Recommendations({ items, agent, sources, busy, onConvert, onArticle }: { items: Json[]; agent: string; sources: TopicItem[]; busy: boolean; onConvert: (item: Json) => void; onArticle?: (item: Json) => void }) {
  if (!items.length) return <Empty title={`还没有${agent === "industry" ? "行业" : agent === "xiaohongshu" ? "小红书" : "抖音"}今日推荐`} description="先同步真实快照，再运行对应选题 Agent；不会根据空白数据生成结论。" />;
  return <div className="topic-recommendations">{items.map(item => {
    const evidenceSources: TopicItem[] = (item.evidence_ids || []).map((id: string) => sources.find(candidate => candidate.id === id)).filter((source: TopicItem | undefined): source is TopicItem => source !== undefined);
    const sourceNames = [...new Set<string>(evidenceSources.map(source => recommendationSourceNames[source.source_key] || source.metadata?.source_name || "研究快照"))];
    return <Card className="topic-recommendation" key={item.id || item.title}>
      <div className="button-row"><Badge tone="green">{pillarNames[item.pillar] || "企业 AI"}</Badge><Badge>{audienceNames[item.audience] || "企业主"}</Badge></div>
      <h3>{item.title}</h3>{agent === "all" && <><p className="topic-recommendation-reason">{item.reason}</p><div className="tag-row">{sourceNames.map(name => <Badge key={name}>{name}</Badge>)}</div></>}<details><summary>推荐理由与证据</summary>{agent !== "all" && <p>{item.reason}</p>}
      <div className="topic-recommendation-sources"><strong>来源</strong>{sourceNames.length ? sourceNames.map(name => <Badge key={name}>{name}</Badge>) : <Badge>未关联来源快照</Badge>}</div>
      {evidenceSources.length > 0 && <div className="topic-recommendation-links">{evidenceSources.map(source => /^https?:\/\//.test(source.url) ? <a key={source.id} href={source.url} target="_blank" rel="noreferrer" title={source.title}>{source.title || "查看原链接"} <ExternalLink size={11} /></a> : null)}</div>}
      {(item.memory_evidence || []).length > 0 && <div className="topic-evidence"><strong>引用我们的增长记忆</strong>{item.memory_evidence.map((memory:Json)=><p key={memory.id}>{memory.title} · {memory.outcome==="hypothesis"?"待验证":memory.outcome==="avoid"?"避坑依据":"有效经验"}：{memory.lesson}<small>依据：{memory.metrics || "尚无效果数据"} · 来源：{memory.evidence || "待补充"}</small></p>)}</div>}
      <div className="topic-evidence"><strong>差异化切入</strong><p>{item.angle}</p>{(item.uncertainties || []).map((value: string) => <small key={value}>待核实：{value}</small>)}</div>
      </details><div className="topic-recommendation-footer"><small className="topic-time">{displayTime(item.created_at)}</small>{agent === "all" && onArticle ? <div className="button-row"><Button size="small" disabled={busy} onClick={() => item.content_format === "article" ? onConvert(item) : onArticle(item)}>{item.content_format === "article" ? "改做视频" : "用这个选题写文章"}</Button><Button size="small" variant="primary" disabled={busy} onClick={() => item.content_format === "article" ? onArticle(item) : onConvert(item)}>{item.content_format === "article" ? "写文章" : item.status === "converted" ? "打开视频任务" : "制作视频"}</Button></div> : <Button size="small" variant="primary" disabled={busy || (item.status === "converted" && !item.task_id)} onClick={() => onConvert(item)}>{item.status === "converted" ? "打开选题" : "转为选题"}</Button>}</div>
    </Card>;
  })}</div>;
}

export default function Topics() {
  const { source = "douyin" } = useParams();
  const navigate = useNavigate();
  const { resources, refresh, notify, loadError } = useApp();
  const [douyinView, setDouyinView] = useState<DouyinView>("featured");
  const [xiaohongshuView, setXiaohongshuView] = useState<XiaohongshuView>("featured");
  const [showArchived, setShowArchived] = useState(false);
  const [busy, setBusy] = useState("");
  const [actionError, setActionError] = useState("");
  const [settings, setSettings] = useState<Settings>(() => ({ ...emptySettings, ...resources?.topics?.settings }));
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [recordsOpen, setRecordsOpen] = useState(false);
  const [wechatManualOpen, setWechatManualOpen] = useState(false);
  const [wechatStatus, setWechatStatus] = useState("");
  useEffect(() => {
    if (source !== "wechat") return;
    let alive = true;
    const load = () => { void api<Json>("/api/topics/wechat/client").then(value => { if (alive) setWechatStatus(value.status); }).catch(() => { if (alive) setWechatStatus("unknown"); }); };
    load();
    const visible = () => { if (!document.hidden) load(); };
    document.addEventListener("visibilitychange", visible);
    return () => { alive = false; document.removeEventListener("visibilitychange", visible); };
  }, [source]);
  const [manualOpen, setManualOpen] = useState(false);
  const [manual, setManual] = useState({ title: "", pillar: "enterprise_ai", audience: "business_owners", pain_point: "", angle: "", favorite_collection: "" });
  const [detail, setDetail] = useState<Json | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [downloadTarget, setDownloadTarget] = useState<TopicItem | null>(null);
  const data: Json = resources?.topics || {};
  const jobs: Job[] = (data.jobs || []).filter((job: Job) => {
    if (job.kind === "topics.recommend") return (job as Json).aggregate_id === source;
    if (source === "xiaohongshu") return (job.kind.startsWith("topics.xhs_") || ["topics.cover", "research.probe", "research.analyze"].includes(job.kind));
    if (source === "douyin") return ["topics.sync", "topics.login", "topics.metadata_backfill", "research.analyze", "topics.cover"].includes(job.kind);
    if (source === "industry") return job.kind === "topics.industry";
    return job.kind === "research.snapshot";
  });
  const hasActiveJobs = jobs.some(job => activeStatuses.includes(job.status));

  useEffect(() => {
    if (!hasActiveJobs) return;
    const timer = window.setInterval(() => { void refresh(); }, 3000);
    return () => window.clearInterval(timer);
  }, [hasActiveJobs, refresh]);

  if (!["industry", "douyin", "wechat", "xiaohongshu"].includes(source)) return <Navigate to="/topics/douyin" replace />;
  const topicSource = source as TopicSource;
  const copy = sourceCopy[topicSource];

  async function perform<T>(key: string, action: () => Promise<T>, success: string, reload = true): Promise<T | null> {
    if (busy) return null;
    setBusy(key); setActionError("");
    try {
      const result = await action();
      if (reload) await refresh();
      notify(success);
      return result;
    } catch (error) {
      const message = errorText(error); setActionError(message); notify(message, true); return null;
    } finally { setBusy(""); }
  }
  async function createResearchTask(item: TopicItem) {
    const task = await perform<Task>(`create-${item.id}`, () => api(`/api/topics/items/${encodeURIComponent(item.id)}/create-task`, jsonOptions("POST")), "任务已创建，来源快照已保留");
    if (task) navigate(`/tasks/${task.content_id}`);
  }
  async function showDetail(item: TopicItem) {
    setDetail({ id: item.id, title: item.title, url: item.url }); setDetailLoading(true); setActionError("");
    try { setDetail(await api(`/api/topics/items/${encodeURIComponent(item.id)}`)); }
    catch (error) { const message = errorText(error); setActionError(message); setDetail(null); notify(message, true); }
    finally { setDetailLoading(false); }
  }
  async function refreshDetail() {
    if (!detail?.id) return;
    setDetailLoading(true);
    try { setDetail(await api(`/api/topics/items/${encodeURIComponent(detail.id)}`)); }
    catch (error) { setActionError(errorText(error)); }
    finally { setDetailLoading(false); }
  }
  function downloadDetail() {
    if (!detail || detailLoading) return;
    const blob = new Blob([JSON.stringify(detail, null, 2)], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob); const anchor = document.createElement("a");
    anchor.href = url; anchor.download = `${String(detail.title || detail.id).replace(/[\\/:*?"<>|]/g, "-").slice(0, 80)}-下载详情.json`;
    anchor.click(); URL.revokeObjectURL(url); notify("已导出当前真实下载详情 JSON");
  }
  async function revealDownload() {
    if (!detail?.id) return;
    await perform("reveal-download", () => api(`/api/topics/items/${encodeURIComponent(detail.id)}/download/reveal`, jsonOptions("POST")), "已打开视频所在文件夹");
  }
  async function copyDownloadPath() {
    const path = detail?.metadata?.download_path;
    if (!path) return;
    try {
      await api(`/api/topics/items/${encodeURIComponent(detail.id)}/download/copy`, jsonOptions("POST"));
      notify("已复制视频本地地址");
    } catch { setActionError("复制失败，请手动选择完整路径"); }
  }
  async function probeDownload(item: TopicItem) {
    setDownloadTarget(item);
    await perform(`probe-${item.id}`, () => api(`/api/topics/items/${encodeURIComponent(item.id)}/download/probe`, jsonOptions("POST")), "素材探测任务已提交；完成后请在弹窗中选择下载模式");
  }
  async function downloadMedia(item: TopicItem, mode: string) {
    const job = await perform(`download-${item.id}`, () => api(`/api/topics/items/${encodeURIComponent(item.id)}/analyze`, jsonOptions("POST", { mode })), "下载任务已提交；完成后可在详情中查看真实本地地址");
    if (job) setDownloadTarget(null);
  }
  async function submitManual(event: FormEvent) {
    event.preventDefault();
    const task = await perform<Task>("manual", () => api("/api/tasks", jsonOptions("POST", manual)), "任务与目录已创建");
    if (task) { setManualOpen(false); setManual(current => ({ ...current, title: "", pain_point: "", angle: "" })); navigate(`/tasks/${task.content_id}`); }
  }
  function updateSetting<K extends keyof Settings>(key: K, value: Settings[K]) { setSettings(current => ({ ...current, [key]: value })); }
  async function saveSettings() {
    await perform("settings", () => api("/api/topics/settings", jsonOptions("POST", settings)), "行业范围、提示词和每日任务已保存");
  }

  async function archiveItem(item: TopicItem) {
    const archived = !item.archived;
    await perform(`archive-${item.id}`, () => api(`/api/topics/items/${encodeURIComponent(item.id)}/archive`, jsonOptions("POST", { archived })), archived ? "选题已归档，可在已归档中恢复" : "选题已恢复到当前列表");
  }

  const sourceKey = topicSource === "industry" ? "industry" : topicSource === "wechat" ? "wechat_inbox" : topicSource === "xiaohongshu" ? `xhs_${xiaohongshuView}` : douyinView;
  const sourceItems: TopicItem[] = showArchived ? (data.archived || []).filter((item: TopicItem) => item.source_key === sourceKey || (topicSource === "xiaohongshu" && ((item as Json).collections || []).includes(settings[`${sourceKey}_collection` as keyof Settings]))) : topicSource === "industry" ? data.sources?.industry || [] : topicSource === "wechat" ? data.sources?.wechat_inbox || [] : topicSource === "xiaohongshu" ? data.sources?.[sourceKey] || [] : data.sources?.[douyinView] || [];
  const visibleSourceItems = topicSource === "xiaohongshu" && xiaohongshuView === "hot" && !showArchived ? [...sourceItems].sort((a, b) => Number(a.metadata?.rank || 0) - Number(b.metadata?.rank || 0)) : sourceItems;
  const collectionStats = (["featured", "competitor", "high_praise"] as const).map(key => {
    const items: TopicItem[] = data.sources?.[key] || [];
    const complete = items.filter(item => collectionMetadataKeys.every(field => item.metadata?.[field] !== null && item.metadata?.[field] !== undefined && item.metadata?.[field] !== "")).length;
    return { key, label: douyinViews.find(view => view.id === key)?.label.replace("选题", "") || key, complete, total: items.length };
  });
  const metadataComplete = collectionStats.reduce((total, group) => total + group.complete, 0);
  const metadataTotal = collectionStats.reduce((total, group) => total + group.total, 0);
  const favorites: Json[] = resources?.core.favorites?.items?.filter((item: Json) => item.enabled) || [];

  const settingsPanel = <Card className="topic-settings-card"><h3>研究范围与每日任务</h3>
    <Field label="行业范围 / 搜索关键词"><Input value={settings.industry_scope} onChange={event => updateSetting("industry_scope", event.target.value)} /></Field>
    <Field label="行业选题 Agent 提示词"><Textarea rows={5} value={settings.industry_prompt} onChange={event => updateSetting("industry_prompt", event.target.value)} /></Field>
    <Field label="抖音选题 Agent 提示词"><Textarea rows={5} value={settings.douyin_prompt} onChange={event => updateSetting("douyin_prompt", event.target.value)} /></Field>
    <Field label="每日时间（本地时间）"><Input type="time" value={settings.daily_time} onChange={event => updateSetting("daily_time", event.target.value)} /></Field>
    <label className="topic-check"><input type="checkbox" checked={settings.daily_enabled} onChange={event => updateSetting("daily_enabled", event.target.checked)} />启用每日任务</label>
    <Field label="精选收藏夹"><Input value={settings.featured_collection} onChange={event => updateSetting("featured_collection", event.target.value)} /></Field>
    <Field label="竞对收藏夹"><Input value={settings.competitor_collection} onChange={event => updateSetting("competitor_collection", event.target.value)} /></Field>
    <Field label="高赞收藏夹"><Input value={settings.high_praise_collection} onChange={event => updateSetting("high_praise_collection", event.target.value)} /></Field>
    {topicSource === "douyin" && <div className="topic-metadata-summary" role="status">
      <strong>收藏作品作者与互动：{metadataComplete}/{metadataTotal} 完整</strong>
      <span>{collectionStats.map(group => `${group.label} ${group.complete}/${group.total}`).join(" · ")}</span>
      <small>只统计精选、竞对和高赞；缺失字段保持未读取，再次补全只处理缺口，热点不参与。</small>
    </div>}
    <div className="topic-settings-actions"><Button variant="primary" disabled={!!busy} onClick={saveSettings}>{busy === "settings" ? "正在保存…" : "保存设置与每日任务"}</Button><Button disabled={!!busy} onClick={() => void perform("login", () => api("/api/topics/browser/open", jsonOptions("POST")), "专用采集窗口正在打开，请本人完成扫码和验证")}>连接抖音采集窗口</Button><Button disabled={!!busy} onClick={() => void perform("metadata-backfill", () => api("/api/topics/metadata-backfill", jsonOptions("POST")), "开始由 Kimi 批量补全作者、粉丝、点赞和评论；进度和错误会显示在同步记录中")}>补全作者与互动</Button></div>
    <p className="topic-boundary">首次使用需要在专用窗口登录。打开窗口不代表连接成功，状态以真实同步结果为准。</p>
  </Card>;

  const xiaohongshuSettingsPanel = <Card className="topic-settings-card"><h3>个人收藏夹与选题 Agent</h3>
    <p className="topic-boundary">热点直接读取平台真实热点或热点灵感，不需要设置个人收藏夹；普通推荐feed不会作为热点入库。</p>
    <Field label="精选收藏夹"><Input value={settings.xhs_featured_collection} onChange={event => updateSetting("xhs_featured_collection", event.target.value)} /></Field>
    <Field label="竞对收藏夹"><Input value={settings.xhs_competitor_collection} onChange={event => updateSetting("xhs_competitor_collection", event.target.value)} /></Field>
    <Field label="高赞收藏夹"><Input value={settings.xhs_high_praise_collection} onChange={event => updateSetting("xhs_high_praise_collection", event.target.value)} /></Field>
    <Field label="小红书选题 Agent 提示词"><Textarea rows={5} value={settings.xiaohongshu_prompt} onChange={event => updateSetting("xiaohongshu_prompt", event.target.value)} /></Field>
    <Field label="每日时间（本地时间）"><Input type="time" value={settings.daily_time} onChange={event => updateSetting("daily_time", event.target.value)} /></Field>
    <label className="settings-switch"><input type="checkbox" checked={settings.daily_enabled} onChange={event => updateSetting("daily_enabled", event.target.checked)} />启用每日任务</label>
    <div className="topic-settings-actions"><Button variant="primary" disabled={!!busy} onClick={saveSettings}>{busy === "settings" ? "正在保存…" : "保存收藏夹与推荐规则"}</Button><Button disabled={!!busy} onClick={() => void perform("xhs-login", () => api("/api/topics/xiaohongshu/browser/open", jsonOptions("POST")), "登录任务已提交；请在同步记录中查看窗口和真实登录结果，不要重复点击")}>连接个人小红书</Button></div>
    <p className="topic-boundary">登录由 Kimi CLI 操作同一固定 Chrome；先读平台热点，再读取三类个人收藏并补全详情，不批量下载媒体。</p>
  </Card>;

  return <>
    <PageHeader eyebrow={copy.eyebrow} title={showArchived ? "已归档选题" : copy.title} description={copy.description} actions={<>{topicSource !== "wechat" && <><Button onClick={() => setShowArchived(value => !value)}><Archive size={15} />{showArchived ? "返回当前选题" : `已归档 ${data.archived_count || 0}`}</Button><Button onClick={() => setSettingsOpen(true)}>采集与自动化</Button><Button variant="primary" disabled={!!busy || hasActiveJobs} onClick={() => void perform("sync", () => api(topicSource === "xiaohongshu" ? "/api/topics/xiaohongshu/sync" : topicSource === "industry" ? "/api/topics/industry" : "/api/topics/sync", jsonOptions("POST")), "采集已开始；运行中的同类同步会复用")}>{hasActiveJobs ? "同步中…" : "同步内容"}</Button></>}{topicSource === "wechat" ? <><a className="button button-small" href={`${location.pathname.startsWith('/demo') ? '/demo' : ''}/setup#wechat-connect`}>微信连接 · {wechatStatus === "connected" ? "已连接" : !wechatStatus ? "检测中" : ["wait", "scaned", "scanned"].includes(wechatStatus) ? "等待扫码" : "待连接"}</a><Button size="small" onClick={() => setWechatManualOpen(true)}>手动记录</Button></> : <Button onClick={() => setManualOpen(true)}>直接创建视频任务</Button>}</>} />
    {topicSource === "douyin" && <nav className="topic-subtabs" aria-label="抖音选题分类">{douyinViews.map(view => <button type="button" className={`topic-filter ${douyinView === view.id ? "active" : ""}`} aria-pressed={douyinView === view.id} key={view.id} onClick={() => setDouyinView(view.id)}>{view.label}{view.id === "hot" ? ` · 实际 ${data.hot_count || 0}/20` : ""}</button>)}</nav>}
    {topicSource === "xiaohongshu" && <nav className="topic-subtabs" aria-label="小红书选题分类">{xiaohongshuViews.map(view => <button type="button" className={`topic-filter ${xiaohongshuView === view.id ? "active" : ""}`} aria-pressed={xiaohongshuView === view.id} key={view.id} onClick={() => setXiaohongshuView(view.id)}>{view.label}{` · ${data.sources?.[`xhs_${view.id}`]?.length || 0}`}</button>)}</nav>}
    {loadError && <ErrorBox>{loadError}<br /><Button size="small" onClick={() => void refresh()}>重新读取</Button></ErrorBox>}
    {actionError && <ErrorBox>{actionError}<br /><Button size="small" onClick={() => setActionError("")}>关闭错误详情</Button></ErrorBox>}
    {topicSource !== "wechat" && <div className="topic-sync-toolbar"><span>{topicSource === "douyin" ? syncSummary(data.last_sync || null) : topicSource === "xiaohongshu" ? xhsSyncSummary(data.xhs_last_sync || null) : "保留真实资讯来源与采集时间"}</span><Button size="small" variant="ghost" onClick={() => setRecordsOpen(true)}>同步记录</Button></div>}
    <Modal side open={settingsOpen} onOpenChange={setSettingsOpen} title="采集与自动化" description="来源、收藏夹与每日任务沿用现有配置。">{topicSource === "xiaohongshu" ? xiaohongshuSettingsPanel : settingsPanel}</Modal>
    <Modal side open={recordsOpen} onOpenChange={setRecordsOpen} title="同步记录" description="保留执行结果与错误详情，不占用内容列表。">{jobs.length ? <JobList jobs={jobs} all /> : <Empty title="暂无同步记录" />}{jobs.some(job => ["failed", "blocked"].includes(job.status)) && <Button disabled={!!busy || hasActiveJobs} onClick={() => void perform("retry-sync", () => api(topicSource === "xiaohongshu" ? "/api/topics/xiaohongshu/sync" : topicSource === "industry" ? "/api/topics/industry" : "/api/topics/sync", jsonOptions("POST")), "已重新同步")}>重试同步</Button>}</Modal>

    {["industry", "douyin", "xiaohongshu"].includes(topicSource) && <div className="topic-content-only"><div>
      <div className="section-heading"><h2>{topicSource === "industry" ? "行业资讯快照" : topicSource === "xiaohongshu" ? xiaohongshuViews.find(view => view.id === xiaohongshuView)?.label : douyinViews.find(view => view.id === douyinView)?.label}</h2><p>{sourceItems.length} 条 · 保留采集时间和原链接</p></div>
      {sourceItems.length ? <div className={(topicSource === "douyin" && douyinView === "hot") || (topicSource === "xiaohongshu" && xiaohongshuView === "hot") ? "topic-hot-list" : topicSource === "xiaohongshu" || (topicSource === "douyin" && ["featured", "competitor"].includes(douyinView)) ? "topic-grid topic-video-grid-compact" : "topic-grid"}>{visibleSourceItems.slice(0, topicSource === "industry" ? 20 : undefined).map(item => <TopicCard key={item.id} item={item} onRetryCover={item => void perform(`cover-${item.id}`, () => api(`/api/topics/items/${encodeURIComponent(item.id)}/cover/retry`, jsonOptions("POST")), "正在重新获取封面；不重复创建选题")} busy={!!busy} allowAnalyze={["douyin", "xiaohongshu"].includes(topicSource)} onCreate={item => void createResearchTask(item)} onAnalyze={item => item.platform === "xiaohongshu" ? void probeDownload(item) : void perform(`analyze-${item.id}`, () => api(`/api/topics/items/${encodeURIComponent(item.id)}/analyze`, jsonOptions("POST")), "已选择该视频，由 Kimi CLI 下载真实文件；完成后显示本地地址，不执行拆解")} onDetail={item => void showDetail(item)} onArchive={archiveItem} archived={showArchived} />)}</div> : <Empty title={showArchived ? "没有已归档选题" : topicSource === "xiaohongshu" ? "当前收藏夹还没有作品快照" : "当前来源还没有作品快照"} description={topicSource === "industry" ? "点击“同步行业热点”读取公开资讯。" : topicSource === "xiaohongshu" ? "核对右侧收藏夹名称并同步个人小红书；未登录或页面结构变化会显示具体错误。" : "检查收藏夹名称并同步；不会用收藏数量冒充已抓取作品。"} />}
    </div></div>}

    {topicSource === "wechat" && <WechatInbox manualOpen={wechatManualOpen} onManualOpenChange={setWechatManualOpen} messages={data.wechat_messages || []} connection={data.wechat_connection} onCreateTask={researchItemId => {
      const item = (data.sources?.wechat_inbox || []).find((candidate: TopicItem) => candidate.id === researchItemId);
      if (item) void createResearchTask(item);
      else setActionError("找不到这条消息对应的研究条目，请刷新后重试");
    }} />}

    <Modal open={manualOpen} onOpenChange={setManualOpen} title="直接创建视频任务" description="输入选题与切入方向，创建视频任务后进入文案编辑。收藏选题与文章创作仍从对应内容入口开始。"><form onSubmit={submitManual}><div className="topic-manual-grid"><div className="topic-span-2"><Field label="选题标题"><Input required maxLength={200} value={manual.title} onChange={event => setManual({ ...manual, title: event.target.value })} placeholder="这条内容要解决什么真实问题？" /></Field></div><Field label="内容支柱"><select value={manual.pillar} onChange={event => setManual({ ...manual, pillar: event.target.value })}>{Object.entries(pillarNames).map(([key, name]) => <option key={key} value={key}>{name}</option>)}</select></Field><Field label="主要人群"><select value={manual.audience} onChange={event => setManual({ ...manual, audience: event.target.value })}>{Object.entries(audienceNames).map(([key, name]) => <option key={key} value={key}>{name}</option>)}</select></Field><Field label="核心痛点（可选）"><Input value={manual.pain_point} onChange={event => setManual({ ...manual, pain_point: event.target.value })} /></Field><Field label="来源收藏夹（可选）"><select value={manual.favorite_collection} onChange={event => setManual({ ...manual, favorite_collection: event.target.value })}><option value="">不使用收藏夹分类</option>{favorites.map(item => <option key={item.name} value={item.name}>{item.name} · {item.role}</option>)}</select></Field><div className="topic-span-2"><Field label="内容切入（可选）"><Textarea value={manual.angle} onChange={event => setManual({ ...manual, angle: event.target.value })} placeholder="用什么真实场景、证据或步骤来讲" /></Field></div></div><Button type="submit" variant="primary" disabled={!!busy}>{busy === "manual" ? "正在创建…" : "创建任务并进入脚本"}</Button></form></Modal>

    {downloadTarget && <DownloadProbeModal item={downloadTarget} jobs={jobs} busy={!!busy} onChoose={mode => void downloadMedia(downloadTarget, mode)} onClose={() => setDownloadTarget(null)} />}

    <Modal open={!!detail} onOpenChange={open => { if (!open) setDetail(null); }} title={detail?.title || "下载详情"} description="Kimi CLI 下载真实视频或图文素材，并显示本地地址；不执行拆解。" wide>{detailLoading ? <div className="topic-detail-loading"><Busy label="正在读取真实下载详情…" /></div> : detail && <><div className="topic-detail-meta">{/^https?:\/\//.test(detail.url) && !String(detail.url).startsWith("https://wechat.local/") ? <a className="button button-small" href={detail.url} target="_blank" rel="noreferrer">打开原链接 <ExternalLink size={13} /></a> : <Badge>纯文本消息</Badge>}<Button size="small" onClick={() => void refreshDetail()}>刷新详情</Button><Button size="small" className="topic-json-download" onClick={downloadDetail}><Download size={13} />导出下载信息</Button></div><DownloadDetail detail={detail} onReveal={() => void revealDownload()} onCopy={() => void copyDownloadPath()} /></>}</Modal>
  </>;
}
