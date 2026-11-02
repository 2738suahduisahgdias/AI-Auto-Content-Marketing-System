import {useContentDraft} from "@/lib/contentDraft";
import ArticleCreativePlan, {normalizeCreativePlan, type CreativePlan} from "@/components/ArticleCreativePlan";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Check, Download, FilePlus2, Plus, Sparkles } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useApp } from "@/AppContext";
import { Badge, Button, Card, Empty, ErrorBox, Field, Modal, PageHeader, Progress, Textarea } from "@/components/ui";
import { api, jsonOptions } from "@/lib/api";
import { articleStateNames, jobStatusNames } from "@/lib/names";
import type { Article, Job, Json } from "@/lib/types";
import "./Articles.css";

const jobNames: Record<string, string> = { "article.outline": "文案 Agent 生成大纲", "article.draft": "文案 Agent 生成正文", "article.export": "导出文章" };
const activeJobs = new Set(["queued", "leased", "running", "retry_wait"]);

function activeRevision(item: Article | undefined, kind: string): Json | undefined {
  const id = item?.active_revisions[kind];
  return item?.revisions.find(revision => revision.id === id);
}

function ArticleJob({ job }: { job: Job }) {
  const error = job.error && Object.keys(job.error).length ? job.error : null;
  return <article className="article-job">
    <div className="article-job-top"><div><strong>{jobNames[job.kind] || job.kind}</strong><small>{job.stage || job.status} · {job.created_at}</small></div><Badge tone={job.status === "succeeded" ? "green" : error ? "red" : "orange"}>{jobStatusNames[job.status] || job.status}</Badge></div>
    {typeof job.progress === "number" && activeJobs.has(job.status) && <Progress value={job.progress} />}
    {error && <p className="article-job-error">{String(error.message || error.code || "任务失败")}{error.action ? `\n怎么改：${String(error.action)}` : ""}</p>}
  </article>;
}

export default function Articles() {
  const { resources, refresh, run, notify } = useApp();
  const { id } = useParams();
  const navigate = useNavigate();
  const items = useMemo(() => resources?.articles.items || [], [resources?.articles.items]);
  const selected = items.find(item => item.id === id);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [switchOpen, setSwitchOpen] = useState(false);
  const [page, setPage] = useState(1);
  const filtered = items.filter(item => String(item.campaign.title).toLowerCase().includes(search.toLowerCase()) && (status === "all" || (status === "draft" ? ["brief_ready","outline_draft","draft","needs_review"].includes(item.state) : status === "delivered" ? ["exported","published"].includes(item.state) : item.state === status))).sort((a,b)=>String((b as any).updated_at || '').localeCompare(String((a as any).updated_at || '')));
  const pageCount = Math.max(1, Math.ceil(filtered.length / 10));
  const currentPage = Math.min(page,pageCount);
  const pageItems = filtered.slice((currentPage-1)*10,currentPage*10);
  const outline = activeRevision(selected, "outline");
  const draft = activeRevision(selected, "draft");
  const exported = activeRevision(selected, "export");
  const revisionKey = `${selected?.id || "none"}:${outline?.id || "none"}:${draft?.id || "none"}`;
  const [brief, setBrief,briefSaveError] = useContentDraft(selected ? `article:${selected.id}:brief` : "", String(selected?.campaign.brief?.text || ""));
  const [outlineText, setOutlineText,outlineSaveError] = useContentDraft(selected ? `article:${revisionKey}:outline` : "", String(outline?.payload.text || ""));
  const [draftText, setDraftText,draftSaveError] = useContentDraft(selected ? `article:${revisionKey}:draft` : "", String(draft?.payload.text || ""));
  const [creativePlan,setCreativePlan,planSaveError]=useContentDraft<CreativePlan>(selected ? `article:${revisionKey}:plan` : "", normalizeCreativePlan(draft?.payload.creative_plan || outline?.payload.creative_plan));
  const [busy, setBusy] = useState("");
  const [workspace, setWorkspace] = useState<"write" | "images" | "delivery">("write");
  const [createOpen, setCreateOpen] = useState(false);
  const [newTitle, setNewTitle] = useContentDraft("article:new:title", "");
  const [newBrief, setNewBrief] = useContentDraft("article:new:brief", "");

  const jobs = useMemo(() => (resources?.articles.jobs || []).filter(job => (job as Job & { aggregate_id?: string }).aggregate_id === selected?.id).slice(0, 5), [resources?.articles.jobs, selected?.id]);
  const hasActiveJob = jobs.some(job => activeJobs.has(job.status));
  useEffect(() => {
    if (!hasActiveJob) return;
    const timer = window.setInterval(() => void refresh(), 3000);
    return () => window.clearInterval(timer);
  }, [hasActiveJob, refresh]);

  const execute = async (key: string, action: () => Promise<unknown>, success: string) => {
    if (busy || !selected) return null;
    setBusy(key);
    try { return await run(action, success); }
    finally { setBusy(""); }
  };

  const createArticle = async (event: FormEvent) => {
    event.preventDefault();
    const title = newTitle.trim();
    if (!title) { notify("请填写文章主题", true); return; }
    setBusy("create");
    const created = await run<Article>(() => api("/api/articles", jsonOptions("POST", { title, brief: { text: newBrief.trim() } })), "文章任务已创建");
    setBusy("");
    if (created) {
      setCreateOpen(false);
      setNewTitle("");
      setNewBrief("");
      navigate(`/articles/${created.id}`);
    }
  };

  const saveRevision = (kind: "outline" | "draft") => execute(`save:${kind}`, () => api(`/api/articles/${selected?.id}/revisions`, jsonOptions("POST", {
    kind,
    payload: { text: kind === "outline" ? outlineText : draftText, format: "markdown", creative_plan:creativePlan },
    expected_version: selected?.version,
  })), `${kind === "outline" ? "大纲" : "正文"}已保存为新版本；下游审批会按版本失效`);

  const generate = (operation: "article.outline" | "article.draft") => execute(operation, () => api(`/api/articles/${selected?.id}/generate`, jsonOptions("POST", {
    operation,
    prompt: brief,
    creative_plan: creativePlan,
    expected_version: selected?.version,
  })), "文章Agent已加入后台；生成期间可离开，完成后会出现新版本");

  const decide = (decision: "approve" | "reject") => {
    if (decision === "reject" && !window.confirm("确定退回当前正文吗？这会记录人工审批决定，正文仍保留为草稿。")) return;
    void execute(decision, () => api(`/api/articles/${selected?.id}/actions`, jsonOptions("POST", {
      action: decision,
      revision_id: draft?.id,
      manifest_hash: selected?.manifest.hash,
    })), decision === "approve" ? "当前正文已人工批准，可导出或创建文章发布批次" : "正文已退回修改");
  };

  const currentStep = exported ? 5 : selected?.state === "approved" ? 5 : draft ? 4 : outline ? 3 : 2;
  const exportPayload = exported?.payload || {};
  const canEdit = Boolean(selected) && !hasActiveJob;
  const dirty = Boolean(selected) && (JSON.stringify(creativePlan)!==JSON.stringify(normalizeCreativePlan(draft?.payload.creative_plan || outline?.payload.creative_plan)) || outlineText !== String(outline?.payload.text || '') || draftText !== String(draft?.payload.text || '') || brief !== String(selected?.campaign.brief?.text || ''));
  const leave = (path:string) => { if((briefSaveError||outlineSaveError||draftSaveError||planSaveError) && !window.confirm("自动保存失败，离开可能丢失内容。是否仍然离开？")) return; setSwitchOpen(false); navigate(path); };
  useEffect(()=>{
    if(!(briefSaveError||outlineSaveError||draftSaveError||planSaveError))return;
    const unload=(event:BeforeUnloadEvent)=>{event.preventDefault();event.returnValue='';};
    const click=(event:MouseEvent)=>{const link=(event.target as Element)?.closest('a'); if(!link || event.defaultPrevented || link.target==='_blank' || link.hasAttribute('download'))return; const url=new URL(link.href,location.href); if(url.origin===location.origin && url.pathname!==location.pathname && !window.confirm('自动保存失败，离开可能丢失内容。请先复制当前内容，或取消离开并保存正式版本。是否仍然离开？')){event.preventDefault();event.stopPropagation();}};
    window.addEventListener('beforeunload',unload);document.addEventListener('click',click,true);
    return()=>{window.removeEventListener('beforeunload',unload);document.removeEventListener('click',click,true);};
  },[briefSaveError,outlineSaveError,draftSaveError,planSaveError]);
  const articleList = <><div className="article-search-tools"><input className="input" aria-label="搜索文章" placeholder="搜索文章标题" value={search} onChange={e=>{setSearch(e.target.value);setPage(1)}}/><select aria-label="文章状态" value={status} onChange={e=>{setStatus(e.target.value);setPage(1)}}><option value="all">全部状态</option><option value="draft">草稿</option><option value="in_review">待审核</option><option value="approved">已批准</option><option value="delivered">已交付</option></select></div>{pageItems.map(item=><button className="article-picker-row" key={item.id} onClick={()=>leave('/articles/'+item.id)}><span><strong>{String(item.campaign.title)}</strong><small>{(item as any).updated_at ? '更新于 '+new Date((item as any).updated_at).toLocaleString() : '暂无更新时间'} · {(item as any).platform === 'xiaohongshu' ? '小红书' : (item as any).platform === 'wechat_official_account' ? '公众号' : '平台未标注'} · {/选题ID[:：]/.test(String(item.campaign.brief?.text || '')) ? '来源：关联选题（详见写作要求）' : '来源：未记录'}</small></span><Badge>{articleStateNames[item.state] || item.state}</Badge><span>打开 →</span></button>)}{!filtered.length&&<Empty title={items.length?'没有符合条件的文章':'还没有文章'} description="可以调整搜索与筛选，或新建文章。"/>}{pageCount > 1 && <nav className="article-pagination" aria-label="文章分页"><Button disabled={currentPage===1} onClick={()=>setPage(currentPage-1)}>上一页</Button><span>{currentPage} / {pageCount} 页</span><Button disabled={currentPage===pageCount} onClick={()=>setPage(currentPage+1)}>下一页</Button></nav>}</>;


  return <div className="articles-page">
    <PageHeader eyebrow="EDITORIAL WORKFLOW" title="文章任务" description="从已选主题开始，或自由写作。文案 Agent 协助写稿、规划配图，再按公众号或小红书整理交付。" actions={<><Button variant="primary" onClick={() => setCreateOpen(true)} disabled={Boolean(busy)}><Plus size={16} />新建文章</Button></>} />
    {id && <div className="article-editor-navigation"><Button onClick={()=>leave("/articles")}>← 返回文章列表</Button><Button onClick={()=>{setSearch("");setStatus("all");setPage(1);setSwitchOpen(true)}}>{selected?.campaign.title || "选择文章"} ▾</Button>{<span role="status">{briefSaveError||outlineSaveError||draftSaveError||planSaveError||(dirty ? "已自动保存本机草稿 · 待保存正式版本" : "已载入保存内容 · 编辑自动保存")}</span>}</div>}
    {id && <nav className="article-work-tabs" aria-label="图文工作区">{([['write','写文案'],['images','配图片'],['delivery','排版交付']] as const).map(([key,label])=><button key={key} aria-pressed={workspace===key} onClick={()=>setWorkspace(key)}>{label}</button>)}</nav>}
    {!id && <Card className="article-library"><div className="article-sidebar-head"><h2>全部文章</h2><span>{filtered.length} 篇 · 按最近更新排序</span></div>{articleList}</Card>}
    {id && <div className="article-workspace article-editor-full">
      <main className="article-main">
        {!selected ? <Empty title={id ? "没有找到这篇文章" : "开始第一条独立文章任务"} description={id ? "它可能已被移除，或链接不完整。请返回文章列表选择已有文章。" : "创建后，大纲和正文都会保存为可追溯版本。"} action={<Button variant="primary" onClick={() => setCreateOpen(true)}><FilePlus2 size={15} />新建文章</Button>} /> : <>
          <div className="article-title-block"><div><p className="eyebrow">文案项目</p><h2>{String(selected.campaign.title)}</h2><details><summary>版本与文章信息</summary><p>文章 ID：{selected.id} · 当前版本 v{selected.version}</p></details></div><Badge tone={["approved", "exported", "published"].includes(selected.state) ? "green" : selected.state === "in_review" ? "orange" : "neutral"}>{articleStateNames[selected.state] || selected.state}</Badge></div>
          <ArticleCreativePlan draftScope={selected.id} key={selected.id} stage={workspace} plan={creativePlan} onChange={setCreativePlan} onSave={()=>void saveRevision("draft")} disabled={Boolean(busy) || hasActiveJob} onApply={text=>setBrief(previous=>previous+"\n\n"+text)} />
          <div hidden={workspace!=="write"}><div className="article-entry-row"><Link className="button" to="/topics/douyin">从选题中心选择主题</Link><Button onClick={()=>setCreateOpen(true)}>自由写作 / 粘贴已有稿</Button><p>已有文案直接编辑并保存；大纲仅为 AI 写作辅助，不是手写稿的必经步骤。</p></div><div className="article-steps" aria-label="文章生产步骤">{["真实需求", "论证大纲", "完整正文", "人工终审", "交付文档"].map((name, index) => <span key={name} aria-current={index + 1 === currentStep ? "step" : undefined} className={`article-step${index + 1 < currentStep ? " done" : index + 1 === currentStep ? " current" : ""}`}>{index + 1} {name}</span>)}</div>
          {hasActiveJob && <div className="article-review-note">后台任务正在运行。当前编辑内容会保留；生成完成后仅在新版本出现时更新编辑器。</div>}
          <Card className="article-card">
            <div className="article-card-head"><div><h3>文章要求</h3><p>生成时作为本次输入，不覆盖其他 Agent，也不会自动保存为正文。</p></div></div>
            <Field label="补充要求" hint="建议写明目标读者、真实场景、可核实证据，以及不能出现的承诺。"><Textarea value={brief} onChange={event => setBrief(event.target.value)} placeholder="例如：面向正在评估 AI 的企业主，使用真实部门任务，不承诺降本比例。" /></Field>
          </Card>
          <Card className="article-card">
            <div className="article-card-head"><div><h3>一、论证大纲</h3><p>结论、场景、方法、边界和行动清单，避免堆砌工具名。</p></div><Button size="small" disabled={Boolean(busy) || hasActiveJob} title={hasActiveJob ? "已有文章后台任务运行中" : undefined} onClick={() => void generate("article.outline")}><Sparkles size={14} />{busy === "article.outline" ? "正在提交…" : "文案 Agent 生成大纲"}</Button></div>
            <p className="article-version-note">{outline ? `已保存大纲` : "尚无大纲，可生成或手动撰写。"}</p>
            <Textarea className="article-outline-editor" value={outlineText} onChange={event => setOutlineText(event.target.value)} disabled={!canEdit} placeholder="先形成大纲，或手动粘贴 Markdown 大纲" />
            <div className="button-row"><Button size="small" disabled={Boolean(busy) || !canEdit} onClick={() => void saveRevision("outline")}>确认大纲，用于生成正文</Button></div>
          </Card>
          <Card className="article-card">
            <div className="article-card-head"><div><h3>二、完整正文</h3><p>生成后必须人工核查事实、案例、数字、来源和过度承诺。</p></div><Button size="small" disabled={Boolean(busy) || !outline || hasActiveJob} title={!outline ? "先保存或生成大纲" : hasActiveJob ? "已有文章后台任务运行中" : undefined} onClick={() => void generate("article.draft")}><Sparkles size={14} />{busy === "article.draft" ? "正在提交…" : "文案 Agent 生成正文"}</Button></div>
            <p className="article-version-note">{draft ? `已保存正文` : "尚无正文；生成或编辑后保存为新版本。"}</p>
            <Textarea className="article-draft-editor" value={draftText} onChange={event => setDraftText(event.target.value)} disabled={!canEdit} placeholder="可以直接手写或粘贴已有文案并保存；使用 AI 生成时先准备大纲" />
            <div className="button-row">
              {draft && !["approved", "exported", "published", "in_review"].includes(selected.state) && <Button size="small" disabled={Boolean(busy)} onClick={() => void execute("review", () => api(`/api/articles/${selected.id}/actions`, jsonOptions("POST", { action: "submit_review", expected_version: selected.version })), "已提交人工审核")}>提交人工审核</Button>}
              {draft && ["draft", "in_review"].includes(selected.state) && <Button size="small" variant="primary" disabled={Boolean(busy)} onClick={() => decide("approve")}><Check size={14} />我已核查并批准当前正文</Button>}
              {draft && selected.state === "in_review" && <Button size="small" variant="danger" disabled={Boolean(busy)} onClick={() => decide("reject")}>退回修改</Button>}
              {draft && ["approved", "exported"].includes(selected.state) && <Button size="small" variant="primary" disabled={Boolean(busy) || hasActiveJob} onClick={() => void execute("export", () => api(`/api/articles/${selected.id}/export`, jsonOptions("POST", { revision_id: draft.id, expected_version: selected.version })), "文章导出已加入后台；完成后可下载真实文件")}><Download size={14} />导出当前正文</Button>}
            </div>
          </Card>
          </div>
          {!!jobs.length && <div className="article-jobs">{jobs.map(job => <ArticleJob job={job} key={job.id} />)}</div>}
          {workspace === "delivery" && <div className="button-row article-next-production"><span>继续制作</span><Button disabled={!selected||!draft||Boolean(busy)||draftText!==String(draft?.payload.text||'')} onClick={()=>{if(!selected||!draft)return;void run<any>(()=>api('/api/tasks',jsonOptions('POST',{title:selected.campaign.title,article_id:selected.id,article_revision_id:draft.id,source_type:'article',pillar:'enterprise_ai',audience:'business_owners'})),'已从保存的文章版本创建视频任务').then(task=>{if(task)void refresh().then(()=>navigate('/tasks/'+task.content_id))})}}>从已保存正文制作视频</Button></div>}
          {workspace === "delivery" && !["approved", "exported", "published"].includes(selected.state) && <p className="article-review-note">当前正文尚未批准。请在“写文案”中保存并审核正文，再导出或交给发布 Agent。</p>}
          {workspace === "delivery" && ["approved", "exported", "published"].includes(selected.state) && <Card className="article-card article-delivery">
            <div className="article-card-head"><div><h3>交付文档</h3><p>这里只提供实际生成的文档；平台预览与公开发布统一在发布中心完成。</p></div><Link className="button button-small" to={`/publish?kind=article&id=${encodeURIComponent(selected.id)}`}>前往发布中心</Link></div>
            {exported && Array.isArray(exportPayload.page_asset_ids) && <div className="article-page-previews">{exportPayload.page_asset_ids.map((assetId:string,index:number)=><a key={assetId} href={`/api/v2/assets/${assetId}/content`} target="_blank" rel="noreferrer"><img src={`/api/v2/assets/${assetId}/content`} alt={`长图第 ${index+1} 页预览`} loading="lazy"/><span>第 {index+1} 页</span></a>)}</div>}{exported ? <div className="article-export"><div><strong>Markdown + 安全 HTML</strong><p>已生成，可预览或下载</p></div><div className="button-row">{Array.isArray(exportPayload.page_asset_ids) && exportPayload.page_asset_ids.map((assetId:string,index:number)=><a className="button button-small" key={assetId} href={`/api/v2/assets/${assetId}/content?download=1`}>第 {index+1} 页 PNG</a>)}{exportPayload.package_asset_id && <a className="button button-small" href={`/api/v2/assets/${exportPayload.package_asset_id}/content?download=1`}><Download size={13}/>下载图文包</a>}{exportPayload.markdown_asset_id ? <a className="button button-small" href={`/api/v2/assets/${exportPayload.markdown_asset_id}/content?download=1`}><Download size={13} />下载 Markdown</a> : <span className="muted-text" title="导出修订缺少 Markdown 资产，请重新导出">Markdown 不可用</span>}{exportPayload.html_asset_id ? <a className="button button-small" href={`/api/v2/assets/${exportPayload.html_asset_id}/content?download=1`}><Download size={13} />下载 HTML</a> : <span className="muted-text" title="导出修订缺少 HTML 资产，请重新导出">HTML 不可用</span>}</div></div> : <Empty title="尚未导出交付文档" description="导出当前已批准正文后，这里会显示真实 Markdown 和 HTML 下载文件。" />}
          </Card>}
        </>}
      </main>
    </div>}
    <Modal open={switchOpen} onOpenChange={setSwitchOpen} title="切换文章" description="按最近更新排序，支持搜索和状态筛选。">{articleList}</Modal>
    <Modal open={createOpen} onOpenChange={setCreateOpen} title="新建文章任务" description="只创建本地编辑任务，不会自动生成或公开发布。">
      <form className="article-create-form" onSubmit={createArticle}><Field label="文章主题"><input className="input" autoFocus required maxLength={200} value={newTitle} onChange={event => setNewTitle(event.target.value)} placeholder="要为目标用户解决什么具体问题？" /></Field><Field label="初始写作要求（可选）"><Textarea value={newBrief} onChange={event => setNewBrief(event.target.value)} placeholder="目标读者、真实场景、事实证据、边界与禁止承诺" /></Field><div className="button-row article-create-actions"><Button type="button" onClick={() => setCreateOpen(false)}>取消</Button><Button variant="primary" type="submit" disabled={busy === "create"}><FilePlus2 size={14} />{busy === "create" ? "正在创建…" : "创建本地文章"}</Button></div></form>
    </Modal>
    {!resources && <ErrorBox>文章数据尚未读取。请检查本地服务；页面不会显示伪造草稿。</ErrorBox>}
  </div>;
}
