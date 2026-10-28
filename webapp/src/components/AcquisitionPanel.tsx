import { ArrowRight, CircleDollarSign, Filter, UserCheck } from "lucide-react";
import { Badge, Card } from "@/components/ui";
import { SectionTitle, numberText } from "@/components/AnalyticsShared";
import { TrendChart } from "@/components/TrendChart";
import { acquisitionTrend, contents, leadSamples, platformLabels, platformMetrics, platformOrder, rangeLabels, totalMetrics, type RangeKey } from "@/lib/analyticsDemo";

export function AcquisitionPanel({ metrics, range }: { metrics: ReturnType<typeof totalMetrics>; range: RangeKey }) {
  const meetings = Math.round(metrics.highIntentLeads * .625);
  const stages = [
    { label: "私信咨询", value: metrics.inquiries, note: "主动询问，不代表符合画像" },
    { label: "有效线索", value: metrics.qualifiedLeads, note: "目标用户 + 明确业务需求" },
    { label: "高意向线索", value: metrics.highIntentLeads, note: "有项目计划、预算或合作意向" },
    { label: "深度沟通", value: meetings, note: "已进入会议、诊断或方案讨论" },
    { label: "成交", value: metrics.deals, note: "人工确认签约或付费" },
  ];
  const topContent = [...contents].sort((a, b) => b.metrics.qualifiedLeads - a.metrics.qualifiedLeads).slice(0, 3);

  return <section className="analytics-section acquisition-panel"><SectionTitle title="获客与业务结果" description="从咨询到成交逐级看质量；所有业务结果均为人工确认的演示数据" action={<Badge tone="blue">人工确认 · Demo</Badge>} />
    <div className="acquisition-summary-grid"><Card className="acquisition-funnel-card"><div className="acquisition-card-head"><div><Filter size={18} /><h3>线索漏斗</h3></div><span>{rangeLabels[range]} · 逐级转化率</span></div><div className="acquisition-funnel">{stages.map((stage, index) => { const previous = stages[index - 1]; const conversion = previous && previous.value ? `${(stage.value / previous.value * 100).toFixed(1)}%` : "100%"; return <div className="acquisition-stage" key={stage.label}><div className="acquisition-stage-label"><span>{stage.label}</span><small>{stage.note}</small></div><div className="acquisition-stage-bar"><span style={{ width: `${Math.max(10, stage.value / Math.max(metrics.inquiries, 1) * 100)}%` }} /><strong>{stage.value}</strong></div><Badge tone={index === stages.length - 1 ? "green" : "neutral"}>{conversion}</Badge></div>; })}</div><details className="acquisition-definition"><summary>线索判定标准与归因边界</summary><p><strong>有效线索：</strong>符合企业主、AI 从业者或 FDE 画像，并主动说明真实场景或问题。</p><p><strong>高意向线索：</strong>进一步表达项目周期、预算、采购或合作计划。</p><p>AI 只辅助分类，有效线索和成交必须人工确认；无法确认内容来源的咨询计入“未归因”，不分摊给内容。</p></details></Card>
      <Card className="acquisition-result-card"><CircleDollarSign size={21} /><span>确认成交金额</span><strong>¥{numberText(metrics.deals * 19900)}</strong><p>{metrics.deals} 笔成交 · 演示客单价 ¥19,900</p><div><span>咨询 → 有效 <strong>{metrics.inquiries ? percent(metrics.qualifiedLeads / metrics.inquiries) : "—"}</strong></span><span>有效 → 高意向 <strong>{metrics.qualifiedLeads ? percent(metrics.highIntentLeads / metrics.qualifiedLeads) : "—"}</strong></span><span>高意向 → 成交 <strong>{metrics.highIntentLeads ? percent(metrics.deals / metrics.highIntentLeads) : "—"}</strong></span></div><small>成交受跟进、报价和交付影响，不能全部归因于内容。</small></Card></div>
    <TrendChart title="有效咨询与高意向线索趋势" description="按周汇总，避免单日稀疏数据造成误判；柱形为有效线索，折线为高意向线索" labels={acquisitionTrend.labels} bars={acquisitionTrend.qualified} line={acquisitionTrend.highIntent} barLabel="有效线索" lineLabel="高意向线索" compact />
    <div className="acquisition-detail-grid"><Card><div className="acquisition-card-head"><div><UserCheck size={18} /><h3>平台线索来源</h3></div><span>有效线索 / 私信咨询</span></div><div className="acquisition-source-list">{platformOrder.map(platform => { const item = platformMetrics[platform][range]; return <div key={platform}><span>{platformLabels[platform]}</span><strong>{item.qualifiedLeads}<small> / {item.inquiries}</small></strong><div><i style={{ width: `${item.inquiries ? item.qualifiedLeads / item.inquiries * 100 : 0}%` }} /></div><Badge tone={platform === "xiaohongshu" ? "green" : "neutral"}>{item.inquiries ? percent(item.qualifiedLeads / item.inquiries) : "—"}</Badge></div>; })}</div></Card>
      <Card><div className="acquisition-card-head"><div><ArrowRight size={18} /><h3>内容线索贡献</h3></div><span>按有效线索排序</span></div><div className="acquisition-content-list">{topContent.map((item, index) => <div key={item.id}><span>{index + 1}</span><div><strong>{item.title}</strong><small>{platformLabels[item.platform]} · {item.publishedAt}</small></div><b>{item.metrics.qualifiedLeads} 条</b></div>)}</div></Card></div>
    <Card className="acquisition-leads-card"><div className="acquisition-card-head"><div><UserCheck size={18} /><h3>最近线索样例</h3></div><span>匿名演示 · 保留原始需求证据</span></div><div className="acquisition-lead-list">{leadSamples.map(lead => <article key={lead.id}><div><Badge tone={lead.level === "有效线索" ? "blue" : "green"}>{lead.level}</Badge><strong>{lead.profile}</strong><small>{platformLabels[lead.platform]} · 来源：{lead.content}</small></div><p>“{lead.need}”</p></article>)}</div></Card>
  </section>;
}

function percent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}
