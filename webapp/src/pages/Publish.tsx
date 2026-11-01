import { useEffect, useMemo, useState } from "react";
import { FileText, Film, Info, Send } from "lucide-react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useApp } from "@/AppContext";
import { PublishingPanel, type PublishingSource } from "@/components/PublishingPanel";

import { api, errorText, jsonOptions } from "@/lib/api";
import { Badge, Button, Card, ErrorBox, Field, PageHeader } from "@/components/ui";
import type { Article, ContentKind, Json } from "@/lib/types";
import { publishStatusNames } from "@/lib/names";
import "./Publish.css";

function draftOf(article: Article) {
  const id = article.active_revisions.draft;
  return article.revisions.find(revision => revision.id === id);
}

type QueueSource = PublishingSource & { batch?: any; status?: string; file_id?: number; delivery?: Json };

export default function Publish() {
  const { resources, run, refresh } = useApp();
  const navigate=useNavigate();
  const [receiving,setReceiving]=useState("");
  async function openReview(id:string){setReceiving(id);try{const result=await run<Json>(()=>api(`/api/review/yingxu/${id}`,jsonOptions("POST")), "已定位原审核批次");if(result)navigate(`/review?batch_id=${result.id}`);}finally{setReceiving("");}}
  const [searchParams, setSearchParams] = useSearchParams();
  const [queueError,setQueueError]=useState("");
  const [queue, setQueue] = useState<QueueSource[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");
  const kind: ContentKind = searchParams.get("kind") === "article" ? "article" : "video";

  const loadQueue = () => api("/api/publishing/queue").then(data => {setQueue(data.items || []);setQueueError("");}).catch(error => setQueueError(errorText(error)));
  useEffect(() => { void loadQueue(); }, []);

  const articles = (resources?.articles.items || []).filter(item => ["approved", "exported"].includes(item.state) && item.active_revisions.draft);
  const videos = kind === "video" ? queue : [];
  const sources: QueueSource[] = kind === "article" ? articles as any : videos;
  const requestedId = searchParams.get("id") || "";
  const sourceKey = (item: QueueSource) => `${item.id}:${item.fileId || item.file_id || 0}`;
  const selected = requestedId ? sources.find(item => (sourceKey(item) === requestedId || item.id === requestedId)) : sources[0];
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
    return { id: selected.id, title: selected.title, body: String(selected.body || selected.title), fileId: selected.fileId || selected.file_id, previewUrl: selected.previewUrl || (selected as any).preview_url, variantId: selected.variantId || (selected as any).variant_id };
  }, [kind, selected]);

  const chooseKind = (next: ContentKind) => {
    setSelectedIds(new Set()); setFilter("all"); setQuery("");
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

  const handoffs=(resources?.core.tasks||[]).filter((task:any)=>task.source?.yingxu_handoff);
  return <div className="publish-page">
    <PageHeader eyebrow="PUBLISHING AGENT" title="发布 Agent 工作区" description="接收制作成果与质检结果 → 准备平台字段 → 打开后台预填 → 人工审核后发布。" />
    <div className="publish-agent-flow">{["01 接收交付", "02 质检与人工审批", "03 平台字段与后台预填", "04 人工审核发布"].map((text,index)=><Card key={text}><small>{index===3 ? "你来确认" : "Agent 协作"}</small><h3>{text}</h3><p>{["文章 Agent 与映序视频 Agent 提交独立版本", "沿用技术预审与人工审批；统一品牌规则待接通", "保留原平台字段、登录与预填接口", "检查账号、封面、正文与媒体后明确确认"][index]}</p></Card>)}</div>
    <div className="publish-boundary"><Info size={16}/><p>外部依赖：字段生成需要配置模型；后台预填需要本机浏览器、平台登录和执行器。当前隔离 Demo 已接通小红书后台预填；文章带配图或分页时上传本地图片。公众号待现场验收，公开发布执行器未启用。<Link to="/settings/agents">配置 Agent</Link></p></div>
    {handoffs.length>0&&<Card><h2>视频制作交付</h2>{handoffs.map((task:any)=>{const h=task.source.yingxu_handoff;return <div className="migration-toolbar" key={task.content_id}><strong>{task.title}</strong><span>{task.content_id} · 文件 #{h.file_id} · 制作版本 {h.revision} · {h.stale?'制作已修改，需重新交付':h.status==='approved'?'已审核，待发布':h.status==='rejected'?'已驳回，返回制作修改':'等待审核，尚未发布'}</span><a className="button" href={'/api/files/'+h.file_id+'/media'} target="_blank" rel="noreferrer">查看成片</a><Link className="button" to={'/tasks/'+task.content_id}>返回制作</Link><Button disabled={!!receiving || h.stale} onClick={()=>void openReview(task.content_id)}>{receiving===task.content_id?"正在定位…":"打开对应审核"}</Button>{h.status==='approved'&&!h.stale&&h.review_item_id&&<Button onClick={()=>setSearchParams({kind:"video",id:h.review_item_id})}>准备发布字段</Button>}</div>})}</Card>}


    {(queueError) && <ErrorBox>发布来源读取失败：{queueError}。请刷新重试；不会把连接错误当成空队列。</ErrorBox>}
    {requestedId && !selected && !queueError && <Card><p>该交付尚未通过审核、已失效，或不在当前发布队列中。请返回对应审核重新确认；不会自动替换成另一条内容。</p><Link className="button" to="/review">查看审核</Link></Card>}
    <div className="publish-kind-tabs" role="tablist" aria-label="发布内容类型"><button role="tab" aria-selected={kind === "article"} className={`publish-kind-tab${kind === "article" ? " active" : ""}`} onClick={() => chooseKind("article")}><FileText size={14} /> 文章发布</button><button role="tab" aria-selected={kind === "video"} className={`publish-kind-tab${kind === "video" ? " active" : ""}`} onClick={() => chooseKind("video")}><Film size={14} /> 视频发布</button></div>
    {kind === "video" && <section className="publish-queue-layout">
      <aside className="publish-queue">
        <div className="publish-queue-head"><strong>发布目标队列</strong></div>
        <div className="publish-queue-filters"><Field label="状态"><select value={filter} onChange={event => setFilter(event.target.value)}><option value="all">全部目标</option><option value="ready">仅就绪</option><option value="incomplete">待处理</option></select></Field><Field label="搜索"><input value={query} onChange={event => setQuery(event.target.value)} placeholder="标题或任务 ID" /></Field><Button size="small" onClick={() => setSelectedIds(new Set(filteredSources.map(sourceKey)))}>全选当前筛选</Button></div>
        <div className="publish-queue-list">{filteredSources.map(item => { const key = sourceKey(item); return <article className={`publish-queue-item${selectedId === key ? " active" : ""}`} key={key}><label><input type="checkbox" checked={selectedIds.has(key)} onChange={() => toggle(key)} /><span><strong>{item.title}</strong><small>{item.id} · {item.delivery ? `来自 ${item.delivery.content_id} · 文件 #${item.delivery.file_id}` : `文件 #${item.fileId || item.file_id || "—"}`}</small></span></label><button type="button" onClick={() => setSearchParams({ kind, id: key })}><Badge tone={item.status === "ready" ? "green" : item.status === "failed" ? "red" : "orange"}>{publishStatusNames[item.status || "draft"] || item.status || "待处理"}</Badge></button></article>; })}</div>
        {selectedTargets.length > 0 && <div className="publish-batch-actions"><strong>已选 {selectedTargets.length} 个内容版本</strong><Button size="small" disabled={!selectedTargets.some(item => item.batch?.targets?.some((target: Json) => ["draft", "failed"].includes(target.status)))} onClick={() => void run(prepare, "选中目标已加入平台预览队列")}><Send size={13} />提交选中后台预填</Button></div>}
      </aside>
      <main className="publish-editor">{source ? <PublishingPanel kind={kind} source={source} /> : <Card><p>暂无可发布内容。</p></Card>}</main>
    </section>}
    {kind === "article" && <Card className="publish-source-card"><div><h2>选择已批准的文章正文</h2><p>公众号与小红书长文只读取当前文章的已审批正文。</p></div><Field label="文章来源"><select value={selectedId} disabled={!sources.length} onChange={event => setSearchParams({ kind, id: event.target.value })}>{!sources.length && <option value="">没有符合发布条件的来源</option>}{sources.map(item => <option value={sourceKey(item)} key={sourceKey(item)}>{(item as any).campaign?.title || item.title} · {item.id}</option>)}</select></Field></Card>}
    {kind === "article" && <PublishingPanel kind={kind} source={source} />}
    <div className="publish-boundary"><Info size={16} /><p>本地预览与实际同步使用同一参数。预览就绪、同步中和公开发布是不同状态；只有平台真实链接才能标记已发布。</p></div>

    <div className="publish-related"><h2>发布记录</h2><p>文章的其他真实链接可在<Link to={selectedId && kind === "article" ? `/articles/${selected?.id}` : "/articles"}>文章任务</Link>补录；视频的手动发布记录与数据在<Link to={selected ? `/tasks/${selected.delivery?.content_id || selected.id}` : "/tasks"}>视频任务</Link>继续处理。</p></div>
  </div>;
}
