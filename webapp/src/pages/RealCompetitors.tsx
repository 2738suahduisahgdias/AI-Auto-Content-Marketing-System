import { useMemo, useState } from "react";
import { Database, ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";
import { useApp } from "@/AppContext";
import { DataBoundary, MetricCard, SectionTitle, numberText } from "@/components/AnalyticsShared";
import { Badge, Card, Empty, PageHeader } from "@/components/ui";
import { platformLabels, platformOrder, type PlatformKey } from "@/lib/analyticsDemo";
import "./Analytics.css";

interface CompetitorItem {
  id: string;
  platform: PlatformKey;
  title: string;
  author: string;
  url: string;
  source: "competitor" | "high_praise";
  likes: number | null;
  comments: number | null;
  shares: number | null;
  favorites: number | null;
  visible_interactions: number | null;
  captured_at: string;
  published_at: string | null;
  completeness: "complete" | "partial";
}

interface CompetitorData {
  items: CompetitorItem[];
  summary: { total: number; authors: number; complete: number; partial: number };
}

function dateText(value?: string | null) {
  return value ? value.replace("T", " ").slice(0, 16) : "未读取";
}

export default function RealCompetitors() {
  const { resources } = useApp();
  const data = (resources?.accounts?.competitor_analytics || resources?.accounts?.analytics?.competitor_analytics) as CompetitorData | undefined;
  const [platform, setPlatform] = useState<"all" | PlatformKey>("all");
  const [source, setSource] = useState("all");
  const [author, setAuthor] = useState("all");
  const [sort, setSort] = useState<"interactions" | "recent">("interactions");
  const items = useMemo(() => data?.items || [], [data]);
  const authors = useMemo(() => [...new Set(items.map(item => item.author))].sort(), [items]);
  const visible = items.filter(item => (platform === "all" || item.platform === platform) && (source === "all" || item.source === source) && (author === "all" || item.author === author)).sort((a, b) => sort === "recent" ? b.captured_at.localeCompare(a.captured_at) : (b.visible_interactions ?? -1) - (a.visible_interactions ?? -1));
  const visibleAuthors = new Set(visible.map(item => item.author)).size;

  return <div className="analytics-page competitor-page">
    <PageHeader eyebrow="VERIFIED PUBLIC RESEARCH" title="竞对分析" description="正式数据页面：只展示真实研究快照和公开可见字段，不生成无依据的竞对排名。" actions={<><Link className="button" to="/competitors?demo=1">查看演示</Link><Link className="button button-primary" to="/topics/douyin">采集竞对选题</Link></>} />
    <div className="analytics-demo-notice real"><div><Database size={17} /><strong>真实公开快照</strong><span>来自现有竞品与高赞研究条目 · 不可见字段保持未读取</span></div><Badge tone="green">LIVE DATA</Badge></div>
    <div className="competitor-filter-bar"><div className="analytics-view-tabs" role="tablist" aria-label="真实竞对平台筛选"><button type="button" role="tab" aria-selected={platform === "all"} className={platform === "all" ? "active" : ""} onClick={() => setPlatform("all")}>全部平台</button>{platformOrder.map(key => <button type="button" role="tab" aria-selected={platform === key} className={platform === key ? "active" : ""} key={key} onClick={() => setPlatform(key)}>{platformLabels[key]}</button>)}</div><div className="button-row"><label className="competitor-group-filter"><span>来源</span><select value={source} onChange={event => setSource(event.target.value)}><option value="all">全部来源</option><option value="competitor">竞品收藏</option><option value="high_praise">高赞收藏</option></select></label><label className="competitor-group-filter"><span>作者</span><select value={author} onChange={event => setAuthor(event.target.value)}><option value="all">全部作者</option>{authors.map(value => <option key={value}>{value}</option>)}</select></label></div></div>

    <section className="analytics-section"><SectionTitle title="当前研究范围" description={`筛选后 ${visible.length} 条内容 · ${visibleAuthors} 位作者`} /><div className="analytics-metrics-grid four"><MetricCard accent label="真实竞对内容" value={visible.length} hint="竞品与高赞研究快照" /><MetricCard label="涉及作者" value={visibleAuthors} hint="未识别作者单独标记" /><MetricCard label="字段较完整" value={visible.filter(item => item.completeness === "complete").length} hint="至少两个公开互动字段" /><MetricCard label="部分数据" value={visible.filter(item => item.completeness === "partial").length} hint="缺失字段不按 0 计算" /></div></section>

    <section className="analytics-section"><SectionTitle title="竞对内容库" description="点击原链接回溯证据；公开互动只汇总实际可见字段" action={<label className="competitor-sort">排序<select value={sort} onChange={event => setSort(event.target.value as typeof sort)}><option value="interactions">可见互动</option><option value="recent">最近采集</option></select></label>} />{visible.length ? <div className="competitor-content-grid">{visible.map(item => <Card className="competitor-content-card" key={item.id}><div className="competitor-content-top"><Badge tone="blue">{item.source === "competitor" ? "竞品收藏" : "高赞收藏"}</Badge><Badge tone={item.completeness === "complete" ? "green" : "orange"}>{item.completeness === "complete" ? "字段较完整" : "部分数据"}</Badge></div><h3>{item.title}</h3><p>{item.author} · {platformLabels[item.platform]} · 采集 {dateText(item.captured_at)}</p><div className="competitor-content-metrics"><span><strong>{numberText(item.visible_interactions)}</strong><small>可见互动</small></span><span><strong>{numberText(item.likes)}</strong><small>点赞</small></span><span><strong>{numberText(item.comments)}</strong><small>评论</small></span></div><div className="competitor-content-foot"><span>分享 {numberText(item.shares)} · 收藏 {numberText(item.favorites)}</span><a href={item.url} target="_blank" rel="noreferrer">查看原文 <ExternalLink size={14} /></a></div></Card>)}</div> : <Card><Empty title="当前筛选没有真实竞对快照" description="可前往抖音选题同步收藏夹，或调整平台、来源和作者筛选。系统不会用模拟内容补齐。" action={<Link className="button button-primary" to="/topics/douyin">前往抖音选题</Link>} /></Card>}</section>
    <DataBoundary>竞对粉丝、播放、完播、咨询和成交没有真实公开证据时不展示。公开互动量是采集时快照，不等于今日新增，也不能直接与自己的后台完播率比较。</DataBoundary>
  </div>;
}
