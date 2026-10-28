import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Check, Download, FilePlus2, FileText, Plus, Send, Sparkles } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useApp } from "@/AppContext";
import { Badge, Button, Card, Empty, ErrorBox, Field, Modal, PageHeader, Progress, Textarea } from "@/components/ui";
import { api, jsonOptions } from "@/lib/api";
import { articleStateNames, jobStatusNames } from "@/lib/names";
import type { Article, Job, Json } from "@/lib/types";
import "./Articles.css";

const jobNames: Record<string, string> = { "article.outline": "文章Agent生成大纲", "article.draft": "文章Agent生成正文", "article.export": "导出文章" };
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
  const selected = items.find(item => item.id === id) || (!id ? items[0] : undefined);
  const [pagination, setPagination] = useState({ key: "", page: 1 });
  const selectionKey = id || "";
  const selectedIndex = Math.max(0, items.findIndex(item => item.id === selected?.id));
  const pageCount = Math.max(1, Math.ceil(items.length / 10));
  const currentPage = Math.min(pagination.key === selectionKey ? pagination.page : Math.floor(selectedIndex / 10) + 1, pageCount);
  const goToPage = (page: number) => setPagination({ key: selectionKey, page });
  const pageItems = items.slice((currentPage - 1) * 10, currentPage * 10);
  const outline = activeRevision(selected, "outline");
  const draft = activeRevision(selected, "draft");
  const exported = activeRevision(selected, "export");
  const revisionKey = `${selected?.id || "none"}:${outline?.id || "none"}:${draft?.id || "none"}`;
  const [loadedRevision, setLoadedRevision] = useState(revisionKey);
  const [brief, setBrief] = useState(String(selected?.campaign.brief?.text || ""));
  const [outlineText, setOutlineText] = useState(String(outline?.payload.text || ""));
  const [draftText, setDraftText] = useState(String(draft?.payload.text || ""));
  const [busy, setBusy] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newBrief, setNewBrief] = useState("");

  if (loadedRevision !== revisionKey) {
    setLoadedRevision(revisionKey);
    setBrief(String(selected?.campaign.brief?.text || ""));
    setOutlineText(String(outline?.payload.text || ""));
    setDraftText(String(draft?.payload.text || ""));
  }

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

  const createSample = async () => {
    setBusy("sample");
    const created = await run<Article>(() => api("/api/articles", jsonOptions("POST", { sample: true })), "写作规范样例已创建；它只是本地草稿，不会公开发布");
    setBusy("");
    if (created) navigate(`/articles/${created.id}`);
  };

  const saveRevision = (kind: "outline" | "draft") => execute(`save:${kind}`, () => api(`/api/articles/${selected?.id}/revisions`, jsonOptions("POST", {
    kind,
    payload: { text: kind === "outline" ? outlineText : draftText, format: "markdown" },
    expected_version: selected?.version,
  })), `${kind === "outline" ? "大纲" : "正文"}已保存为新版本；下游审批会按版本失效`);

  const generate = (operation: "article.outline" | "article.draft") => execute(operation, () => api(`/api/articles/${selected?.id}/generate`, jsonOptions("POST", {
    operation,
    prompt: brief,
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

  return <div className="articles-page">
    <PageHeader eyebrow="EDITORIAL WORKFLOW" title="文章任务" description="真实需求、论证大纲、完整正文与人工审批。文章独立生产，不依赖音频、字幕或视频渲染。" actions={<><Button onClick={() => void createSample()} disabled={Boolean(busy)}><FileText size={15} />创建规范样例</Button><Button variant="primary" onClick={() => setCreateOpen(true)} disabled={Boolean(busy)}><Plus size={16} />新建文章</Button></>} />
    <div className="article-workspace">
      <Card className="article-sidebar">
        <div className="article-sidebar-head"><strong>全部文章</strong><span>{items.length} 篇</span></div>
        {pageItems.map(item => <Link to={`/articles/${item.id}`} key={item.id} className={`article-list-item${item.id === selected?.id ? " active" : ""}`}><strong>{String(item.campaign.title)}</strong><small>{articleStateNames[item.state] || item.state} · v{item.version}<br />{item.id}</small></Link>)}
        {!items.length && <Empty title="还没有文章" description="新建真实主题，或创建本地写作规范样例。" />}
        {items.length > 10 && <nav className="article-pagination" aria-label="文章分页"><Button size="small" disabled={currentPage === 1} onClick={() => goToPage(currentPage - 1)}>上一页</Button><span>{currentPage} / {pageCount} 页</span><Button size="small" disabled={currentPage === pageCount} onClick={() => goToPage(currentPage + 1)}>下一页</Button></nav>}
      </Card>
      <main className="article-main">
        {!selected ? <Empty title={id ? "没有找到这篇文章" : "开始第一条独立文章任务"} description={id ? "它可能已被移除，或链接不完整。请从左侧选择真实文章。" : "创建后，大纲和正文都会保存为可追溯版本。"} action={<Button variant="primary" onClick={() => setCreateOpen(true)}><FilePlus2 size={15} />新建文章</Button>} /> : <>
          <div className="article-title-block"><div><p className="eyebrow">公众号文章 · {selected.id}</p><h2>{String(selected.campaign.title)}</h2><p>当前版本 v{selected.version} · 每次保存生成新版本</p></div><Badge tone={["approved", "exported", "published"].includes(selected.state) ? "green" : selected.state === "in_review" ? "orange" : "neutral"}>{articleStateNames[selected.state] || selected.state}</Badge></div>
          <div className="article-steps" aria-label="文章生产步骤">{["真实需求", "论证大纲", "完整正文", "人工终审", "交付文档"].map((name, index) => <span key={name} aria-current={index + 1 === currentStep ? "step" : undefined} className={`article-step${index + 1 < currentStep ? " done" : index + 1 === currentStep ? " current" : ""}`}>{index + 1} {name}</span>)}</div>
          {hasActiveJob && <div className="article-review-note">后台任务正在运行。当前编辑内容会保留；生成完成后仅在新版本出现时更新编辑器。</div>}
          <Card className="article-card">
            <div className="article-card-head"><div><h3>文章要求</h3><p>生成时作为本次输入，不覆盖其他 Agent，也不会自动保存为正文。</p></div></div>
            <Field label="补充要求" hint="建议写明目标读者、真实场景、可核实证据，以及不能出现的承诺。"><Textarea value={brief} onChange={event => setBrief(event.target.value)} placeholder="例如：面向正在评估 AI 的企业主，使用真实部门任务，不承诺降本比例。" /></Field>
          </Card>
          <Card className="article-card">
            <div className="article-card-head"><div><h3>一、论证大纲</h3><p>结论、场景、方法、边界和行动清单，避免堆砌工具名。</p></div><Button size="small" disabled={Boolean(busy) || hasActiveJob} title={hasActiveJob ? "已有文章后台任务运行中" : undefined} onClick={() => void generate("article.outline")}><Sparkles size={14} />{busy === "article.outline" ? "正在提交…" : "文章Agent生成大纲"}</Button></div>
            <p className="article-version-note">{outline ? `当前大纲 ${outline.id}` : "尚无大纲，可生成或手动撰写。"}</p>
            <Textarea className="article-outline-editor" value={outlineText} onChange={event => setOutlineText(event.target.value)} disabled={!canEdit} placeholder="先形成大纲，或手动粘贴 Markdown 大纲" />
            <div className="button-row"><Button size="small" disabled={Boolean(busy) || !canEdit} onClick={() => void saveRevision("outline")}>保存大纲</Button></div>
          </Card>
          <Card className="article-card">
            <div className="article-card-head"><div><h3>二、完整正文</h3><p>生成后必须人工核查事实、案例、数字、来源和过度承诺。</p></div><Button size="small" disabled={Boolean(busy) || !outline || hasActiveJob} title={!outline ? "先保存或生成大纲" : hasActiveJob ? "已有文章后台任务运行中" : undefined} onClick={() => void generate("article.draft")}><Sparkles size={14} />{busy === "article.draft" ? "正在提交…" : "文章Agent生成正文"}</Button></div>
            <p className="article-version-note">{draft ? `当前正文 ${draft.id}` : "尚无正文；生成或编辑后保存为新版本。"}</p>
            <Textarea className="article-draft-editor" value={draftText} onChange={event => setDraftText(event.target.value)} disabled={!canEdit} placeholder="先保存大纲，再生成或编辑完整 Markdown 正文" />
            <div className="button-row">
              <Button size="small" disabled={Boolean(busy) || !canEdit} onClick={() => void saveRevision("draft")}>保存正文</Button>
              {draft && !["approved", "exported", "published", "in_review"].includes(selected.state) && <Button size="small" disabled={Boolean(busy)} onClick={() => void execute("review", () => api(`/api/articles/${selected.id}/actions`, jsonOptions("POST", { action: "submit_review", expected_version: selected.version })), "已提交人工审核")}>提交人工审核</Button>}
              {draft && ["draft", "in_review"].includes(selected.state) && <Button size="small" variant="primary" disabled={Boolean(busy)} onClick={() => decide("approve")}><Check size={14} />我已核查并批准当前正文</Button>}
              {draft && selected.state === "in_review" && <Button size="small" variant="danger" disabled={Boolean(busy)} onClick={() => decide("reject")}>退回修改</Button>}
              {draft && ["approved", "exported"].includes(selected.state) && <Button size="small" variant="primary" disabled={Boolean(busy) || hasActiveJob} onClick={() => void execute("export", () => api(`/api/articles/${selected.id}/export`, jsonOptions("POST", { revision_id: draft.id, expected_version: selected.version })), "文章导出已加入后台；完成后可下载真实文件")}><Download size={14} />导出当前正文</Button>}
            </div>
          </Card>
          {!!jobs.length && <div className="article-jobs">{jobs.map(job => <ArticleJob job={job} key={job.id} />)}</div>}
          {["approved", "exported", "published"].includes(selected.state) && <Card className="article-card article-delivery">
            <div className="article-card-head"><div><h3>交付文档</h3><p>这里只提供实际生成的文档；平台预览与公开发布统一在发布中心完成。</p></div><Link className="button button-small" to={`/publish?kind=article&id=${encodeURIComponent(selected.id)}`}>前往发布中心</Link></div>
            {exported ? <div className="article-export"><div><strong>Markdown + 安全 HTML</strong><p>{exported.id} · 文件由后端真实生成</p></div><div className="button-row">{exportPayload.markdown_asset_id ? <a className="button button-small" href={`/api/v2/assets/${exportPayload.markdown_asset_id}/content?download=1`}><Download size={13} />下载 Markdown</a> : <Button size="small" disabled title="导出修订缺少 Markdown 资产，请重新导出">Markdown 不可用</Button>}{exportPayload.html_asset_id ? <a className="button button-small" href={`/api/v2/assets/${exportPayload.html_asset_id}/content?download=1`}><Download size={13} />下载 HTML</a> : <Button size="small" disabled title="导出修订缺少 HTML 资产，请重新导出">HTML 不可用</Button>}</div></div> : <Empty title="尚未导出交付文档" description="导出当前已批准正文后，这里会显示真实 Markdown 和 HTML 下载文件。" />}
          </Card>}
        </>}
      </main>
    </div>
    <Modal open={createOpen} onOpenChange={setCreateOpen} title="新建文章任务" description="只创建本地编辑任务，不会自动生成或公开发布。">
      <form className="article-create-form" onSubmit={createArticle}><Field label="文章主题"><input className="input" autoFocus required maxLength={200} value={newTitle} onChange={event => setNewTitle(event.target.value)} placeholder="要为目标用户解决什么具体问题？" /></Field><Field label="初始写作要求（可选）"><Textarea value={newBrief} onChange={event => setNewBrief(event.target.value)} placeholder="目标读者、真实场景、事实证据、边界与禁止承诺" /></Field><div className="button-row article-create-actions"><Button type="button" onClick={() => setCreateOpen(false)}>取消</Button><Button variant="primary" type="submit" disabled={busy === "create"}><Send size={14} />{busy === "create" ? "正在创建…" : "创建本地文章"}</Button></div></form>
    </Modal>
    {!resources && <ErrorBox>文章数据尚未读取。请检查本地服务；页面不会显示伪造草稿。</ErrorBox>}
  </div>;
}
