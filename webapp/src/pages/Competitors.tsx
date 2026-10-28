import { useMemo, useState } from "react";
import { ArrowUpRight, Crosshair, Search, UsersRound } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { Badge, Card, Modal, PageHeader } from "@/components/ui";
import RealCompetitors from "@/pages/RealCompetitors";
import { DataBoundary, DemoNotice, MetricCard, SectionTitle, numberText, percentText } from "@/components/AnalyticsShared";
import { competitorAccounts, competitorContents, competitorGroups, myPublicBenchmark, platformLabels, platformOrder, visibleInteractions, type CompetitorContent, type PlatformKey } from "@/lib/analyticsDemo";
import "./Analytics.css";

function DemoCompetitors() {
  const [platform, setPlatform] = useState<"all" | PlatformKey>("all");
  const [group, setGroup] = useState<(typeof competitorGroups)[number]>("全部");
  const [account, setAccount] = useState<string | null>(null);
  const [sort, setSort] = useState<"interactions" | "followers">("interactions");
  const [selected, setSelected] = useState<CompetitorContent | null>(null);
  const accounts = useMemo(() => competitorAccounts.filter(item => (platform === "all" || item.platform === platform) && (group === "全部" || item.group === group) && (!account || item.id === account)), [platform, group, account]);
  const accountIds = new Set(accounts.map(item => item.id));
  const items = competitorContents.filter(item => accountIds.has(item.accountId)).sort((a, b) => sort === "interactions" ? visibleInteractions(b) - visibleInteractions(a) : b.followersSnapshot - a.followersSnapshot);
  const median = accounts.length ? Math.round(accounts.reduce((sum, item) => sum + item.medianInteractions, 0) / accounts.length) : 0;
  const selectedAccount = selected ? competitorAccounts.find(item => item.id === selected.accountId) : null;

  function resetAccount() { setAccount(null); }

  return <div className="analytics-page competitor-page">
    <PageHeader eyebrow="PUBLIC COMPETITOR INTELLIGENCE" title="竞对分析" description="用公开口径研究账号、内容和选题。竞对数据不计入自己的传播总量，也不推测不可见指标。" actions={<Badge tone="orange">公开数据 Demo</Badge>} />
    <DemoNotice coverage="8 个竞对账号 · 8 条公开内容样本" />
    <div className="competitor-filter-bar"><div className="analytics-view-tabs" role="tablist" aria-label="竞对平台筛选"><button type="button" role="tab" aria-selected={platform === "all"} className={platform === "all" ? "active" : ""} onClick={() => { setPlatform("all"); resetAccount(); }}>全部平台</button>{platformOrder.map(key => <button type="button" role="tab" aria-selected={platform === key} className={platform === key ? "active" : ""} key={key} onClick={() => { setPlatform(key); resetAccount(); }}>{platformLabels[key]}</button>)}</div><label className="competitor-group-filter"><span>竞对分组</span><select value={group} onChange={event => { setGroup(event.target.value as (typeof competitorGroups)[number]); resetAccount(); }}>{competitorGroups.map(item => <option key={item}>{item}</option>)}</select></label></div>
    {account && <div className="competitor-active-filter">正在查看：{competitorAccounts.find(item => item.id === account)?.name}<button type="button" onClick={resetAccount}>清除账号筛选</button></div>}

    <section className="analytics-section"><SectionTitle title="公开口径基准" description={`当前筛选 ${accounts.length} 个账号 · ${items.length} 条内容；同平台比较才有意义`} /><div className="analytics-metrics-grid four"><MetricCard accent label="我的单篇互动中位数" value={myPublicBenchmark.medianInteractions} hint="公开口径 · 相同观察窗口" /><MetricCard label="竞对组互动中位数" value={median} hint="按当前账号样本计算" /><MetricCard label="我的更新频率" value={`${myPublicBenchmark.postingFrequency} 条/周`} hint={`竞对组 ${(accounts.reduce((sum, item) => sum + item.posts30d, 0) / Math.max(accounts.length, 1) / 30 * 7).toFixed(1)} 条/周`} /><MetricCard label="我的爆款率" value={percentText(myPublicBenchmark.hitRate)} hint="超过竞对组 P75 的内容占比" /></div></section>

    <section className="analytics-section"><SectionTitle title="竞对账号" description="点击账号可下钻；粉丝增长来自连续公开快照" /><div className="competitor-account-grid">{accounts.map(item => <button type="button" className={`competitor-account-card${account === item.id ? " active" : ""}`} key={item.id} onClick={() => setAccount(account === item.id ? null : item.id)}><div className="competitor-account-head"><span>{item.name.slice(0, 1)}</span><div><strong>{item.name}</strong><small>{platformLabels[item.platform]} · {item.group}</small></div><Badge tone={item.completeness === "完整" ? "green" : "orange"}>{item.completeness}</Badge></div><div className="competitor-account-stats"><span><small>粉丝</small><strong>{numberText(item.followers)}</strong></span><span><small>30 天涨粉</small><strong>+{numberText(item.followerGrowth)}</strong></span><span><small>互动中位数</small><strong>{numberText(item.medianInteractions)}</strong></span></div></button>)}</div>{!accounts.length && <Card>当前筛选没有竞对账号，请调整平台或分组。</Card>}</section>

    <section className="analytics-section"><SectionTitle title="竞对内容库" description="只展示公开可见互动；缺失字段不参与对应比率" action={<label className="competitor-sort">排序<select value={sort} onChange={event => setSort(event.target.value as typeof sort)}><option value="interactions">可见互动</option><option value="followers">发布时粉丝快照</option></select></label>} /><div className="competitor-content-grid">{items.map(item => { const owner = competitorAccounts.find(accountItem => accountItem.id === item.accountId)!; return <Card className="competitor-content-card" key={item.id}><div className="competitor-content-top"><Badge tone="blue">{owner.group}</Badge><Badge>{item.observationWindow} 观察</Badge></div><h3>{item.title}</h3><p>{owner.name} · {platformLabels[owner.platform]} · {item.publishedAt}</p><div className="competitor-content-metrics"><span><strong>{numberText(visibleInteractions(item))}</strong><small>可见互动</small></span><span><strong>{numberText(item.likes)}</strong><small>点赞</small></span><span><strong>{item.favorites === null ? "—" : numberText(item.favorites)}</strong><small>收藏</small></span></div><div className="competitor-content-foot"><span>{item.format} · {item.topic}</span><button type="button" aria-label={`研究 ${item.title}`} onClick={() => setSelected(item)}>研究内容 <ArrowUpRight size={14} /></button></div></Card>; })}</div></section>

    <div className="competitor-insight-grid"><Card><Crosshair size={20} /><p className="eyebrow">TOPIC OPPORTUNITY</p><h2>值得差异化跟进</h2><ul><li>企业 AI 验收：竞对强调清单，你可以补充真实项目证据。</li><li>FDE 第一周：讨论度高，适合拆解成连续实操内容。</li><li>试点失败复盘：收藏表现好，可用你的真实案例形成差异。</li></ul></Card><Card><Search size={20} /><p className="eyebrow">CONTENT PATTERN</p><h2>近期高反馈结构</h2><ul><li>明确企业规模或岗位，降低适用性判断成本。</li><li>反常识开头后，立即给出清单或结果。</li><li>真实数量、失败决策与业务结果增强可信度。</li></ul></Card></div>
    <DataBoundary>公开数据完整度分为完整、部分、有限；竞对播放、完播、咨询与成交没有公开证据时不显示。演示页面不执行下载、拆解或同步。</DataBoundary>

    {selected && <Modal open onOpenChange={open => { if (!open) setSelected(null); }} title={selected.title} description={`${selectedAccount?.name} · ${platformLabels[selectedAccount!.platform]} · 公开数据 Demo`} wide><div className="competitor-detail-layout"><div><div className="analytics-detail-meta"><Badge tone="blue">{selected.topic}</Badge><Badge>{selected.format}</Badge><Badge tone="orange">{selected.completeness}数据</Badge></div><div className="analytics-detail-metrics"><MetricCard label="点赞" value={selected.likes} hint="公开快照" /><MetricCard label="评论" value={selected.comments} hint="公开快照" /><MetricCard label="可见互动" value={visibleInteractions(selected)} hint={`${selected.observationWindow} 观察窗口`} /></div><div className="competitor-public-fields"><p>分享：<strong>{selected.shares ?? "未读取"}</strong></p><p>收藏：<strong>{selected.favorites ?? "未读取"}</strong></p><p>粉丝快照：<strong>{numberText(selected.followersSnapshot)}</strong></p><p>播放 / 完播：<strong>无公开数据，不推测</strong></p></div></div><Card className="competitor-detail-insight"><UsersRound size={20} /><h3>策略拆解</h3><p>{selected.insight}</p><h3>我的差异化方向</h3><p>保留用户明确关心的问题，用真实企业场景、操作过程与验收证据替换泛化观点。</p><Link className="button button-small" to={`/accounts/${selectedAccount!.platform}`}>查看我的{platformLabels[selectedAccount!.platform]}日报 <ArrowUpRight size={14} /></Link></Card></div></Modal>}
  </div>;
}

export default function Competitors() {
  const [searchParams] = useSearchParams();
  return searchParams.get("demo") === "1" ? <DemoCompetitors /> : <RealCompetitors />;
}
