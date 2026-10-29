import { useEffect, useState, type FormEvent } from "react";
import { Archive, Download, ExternalLink, RefreshCw } from "lucide-react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { useApp } from "@/AppContext";
import { TopicCard } from "@/components/TopicCard";
import { Badge, Busy, Button, Card, Empty, ErrorBox, Field, Input, Modal, PageHeader, Progress, Textarea } from "@/components/ui";
import { api, errorText, jsonOptions } from "@/lib/api";
import { audienceNames, jobStatusNames, pillarNames } from "@/lib/names";
import type { Job, Json, Task, TopicItem } from "@/lib/types";
import "./Topics.css";

type TopicSource = "industry" | "douyin" | "wechat" | "xiaohongshu";
type DouyinView = "hot" | "featured" | "competitor" | "high_praise";
type Settings = { industry_scope: string; industry_prompt: string; douyin_prompt: string; daily_time: string; daily_enabled: boolean; featured_collection: string; competitor_collection: string; high_praise_collection: string };
const emptySettings: Settings = { industry_scope: "", industry_prompt: "", douyin_prompt: "", daily_time: "09:00", daily_enabled: false, featured_collection: "", competitor_collection: "", high_praise_collection: "" };
const sourceCopy: Record<TopicSource, { title: string; eyebrow: string; description: string }> = {
  industry: { title: "行业热点", eyebrow: "INDUSTRY RESEARCH", description: "只分析真实公开资讯，把行业变化转成有证据、可核查的内容方向。" },
  douyin: { title: "抖音选题", eyebrow: "DOUYIN RESEARCH", description: "热榜与收藏夹只是研究快照；选择后才下载，不把热度当作事实。" },
  wechat: { title: "视频号选题", eyebrow: "WECHAT INBOX", description: "用链接、文本和标签保存微信里的灵感，保留原始消息以便回溯。" },
  xiaohongshu: { title: "小红书选题", eyebrow: "XIAOHONGSHU NOTES", description: "读取自己创作者账号的近期笔记元数据，不套用抖音收藏夹模型。" },
};
const douyinViews: { id: DouyinView; label: string }[] = [{ id: "hot", label: "热点选题" }, { id: "featured", label: "精选选题" }, { id: "competitor", label: "竞品选题" }, { id: "high_praise", label: "高赞选题" }];
const jobNames: Record<string, string> = { "topics.sync": "同步抖音快照", "topics.industry": "同步行业热点与推荐", "topics.recommend": "生成选题推荐", "topics.login": "抖音采集窗口登录", "research.analyze": "下载并拆解所选视频", "accounts.sync": "同步小红书与账号", "accounts.login": "平台登录窗口" };
const activeStatuses = ["queued", "leased", "running", "retry_wait"];

function syncSummary(last: Json | null) {
  if (!last) return "尚未运行新采集。旧热榜历史快照不能当作今日 Top 20。";
  let stats: Json = {};
  try { stats = JSON.parse(last.stats_json || "{}"); } catch { stats = {}; }
  const errors = (stats.errors || []).map((item: Json) => item.code === "LOGIN_REQUIRED" ? "收藏需要登录" : item.code).filter(Boolean);
  return `最近快照：${last.status} · ${last.started_at} · 热榜 ${stats.hot ?? 0}/20 · 精选 ${stats.featured ?? 0} · 竞品 ${stats.competitor ?? 0} · 高赞 ${stats.high_praise ?? 0} · 未下载媒体${errors.length ? ` · ${[...new Set<string>(errors)].join("、")}` : ""}`;
}

function JobList({ jobs }: { jobs: Job[] }) {
  if (!jobs.length) return null;
  const active = jobs.filter(job => activeStatuses.includes(job.status));
  const visible = [...active, ...jobs.filter(job => !activeStatuses.includes(job.status)).slice(0, 1)];
  return <div>{visible.map(job => <article className="topic-job" key={job.id}>
    <div className="topic-job-head"><div><strong>{jobNames[job.kind] || job.kind}</strong><small>{job.stage || job.status} · {job.created_at}</small></div><Badge tone={job.status === "succeeded" ? "green" : ["failed", "unknown_remote"].includes(job.status) ? "red" : "orange"}>{jobStatusNames[job.status] || job.status}</Badge></div>
    {activeStatuses.includes(job.status) && <Progress value={job.progress ?? 0} />}
    {job.error && Object.keys(job.error).length > 0 && <p className="topic-job-error">{job.error.message || job.error.code}{job.error.action ? `\n怎么改：${job.error.action}` : ""}</p>}
  </article>)}</div>;
}

function Recommendations({ items, agent }: { items: Json[]; agent: string }) {
  if (!items.length) return <Empty title={`还没有${agent === "industry" ? "行业" : "抖音"}今日推荐`} description="先同步真实快照，再运行对应选题 Agent；不会根据空白数据生成结论。" />;
  return <div className="topic-recommendations">{items.map(item => <Card className="topic-recommendation" key={item.id || item.title}>
    <div className="button-row"><Badge tone="green">{pillarNames[item.pillar] || "企业 AI"}</Badge><Badge>{audienceNames[item.audience] || "企业主"}</Badge></div>
    <h3>{item.title}</h3><p>{item.reason}</p>
    <div className="topic-evidence"><strong>差异化切入</strong><p>{item.angle}</p>{(item.uncertainties || []).map((value: string) => <small key={value}>待核实：{value}</small>)}</div>
    <small className="topic-time">{item.created_at}</small>
  </Card>)}</div>;
}

export default function Topics() {
  const { source = "douyin" } = useParams();
  const navigate = useNavigate();
  const { resources, refresh, notify, loadError } = useApp();
  const [douyinView, setDouyinView] = useState<DouyinView>("hot");
  const [showArchived, setShowArchived] = useState(false);
  const [busy, setBusy] = useState("");
  const [actionError, setActionError] = useState("");
  const [settings, setSettings] = useState<Settings>(() => ({ ...emptySettings, ...resources?.topics?.settings }));
  const [manualOpen, setManualOpen] = useState(false);
  const [manual, setManual] = useState({ title: "", pillar: "enterprise_ai", audience: "business_owners", pain_point: "", angle: "", favorite_collection: "" });
  const [wechat, setWechat] = useState({ url: "", tag: "精选", text: "" });
  const [detail, setDetail] = useState<Json | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const data: Json = resources?.topics || {};
  const jobs: Job[] = data.jobs || [];
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
    anchor.href = url; anchor.download = `${String(detail.title || detail.id).replace(/[\\/:*?"<>|]/g, "-").slice(0, 80)}-拆解详情.json`;
    anchor.click(); URL.revokeObjectURL(url); notify("已导出当前真实拆解详情 JSON");
  }
  async function submitManual(event: FormEvent) {
    event.preventDefault();
    const task = await perform<Task>("manual", () => api("/api/tasks", jsonOptions("POST", manual)), "任务与目录已创建");
    if (task) { setManualOpen(false); setManual(current => ({ ...current, title: "", pain_point: "", angle: "" })); navigate(`/tasks/${task.content_id}`); }
  }
  async function submitWechat(event: FormEvent) {
    event.preventDefault();
    const saved = await perform("wechat", () => api("/api/topics/wechat/messages", jsonOptions("POST", wechat)), "微信选题快照已保存");
    if (saved) setWechat({ url: "", tag: "精选", text: "" });
  }
  function updateSetting<K extends keyof Settings>(key: K, value: Settings[K]) { setSettings(current => ({ ...current, [key]: value })); }
  async function saveSettings() {
    await perform("settings", () => api("/api/topics/settings", jsonOptions("POST", settings)), "行业范围、提示词和每日任务已保存");
  }

  async function archiveItem(item: TopicItem) {
    const archived = !item.archived;
    await perform(`archive-${item.id}`, () => api(`/api/topics/items/${encodeURIComponent(item.id)}/archive`, jsonOptions("POST", { archived })), archived ? "选题已归档，可在已归档中恢复" : "选题已恢复到当前列表");
  }

  const sourceKey = topicSource === "industry" ? "industry" : topicSource === "wechat" ? "wechat_inbox" : topicSource === "xiaohongshu" ? "xhs_notes" : douyinView;
  const sourceItems: TopicItem[] = showArchived ? (data.archived || []).filter((item: TopicItem) => item.source_key === sourceKey) : topicSource === "industry" ? data.sources?.industry || [] : topicSource === "wechat" ? data.sources?.wechat_inbox || [] : topicSource === "xiaohongshu" ? data.sources?.xhs_notes || [] : data.sources?.[douyinView] || [];
  const recommendationAgent = topicSource === "industry" ? "industry" : "douyin";
  const recommendations: Json[] = data.recommendations?.[recommendationAgent] || [];
  const legacyTopics: Json[] = resources?.core.topics || [];
  const favorites: Json[] = resources?.core.favorites?.items?.filter((item: Json) => item.enabled) || [];
  const analysis = detail?.analyses?.[0];
  const report: Json = analysis?.report || {};
  const sourceAsset = detail?.assets?.find((asset: Json) => asset.id === analysis?.source_asset_id) || detail?.assets?.find((asset: Json) => asset.purpose === "source_video");

  const settingsPanel = <Card className="topic-settings-card"><h3>研究范围与每日任务</h3>
    <Field label="行业范围 / 搜索关键词"><Input value={settings.industry_scope} onChange={event => updateSetting("industry_scope", event.target.value)} /></Field>
    <Field label="行业选题 Agent 提示词"><Textarea rows={5} value={settings.industry_prompt} onChange={event => updateSetting("industry_prompt", event.target.value)} /></Field>
    <Field label="抖音选题 Agent 提示词"><Textarea rows={5} value={settings.douyin_prompt} onChange={event => updateSetting("douyin_prompt", event.target.value)} /></Field>
    <Field label="每日时间（本地时间）"><Input type="time" value={settings.daily_time} onChange={event => updateSetting("daily_time", event.target.value)} /></Field>
    <label className="topic-check"><input type="checkbox" checked={settings.daily_enabled} onChange={event => updateSetting("daily_enabled", event.target.checked)} />启用每日任务</label>
    <Field label="精选收藏夹"><Input value={settings.featured_collection} onChange={event => updateSetting("featured_collection", event.target.value)} /></Field>
    <Field label="竞品收藏夹"><Input value={settings.competitor_collection} onChange={event => updateSetting("competitor_collection", event.target.value)} /></Field>
    <Field label="高赞收藏夹"><Input value={settings.high_praise_collection} onChange={event => updateSetting("high_praise_collection", event.target.value)} /></Field>
    <div className="topic-settings-actions"><Button variant="primary" disabled={!!busy} onClick={saveSettings}>{busy === "settings" ? "正在保存…" : "保存设置与每日任务"}</Button><Button disabled={!!busy} onClick={() => void perform("sync", () => api("/api/topics/sync", jsonOptions("POST")), "抖音快照同步已加入后台，此阶段不下载视频")}><RefreshCw size={14} />同步抖音快照</Button><Button disabled={!!busy} onClick={() => void perform("login", () => api("/api/topics/browser/open", jsonOptions("POST")), "专用采集窗口正在打开，请本人完成扫码和验证")}>连接抖音采集窗口</Button></div>
    <p className="topic-boundary">首次使用需要在专用窗口登录。打开窗口不代表连接成功，状态以真实同步结果为准。</p>
  </Card>;

  return <>
    <PageHeader eyebrow={copy.eyebrow} title={showArchived ? "已归档选题" : copy.title} description={copy.description} actions={<><Button onClick={() => setShowArchived(value => !value)}><Archive size={15} />{showArchived ? "返回当前选题" : `已归档 ${data.archived_count || 0}`}</Button><Button onClick={() => setManualOpen(true)}>手动创建选题</Button>{["industry", "douyin"].includes(topicSource) && <Button variant="primary" disabled={!!busy} onClick={() => void perform(`recommend-${recommendationAgent}`, () => api("/api/topics/recommend", jsonOptions("POST", { agent: recommendationAgent })), "选题 Agent 已加入后台，正在分析真实快照")}>生成今日推荐</Button>}</>} />
    {topicSource === "douyin" && <nav className="topic-subtabs" aria-label="抖音选题分类">{douyinViews.map(view => <button type="button" className={`topic-filter ${douyinView === view.id ? "active" : ""}`} aria-pressed={douyinView === view.id} key={view.id} onClick={() => setDouyinView(view.id)}>{view.label}{view.id === "hot" ? ` · 实际 ${data.hot_count || 0}/20` : ""}</button>)}</nav>}
    {loadError && <ErrorBox>{loadError}<br /><Button size="small" onClick={() => void refresh()}>重新读取</Button></ErrorBox>}
    {actionError && <ErrorBox>{actionError}<br /><Button size="small" onClick={() => setActionError("")}>关闭错误详情</Button></ErrorBox>}
    <div className="topic-intro"><div><Badge tone={data.connection?.connection_status === "ready" ? "green" : "orange"}>{topicSource === "douyin" ? `采集状态：${data.connection?.connection_status || "未配置"}` : topicSource === "xiaohongshu" ? "同步后才知道登录状态" : topicSource === "wechat" ? "手动入库可用" : "公开资讯元数据"}</Badge><h2>{topicSource === "wechat" ? "把聊天里的灵感变成可回溯快照" : topicSource === "xiaohongshu" ? "从自己的近期笔记寻找下一步实验" : "先看证据，再决定做什么"}</h2><p>{topicSource === "wechat" ? "OpenClaw 与聊天卡片自动转发尚未接入；当前真实可用的是下方手动入库。" : topicSource === "xiaohongshu" ? "需要登录时会明确报错；不把打开登录窗口写成已连接。" : "推荐、快照和拆解各自保留状态，失败不会用静态内容补齐。"}</p></div>{topicSource === "industry" && <Button disabled={!!busy} onClick={() => void perform("industry", () => api("/api/topics/industry", jsonOptions("POST", { agent: "industry" })), "行业热点与推荐已加入后台")}><RefreshCw size={14} />同步行业热点</Button>}{topicSource === "douyin" && <Button disabled={!!busy} onClick={() => void perform("sync", () => api("/api/topics/sync", jsonOptions("POST")), "抖音快照同步已加入后台，此阶段不下载视频")}><RefreshCw size={14} />同步快照</Button>}</div>
    {topicSource === "douyin" && <div className="topic-sync-summary">{syncSummary(data.last_sync || null)}</div>}
    <JobList jobs={jobs} />

    {["industry", "douyin"].includes(topicSource) && <div className="topic-layout"><div>
      {(topicSource === "industry" || douyinView === "hot") && <><div className="section-heading"><h2>{topicSource === "industry" ? "行业今日推荐" : "抖音今日推荐"}</h2><p>{recommendations.length} 条 · 事实与待核实项分开</p></div><Recommendations items={recommendations} agent={recommendationAgent} /></>}
      <div className="section-heading"><h2>{topicSource === "industry" ? "行业资讯快照" : douyinViews.find(view => view.id === douyinView)?.label}</h2><p>{sourceItems.length} 条 · 保留采集时间和原链接</p></div>
      {sourceItems.length ? <div className="topic-grid">{sourceItems.slice(0, topicSource === "industry" ? 20 : undefined).map(item => <TopicCard key={item.id} item={item} busy={!!busy} allowAnalyze={topicSource === "douyin"} onCreate={item => void createResearchTask(item)} onAnalyze={item => void perform(`analyze-${item.id}`, () => api(`/api/topics/items/${encodeURIComponent(item.id)}/analyze`, jsonOptions("POST")), "已选择该视频，开始按需下载、抽帧和 OCR")} onDetail={item => void showDetail(item)} onArchive={archiveItem} archived={showArchived} />)}</div> : <Empty title={showArchived ? "没有已归档选题" : "当前来源还没有作品快照"} description={topicSource === "industry" ? "点击“同步行业热点”读取公开资讯。" : "检查收藏夹名称并同步；不会用收藏数量冒充已抓取作品。"} />}
    </div><aside className="topic-side">{settingsPanel}</aside></div>}

    {topicSource === "wechat" && <>
      <div className="wechat-columns"><Card><h3>微信 ClawBot 接入边界</h3><ol className="topic-guide"><li>OpenClaw 官方渠道列表目前没有微信，需要另做合规机器人或自定义渠道。</li><li>约定消息格式：<code>视频号链接 + 空格 + #精选</code>，也支持 #竞品、#高赞、#行业。</li><li>机器人应保存原始链接、文本、标签和发送时间，不自动下载或公开转发。</li><li>聊天卡片回调尚未接入，请先用右侧表单保存。</li></ol><div className="button-row"><a className="button button-small" href="https://channels.weixin.qq.com/login.html" target="_blank" rel="noreferrer">打开视频号助手 <ExternalLink size={13} /></a><a className="button button-small" href="https://docs.openclaw.ai/" target="_blank" rel="noreferrer">OpenClaw 官方文档 <ExternalLink size={13} /></a></div></Card>
      <Card><form onSubmit={submitWechat}><h3>保存一条微信消息</h3><p className="topic-boundary">保存研究快照不代表获得转载授权。</p><Field label="视频号 / 公众号链接（可选）"><Input type="url" value={wechat.url} onChange={event => setWechat({ ...wechat, url: event.target.value })} placeholder="https://" /></Field><Field label="标签"><select value={wechat.tag} onChange={event => setWechat({ ...wechat, tag: event.target.value })}>{["精选", "竞品", "高赞", "行业"].map(tag => <option key={tag}>{tag}</option>)}</select></Field><Field label="标题或灵感文本"><Textarea required maxLength={12000} value={wechat.text} onChange={event => setWechat({ ...wechat, text: event.target.value })} placeholder="粘贴标题、口播文字或自己的选题备注" /></Field><Button variant="primary" type="submit" disabled={!!busy}>{busy === "wechat" ? "正在保存…" : "保存到视频号选题"}</Button></form></Card></div>
      <div className="section-heading"><h2>微信选题快照</h2><p>{sourceItems.length} 条 · 先研究，再创作</p></div>
      {sourceItems.length ? <><div className="topic-tag-row">{[...new Set<string>(sourceItems.map(item => item.metadata?.tag).filter(Boolean))].map(tag => <Badge key={tag}>{tag}</Badge>)}</div><div className="topic-grid">{sourceItems.map(item => <TopicCard key={item.id} item={item} busy={!!busy} allowAnalyze={false} onCreate={value => void createResearchTask(value)} onDetail={value => void showDetail(value)} onArchive={archiveItem} archived={showArchived} />)}</div></> : <Empty title="还没有微信消息" description="使用上方表单保存第一条链接或灵感。" />}
    </>}

    {topicSource === "xiaohongshu" && <>
      <Card><div className="topic-intro"><div><h2>连接自己的小红书创作者后台</h2><p>同步同时尝试账号日报所需的小红书笔记和抖音快照。页面结构变化或登录失效会返回具体错误。</p></div><div className="button-row"><Button disabled={!!busy} onClick={() => void perform("xhs-login", () => api("/api/accounts/browser/open", jsonOptions("POST", { platform: "xiaohongshu" })), "小红书专用登录窗口正在打开，请在 5 分钟内完成扫码")}>打开小红书登录窗口</Button><Button variant="primary" disabled={!!busy} onClick={() => void perform("xhs-sync", () => api("/api/accounts/sync", jsonOptions("POST")), "账号同步已加入后台，请在专用窗口处理登录")}><RefreshCw size={14} />同步小红书与账号</Button></div></div></Card>
      <div className="section-heading"><h2>近期笔记快照</h2><p>{sourceItems.length} 条 · 阅读数缺失时保持未读取</p></div>
      {sourceItems.length ? <div className="topic-grid">{sourceItems.map(item => <TopicCard key={item.id} item={item} busy={!!busy} allowAnalyze={false} onCreate={value => void createResearchTask(value)} onDetail={value => void showDetail(value)} onArchive={archiveItem} archived={showArchived} />)}</div> : <Empty title="尚未读取小红书笔记" description="点击“同步小红书与账号”；不会补造指标或显示虚假连接状态。" />}
    </>}

    <div className="section-heading"><h2>保留：账号候选选题</h2><p>{legacyTopics.length} 个历史候选</p></div>
    {legacyTopics.length ? <div className="topic-legacy-list">{legacyTopics.map(topic => <Card className="topic-legacy-item" key={topic.id}><div><div className="button-row"><Badge tone="green">{pillarNames[topic.pillar]}</Badge><Badge>{audienceNames[topic.audience]}</Badge></div><h3>{topic.title}</h3><p><strong>切入：</strong>{topic.script_angle}</p>{(topic.evidence || []).map((evidence: Json, index: number) => <p key={index}>{evidence.content} · 来源：{evidence.source}</p>)}</div><Button size="small" disabled={!!busy} onClick={() => void perform(`legacy-${topic.id}`, () => api<Task>("/api/tasks", jsonOptions("POST", { topic_id: Number(topic.id) })), "已根据候选选题创建任务").then(task => { if (task) navigate(`/tasks/${task.content_id}`); })}>选此题并创建任务</Button></Card>)}</div> : <Empty title="没有历史候选选题" description="可使用研究快照或手动创建真实任务。" />}

    <Modal open={manualOpen} onOpenChange={setManualOpen} title="手动创建选题" description="创建后进入真实视频任务，不会自动发布。"><form onSubmit={submitManual}><div className="topic-manual-grid"><div className="topic-span-2"><Field label="选题标题"><Input required maxLength={200} value={manual.title} onChange={event => setManual({ ...manual, title: event.target.value })} placeholder="这条内容要解决什么真实问题？" /></Field></div><Field label="内容支柱"><select value={manual.pillar} onChange={event => setManual({ ...manual, pillar: event.target.value })}>{Object.entries(pillarNames).map(([key, name]) => <option key={key} value={key}>{name}</option>)}</select></Field><Field label="主要人群"><select value={manual.audience} onChange={event => setManual({ ...manual, audience: event.target.value })}>{Object.entries(audienceNames).map(([key, name]) => <option key={key} value={key}>{name}</option>)}</select></Field><Field label="核心痛点（可选）"><Input value={manual.pain_point} onChange={event => setManual({ ...manual, pain_point: event.target.value })} /></Field><Field label="来源收藏夹（可选）"><select value={manual.favorite_collection} onChange={event => setManual({ ...manual, favorite_collection: event.target.value })}><option value="">不使用收藏夹分类</option>{favorites.map(item => <option key={item.name} value={item.name}>{item.name} · {item.role}</option>)}</select></Field><div className="topic-span-2"><Field label="内容切入（可选）"><Textarea value={manual.angle} onChange={event => setManual({ ...manual, angle: event.target.value })} placeholder="用什么真实场景、证据或步骤来讲" /></Field></div></div><Button type="submit" variant="primary" disabled={!!busy}>{busy === "manual" ? "正在创建…" : "创建任务并进入脚本"}</Button></form></Modal>

    <Modal open={!!detail} onOpenChange={open => { if (!open) setDetail(null); }} title={detail?.title || "研究详情"} description="研究与生产授权分开；OCR 不等同于口播全文。" wide>{detailLoading ? <div className="topic-detail-loading"><Busy label="正在读取真实拆解详情…" /></div> : detail && <><div className="topic-detail-meta">{/^https?:\/\//.test(detail.url) && !String(detail.url).startsWith("https://wechat.local/") ? <a className="button button-small" href={detail.url} target="_blank" rel="noreferrer">打开原链接 <ExternalLink size={13} /></a> : <Badge>纯文本消息</Badge>}<Button size="small" onClick={() => void refreshDetail()}>刷新详情</Button><Button size="small" className="topic-json-download" onClick={downloadDetail}><Download size={13} />下载拆解详情</Button></div>{!analysis ? <Empty title="尚未拆解" description="抖音条目可点击“下载并拆解”后才读取视频和抽帧；同步不会批量下载。" /> : <><div className="topic-detail-report"><strong>{report.ocr_engine || "OCR"}</strong> · {report.frame_count || 0} 帧 · {report.frames_with_text || 0} 帧有文字{report.duration_seconds != null ? ` · 视频 ${report.duration_seconds} 秒` : ""}</div><div className="topic-detail-paths"><strong>保存位置</strong><p>原视频：{sourceAsset?.storage_key || "未记录"}</p><p>帧目录：assets/research/{detail.id}/frames</p></div><div className="topic-frame-list">{(report.timeline || []).map((frame: Json) => <article className="topic-frame" key={frame.asset_id}><a href={`/api/v2/assets/${frame.asset_id}/content`} target="_blank" rel="noreferrer"><img src={`/api/v2/assets/${frame.asset_id}/content`} alt={`视频帧 ${frame.start_ms}`} /></a><div><strong>{(frame.start_ms / 1000).toFixed(1)}s <Badge>置信度 {frame.confidence}</Badge></strong><p>{frame.text || "未识别到清晰文字"}</p></div></article>)}</div><div className="topic-limitations"><strong>拆解边界</strong><ul>{(report.limitations || []).map((value: string) => <li key={value}>{value}</li>)}</ul></div></>}</>}</Modal>
  </>;
}
