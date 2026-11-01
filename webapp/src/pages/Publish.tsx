import { useEffect, useMemo, useState } from "react";
import { FileText, Film, Info, Send } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { useApp } from "@/AppContext";
import { PublishingPanel, type PublishingSource } from "@/components/PublishingPanel";
import { ScheduleSettings } from "@/components/ScheduleSettings";
import { api, jsonOptions } from "@/lib/api";
import { Badge, Button, Card, Field, PageHeader } from "@/components/ui";
import type { Article, ContentKind, Json } from "@/lib/types";
import { publishStatusNames } from "@/lib/names";
import "./Publish.css";

function draftOf(article: Article) {
  const id = article.active_revisions.draft;
  return article.revisions.find(revision => revision.id === id);
}

type QueueSource = PublishingSource & { batch?: any; status?: string; file_id?: number };

export default function Publish() {
  const { resources, run, refresh } = useApp();
  const [searchParams, setSearchParams] = useSearchParams();
  const [reviewed, setReviewed] = useState<any[]>([]);
  const [queue, setQueue] = useState<QueueSource[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");
  const kind: ContentKind = searchParams.get("kind") === "article" ? "article" : "video";

  useEffect(() => {
    api("/api/review/bootstrap").then(data => setReviewed((data.batch?.items || []).filter((item: any) => item.decision === "approved").map((item: any) => ({ ...item, content_id: item.id, title: item.source_path.split("/").pop() })))).catch(() => setReviewed([]));
  }, []);
  const loadQueue = () => api("/api/publishing/queue").then(data => setQueue(data.items || [])).catch(() => setQueue([]));
  useEffect(() => { void loadQueue(); }, []);

  const articles = (resources?.articles.items || []).filter(item => ["approved", "exported"].includes(item.state) && item.active_revisions.draft);
  const videos = kind === "video" ? [...queue, ...reviewed] : [];
  const sources: QueueSource[] = kind === "article" ? articles as any : videos;
  const requestedId = searchParams.get("id") || "";
  const sourceKey = (item: QueueSource) => `${item.id}:${item.fileId || item.file_id || 0}`;
  const selected = sources.find(item => sourceKey(item) === requestedId) || sources[0];
  const selectedId = selected ? sourceKey(selected) : "";
  const filteredSources = sources.filter(item => {
    const matchesFilter = filter === "all" || (filter === "ready" ? item.status === "ready" : filter === "incomplete" ? item.status !== "ready" : true);
    return matchesFilter && `${item.title} ${item.id}`.toLowerCase().includes(query.toLowerCase());
  });

  const source = useMemo<PublishingSource | null>(() => {
    if (!selected) return null;
    if (kind === "article") {
      const article = selected as any as Article;
      return { id: article.id, title: String(article.campaign.title), body: String(draftOf(article)?.payload.text || "") };
    }
    return { id: selected.id, title: selected.title, body: String(selected.body || selected.title), fileId: selected.fileId || selected.file_id, previewUrl: selected.previewUrl, variantId: selected.variantId };
  }, [kind, selected]);

  const chooseKind = (next: ContentKind) => {
    const nextSources = next === "article" ? articles : queue;
    const first = nextSources[0] as any;
    setSearchParams(first ? { kind: next, id: sourceKey(first) } : { kind: next });
  };
  const toggle = (key: string) => setSelectedIds(current => {
    const next = new Set(current);
    if (next.has(key)) next.delete(key); else next.add(key);
    return next;
  });
  const selectedTargets = queue.filter(item => selectedIds.has(sourceKey(item)));
  const prepare = async () => {
    const jobs = selectedTargets.flatMap(item => (item.batch?.targets || []).filter((target: Json) => ["draft", "failed"].includes(target.status)).map((target: Json) => ({ item, target })));
    if (!jobs.length) return;
    for (const { item, target } of jobs) {
      await api(`/api/publishing/batches/${item.batch.id}/prepare`, jsonOptions("POST", { platforms: [target.platform] }));
    }
    await refresh();
    await loadQueue();
  };
  const confirm = async () => {
    const jobs = selectedTargets.flatMap(item => (item.batch?.targets || []).filter((target: Json) => target.status === "ready").map((target: Json) => ({ item, target })));
    if (!jobs.length) return;
    for (const { item, target } of jobs) {
      await api(`/api/publishing/batches/${item.batch.id}/confirm`, jsonOptions("POST", { source_hash: item.batch.source_hash, platforms: [target.platform] }));
    }
    await refresh();
    await loadQueue();
  };

  const handoffs=(resources?.core.tasks||[]).filter((task:any)=>task.source?.yingxu_handoff);
  return <div className="publish-page">
    {handoffs.length>0&&<Card><h2>视频制作交付 · 待审核</h2>{handoffs.map((task:any)=>{const h=task.source.yingxu_handoff;return <div className="migration-toolbar" key={task.content_id}><strong>{task.title}</strong><span>{task.content_id} · 文件 #{h.file_id} · 制作版本 {h.revision} · {h.stale?'制作已修改，需重新交付':'等待审核，尚未发布'}</span><a className="button" href={'/api/files/'+h.file_id+'/media'} target="_blank" rel="noreferrer">查看成片</a><Link className="button" to={'/tasks/'+task.content_id}>返回制作</Link><Link className="button" to="/review">进入原审核中心</Link></div>})}</Card>}

    <PageHeader eyebrow="HUMAN-CONFIRMED DISTRIBUTION" title="发布中心" description="按“内容版本 × 平台”管理发布目标。队列选择、逐平台编辑、预览和公开确认均保留真实证据。" />
    <div className="publish-kind-tabs" role="tablist" aria-label="发布内容类型"><button role="tab" aria-selected={kind === "article"} className={`publish-kind-tab${kind === "article" ? " active" : ""}`} onClick={() => chooseKind("article")}><FileText size={14} /> 文章发布</button><button role="tab" aria-selected={kind === "video"} className={`publish-kind-tab${kind === "video" ? " active" : ""}`} onClick={() => chooseKind("video")}><Film size={14} /> 视频发布</button></div>
    {kind === "video" && <section className="publish-queue-layout">
      <aside className="publish-queue">
        <div className="publish-queue-head"><strong>发布目标队列</strong></div>
        <div className="publish-queue-filters"><Field label="状态"><select value={filter} onChange={event => setFilter(event.target.value)}><option value="all">全部目标</option><option value="ready">仅就绪</option><option value="incomplete">待处理</option></select></Field><Field label="搜索"><input value={query} onChange={event => setQuery(event.target.value)} placeholder="标题或任务 ID" /></Field><Button size="small" onClick={() => setSelectedIds(new Set(filteredSources.map(sourceKey)))}>全选当前筛选</Button></div>
        <div className="publish-queue-list">{filteredSources.map(item => { const key = sourceKey(item); return <article className={`publish-queue-item${selectedId === key ? " active" : ""}`} key={key}><label><input type="checkbox" checked={selectedIds.has(key)} onChange={() => toggle(key)} /><span><strong>{item.title}</strong><small>{item.id} · 文件 {item.fileId || item.file_id}</small></span></label><button type="button" onClick={() => setSearchParams({ kind, id: key })}><Badge tone={item.status === "ready" ? "green" : item.status === "failed" ? "red" : "orange"}>{publishStatusNames[item.status || "draft"] || item.status || "待处理"}</Badge></button></article>; })}</div>
        {selectedTargets.length > 0 && <div className="publish-batch-actions"><strong>已选 {selectedTargets.length} 个内容版本</strong><Button size="small" disabled={!selectedTargets.some(item => item.batch?.targets?.some((target: Json) => ["draft", "failed"].includes(target.status)))} onClick={() => void run(prepare, "选中目标已加入平台预览队列")}><Send size={13} />同步选中预览</Button><Button size="small" variant="primary" disabled={!selectedTargets.some(item => item.batch?.targets?.some((target: Json) => target.status === "ready"))} onClick={() => void run(confirm, "选中就绪目标已确认公开")}>发布选中就绪项</Button></div>}
      </aside>
      <main className="publish-editor">{source ? <PublishingPanel kind={kind} source={source} /> : <Card><p>暂无可发布内容。</p></Card>}</main>
    </section>}
    {kind === "article" && <Card className="publish-source-card"><div><h2>选择已批准的文章正文</h2><p>公众号与小红书长文只读取当前文章的已审批正文。</p></div><Field label="文章来源"><select value={selectedId} disabled={!sources.length} onChange={event => setSearchParams({ kind, id: event.target.value })}>{!sources.length && <option value="">没有符合发布条件的来源</option>}{sources.map(item => <option value={sourceKey(item)} key={sourceKey(item)}>{item.title} · {item.id}</option>)}</select></Field></Card>}
    {kind === "article" && <PublishingPanel kind={kind} source={source} />}
    <div className="publish-boundary"><Info size={16} /><p>本地预览与实际同步使用同一参数。预览就绪、同步中和公开发布是不同状态；只有平台真实链接才能标记已发布。</p></div>
    <ScheduleSettings kind={kind} source={source} />
    <div className="publish-related"><h2>发布记录与复盘</h2><p>文章的其他真实链接可在<Link to={selectedId && kind === "article" ? `/articles/${selected?.id}` : "/articles"}>文章任务</Link>补录；视频的手动发布记录与数据在<Link to={selected ? `/tasks/${selected.id}` : "/tasks"}>视频任务</Link>继续处理。</p></div>
  </div>;
}
