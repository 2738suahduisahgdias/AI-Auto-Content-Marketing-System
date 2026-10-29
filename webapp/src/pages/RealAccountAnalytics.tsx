import { useState } from "react";
import { Database, ExternalLink, RefreshCw } from "lucide-react";
import { Link, Navigate, useParams, useSearchParams } from "react-router-dom";
import { useApp } from "@/AppContext";
import { LeadPanel, type LeadRecord } from "@/components/LeadPanel";
import { DataBoundary, MetricCard, RangeTabs, SectionTitle, numberText } from "@/components/AnalyticsShared";
import { TrendChart } from "@/components/TrendChart";
import { Badge, Button, Card, Empty, ErrorBox, PageHeader } from "@/components/ui";
import { api, errorText, jsonOptions } from "@/lib/api";
import { aggregateCustom, inPeriod, localDay, periodFor, publicationTrend, type DimensionRange } from "@/lib/analyticsDimensions";
import { platformLabels, platformOrder, rangeLabels, type PlatformKey, type RangeKey } from "@/lib/analyticsDemo";
import "./Analytics.css";

interface RealMetrics {
  originals: number;
  publications: number;
  articles: number;
  videos: number;
  reach: number | null;
  likes: number | null;
  comments: number | null;
  shares: number | null;
  favorites: number | null;
  inquiries: number | null;
  qualifiedLeads: number | null;
  highIntentLeads: number | null;
  meetings: number | null;
  deals: number | null;
  revenue: number | null;
}

interface RealContent {
  id: string;
  source_id?: string | null;
  platform: PlatformKey;
  title: string;
  kind: "article" | "video";
  published_at: string | null;
  captured_at?: string;
  url: string | null;
  verified: boolean;
  metrics?: Partial<RealMetrics>;
}

interface RealAnalytics {
  generated_at: string;
  totals: Record<RangeKey, RealMetrics>;
  platforms: Record<PlatformKey, { metrics: Record<RangeKey, RealMetrics>; snapshot: null | { captured_at: string; profile: Record<string, unknown>; totals: Partial<RealMetrics> } }>;
  contents: RealContent[];
  trends: { publications: { labels: string[]; values: number[] } };
  sync: { platform: PlatformKey; status: string; captured_at: string | null; detail: string }[];
  errors: { platform: PlatformKey; type: string; message: string; action: string; captured_at: string }[];
  competitor_analytics: { items: { platform: PlatformKey }[] };
  leads: LeadRecord[];
  data_boundaries: string[];
}

const platformViews: PlatformKey[] = ["douyin", "wechat_channels", "xiaohongshu", "wechat_official_account"];

function dateText(value?: string | null) {
  return value ? value.replace("T", " ").slice(0, 16) : "未读取";
}

export default function RealAccountAnalytics() {
  const { view = "overview" } = useParams();
  const { resources, refresh, notify } = useApp();
  const [searchParams, setSearchParams] = useSearchParams();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [contentMode, setContentMode] = useState<"published" | "recorded">("published");
  const data = resources?.accounts?.analytics as RealAnalytics | undefined;
  if (view !== "overview" && !platformViews.includes(view as PlatformKey)) return <Navigate to="/accounts" replace />;
  const platform = view === "overview" ? null : view as PlatformKey;
  const requestedRange = searchParams.get("range") as DimensionRange;
  const range: DimensionRange = ["today", "yesterday", "7d", "30d", "custom"].includes(requestedRange) ? requestedRange : "today";
  const start = searchParams.get("start") || "";
  const end = searchParams.get("end") || "";
  const period = periodFor(range, start, end);
  const rangeTitle = range === "custom" ? "自定义周期" : rangeLabels[range];

  function selectRange(next: DimensionRange) {
    const params = new URLSearchParams(searchParams);
    params.set("range", next);
    if (next === "custom") {
      const now = new Date();
      params.set("start", start || localDay(new Date(now.getTime() - 6 * 86400000)));
      params.set("end", end || localDay(now));
    } else { params.delete("start"); params.delete("end"); }
    setSearchParams(params);
  }
  function setCustomDate(key: "start" | "end", value: string) {
    const params = new URLSearchParams(searchParams);
    params.set("range", "custom"); params.set(key, value); setSearchParams(params);
  }

  async function sync() {
    if (busy) return;
    setBusy(true); setError("");
    try {
      await api("/api/accounts/sync", jsonOptions("POST"));
      await refresh();
      notify("真实账号同步已加入后台；抖音和小红书需要有效登录，其他平台不会被伪造为已同步");
    } catch (reason) { const message = errorText(reason); setError(message); notify(message, true); }
    finally { setBusy(false); }
  }

  if (!data) return <><PageHeader title="账号日报" description="读取真实发布与账号快照。" /><Card><Empty title="当前服务还没有真实分析数据" description="请确认本地服务已加载最新后端，并重新读取页面。" action={<Button onClick={() => void refresh()}>重新读取</Button>} /></Card></>;
  const leads = data.leads || [];
  const metrics = range === "custom" ? aggregateCustom(data.contents, leads, period, platform || undefined) : platform ? data.platforms[platform].metrics[range] : data.totals[range];
  const snapshot = platform ? data.platforms[platform].snapshot : null;
  const hasPropagation = ["reach", "likes", "comments", "shares", "favorites"].some(key => metrics[key as keyof typeof metrics] != null);
  const scopedContents = platform ? data.contents.filter(item => item.platform === platform) : data.contents;
  const visibleContents = scopedContents.filter(item => contentMode === "published" ? inPeriod(item.published_at, period) : inPeriod(item.published_at || item.captured_at, period));
  const visibleLeads = leads.filter(lead => (!platform || lead.platform === platform) && inPeriod(lead.occurred_at, period));
  const competitorCount = platform ? data.competitor_analytics.items.filter(item => item.platform === platform).length : data.competitor_analytics.items.length;
  const trend = publicationTrend(data.contents, period, platform || undefined);
  const movingAverage = trend.values.map((_, index, values) => { const window = values.slice(Math.max(0, index - 6), index + 1); return window.reduce((sum, value) => sum + value, 0) / window.length; });
  const query = searchParams.toString();
  const actions = <><Link className="button" to={`/accounts${platform ? `/${platform}` : ""}?demo=1`}>查看演示</Link><Button variant="primary" disabled={busy} onClick={() => void sync()}><RefreshCw size={14} />{busy ? "正在提交…" : "同步真实账号"}</Button></>;

  return <div className="analytics-page">
    <PageHeader eyebrow="VERIFIED ACCOUNT ANALYTICS" title={platform ? `${platformLabels[platform]}日报` : "日报总览"} description="正式数据页面：已核验发布、真实账号快照和缺失边界分开呈现。" actions={actions} />
    <div className="analytics-demo-notice real"><div><Database size={17} /><strong>真实数据</strong><span>生成于 {dateText(data.generated_at)} · 模拟数据不会进入本页</span></div><Badge tone="green">LIVE DATA</Badge></div>
    <div className="analytics-toolbar"><div className="button-row"><RangeTabs value={range === "custom" ? null : range} onChange={selectRange} /><button type="button" className={`analytics-custom-range${range === "custom" ? " active" : ""}`} onClick={() => selectRange("custom")}>自定义</button></div><span>统计时区 Asia/Shanghai · 缺失不等于 0</span></div>
    {range === "custom" && <div className="analytics-custom-dates"><label>开始日期<input type="date" value={start} max={end || undefined} onChange={event => setCustomDate("start", event.target.value)} /></label><span>至</span><label>结束日期<input type="date" value={end} min={start || undefined} onChange={event => setCustomDate("end", event.target.value)} /></label><small>按本地自然日聚合，结束日期包含当天</small></div>}
    {error && <ErrorBox>{error}</ErrorBox>}

    <section className="analytics-section"><SectionTitle title={`${rangeTitle}生产与发布`} description="仅统计后台已核验发布，不把预览、失败或待核对记录算入" /><div className="analytics-metrics-grid four"><MetricCard accent label="原创内容" value={metrics.originals} hint="跨平台按来源去重" /><MetricCard label="发布条次" value={metrics.publications} hint="已核验平台发布记录" /><MetricCard label="文章" value={metrics.articles} hint="原创文章来源去重" /><MetricCard label="视频" value={metrics.videos} hint="原创视频来源去重" /></div></section>

    {!platform && <>
      <TrendChart title="已核验发布趋势" description={`${rangeTitle}发布条次；这是生产趋势，不是播放趋势`} labels={trend.labels} bars={trend.values} line={movingAverage} barLabel="发布条次" lineLabel="移动平均" />
      <section className="analytics-section"><SectionTitle title="传播与内容质量" description={hasPropagation ? "基于同内容 ID 的最近一次前后快照差值；首次基线不伪造新增" : "需要同内容、同指标的前后快照才能计算今日新增"} />{hasPropagation ? <div className="analytics-metrics-grid four"><MetricCard accent label="阅读 / 播放增量" value={numberText(metrics.reach)} hint="最近两次快照差值" /><MetricCard label="点赞增量" value={numberText(metrics.likes)} hint="同内容 ID 去重" /><MetricCard label="评论增量" value={numberText(metrics.comments)} hint="没有前值时不计算" /><MetricCard label="分享增量" value={numberText(metrics.shares)} hint="缺失不按 0 计算" /></div> : <Card><Empty title="暂无可计算的新增传播指标" description="当前账号快照主要是累计公开数据，不能与今日发布记录直接拼成新增播放。完成连续同步后，这里会展示阅读/播放、互动、完成率和真实趋势。" /></Card>}</section>
      <section className="analytics-section"><SectionTitle title="获客与业务结果" description="私信只存本机；有效、高意向和成交由你人工确认" /><LeadPanel leads={visibleLeads} metrics={metrics} contents={data.contents} /></section>
      <section className="analytics-section"><SectionTitle title="各平台数据拆分" description="发布为真实新增；快照为累计公开数据，两种口径不混算" /><Card className="analytics-table-card"><div className="analytics-table-scroll"><table className="analytics-table platform"><thead><tr><th>平台</th><th>原创</th><th>发布条次</th><th>累计点赞快照</th><th>累计评论快照</th><th>最近快照</th><th>竞对内容</th></tr></thead><tbody>{platformOrder.map(key => { const item = data.platforms[key]; const platformMetric = range === "custom" ? aggregateCustom(data.contents, leads, period, key) : item.metrics[range]; const count = data.competitor_analytics.items.filter(content => content.platform === key).length; return <tr key={key}><td><Link className="analytics-platform-link" to={`/accounts/${key}${query ? `?${query}` : ""}`}>{platformLabels[key]}<span>查看日报 →</span></Link></td><td>{platformMetric.originals}</td><td>{platformMetric.publications}</td><td>{numberText(item.snapshot?.totals.likes ?? null)}</td><td>{numberText(item.snapshot?.totals.comments ?? null)}</td><td>{dateText(item.snapshot?.captured_at)}</td><td>{count}</td></tr>; })}</tbody></table></div></Card></section>
    </>}

    {platform && <>
      <Card className="analytics-account-hero"><div className="analytics-account-identity"><span>{platformLabels[platform].slice(0, 1)}</span><div><Badge tone={snapshot ? "green" : "orange"}>{snapshot ? "真实累计快照" : "未同步"}</Badge><h2>{String(snapshot?.profile.account_name || `刘量 · ${platformLabels[platform]}`)}</h2><p>最近快照 {dateText(snapshot?.captured_at)} · 当前有 {competitorCount} 条竞对研究快照</p></div></div><Link className="button button-small" to="/competitors">查看真实竞对 <ExternalLink size={13} /></Link></Card>
      <section className="analytics-section"><SectionTitle title="账号累计公开快照" description="以下不是今日新增；只有明确读取到的指标才显示" /><div className="analytics-metrics-grid four"><MetricCard label="累计阅读 / 播放" value={numberText(snapshot?.totals.reach ?? null)} hint="无公开分母时保持未读取" /><MetricCard label="累计点赞" value={numberText(snapshot?.totals.likes ?? null)} hint="来自最近账号快照" /><MetricCard label="累计评论" value={numberText(snapshot?.totals.comments ?? null)} hint="不根据其他指标推算" /><MetricCard label="累计分享" value={numberText(snapshot?.totals.shares ?? null)} hint="平台未提供时保持未读取" /></div></section>
      <section className="analytics-section"><SectionTitle title="消费质量" description="平台未提供或未接入时不生成趋势" /><Card><Empty title="完成率与留存尚未接入" description="需要创作者后台质量指标。当前只展示可核验发布和累计公开快照。" /></Card></section>
      <section className="analytics-section"><SectionTitle title={`${platformLabels[platform]}私信与获客`} description="在本页面直接标注是否有效，不回写外部平台" /><LeadPanel leads={visibleLeads} metrics={metrics} contents={data.contents} platform={platform} /></section>
    </>}

    <section className="analytics-section"><SectionTitle title="真实内容记录" description={`${visibleContents.length} 条 · 已核验发布与账号公开快照分别标记`} action={<div className="analytics-view-tabs"><button type="button" className={contentMode === "published" ? "active" : ""} onClick={() => setContentMode("published")}>期间发布</button><button type="button" className={contentMode === "recorded" ? "active" : ""} onClick={() => setContentMode("recorded")}>期间有记录</button></div>} />{visibleContents.length ? <Card className="analytics-content-card"><div className="analytics-table-scroll"><table className="analytics-table"><thead><tr><th>内容</th><th>类型</th><th>记录时间</th><th>点赞快照</th><th>来源</th><th>原链接</th></tr></thead><tbody>{visibleContents.map(item => <tr key={item.id}><td><strong>{item.title}</strong><small>{platformLabels[item.platform]}</small></td><td>{item.kind === "article" ? "文章" : "视频"}</td><td>{dateText(item.published_at || item.captured_at)}</td><td>{numberText(item.metrics?.likes ?? null)}</td><td><Badge tone={item.verified ? "green" : "neutral"}>{item.verified ? "已核验发布" : "累计公开快照"}</Badge></td><td>{item.url ? <a className="analytics-row-action" href={item.url} target="_blank" rel="noreferrer" aria-label={`打开 ${item.title}`}><ExternalLink size={15} /></a> : "未读取"}</td></tr>)}</tbody></table></div></Card> : <Empty title="当前平台没有真实内容记录" description="可以先完成一次已核验发布，或同步真实账号快照。" />}</section>

    {!platform && <section className="analytics-section"><SectionTitle title="今天同步情况" description="四平台增量同步，失败不自动重试" /><div className="analytics-sync-grid">{data.sync.map(item => <Card className="analytics-sync-card" key={item.platform}><div><strong>{platformLabels[item.platform]}</strong><Badge tone={item.status === "succeeded" ? "green" : "orange"}>{item.status === "succeeded" ? "有快照" : "未接入"}</Badge></div><p>{item.detail}</p><small>{dateText(item.captured_at)}</small></Card>)}</div>{(data.errors || []).length > 0 && <div className="analytics-sync-errors">{data.errors.map((error, index) => <Card key={`${error.platform}-${error.captured_at}-${index}`}><Badge tone={error.type === "STRUCTURE_CHANGED" ? "orange" : "red"}>{error.type}</Badge><strong>{platformLabels[error.platform]}</strong><p>{error.message}</p><small>怎么改：{error.action} · {dateText(error.captured_at)}</small></Card>)}</div>}</section>}
    <DataBoundary>{data.data_boundaries.join(" ")}</DataBoundary>
  </div>;
}
