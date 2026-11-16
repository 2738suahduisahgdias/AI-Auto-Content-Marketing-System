import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useApp } from "../../AppContext";
import { Badge, Card, Empty, Input, PageHeader } from "../../components/ui";
import { projectType } from "./useVideoProject";
import type { Task } from "../../lib/types";
import "./video-projects.css";

export default function VideoProjectHome() {
  const { resources } = useApp();
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState<"all" | "original" | "benchmark">("all");
  const tasks = useMemo(() => [...(resources?.core.tasks || []) as Task[]]
    .filter(task => (kind === "all" || projectType(task) === kind))
    .filter(task => `${task.title}${task.content_id}`.toLowerCase().includes(query.toLowerCase()))
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at)), [kind, query, resources?.core.tasks]);

  return <div className="video-projects-home">
    <PageHeader eyebrow="VIDEO PROJECTS" title="视频项目" description="继续已有创作，或从原创和对标开始一个新项目。" actions={<div className="actions"><Link className="button" to="/projects/original">新建原创</Link><Link className="button button-primary" to="/projects/benchmark">新建对标</Link></div>} />
    <Card className="video-project-toolbar">
      <Input aria-label="搜索视频项目" placeholder="搜索项目名称或编号" value={query} onChange={event => setQuery(event.target.value)} />
      <select aria-label="项目类型" className="input" value={kind} onChange={event => setKind(event.target.value as typeof kind)}>
        <option value="all">全部项目</option><option value="original">原创</option><option value="benchmark">对标</option>
      </select>
      <Link className="button" to="/projects/original">新建视频</Link>
    </Card>
    {tasks.length ? <div className="video-project-grid">{tasks.map(task => {
      const type = projectType(task);
      const href = type === "benchmark" ? `/projects/benchmark/${task.content_id}` : `/projects/original/${task.content_id}`;
      const handoff = task.source?.yingxu_handoff;
      return <Link className="video-project-card" to={href} key={task.content_id}>
        <div className="video-project-card-top"><Badge tone={type === "benchmark" ? "blue" : "orange"}>{type === "benchmark" ? "对标" : "原创"}</Badge><time>{new Date(task.updated_at).toLocaleString("zh-CN")}</time></div>
        <h2>{task.title}</h2>
        <p>{task.content_id}</p>
        <div className="video-project-card-status">{handoff?.stale ? "内容已修改，需重新交付" : handoff ? "已关联审核与发布" : "继续创作"}<span>打开 →</span></div>
      </Link>;
    })}</div> : <Empty title={query || kind !== "all" ? "没有匹配的视频项目" : "还没有视频项目"} description="从一份原创文案或一个参考视频开始。" action={<div className="actions"><Link className="button" to="/projects/original">新建原创</Link><Link className="button" to="/projects/benchmark">新建对标</Link></div>} />}
  </div>;
}
