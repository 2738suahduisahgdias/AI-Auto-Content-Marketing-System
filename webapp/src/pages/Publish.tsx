import { useMemo } from "react";
import { FileText, Film, Info } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { useApp } from "@/AppContext";
import { PublishingPanel, type PublishingSource } from "@/components/PublishingPanel";
import { Card, Field, PageHeader } from "@/components/ui";
import type { Article, ContentKind, Task } from "@/lib/types";
import "./Publish.css";

function draftOf(article: Article) {
  const id = article.active_revisions.draft;
  return article.revisions.find(revision => revision.id === id);
}

export default function Publish() {
  const { resources } = useApp();
  const [searchParams, setSearchParams] = useSearchParams();
  const kind: ContentKind = searchParams.get("kind") === "article" ? "article" : "video";
  const articles = (resources?.articles.items || []).filter(item => ["approved", "exported"].includes(item.state) && item.active_revisions.draft);
  const videos = ((resources?.core.tasks || []) as Task[]).filter(task => task.state === "approved" && task.files.some(file => file.kind === "video" && String(file.relative_path || "").toLowerCase().endsWith(".mp4")));
  const sources: (Article | Task)[] = kind === "article" ? articles : videos;
  const requestedId = searchParams.get("id") || "";
  const selected = sources.find(item => (kind === "article" ? (item as Article).id : (item as Task).content_id) === requestedId) || sources[0];
  const selectedId = selected ? kind === "article" ? (selected as Article).id : (selected as Task).content_id : "";

  const source = useMemo<PublishingSource | null>(() => {
    if (!selected) return null;
    if (kind === "article") {
      const article = selected as Article;
      return { id: article.id, title: String(article.campaign.title), body: String(draftOf(article)?.payload.text || "") };
    }
    const task = selected as Task;
    return {
      id: task.content_id,
      title: task.title,
      body: String(task.publications?.douyin?.description || task.scripts.douyin || task.scripts.master || task.title),
    };
  }, [kind, selected]);

  const chooseKind = (next: ContentKind) => {
    const nextSources = next === "article" ? articles : videos;
    const first = nextSources[0];
    const firstId = first ? next === "article" ? (first as Article).id : (first as Task).content_id : "";
    setSearchParams(firstId ? { kind: next, id: firstId } : { kind: next });
  };

  return <div className="publish-page">
    <PageHeader eyebrow="HUMAN-CONFIRMED DISTRIBUTION" title="发布中心" description="文章与视频使用完全独立的来源、表单和发布批次。先生成真实平台预览，再由你一次确认公开；不会自动发布测试内容。" />
    <div className="publish-kind-tabs" role="tablist" aria-label="发布内容类型"><button role="tab" aria-selected={kind === "article"} className={`publish-kind-tab${kind === "article" ? " active" : ""}`} onClick={() => chooseKind("article")}><FileText size={14} /> 文章发布</button><button role="tab" aria-selected={kind === "video"} className={`publish-kind-tab${kind === "video" ? " active" : ""}`} onClick={() => chooseKind("video")}><Film size={14} /> 视频发布</button></div>
    <Card className="publish-source-card"><div><h2>{kind === "article" ? "选择已批准的文章正文" : "选择已人工批准的视频任务"}</h2><p>{kind === "article" ? "公众号与小红书长文只读取当前文章的已审批正文。" : "抖音、小红书与视频号只读取已批准 MP4；不会用文章、音频或 SRT 代替成片。"}</p></div><Field label={kind === "article" ? "文章来源" : "视频来源"}><select value={selectedId} disabled={!sources.length} onChange={event => setSearchParams({ kind, id: event.target.value })}>{!sources.length && <option value="">没有符合发布条件的来源</option>}{sources.map(item => { const itemId = kind === "article" ? (item as Article).id : (item as Task).content_id; const title = kind === "article" ? String((item as Article).campaign.title) : (item as Task).title; return <option value={itemId} key={itemId}>{title} · {itemId}</option>; })}</select></Field></Card>
    <div className="publish-boundary"><Info size={16} /><p>登录窗口任务、预览就绪和公开成功是三种不同状态。页面只展示后端真实结果；公开发布前请检查专用浏览器中的账号、上传进度和平台提示。</p></div>
    <PublishingPanel kind={kind} source={source} />
    <div className="publish-related"><h2>发布记录与复盘</h2><p>文章的其他真实链接可在<Link to={selectedId && kind === "article" ? `/articles/${selectedId}` : "/articles"}>文章任务</Link>补录；视频的手动发布记录与 2h / 1d / 3d / 7d 数据在<Link to={selectedId && kind === "video" ? `/tasks/${selectedId}` : "/tasks"}>视频任务</Link>继续处理。</p></div>
  </div>;
}
