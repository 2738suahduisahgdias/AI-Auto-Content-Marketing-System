import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowLeft, Check, ChevronRight, RefreshCw } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useApp } from "@/AppContext";
import VideoStages, { type TaskAction, type TaskRequest } from "@/components/VideoStages";
import { Badge, Button, Card, Empty, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import type { Json, Task } from "@/lib/types";
import { audienceNames, pillarNames, stageFor, stateNames } from "@/lib/names";
import "./tasks.css";

const stages = ["选题", "脚本", "录音字幕", "素材授权", "成片", "质检", "人工审核", "发布", "复盘"];
const stageAgents = ["选题Agent", "脚本Agent", "用户", "素材规划Agent", "视频构建Agent", "人工质检", "用户", "发布复盘Agent", "数据分析Agent"];
type VideoTask = Task & { source?: Json; completed_at?: string };

export default function Tasks() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { resources, refresh, run } = useApp();
  const [busy, setBusy] = useState("");
  const busyRef = useRef(false);
  const tasks = (resources?.core.tasks || []) as VideoTask[];
  const selected = tasks.find(task => task.content_id === id) || (!id ? tasks[0] : undefined);
  useEffect(() => {
    if (!id && selected) navigate(`/tasks/${selected.content_id}`, { replace: true });
  }, [id, selected, navigate]);
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
  const action = useCallback<TaskAction>(async name => {
    if (!selected) return false;
    return execute(`action-${name}`, `/api/tasks/${selected.content_id}/actions`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: name }) }, "工作流状态已保存");
  }, [execute, selected]);
  if (!resources) return null;
  if (!tasks.length) return <><PageHeader eyebrow="VIDEO WORKFLOW" title="视频任务" description="从脚本、录音、素材到发布复盘的完整生产记录。" /><Empty title="任务工作台还是空的" description="从真实选题创建第一条视频任务，任务目录与工作流会自动建立。" action={<Link to="/topics/douyin" className="button button-primary">去选题库创建任务</Link>} /></>;
  if (!selected) return <><PageHeader eyebrow="VIDEO WORKFLOW" title="视频任务" /><Empty title="没有找到这个视频任务" description={`任务 ${id || "未指定"} 不存在，或本地数据已更新。`} action={<Button onClick={() => navigate(`/tasks/${tasks[0].content_id}`, { replace: true })}><ArrowLeft size={15} />返回最新任务</Button>} /></>;
  const stage = stageFor(selected);
  return <>
    <PageHeader eyebrow="VIDEO WORKFLOW · 全流程留痕" title="视频任务" description="每一步使用真实文件和后端状态；生成不等于审批，质检不等于终审，记录不等于发布。" actions={<Button size="small" disabled={Boolean(busy)} onClick={() => void refresh()}><RefreshCw size={14} />刷新任务数据</Button>} />
    <div className="tasks-layout">
      <aside className="tasks-sidebar"><div className="tasks-sidebar-head"><strong>全部任务</strong><Badge>{tasks.length}</Badge></div><nav aria-label="视频任务列表">{tasks.map(task => <Link className={`tasks-nav-item${task.content_id === selected.content_id ? " active" : ""}`} to={`/tasks/${task.content_id}`} key={task.content_id}><span><strong>{task.title}</strong><small>{task.content_id}</small></span><Badge tone={task.state === "analyzed" ? "green" : task.state === "review_required" ? "orange" : "neutral"}>{stateNames[task.state] || task.state}</Badge></Link>)}</nav><Link className="tasks-new-link" to="/topics/douyin">从选题库新建任务 <ChevronRight size={14} /></Link></aside>
      <main className="tasks-workbench">
        <header className="tasks-project-head"><div><p className="eyebrow">{pillarNames[selected.pillar] || selected.pillar} · {audienceNames[selected.audience] || selected.audience}</p><h1>{selected.title}</h1><p>{selected.content_id}{selected.angle ? ` · ${selected.angle}` : ""}</p>{selected.source?.type === "douyin_hotspot" && <p className="tasks-source">来源：抖音热点 #{selected.source.rank}「{selected.source.title}」 · 热度 {selected.source.heat} · {selected.source.captured_at} 快照</p>}{selected.source?.type === "douyin_favorite_collection" && <p className="tasks-source">来源：抖音收藏夹「{selected.source.name}」 · {selected.source.usage}</p>}</div><Badge tone={selected.state === "analyzed" ? "green" : selected.state === "review_required" ? "orange" : "blue"}>{stateNames[selected.state] || selected.state}</Badge></header>
        <ol className="tasks-steps" aria-label="视频工作流进度">{stages.map((name, index) => { const done = index < stage || selected.state === "analyzed"; const current = index === stage && selected.state !== "analyzed"; return <li className={`${done ? "done" : ""}${current ? " current" : ""}`} key={name} aria-current={current ? "step" : undefined}><span>{done ? <Check size={13} /> : index + 1}</span><strong>{name}</strong><small>{index === 8 && selected.state === "analyzed" ? "发布复盘Agent" : stageAgents[index]}</small></li>; })}</ol>
        {busy && <div className="tasks-busy" role="status"><span className="tasks-busy-dot" />正在执行：{busy}。请保持本地服务运行，完成或失败后会显示真实结果。</div>}
        <Card className="tasks-stage-card"><VideoStages key={`${selected.content_id}:${selected.updated_at}`} task={selected} core={resources.core} busy={busy} request={execute} action={action} stage={stage} /><details className="tasks-history"><summary>操作记录（{selected.events.length}）</summary>{selected.events.length ? <ul>{selected.events.map((event, index) => <li key={`${event.created_at}-${event.event}-${index}`}><time>{event.created_at}</time><strong>{event.event}</strong><span>{event.detail}</span></li>)}</ul> : <p>尚无操作记录。</p>}</details></Card>
      </main>
    </div>
  </>;
}
