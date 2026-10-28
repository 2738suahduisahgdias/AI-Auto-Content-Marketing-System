import { useState } from "react";
import { BarChart3, BookOpen, Eye } from "lucide-react";
import { Link, Navigate, useParams, useSearchParams } from "react-router-dom";
import { Badge, Card, PageHeader } from "@/components/ui";
import RealAccountAnalytics from "@/pages/RealAccountAnalytics";
import { AcquisitionPanel } from "@/components/AcquisitionPanel";
import { CompetitorTeaser, ContentDetail, ContentPerformance, DataBoundary, DemoNotice, InsightPanel, MetricCard, RangeTabs, SectionTitle, SyncOverview, numberText, percentText } from "@/components/AnalyticsShared";
import { TrendChart } from "@/components/TrendChart";
import { contents, overviewReachTrend, platformLabels, platformMetrics, platformOrder, platformTrends, rangeLabels, syncStatuses, totalMetrics, type ContentItem, type PlatformKey, type RangeKey } from "@/lib/analyticsDemo";
import "./Analytics.css";

const platformViews: PlatformKey[] = ["douyin", "wechat_channels", "xiaohongshu", "wechat_official_account"];
const nativeMetrics: Record<PlatformKey, { label: string; value: string }[]> = {
  douyin: [{ label: "3 秒留存", value: "76.8%" }, { label: "5 秒留存", value: "68.2%" }, { label: "复播率", value: "8.4%" }, { label: "平均观看", value: "47 秒" }],
  wechat_channels: [{ label: "推荐 / 点赞", value: "482" }, { label: "分享率", value: "1.54%" }, { label: "关注转化", value: "0.30%" }, { label: "平均观看", value: "52 秒" }],
  xiaohongshu: [{ label: "封面点击率", value: "11.8%" }, { label: "搜索流量占比", value: "32.4%" }, { label: "收藏率", value: "7.82%" }, { label: "平均阅读", value: "68 秒" }],
  wechat_official_account: [{ label: "阅读完成率", value: "38.6%" }, { label: "分享率", value: "3.19%" }, { label: "读完关注率", value: "0.49%" }, { label: "平均阅读", value: "126 秒" }],
};

function DemoAccountAnalytics() {
  const { view = "overview" } = useParams();
  const [range, setRange] = useState<RangeKey>("today");
  const [selected, setSelected] = useState<ContentItem | null>(null);
  if (view !== "overview" && !platformViews.includes(view as PlatformKey)) return <Navigate to="/accounts" replace />;
  const platform = view === "overview" ? null : view as PlatformKey;
  const total = totalMetrics(range);
  const metrics = platform ? platformMetrics[platform][range] : total;
  const visibleContents = platform ? contents.filter(item => item.platform === platform) : contents;
  const title = platform ? `${platformLabels[platform]}日报` : "日报总览";

  return <div className="analytics-page">
    <PageHeader eyebrow={platform ? `${platformLabels[platform]} PERFORMANCE` : "ACCOUNT DAILY BRIEF"} title={title} description={platform ? "从平台原生指标到内容质量与业务结果，定位下一条内容的优化方向。" : "把生产、传播、内容质量和获客放在同一口径下，先看整体，再下钻平台与内容。"} actions={<Badge tone="orange">交互 Demo</Badge>} />
    <DemoNotice coverage={platform ? `${platformLabels[platform]}账号与内容演示快照` : "4 个平台 · 5 条发布条次 · 5 条原创内容"} />
    <div className="analytics-toolbar"><RangeTabs value={range} onChange={setRange} /><span>统计时区 Asia/Shanghai · 对比昨日同时间</span></div>

    {!platform && <>
      <section className="analytics-section"><SectionTitle title={`${rangeLabels[range]}生产了多少`} description="原创内容去重，跨平台分发按发布条次另算" /><div className="analytics-metrics-grid four"><MetricCard accent label="原创内容" value={metrics.originals} hint="4 个主题方向" /><MetricCard label="发布条次" value={metrics.publications} hint="覆盖 4 个平台" /><MetricCard label="文章" value={Math.round(metrics.originals * .4)} hint="小红书图文 · 公众号" /><MetricCard label="视频" value={metrics.originals - Math.round(metrics.originals * .4)} hint="抖音 · 视频号 · 小红书" /></div></section>
      <section className="analytics-section"><SectionTitle title="整体传播怎么样" description="阅读与播放合并；缺失指标不按 0 计算" /><div className="analytics-metrics-grid four"><MetricCard accent label="阅读 / 播放" value={numberText(metrics.reach)} hint="4/4 平台覆盖 · 较昨日 +12.6%" /><MetricCard label="点赞" value={numberText(metrics.likes)} hint="4/4 平台覆盖" /><MetricCard label="评论" value={numberText(metrics.comments)} hint="有效评论 68 · AI 演示" /><MetricCard label="分享" value={numberText(metrics.shares)} hint="4/4 平台覆盖" /></div></section>
      <TrendChart title="阅读 / 播放趋势" description="柱形为每日内容消费次数，折线为 7 日移动平均；标记变化但不自动归因" labels={overviewReachTrend.labels} bars={overviewReachTrend.values} line={overviewReachTrend.values.map((_, index, values) => { const window = values.slice(Math.max(0, index - 6), index + 1); return Math.round(window.reduce((sum, value) => sum + value, 0) / window.length); })} barLabel="每日阅读 / 播放" lineLabel="7 日移动平均" />
      <section className="analytics-section"><Card><div className="analytics-card-title"><BarChart3 size={18} /><h2>内容质量</h2><Badge>系统计算</Badge></div><div className="analytics-quality-list"><div><span>平均观看 / 阅读</span><strong>{numberText(metrics.avgConsumptionSeconds, " 秒")}</strong></div><div><span>平均完成率</span><strong>{percentText(metrics.completionRate)}</strong></div><div><span>综合互动率</span><strong>{percentText(metrics.engagementRate)}</strong></div><div><span>收藏</span><strong>{numberText(metrics.favorites)}</strong><small>视频号未提供 · 不按 0 计入</small></div></div></Card></section>
      <AcquisitionPanel metrics={metrics} range={range} />
      <section className="analytics-section"><SectionTitle title="各平台数据拆分" description="点击进入平台详情；竞对数据不计入这些总量" /><Card className="analytics-table-card"><div className="analytics-table-scroll"><table className="analytics-table platform"><thead><tr><th>平台</th><th>发布条次</th><th>阅读 / 播放</th><th>互动</th><th>完成率</th><th>新增关注</th><th>有效咨询</th><th>同步</th></tr></thead><tbody>{platformOrder.map(key => { const item = platformMetrics[key][range]; const sync = syncStatuses.find(status => status.platform === key)!; return <tr key={key}><td><Link className="analytics-platform-link" to={`/accounts/${key}`}>{platformLabels[key]}<span>查看日报 →</span></Link></td><td>{item.publications}</td><td>{numberText(item.reach)}</td><td>{numberText((item.likes ?? 0) + (item.comments ?? 0) + (item.shares ?? 0))}</td><td>{percentText(item.completionRate)}</td><td>{numberText(item.newFollowers)}</td><td>{item.qualifiedLeads}</td><td><Badge tone={sync.status === "成功" ? "green" : "orange"}>{sync.status}</Badge></td></tr>; })}</tbody></table></div></Card></section>
      <section className="analytics-section"><SectionTitle title="今日内容表现" description="传播、内容质量与业务价值分开排名" /><ContentPerformance items={visibleContents} onSelect={setSelected} /></section>
      <div className="analytics-two-columns"><section><SectionTitle title="今天同步得怎么样" description="失败与缺失必须可见" /><SyncOverview compact /></section><InsightPanel /></div>
    </>}

    {platform && <>
      <Card className="analytics-account-hero"><div className="analytics-account-identity"><span>{platformLabels[platform].slice(0, 1)}</span><div><Badge tone="green">账号演示快照</Badge><h2>刘量 · {platformLabels[platform]}</h2><p>粉丝 86,420 · 今日净增 {numberText(metrics.newFollowers)} · 最近同步 09:30</p></div></div><div className="analytics-account-position"><Eye size={19} /><span>当前内容策略<strong>{platform === "xiaohongshu" ? "搜索长尾 + 清单收藏" : platform === "wechat_official_account" ? "深度信任 + 方法沉淀" : "真实案例 + 口播方法"}</strong></span></div></Card>
      <section className="analytics-section"><SectionTitle title="平台核心指标" description="今日新增与账号累计值分层展示" /><div className="analytics-metrics-grid four"><MetricCard accent label="阅读 / 播放" value={numberText(metrics.reach)} hint="今日新增 · 演示" /><MetricCard label="互动总量" value={numberText((metrics.likes ?? 0) + (metrics.comments ?? 0) + (metrics.shares ?? 0) + (metrics.favorites ?? 0))} hint="点赞 · 评论 · 分享 · 收藏" /><MetricCard label="主页访问" value={numberText(metrics.profileVisits)} hint={metrics.profileVisits === null ? "平台未提供，不补零" : "账号后台原始指标"} /><MetricCard label="新增关注" value={numberText(metrics.newFollowers)} hint="净增关注单独保存" /></div></section>
      <section className="analytics-section"><SectionTitle title="趋势判断" description="分发规模与内容吸引力分开看，不使用双轴混淆口径" /><div className="platform-trend-grid"><TrendChart compact title="阅读 / 播放趋势" description="每日量与 7 日移动平均" labels={platformTrends[platform].labels} bars={platformTrends[platform].reach} line={platformTrends[platform].reach.map((_, index, values) => { const window = values.slice(Math.max(0, index - 6), index + 1); return Math.round(window.reduce((sum, value) => sum + value, 0) / window.length); })} barLabel="每日阅读 / 播放" lineLabel="7 日移动平均" /><TrendChart compact title="互动率趋势" description="互动总量 ÷ 阅读 / 播放；真实版展示分子分母" labels={platformTrends[platform].labels} line={platformTrends[platform].engagement} lineLabel="互动率" format="percent" /></div></section>
      <section className="analytics-section"><SectionTitle title="消费与互动质量" description={`${platformLabels[platform]}原生指标，不强行套用到其他平台`} /><div className="analytics-native-grid">{nativeMetrics[platform].map(item => <Card key={item.label}><BookOpen size={16} /><span>{item.label}</span><strong>{item.value}</strong><small>平台原始 / 系统计算 · Demo</small></Card>)}</div><div className="analytics-rate-row"><span>完成率 <strong>{percentText(metrics.completionRate)}</strong></span><span>互动率 <strong>{percentText(metrics.engagementRate)}</strong></span><span>平均消费 <strong>{numberText(metrics.avgConsumptionSeconds, " 秒")}</strong></span><span>有效咨询 <strong>{metrics.qualifiedLeads}</strong></span></div></section>
      <CompetitorTeaser platform={platform} />
      <section className="analytics-section"><SectionTitle title={`${platformLabels[platform]}内容表现`} description="点击标题查看留存、评论证据和修改建议" /><ContentPerformance items={visibleContents} onSelect={setSelected} initialMode={platform === "xiaohongshu" ? "quality" : "reach"} /></section>
      <InsightPanel platform={platform} />
      <DataBoundary>{platform === "wechat_channels" ? "收藏、主页访问等平台未读取字段保持为空；竞对比较不推算播放与完播。" : "当前所有数字只用于产品 Demo。真实版将区分平台原始、系统计算、AI 识别和人工确认。"}</DataBoundary>
    </>}
    {selected && <ContentDetail key={selected.id} item={selected} onClose={() => setSelected(null)} />}
  </div>;
}

export default function AccountAnalytics() {
  const [searchParams] = useSearchParams();
  return searchParams.get("demo") === "1" ? <DemoAccountAnalytics /> : <RealAccountAnalytics />;
}
