import { useEffect, useState } from "react";
import { ExternalLink, RefreshCw } from "lucide-react";
import { useApp } from "@/AppContext";
import { Badge, Button, Card, Empty, ErrorBox, PageHeader, Progress } from "@/components/ui";
import { api, errorText, formatNumber, jsonOptions } from "@/lib/api";
import { jobStatusNames, metricLabels, platformNames } from "@/lib/names";
import type { Job, Json } from "@/lib/types";
import "./Accounts.css";

const platforms = ["douyin", "wechat_channels", "xiaohongshu", "wechat_official_account"];
const activeStatuses = ["queued", "leased", "running", "retry_wait"];
const accountJobNames: Record<string, string> = { "accounts.sync": "同步账号快照", "accounts.recommend": "账号分析 Agent", "accounts.daily": "每日账号分析", "accounts.login": "平台登录窗口（5 分钟）" };
const extraMetricLabels: Record<string, string> = { ...metricLabels, total_likes: "累计获赞", works_count: "作品数", content_manager_total: "内容管理总数", total_likes_and_favorites: "获赞与收藏", published_notes_count: "已发布笔记", videos_count: "视频数", original_content_count: "原创内容", total_publications: "总发表", exposures: "曝光", heart_reactions: "心形反应", thumb_reactions: "拇指反应", favorites: "收藏", net_new_followers: "净增关注", new_heart_reactions: "新增心形反应", new_comments: "新增评论", new_views: "新增观看" };
const ignoredMetrics = new Set(["account_name", "biography", "biography_is_truncated", "period_start", "period_end", "date", "connection"]);

function AccountJobs({ jobs }: { jobs: Job[] }) {
  if (!jobs.length) return <Empty title="还没有账号后台任务" description="同步或推荐后，这里会显示持久任务状态与具体错误。" />;
  return <div className="account-jobs">{jobs.slice(0, 8).map(job => {
    const partialErrors = Object.entries(job.result?.accounts || {}).filter(([key]) => key.endsWith("_error"));
    return <article className="account-job" key={job.id}><div className="account-job-head"><div><strong>{accountJobNames[job.kind] || job.kind}</strong><small>{job.stage || job.status} · {job.created_at}</small></div><Badge tone={job.status === "succeeded" && !partialErrors.length ? "green" : job.error || ["failed", "unknown_remote"].includes(job.status) ? "red" : "orange"}>{jobStatusNames[job.status] || job.status}</Badge></div>{activeStatuses.includes(job.status) && <Progress value={job.progress ?? 0} />}{job.error && Object.keys(job.error).length > 0 && <p className="account-job-issue">{job.error.message || job.error.code}{job.error.action ? `\n怎么改：${job.error.action}` : ""}</p>}{partialErrors.map(([key, value]) => <p className="account-job-issue" key={key}>部分失败：{key} · {String(value)}<br />怎么改：在专用窗口登录对应平台后重试；其他平台快照仍可使用。</p>)}</article>;
  })}</div>;
}

function ContentTable({ account, automated }: { account: Json | null; automated: Json | null }) {
  const historical = account?.content_items || [];
  const latest = automated?.items || [];
  const rows = latest.length ? latest : historical;
  const platform = automated?.platform || account?.platform || "douyin";
  const metricKeys = platform === "wechat_official_account" ? ["readers", "likes", "comments", "shares"] : platform === "wechat_channels" ? ["views", "heart_reactions", "comments", "shares"] : ["views", "likes", "comments", "shares"];
  if (!rows.length) return <Empty title="没有可展示的公开内容" description="私密、仅自己可见或未通过内容不进入对比；未读取的指标保持为空。" />;
  return <Card className="account-table-card"><table className="account-data-table"><thead><tr><th>内容</th><th>发布时间</th>{metricKeys.map(key => <th key={key}>{extraMetricLabels[key] || key}</th>)}<th>链接</th></tr></thead><tbody>{rows.map((item: Json, index: number) => { const url = item.url || item.canonical_url || item.metadata?.source_url; return <tr key={item.id || url || `${item.title}-${index}`}><td>{item.title || item.metadata?.title || "未读取标题"}{latest.length > 0 && <Badge>本次同步</Badge>}</td><td>{item.published_at || item.metadata?.published_at ? String(item.published_at || item.metadata?.published_at).slice(0, 10) : "未读取"}</td>{metricKeys.map(key => <td key={key}>{formatNumber(item.metrics?.[key] ?? item[key] ?? item.metadata?.[key] ?? (key === "likes" ? item.metadata?.like_count : null))}</td>)}<td>{url && /^https?:\/\//.test(url) ? <a href={url} target="_blank" rel="noreferrer">查看原文</a> : "未读取"}</td></tr>; })}</tbody></table></Card>;
}

export default function Accounts() {
  const { resources, refresh, notify, loadError } = useApp();
  const [platform, setPlatform] = useState("douyin");
  const [busy, setBusy] = useState("");
  const [actionError, setActionError] = useState("");
  const data: Json = resources?.accounts || {};
  const jobs: Job[] = (data.jobs || []).filter((job: Job) => job.kind.startsWith("accounts."));
  const hasActiveJobs = jobs.some(job => activeStatuses.includes(job.status));
  useEffect(() => {
    if (!hasActiveJobs) return;
    const timer = window.setInterval(() => { void refresh(); }, 3000);
    return () => window.clearInterval(timer);
  }, [hasActiveJobs, refresh]);

  async function perform(key: string, action: () => Promise<unknown>, success: string) {
    if (busy) return;
    setBusy(key); setActionError("");
    try { await action(); await refresh(); notify(success); }
    catch (error) { const message = errorText(error); setActionError(message); notify(message, true); }
    finally { setBusy(""); }
  }

  const historicalAccounts: Json[] = resources?.core.accounts || [];
  const automatedAccounts: Json[] = data.accounts || [];
  const account = historicalAccounts.find(item => item.platform === platform) || null;
  const automated = automatedAccounts.find(item => item.platform === platform) || null;
  const profile = { ...(account?.profile || {}), ...(account?.weekly_summary || {}), ...(account?.daily_summary || {}), ...(automated?.profile || {}) };
  const metrics = Object.entries(profile).filter(([key]) => !ignoredMetrics.has(key) && !key.includes("change") && !key.includes("rate")).slice(0, 8);
  const recommendations: Json[] = data.recommendations || [];

  return <>
    <PageHeader eyebrow="ACCOUNT DAILY BRIEF" title="账号日报" description="每天 09:30 调度：先同步真实快照，再由账号分析 Agent 提出选题实验；缺失指标不补零。" actions={<><Button disabled={!!busy} onClick={() => void perform("sync", () => api("/api/accounts/sync", jsonOptions("POST")), "账号同步已加入后台，请在专用窗口处理登录")}><RefreshCw size={14} />{busy === "sync" ? "正在提交…" : "立即同步"}</Button><Button variant="primary" disabled={!!busy || !automatedAccounts.length} title={!automatedAccounts.length ? "先同步至少一个真实账号快照" : undefined} onClick={() => void perform("recommend", () => api("/api/accounts/recommend", jsonOptions("POST")), "账号分析 Agent 已加入后台")}>生成账号选题推荐</Button></>} />
    {loadError && <ErrorBox>{loadError}<br /><Button size="small" onClick={() => void refresh()}>重新读取</Button></ErrorBox>}
    {actionError && <ErrorBox>{actionError}<br /><Button size="small" onClick={() => setActionError("")}>关闭错误详情</Button></ErrorBox>}
    <div className="account-platform-tabs">{platforms.map(key => <button key={key} className={`account-platform-tab ${platform === key ? "active" : ""}`} onClick={() => setPlatform(key)}>{platformNames[key]}{automatedAccounts.some(item => item.platform === key) ? " · 已同步" : ""}</button>)}</div>

    {account || automated ? <div className="account-summary"><Card className="account-profile-card"><div className="account-profile-head"><div><Badge tone={automated ? "green" : "orange"}>{automated ? "含今日自动快照" : "历史只读快照"}</Badge><h2>{account?.account_name || account?.profile?.account_name || automated?.profile?.account_name || "账号名称未读取"}</h2><p>{platformNames[platform]} · 账号 ID：{formatNumber(account?.account_id)}</p></div>{account?.backend_url && <a className="button button-small" href={account.backend_url} target="_blank" rel="noreferrer">官方后台 <ExternalLink size={13} /></a>}</div><p className="account-bio">{account?.profile?.biography || (automated ? `自动采集于 ${automated.captured_at}` : "简介未读取")}</p>{automated && <p>最近自动同步：{automated.captured_at}</p>}{account && <p>历史采集：{account.captured_at || "未读取"}</p>}</Card><div>{metrics.length ? <div className="account-metrics">{metrics.map(([key, value]) => <div className="account-metric" key={key}><span>{extraMetricLabels[key] || key}</span><strong>{formatNumber(value)}</strong></div>)}</div> : <Card><Empty title="账号指标未读取" description="同步成功只代表取得了快照，不会为缺失字段生成数字。" /></Card>}</div></div> : <Empty title={`${platformNames[platform]}还没有账号快照`} description="可同步自动支持的抖音与小红书；其他平台的历史数据仍保留，不能冒充今日数据。" />}

    <Card className="account-actions-card"><div><h3>专用浏览器与人工登录</h3><p>只打开真实平台窗口，不伪造连接成功。扫码、短信和二次验证始终由你本人完成。</p></div><div className="button-row"><Button size="small" disabled={!!busy} onClick={() => void perform("login-xhs", () => api("/api/accounts/browser/open", jsonOptions("POST", { platform: "xiaohongshu" })), "小红书专用登录窗口正在打开，请在 5 分钟内完成扫码后重新同步")}>打开小红书登录窗口</Button><Button size="small" disabled={!!busy} onClick={() => void perform("login-douyin", () => api("/api/accounts/browser/open", jsonOptions("POST", { platform: "douyin_publish" })), "抖音发布后台登录窗口正在打开，请在 5 分钟内完成验证")}>打开抖音发布后台登录</Button></div></Card>

    <div className="section-heading"><h2>同步与分析任务</h2><p>后台持久执行 · 部分平台失败不会覆盖其他成功快照</p></div><AccountJobs jobs={jobs} />

    <div className="section-heading"><h2>各平台最近自动快照</h2><p>{automatedAccounts.length} 个平台 · 与上方历史只读数据分开</p></div>
    {automatedAccounts.length ? <div className="account-snapshot-grid">{automatedAccounts.map(item => <Card className="account-snapshot-card" key={item.id}><Badge tone="green">真实快照</Badge><h3>{platformNames[item.platform] || item.platform}</h3><p>{item.profile?.account_name || "账号名称未读取"}</p><small>{item.captured_at}</small><small>{Object.entries(item.profile || {}).filter(([key]) => !ignoredMetrics.has(key)).map(([key, value]) => `${extraMetricLabels[key] || key}：${formatNumber(value)}`).join(" · ") || "账号指标未读取"}</small></Card>)}</div> : <div className="account-empty-note">还没有自动同步的账号快照。上方手动录入的历史数据仍保留，不能冒充今日数据。</div>}

    <div className="section-heading"><h2>最近公开内容</h2><p>{automated?.items?.length ? "显示最近一次自动同步作品" : "显示历史只读公开内容"}</p></div><ContentTable account={account} automated={automated} />
    {(account?.collection_issues?.length || account?.missing_fields?.length) ? <div className="account-issues"><strong>数据边界</strong><ul>{(account.collection_issues || []).map((issue: string) => <li key={issue}>{issue}</li>)}<li>未读取字段：{(account.missing_fields || []).join("、") || "无"}</li></ul></div> : null}

    <div className="section-heading"><h2>账号分析 Agent 推荐</h2><p>{recommendations.length} 条 · 事实、推断和实验分开</p></div>
    {recommendations.length ? <div className="account-recommend-grid">{recommendations.map(item => <Card className="account-recommendation" key={item.id || item.title}><Badge tone="green">账号分析 Agent</Badge><h3>{item.title}</h3><p>{item.reason}</p><div className="account-recommend-evidence"><strong>建议切入</strong><p>{item.angle}</p>{(item.uncertainties || []).map((value: string) => <small key={value}>待核实：{value}</small>)}</div><small>{item.created_at}</small></Card>)}</div> : <Empty title="还没有账号选题推荐" description="同步后点击“生成账号选题推荐”；未同步时不生成无依据结论。" />}
  </>;
}
