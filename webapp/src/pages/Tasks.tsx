import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, Check, ChevronRight, Plus, RefreshCw } from "lucide-react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useApp } from "@/AppContext";
import VideoStages, { type TaskAction, type TaskRequest } from "@/components/VideoStages";
import { Badge, Button, Card, Empty, Field, Input, PageHeader, Textarea } from "@/components/ui";
import { api } from "@/lib/api";
import type { Json, Task } from "@/lib/types";
import { audienceNames, groupFor, groupStages, nextStepFor, pillarNames, platformNames, stateNames, taskAttention, videoGroupOwners, videoGroups } from "@/lib/names";
import "./tasks.css";

const stageKeys = ["content", "scripts", "audio", "assets", "render", "quality", "review", "publish", "retro"];
type VideoTask = Task & { source?: Json; completed_at?: string };
type VideoJob = { aggregate_id: string; status: string; progress?: number; stage?: string };

const filters: Record<string, string> = { all: "全部", active: "进行中", review: "待终审", done: "已完成", failed: "失败" };

function matchesFilter(task: VideoTask, jobs: VideoJob[], filter: string) {
  if (filter === "failed") return jobs.some(job => job.aggregate_id === task.content_id && job.status === "failed");
  if (filter === "review") return task.state === "review_required";
  if (filter === "done") return ["published", "analyzed"].includes(task.state);
  if (filter === "active") return !["published", "analyzed"].includes(task.state);
  return true;
}

function CreateTaskDialog({ onClose, onCreated }: { onClose: () => void; onCreated: (id: string) => void }) {
  const [sourceType, setSourceType] = useState("topic");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [pillar, setPillar] = useState("enterprise_ai");
  const [audience, setAudience] = useState("business_owners");
  const [platform, setPlatform] = useState("douyin");
  const [reviewMode, setReviewMode] = useState("agent");
  const [publishMode, setPublishMode] = useState("local_only");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      const task = await api("/api/tasks", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title, content, pillar, audience, platform, review_mode: reviewMode, publish_mode: publishMode, source_type: sourceType }) });
      onCreated(task.content_id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "创建失败");
    } finally {
      setBusy(false);
    }
  };
  return <div className="task-dialog-backdrop" role="dialog" aria-modal="true" aria-label="新建视频任务">
    <div className="task-dialog">
      <div className="task-section-head"><div><h2>新建视频任务</h2><p>统一生成视频内容项目；审核与发布方式创建后仍可调整。</p></div><Button size="small" onClick={onClose}>取消</Button></div>
      <fieldset className="task-fieldset"><legend>内容来源</legend>
        <div className="task-check-grid">
          <label><input type="radio" name="source-type" checked={sourceType === "topic"} onChange={() => setSourceType("topic")} />输入主题</label>
          <label><input type="radio" name="source-type" checked={sourceType === "article"} onChange={() => setSourceType("article")} />粘贴文章</label>
        </div>
        <p className="task-help">从选题库或抖音热点创建，请前往<Link to="/topics/douyin">选题中心</Link>，来源证据会自动带入任务。</p>
      </fieldset>
      <Field label="选题标题"><Input value={title} maxLength={200} onChange={event => setTitle(event.target.value)} placeholder="例如：企业 AI 落地为什么容易失败" /></Field>
      {sourceType === "article" && <Field label="粘贴文章或文稿" hint="会作为当前平台口播稿的初始内容，之后仍可编辑"><Textarea value={content} onChange={event => setContent(event.target.value)} placeholder="粘贴原文或你的初稿…" /></Field>}
      <div className="task-form-grid task-form-grid-three">
        <Field label="目标平台"><select value={platform} onChange={event => setPlatform(event.target.value)}>{Object.entries(platformNames).map(([key, name]) => <option key={key} value={key}>{name}</option>)}</select></Field>
        <Field label="内容方向"><select value={pillar} onChange={event => setPillar(event.target.value)}>{Object.entries(pillarNames).map(([key, name]) => <option key={key} value={key}>{name}</option>)}</select></Field>
        <Field label="受众"><select value={audience} onChange={event => setAudience(event.target.value)}>{Object.entries(audienceNames).map(([key, name]) => <option key={key} value={key}>{name}</option>)}</select></Field>
      </div>
      <div className="task-form-grid">
        <Field label="审核方式"><select value={reviewMode} onChange={event => setReviewMode(event.target.value)}><option value="agent">审核 Agent</option><option value="human">人工审核</option><option value="none">仅机器检查</option></select></Field>
        <Field label="发布方式"><select value={publishMode} onChange={event => setPublishMode(event.target.value)}><option value="local_only">仅保存本地</option><option value="manual">人工发布</option><option value="auto">自动发布（需另行开启）</option></select></Field>
      </div>
      {error && <div className="task-info">{error}</div>}
      <div className="button-row"><Button variant="primary" disabled={busy || !title.trim()} title={!title.trim() ? "请填写选题标题" : "创建视频任务"} onClick={() => void submit()}>{busy ? "正在创建…" : "创建并继续"}</Button></div>
    </div>
  </div>;
}

export default function Tasks() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { resources, refresh, run } = useApp();
  const [busy, setBusy] = useState("");
  const busyRef = useRef(false);
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const jobs = useMemo(() => ((resources?.core.video_jobs || []) as VideoJob[]), [resources?.core.video_jobs]);
  const tasks = useMemo(() => {
    const all = (resources?.core.tasks || []) as VideoTask[];
    const keyword = search.trim().toLowerCase();
    return all
      .filter(task => matchesFilter(task, jobs, filter))
      .filter(task => !keyword || task.title.toLowerCase().includes(keyword) || task.content_id.includes(keyword))
      .sort((a, b) => taskAttention(a, jobs) - taskAttention(b, jobs) || String(b.updated_at).localeCompare(String(a.updated_at)));
  }, [resources?.core.tasks, jobs, filter, search]);
  const selected = ((resources?.core.tasks || []) as VideoTask[]).find(task => task.content_id === id) || (!id ? tasks[0] : undefined);
  const [pagination, setPagination] = useState({ key: "", page: 1 });
  const selectionKey = `${filter}:${search}:${id || ""}`;
  const selectedIndex = Math.max(0, tasks.findIndex(task => task.content_id === selected?.content_id));
  const pageCount = Math.max(1, Math.ceil(tasks.length / 10));
  const currentPage = Math.min(pagination.key === selectionKey ? pagination.page : Math.floor(selectedIndex / 10) + 1, pageCount);
  const goToPage = (page: number) => setPagination({ key: selectionKey, page });
  const pageItems = tasks.slice((currentPage - 1) * 10, currentPage * 10);
  useEffect(() => {
    if (!id && selected) navigate(`/tasks/${selected.content_id}`, { replace: true });
  }, [id, selected, navigate]);
  const selectedState = selected?.state;
  const waitingSubtitle = Boolean(selected && selectedState === "waiting_audio"
    && selected.files.some(file => file.kind === "audio") && !selected.files.some(file => file.kind === "srt"));
  useEffect(() => {
    if (!waitingSubtitle) return;
    const timer = window.setInterval(() => void refresh(), 5000);
    return () => window.clearInterval(timer);
  }, [waitingSubtitle, refresh]);
  const execute = useCallback<TaskRequest>(async (key, path, options, success) => {
    if (busyRef.current) return false;
    busyRef.current = true;
    setBusy(key);
    try {
      const result = await run(() => api(path, options), success);
      return result !== null;
    } finally {
      busyRef.current = false;
      setBusy("");
    }
  }, [run]);
  const action = useCallback<TaskAction>(async (name, payload = {}) => {
    if (!selected) return false;
    return execute(`action-${name}`, `/api/tasks/${selected.content_id}/actions`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: name, ...payload }) }, "工作流状态已保存");
  }, [execute, selected]);
  if (!resources) return null;
  const allTasks = (resources.core.tasks || []) as VideoTask[];
  const createButton = <Button size="small" onClick={() => setCreating(true)}><Plus size={14} />新建视频任务</Button>;
  if (!allTasks.length) return <><PageHeader eyebrow="VIDEO WORKFLOW" title="视频任务" description="从脚本、录音、素材到发布复盘的完整生产记录。" actions={createButton} /><Empty title="任务工作台还是空的" description="从真实选题创建第一条视频任务，任务目录与工作流会自动建立。" action={<Link to="/topics/douyin" className="button button-primary">去选题库创建任务</Link>} />{creating && <CreateTaskDialog onClose={() => setCreating(false)} onCreated={contentId => { setCreating(false); void refresh().then(() => navigate(`/tasks/${contentId}`)); }} />}</>;
  if (!selected) return <><PageHeader eyebrow="VIDEO WORKFLOW" title="视频任务" actions={createButton} /><Empty title="没有找到这个视频任务" description={`任务 ${id || "未指定"} 不存在，或本地数据已更新。`} action={<Button onClick={() => navigate(`/tasks/${allTasks[0].content_id}`, { replace: true })}><ArrowLeft size={15} />返回最新任务</Button>} /></>;
  const group = groupFor(selected);
  const requestedGroup = searchParams.has("stage") ? Number(searchParams.get("stage")) : group;
  const viewGroup = Number.isInteger(requestedGroup) && requestedGroup >= 0 && requestedGroup <= group ? requestedGroup : group;
  let displayTask = selected;
  if (viewGroup < group) {
    const payloads = groupStages[viewGroup]
      .map(stageIndex => (selected.stage_revisions || []).find(item => item.stage === stageKeys[stageIndex]))
      .filter(Boolean) as Json[];
    if (payloads.length) displayTask = { ...selected, ...Object.assign({}, ...payloads.map(item => item.payload)), variants: selected.variants, stage_revisions: selected.stage_revisions };
  }
  const goToGroup = (next: number) => setSearchParams(next === group ? {} : { stage: String(next) });
  return <>
    <PageHeader eyebrow="VIDEO WORKFLOW · 全流程留痕" title="视频任务" description="每一步使用真实文件和后端状态；生成不等于审批，质检不等于终审，记录不等于发布。" actions={<div className="button-row">{createButton}<Button size="small" disabled={Boolean(busy)} onClick={() => void refresh()}><RefreshCw size={14} />刷新任务数据</Button></div>} />
    <div className="tasks-layout">
      <aside className="tasks-sidebar">
        <div className="tasks-sidebar-head"><strong>全部任务</strong><Badge>{tasks.length}</Badge></div>
        <div className="tasks-filter-row" role="tablist" aria-label="任务筛选">{Object.entries(filters).map(([key, name]) => <button type="button" role="tab" aria-selected={filter === key} className={filter === key ? "active" : ""} key={key} onClick={() => setFilter(key)}>{name}</button>)}</div>
        <Input aria-label="搜索任务" value={search} onChange={event => setSearch(event.target.value)} placeholder="标题或任务 ID" />
        <nav aria-label="视频任务列表">{pageItems.map(task => { const next = nextStepFor(task, jobs); return <Link className={`tasks-nav-item${task.content_id === selected.content_id ? " active" : ""}`} to={`/tasks/${task.content_id}`} key={task.content_id}><span><strong>{task.title}</strong><small>{task.content_id} · {next}</small></span><Badge tone={task.state === "analyzed" ? "green" : task.state === "review_required" ? "orange" : next.startsWith("生产失败") ? "red" : "neutral"}>{stateNames[task.state] || task.state}</Badge></Link>; })}{!pageItems.length && <p className="task-help">当前筛选下没有任务。</p>}</nav>
        {tasks.length > 10 && <nav className="tasks-pagination" aria-label="视频分页"><Button size="small" disabled={currentPage === 1} onClick={() => goToPage(currentPage - 1)}>上一页</Button><span>{currentPage} / {pageCount} 页</span><Button size="small" disabled={currentPage === pageCount} onClick={() => goToPage(currentPage + 1)}>下一页</Button></nav>}
        <Link className="tasks-new-link" to="/topics/douyin">从选题库新建任务 <ChevronRight size={14} /></Link>
      </aside>
      <main className="tasks-workbench">
        <header className="tasks-project-head"><div><p className="eyebrow">{pillarNames[selected.pillar] || selected.pillar} · {audienceNames[selected.audience] || selected.audience}</p><h1>{selected.title}</h1><p>{selected.content_id}{selected.angle ? ` · ${selected.angle}` : ""}</p>{selected.source?.type === "douyin_hotspot" && <p className="tasks-source">来源：抖音热点 #{selected.source.rank}「{selected.source.title}」 · 热度 {selected.source.heat} · {selected.source.captured_at} 快照</p>}{selected.source?.type === "douyin_favorite_collection" && <p className="tasks-source">来源：抖音收藏夹「{selected.source.name}」 · {selected.source.usage}</p>}</div><Badge tone={selected.state === "analyzed" ? "green" : selected.state === "review_required" ? "orange" : "blue"}>{nextStepFor(selected, jobs)}</Badge></header>
        <ol className="tasks-steps" aria-label="视频工作流进度">{videoGroups.map((name, index) => { const done = index < group || selected.state === "analyzed"; const current = index === group && selected.state !== "analyzed"; return <li className={`${done ? "done" : ""}${current ? " current" : ""}${viewGroup === index ? " viewing" : ""}`} key={name} aria-current={current ? "step" : undefined}><button type="button" disabled={index > group} onClick={() => setSearchParams(index === group ? {} : { stage: String(index) })}><span>{done ? <Check size={13} /> : `0${index + 1}`}</span><strong>{name}</strong><small>{videoGroupOwners[index]}</small></button></li>; })}</ol>
        {viewGroup < group && <div className="task-info">正在查看历史步骤「{videoGroups[viewGroup]}」，内容只读，不会改变当前工作流。<Button size="small" onClick={() => setSearchParams({})}>返回当前步骤</Button></div>}
        {busy && <div className="tasks-busy" role="status"><span className="tasks-busy-dot" />正在执行：{busy}。请保持本地服务运行，完成或失败后会显示真实结果。</div>}
        <Card className="tasks-stage-card"><VideoStages key={`${selected.content_id}:${viewGroup}`} task={displayTask} core={resources.core} busy={busy} request={execute} action={action} group={viewGroup} readOnly={viewGroup < group} onNavigateGroup={goToGroup} /><details className="tasks-history"><summary>操作记录（{selected.events.length}）</summary>{selected.events.length ? <ul>{selected.events.map((event, index) => <li key={`${event.created_at}-${event.event}-${index}`}><time>{event.created_at}</time><strong>{event.event}</strong><span>{event.detail}</span></li>)}</ul> : <p>尚无操作记录。</p>}</details></Card>
      </main>
    </div>
    {creating && <CreateTaskDialog onClose={() => setCreating(false)} onCreated={contentId => { setCreating(false); void refresh().then(() => navigate(`/tasks/${contentId}`)); }} />}
  </>;
}
