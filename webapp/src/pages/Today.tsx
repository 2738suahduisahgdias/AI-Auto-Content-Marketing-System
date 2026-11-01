import { ArrowRight, CheckCircle2, Clock3, FileWarning, Send } from "lucide-react";
import { Link } from "react-router-dom";
import { useApp } from "@/AppContext";
import { Badge, Card, Empty, PageHeader } from "@/components/ui";
import { audienceNames, pillarNames, stateNames } from "@/lib/names";

import WorkOverview from "@/components/WorkOverview";

const nextNames: Record<string, string> = { topic_approved: "手填或按需生成口播稿", script_drafted: "确认当前口播稿", script_approved: "按场景配置旁白与字幕", waiting_audio: "按需配置旁白与字幕", transcribed: "规划素材与授权", assets_planned: "确认素材与授权", assets_approved: "选择模板并生成", rendered: "交付成片至审核中心", quality_checked: "提交人工审核", review_required: "观看成片并最终审核", approved: "交给发布 Agent，人工确认后发布", published: "已发布", analyzed: "已归档" };
export default function Today() {
  const { resources } = useApp();
  const tasks = resources?.core.tasks || [];
  const active = tasks.filter((task: any) => !["published", "analyzed"].includes(task.state));
  const current = active[0];
  const monday = new Date(); const day = monday.getDay() || 7;
  monday.setHours(0, 0, 0, 0); monday.setDate(monday.getDate() - day + 1);
  const published = tasks.filter((task: any) => task.published_at && new Date(task.published_at) >= monday).length;
  const stats = [
    ["本周视频发布", `${published} / 3–5`, "稳定生产，不用低质量凑更", Send],
    ["视频进行中", active.length, "从文案到发布的真实任务", Clock3],
    ["视频待人工审核", tasks.filter((task: any) => task.state === "review_required").length, "最终审核不能由质检替代", FileWarning],
    ["已发布视频", tasks.filter((task: any) => task.state === "published").length, "已完成发布的内容", CheckCircle2],
  ] as const;
  const runningJobs = (resources?.core.video_jobs || []).filter((job: any) => ["queued", "leased", "running", "retry_wait", "cancel_requested"].includes(job.status));
  return <>
    <PageHeader eyebrow="YOUR NEXT BEST ACTION" title="今天，先推进最重要的一步" description="热点只是输入，交付和证据才是结果。" />
    <div className="metric-grid">{stats.map(([label, value, hint, Icon]) => <Card className="metric-card" key={label}><div className="metric-label">{label}<Icon size={16} /></div><strong>{value}</strong><p>{hint}</p></Card>)}</div>
    <WorkOverview />
    {current ? <Card className="focus-card"><div><p className="eyebrow">当前项目 · {current.content_id}</p><h2>{nextNames[current.state]}</h2><p className="focus-title">{current.title}</p><div className="tag-row"><Badge>{pillarNames[current.pillar]}</Badge><Badge tone="blue">{audienceNames[current.audience]}</Badge><Badge tone="orange">{stateNames[current.state]}</Badge></div></div><Link to={`/tasks/${current.content_id}`} className="button button-primary">继续这条内容 <ArrowRight size={16} /></Link></Card> : <Empty title="从选题开始今天的内容项目" action={<Link to="/topics/douyin" className="button button-primary">去选择选题</Link>} />}
    {runningJobs.length > 0 && <Card><div><p className="eyebrow">视频生成 Agent</p><h2>{runningJobs[0].stage}</h2><p>后台任务 {runningJobs[0].id} · 进度 {Math.round((runningJobs[0].progress || 0) * 100)}%</p><Link to={`/tasks/${runningJobs[0].aggregate_id}`} className="button button-small">查看生产进度 <ArrowRight size={14} /></Link></div></Card>}
    <div className="section-heading"><h2>进行中的项目</h2><p>{active.length} 条 · 每条只推进当前允许的步骤</p></div>
    <div className="project-list">{active.map((task: any) => <Link to={`/tasks/${task.content_id}`} className="project-row" key={task.content_id}><div><h3>{task.title}</h3><p>{task.content_id} · {pillarNames[task.pillar]} / {audienceNames[task.audience]}</p></div><Badge tone={task.state === "review_required" ? "orange" : "green"}>{stateNames[task.state]}</Badge><span className="project-next">{nextNames[task.state]}</span><ArrowRight size={16} /></Link>)}</div>
    <div className="today-footnote"><span>自动化边界</span><p>Agent 负责研究、生成和执行整理；事实、授权、终审和公开风险由你确认。</p><Link to="/settings">查看 Agent 配置 <ArrowRight size={14} /></Link></div>
  </>;
}
