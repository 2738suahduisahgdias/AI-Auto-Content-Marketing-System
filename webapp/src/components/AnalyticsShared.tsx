import { useState } from "react";
import { ArrowUpRight, CheckCircle2, Database, Lightbulb, MessageSquareText } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge, Card, Modal } from "@/components/ui";
import { platformLabels, rangeLabels, syncStatuses, windowLabels, type ContentItem, type PlatformKey, type RangeKey, type WindowKey } from "@/lib/analyticsDemo";

export function numberText(value: number | null, suffix = "") {
  if (value === null) return "未读取";
  return `${new Intl.NumberFormat("zh-CN").format(value)}${suffix}`;
}

export function percentText(value: number | null) {
  return value === null ? "未读取" : `${(value * 100).toFixed(1)}%`;
}

export function DemoNotice({ coverage = "4 个平台演示快照" }: { coverage?: string }) {
  return <div className="analytics-demo-notice"><div><Database size={17} /><strong>产品演示 · 全部指标为模拟数据</strong><span>{coverage}，不会写入真实账号数据库</span></div><Badge tone="orange">DEMO DATA</Badge></div>;
}

export function RangeTabs({ value, onChange }: { value: RangeKey | null; onChange: (range: RangeKey) => void }) {
  return <div className="analytics-range-tabs" role="tablist" aria-label="日报时间范围">{(Object.keys(rangeLabels) as RangeKey[]).map(key => <button type="button" role="tab" aria-selected={value === key} className={value === key ? "active" : ""} key={key} onClick={() => onChange(key)}>{rangeLabels[key]}</button>)}</div>;
}

export function MetricCard({ label, value, hint, accent = false }: { label: string; value: string | number; hint: string; accent?: boolean }) {
  return <Card className={`analytics-metric${accent ? " accent" : ""}`}><span>{label}</span><strong>{value}</strong><small>{hint}</small></Card>;
}

export function SectionTitle({ title, description, action }: { title: string; description?: string; action?: React.ReactNode }) {
  return <div className="section-heading"><div><h2>{title}</h2>{description && <p>{description}</p>}</div>{action}</div>;
}

export function ContentPerformance({ items, onSelect, initialMode = "reach" }: { items: ContentItem[]; onSelect: (item: ContentItem) => void; initialMode?: "reach" | "quality" | "business" }) {
  const [mode, setMode] = useState(initialMode);
  const sorted = [...items].sort((a, b) => mode === "quality" ? (b.metrics.completionRate ?? -1) - (a.metrics.completionRate ?? -1) : mode === "business" ? b.metrics.qualifiedLeads - a.metrics.qualifiedLeads : (b.metrics.reach ?? -1) - (a.metrics.reach ?? -1));
  return <Card className="analytics-content-card"><div className="analytics-content-head"><div className="analytics-view-tabs" role="tablist" aria-label="内容排序视角">{([{ key: "reach", label: "传播最好" }, { key: "quality", label: "内容最扎实" }, { key: "business", label: "业务价值最高" }] as const).map(item => <button type="button" role="tab" aria-selected={mode === item.key} className={mode === item.key ? "active" : ""} key={item.key} onClick={() => setMode(item.key)}>{item.label}</button>)}</div><span>发布后同窗口比较</span></div><div className="analytics-table-scroll"><table className="analytics-table"><thead><tr><th>内容</th><th>阅读 / 播放</th><th>完成率</th><th>互动率</th><th>有效线索</th><th>观察</th></tr></thead><tbody>{sorted.map(item => <tr key={item.id}><td><button type="button" className="analytics-content-link" onClick={() => onSelect(item)}>{item.title}</button><small>{platformLabels[item.platform]} · {item.kind} · {item.publishedAt}</small></td><td>{numberText(item.metrics.reach)}</td><td>{percentText(item.metrics.completionRate)}</td><td>{percentText(item.metrics.engagementRate)}</td><td>{item.metrics.qualifiedLeads}</td><td><button type="button" className="analytics-row-action" aria-label={`分析 ${item.title}`} onClick={() => onSelect(item)}><ArrowUpRight size={16} /></button></td></tr>)}</tbody></table></div></Card>;
}

export function ContentDetail({ item, onClose }: { item: ContentItem; onClose: () => void }) {
  const [window, setWindow] = useState<WindowKey>("24h");
  return <Modal open onOpenChange={open => { if (!open) onClose(); }} title={item.title} description={`${platformLabels[item.platform]} · ${item.kind} · 演示数据`} wide><div className="analytics-detail-meta"><Badge tone="blue">{item.pillar}</Badge><Badge>{item.duration}</Badge><Badge tone="orange">模拟指标</Badge></div><div className="analytics-window-row"><strong>观察窗口</strong><div className="analytics-view-tabs">{(Object.keys(windowLabels) as WindowKey[]).map(key => <button type="button" className={window === key ? "active" : ""} key={key} onClick={() => setWindow(key)}>{windowLabels[key]}</button>)}</div></div><div className="analytics-detail-metrics"><MetricCard label="阅读 / 播放" value={numberText(item.windows[window].reach)} hint="公开内容消费次数" /><MetricCard label="可见互动" value={numberText(item.windows[window].interactions)} hint="点赞、评论、分享、收藏" /><MetricCard label="有效线索" value={item.metrics.qualifiedLeads} hint="人工确认 · 演示" /></div><div className="analytics-detail-grid"><Card><h3>消费留存示例</h3><p className="analytics-muted">用于确认留存曲线的信息层级，并非真实平台读取结果。</p><div className="analytics-retention">{item.retention.map((value, index) => <div key={index}><span style={{ height: `${value}%` }} /><small>{index === 0 ? "0s" : `${index * 15}s`}</small><b>{value}%</b></div>)}</div></Card><Card><h3><MessageSquareText size={16} /> 评论与需求证据</h3>{item.comments.map(comment => <blockquote key={comment}>{comment}<small>AI 需求识别 · 演示样本</small></blockquote>)}</Card></div><div className="analytics-recommendation"><Lightbulb size={19} /><div><strong>内容诊断</strong><p>{item.insight}</p><strong>下一条怎么改</strong><p>{item.suggestion}</p></div></div></Modal>;
}

export function InsightPanel({ platform }: { platform?: PlatformKey }) {
  const title = platform ? `${platformLabels[platform]}专属洞察` : "今日综合洞察";
  return <Card className="analytics-insight-panel"><div className="analytics-insight-head"><Lightbulb size={19} /><h2>{title}</h2><Badge tone="orange">演示结论</Badge></div><div className="analytics-insight-row"><Badge tone="blue">事实</Badge><p>{platform === "xiaohongshu" ? "清单型内容的收藏率与有效咨询高于其他内容。" : platform === "wechat_official_account" ? "长文的阅读完成度稳定，分享是主要传播方式。" : "流程图和真实项目验收内容获得更高的收藏与分享。"}</p></div><div className="analytics-insight-row"><Badge>推断</Badge><p>用户更需要可以直接套用的流程、模板和验收证据，而非泛化的工具介绍。</p></div><div className="analytics-insight-row"><Badge tone="green">建议</Badge><p>下一条保留同一核心方法，用一个具体行业案例复测，并在前 5 秒展示最终结果。</p></div><small>推断基于演示样本；真实版会显示样本量、证据和可信度。</small></Card>;
}

export function SyncOverview({ compact = false }: { compact?: boolean }) {
  return <div className={`analytics-sync-grid${compact ? " compact" : ""}`}>{syncStatuses.map(item => <Card className="analytics-sync-card" key={item.platform}><div><strong>{platformLabels[item.platform]}</strong><Badge tone={item.status === "成功" ? "green" : item.status === "部分成功" ? "orange" : "neutral"}>{item.status}</Badge></div><p>{item.detail}</p><small>{item.time}</small></Card>)}</div>;
}

export function CompetitorTeaser({ platform }: { platform: PlatformKey }) {
  return <Card className="analytics-competitor-teaser"><div><p className="eyebrow">PUBLIC BENCHMARK</p><h2>我的表现 vs {platformLabels[platform]}竞对</h2><p>只比较公开可见互动、更新频率和爆款率，不推测竞对播放或完播。</p></div><div className="analytics-benchmark-values"><span><small>我的互动中位数</small><strong>902</strong></span><span><small>竞对组中位数</small><strong>{platform === "xiaohongshu" ? "1,680" : platform === "douyin" ? "1,090" : "590"}</strong></span><span><small>我的爆款率</small><strong>25.0%</strong></span></div><Link className="button button-small" to="/competitors">查看竞对分析 <ArrowUpRight size={14} /></Link></Card>;
}

export function DataBoundary({ children }: { children: React.ReactNode }) {
  return <div className="analytics-data-boundary"><CheckCircle2 size={16} /><p>{children}</p></div>;
}
