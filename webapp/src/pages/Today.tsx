import { ArrowRight, CheckCircle2, Clock3, FileWarning, Send } from "lucide-react";
import { Link } from "react-router-dom";
import { useApp } from "@/AppContext";
import { Badge, Card, Empty, PageHeader } from "@/components/ui";
import { audienceNames, pillarNames, stateNames } from "@/lib/names";

const nextNames: Record<string, string> = { topic_approved: "编辑并保存五个脚本版本", script_drafted: "人工确认脚本", script_approved: "上传录音和 SRT 字幕", waiting_audio: "确认录音与字幕", transcribed: "规划素材与授权", assets_planned: "确认素材与授权", assets_approved: "上传或渲染成片", rendered: "完成五项质检", quality_checked: "提交人工审核", review_required: "观看成片并最终审核", approved: "选择平台并发布", published: "录入四窗口数据", analyzed: "复盘已完成" };
export default function Today() {
  const { resources } = useApp();
  const tasks = resources?.core.tasks || [];
  const active = tasks.filter((task: any) => task.state !== "analyzed");
  const current = active[0];
  const monday = new Date(); const day = monday.getDay() || 7;
  monday.setHours(0, 0, 0, 0); monday.setDate(monday.getDate() - day + 1);
  const published = tasks.filter((task: any) => task.published_at && new Date(task.published_at) >= monday).length;
  const stats = [
    ["本周发布", `${published} / 3–5`, "稳定生产，不用低质量凑更", Send],
    ["进行中", active.length, "从脚本到复盘的真实任务", Clock3],
    ["待人工审核", tasks.filter((task: any) => task.state === "review_required").length, "最终审核不能由质检替代", FileWarning],
    ["待复盘", tasks.filter((task: any) => task.state === "published").length, "回收四窗口真实数据", CheckCircle2],
  ] as const;
  return <>
    <PageHeader eyebrow="YOUR NEXT BEST ACTION" title="今天，先推进最重要的一步" description="热点只是输入，交付和证据才是结果。" />
    <div className="metric-grid">{stats.map(([label, value, hint, Icon]) => <Card className="metric-card" key={label}><div className="metric-label">{label}<Icon size={16} /></div><strong>{value}</strong><p>{hint}</p></Card>)}</div>
    {current ? <Card className="focus-card"><div><p className="eyebrow">当前项目 · {current.content_id}</p><h2>{nextNames[current.state]}</h2><p className="focus-title">{current.title}</p><div className="tag-row"><Badge>{pillarNames[current.pillar]}</Badge><Badge tone="blue">{audienceNames[current.audience]}</Badge><Badge tone="orange">{stateNames[current.state]}</Badge></div></div><Link to={`/tasks/${current.content_id}`} className="button button-primary">继续这条内容 <ArrowRight size={16} /></Link></Card> : <Empty title="从选题开始今天的内容项目" action={<Link to="/topics/douyin" className="button button-primary">去选择选题</Link>} />}
    <div className="section-heading"><h2>进行中的项目</h2><p>{active.length} 条 · 每条只推进当前允许的步骤</p></div>
    <div className="project-list">{active.map((task: any) => <Link to={`/tasks/${task.content_id}`} className="project-row" key={task.content_id}><div><h3>{task.title}</h3><p>{task.content_id} · {pillarNames[task.pillar]} / {audienceNames[task.audience]}</p></div><Badge tone={task.state === "review_required" ? "orange" : "green"}>{stateNames[task.state]}</Badge><span className="project-next">{nextNames[task.state]}</span><ArrowRight size={16} /></Link>)}</div>
    <div className="today-footnote"><span>自动化边界</span><p>Agent 负责研究、生成和执行整理；事实、授权、终审和公开风险由你确认。</p><Link to="/settings">查看 Agent 配置 <ArrowRight size={14} /></Link></div>
  </>;
}
