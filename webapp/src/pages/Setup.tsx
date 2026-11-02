import WechatConnection from "@/components/WechatConnection";
import { useEffect, useState } from "react";
import { CheckCircle2, ExternalLink, MonitorCog, RefreshCw, ShieldCheck } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { useApp } from "@/AppContext";
import { Badge, Button, Card, Empty, ErrorBox, PageHeader } from "@/components/ui";
import { api, errorText, jsonOptions } from "@/lib/api";
import "./Setup.css";

interface SetupData {
  activation?: string;
  wechat_client?: {status:string;error?:string};
  readiness?: {delivery_ready:boolean;delivery_blockers:string[];capabilities:{name:string;status:string;note:string;missing_dependencies:string[]}[]};
  os_name: string;
  python_version: string;
  local_url: string;
  core_ready: boolean;
  boundary: string;
  dependencies: { name: string; installed: boolean; required: boolean; action: string }[];
  platforms: { platform: string; name: string; status: string; verified: boolean; action: string }[];
}

const commands = {
  macOS: ["git clone https://github.com/2738suahduisahgdias/AI-Auto-Content-Marketing-System.git", "cd AI-Auto-Content-Marketing-System", "bash scripts/setup.sh", "bash scripts/start.sh"],
  Windows: ["git clone https://github.com/2738suahduisahgdias/AI-Auto-Content-Marketing-System.git", "cd AI-Auto-Content-Marketing-System", "powershell -ExecutionPolicy Bypass -File scripts/setup.ps1", "powershell -ExecutionPolicy Bypass -File scripts/start.ps1"],
};

export default function Setup() {
  const { hash } = useLocation();
  const { run, resources, refresh } = useApp();
  const [data, setData] = useState<SetupData | null>(null);
  const [connection, setConnection] = useState<any>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [os, setOs] = useState<"macOS" | "Windows">("macOS");
  const [busy, setBusy] = useState("");
  useEffect(() => {
    if (loading || !hash) return;
    const frame = requestAnimationFrame(() => document.getElementById(decodeURIComponent(hash.slice(1)))?.scrollIntoView({block: "start"}));
    return () => cancelAnimationFrame(frame);
  }, [hash, loading, data]);
  const jobs = (resources?.accounts?.jobs || []).filter((job: any) => ["accounts.login", "publish.login"].includes(job.kind)).slice(0, 6);
  const hasActiveJob = jobs.some((job: any) => ["queued", "leased", "running", "retry_wait"].includes(job.status));

  async function load() {
    setLoading(true); setError("");
    try { const result = await api<SetupData>("/api/accounts/setup"); setData(result); setConnection(await api("/api/accounts/browser/connection")); setOs(result.os_name === "Windows" ? "Windows" : "macOS"); }
    catch (reason) { setError(errorText(reason)); }
    finally { setLoading(false); }
  }
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, []);
  useEffect(() => {
    if (!hasActiveJob) return;
    const timer = window.setInterval(() => { void refresh(); void load(); }, 3000);
    return () => window.clearInterval(timer);
  }, [hasActiveJob, refresh]);

  useEffect(() => {
    const timer = window.setInterval(() => { if (!document.hidden) void api("/api/accounts/browser/connection").then(setConnection).catch(()=>setConnection({reason:"本地服务连接已断开，请确认客户端仍在运行后重新检测"})); }, 10000);
    return () => window.clearInterval(timer);
  }, []);

  async function login(platform: string) {
    if (busy) return;
    setBusy(platform); setError("");
    try {
      const body = { platform: platform === "douyin" ? "douyin_publish" : platform };
      await run(() => api("/api/accounts/browser/open", jsonOptions("POST", body)), "平台登录窗口已提交，请在窗口内完成登录；不再自动抓取账号经营数据");
    } catch (reason) { setError(errorText(reason)); }
    finally { setBusy(""); }
  }

  return <div className="setup-page">
    <PageHeader eyebrow="FIRST RUN & CONNECTIONS" title="接入向导" description="先确认本机环境，再逐个平台完成本人登录。代码、账号凭据和浏览器数据始终留在你的电脑上。" actions={<a className="button" href={data?.local_url || "http://127.0.0.1:8765/"} target="_blank" rel="noreferrer">打开本地工作台 <ExternalLink size={14} /></a>} />
    {error && <ErrorBox>{error}</ErrorBox>}
    <Card><h2>安装后的接入清单</h2><p>激活和平台扫码只完成身份连接。AI 模型、浏览器连接和素材上传需分别验证；未完成的能力不会显示为可用。</p>
      <div className="button-row"><Link className="button" to="/activation">1. {data?.activation === "valid" ? "已激活 · 查看授权" : "完成离线激活"}</Link><Link className="button" to="/setup#wechat-connect">2. {data?.wechat_client?.status === "connected" ? "微信 Bot 已连接" : "微信 Bot 扫码连接"}</Link><Link className="button" to="/settings/models">3. 安装并登录 AI 模型</Link><a className="button" href="#platform-logins">4. 平台扫码登录</a><Link className="button" to="/welcome">5. 制作第一份内容</Link></div>
      {data?.wechat_client?.error && <ErrorBox>{data.wechat_client.error}</ErrorBox>}
    </Card>
    <Card><h2>Chrome 连接向导</h2><ol>
      <li>安装并打开 <a href="https://www.google.com/chrome/" target="_blank" rel="noreferrer">Chrome</a>。</li>
      <li>按 <a href="https://www.kimi.com/zh-cn/features/webbridge" target="_blank" rel="noreferrer">官方说明安装本地浏览器服务</a>。</li>
      <li><a href="https://chromewebstore.google.com/detail/kimi-webbridge/fldmhceldgbpfpkbgopacenieobmligc" target="_blank" rel="noreferrer">安装 Kimi WebBridge 扩展</a> → Chrome 右上角扩展图标 → 启用并确认所需权限。</li>
      <li>点击启动连接，检测通过后，在下面打开平台完成本人扫码。断线时点击重启连接。</li>
    </ol><p>Chrome：{connection?.chrome_installed ? "已安装" : "待安装"} · 服务：{connection?.running ? "运行中" : "未连接"} · 扩展：{connection?.extension_connected ? "已连接" : "未连接"}</p><p role="status">{connection?.reason}</p>
    <div className="button-row"><Button disabled={loading || Boolean(busy)} onClick={()=>void load()}>检测连接</Button>{(["start","restart","stop"] as const).map(action=><Button key={action} disabled={Boolean(busy) || !connection?.service_installed} onClick={async()=>{setBusy(action);setError("");try{setConnection(await api("/api/accounts/browser/connection",jsonOptions("POST",{action})));}catch(e){setError(errorText(e));}finally{setBusy("");}}}>{({start:"启动连接",restart:"重启连接",stop:"停止连接"})[action]}</Button>)}</div><p>连接检测不代表平台已登录。扫码、短信或风控验证由你在 Chrome 中完成；模型授权在模型设置中单独完成。</p></Card>
    {data?.readiness && <Card><details><summary>当前可用范围与未完成项</summary><p>检测工具存在不等于已登录；登录成功不等于上传成功。下列状态来自当前本机检查。</p>
      <ul>{data.readiness.delivery_blockers.map(item=><li key={item}>{item}</li>)}</ul>
      <div className="setup-dependency-grid">{data.readiness.capabilities.map(item=><div className="setup-dependency" key={item.name}><strong>{item.name}</strong><Badge tone={item.status === "blocked" || item.status === "not_implemented" ? "orange" : "neutral"}>{({blocked:"缺少依赖或未启用",not_implemented:"尚未接通",requires_validation:"需要实际验收"} as Record<string,string>)[item.status] || item.status}</Badge><p>{item.note}</p>{item.missing_dependencies.length>0&&<small>缺少：{item.missing_dependencies.join("、")}</small>}</div>)}</div>
      <p>公众号、视频号自动上传尚未完成验收：目前可先在文章／视频任务导出本地成品，手动上传平台并审核发布。</p></details>
    </Card>}

    <Card className={`setup-status ${data?.core_ready ? "ready" : ""}`}><MonitorCog size={24} /><div><h2>{data?.core_ready ? "核心环境已就绪" : "还需要完成环境检查"}</h2><p>{data ? `${data.os_name} · Python ${data.python_version} · ${data.local_url}` : "正在读取本机依赖状态"}</p></div><Button size="small" disabled={loading} onClick={() => void load()}><RefreshCw size={14} />重新检查</Button></Card>

    <details><summary>源码开发者安装说明（客户端用户无需重复安装项目）</summary><div className="setup-section"><div className="section-heading"><h2>0. 网络与账号准备</h2><p>先能访问 GitHub，再下载和安装</p></div><Card className="setup-command-card"><ol><li>如果你所在网络无法直接打开 GitHub，请先准备合规、稳定的访问环境（也常被称为“翻墙环境”），确认能读取仓库并下载 ZIP。</li><li>没有邮箱时可先注册 Gmail；Gmail 或其他可接收验证邮件的邮箱均可注册 GitHub，不强制要求谷歌邮箱。</li><li>前往 <a href="https://github.com/signup" target="_blank" rel="noreferrer">GitHub 注册页</a> 注册或登录。仅下载公开 ZIP 不强制要求账号。</li></ol><small>安装协助：刘洋 · liuyangfjnu。请不要发送密码、Cookie、Token 或短信验证码。</small></Card></div>
    <div className="setup-section"><div className="section-heading"><h2>1. 下载与启动</h2><p>选择你的操作系统</p></div><div className="setup-os-tabs">{(["macOS", "Windows"] as const).map(key => <button type="button" className={os === key ? "active" : ""} key={key} onClick={() => setOs(key)}>{key}</button>)}</div><Card className="setup-command-card"><p>需要 Git、Python 3.9+、Node.js、FFmpeg 和 Chrome。安装脚本会创建隔离环境并构建前端。</p><ol>{commands[os].map(command => <li key={command}><code>{command}</code></li>)}</ol><small>也可以直接下载 GitHub ZIP 并解压后，从第 3 条命令开始执行。Windows 使用 PowerShell。</small></Card></div>

    </details><div className="setup-section"><div className="section-heading"><h2>2. 核心依赖检查</h2><p>{data?.dependencies.filter(item => item.installed).length || 0} / {data?.dependencies.length || 0} 项已检测</p></div>{loading && !data ? <Card><Empty title="正在检查本机环境…" /></Card> : <div className="setup-dependency-grid">{data?.dependencies.map(item => <Card className="setup-dependency" key={item.name}><div><strong>{item.name}</strong><Badge tone={item.installed ? "green" : item.required ? "orange" : "neutral"}>{item.installed ? "已检测" : item.required ? "待安装" : "可选"}</Badge></div>{!item.installed && <p>{item.action}</p>}</Card>)}</div>}</div>

    <WechatConnection />
    <div className="setup-section"><div className="section-heading"><h2 id="platform-logins">3. 登录内容平台</h2><p>一次只处理一个平台，完成后重新检查</p></div><div className="setup-platform-grid">{data?.platforms.map(item => <Card className="setup-platform" key={item.platform}><div className="setup-platform-head"><ShieldCheck size={19} /><Badge tone={item.verified ? "green" : "orange"}>{item.verified ? "有真实证据" : "待本人登录"}</Badge></div><h3>{item.name}</h3><p>{item.action}</p><Button size="small" disabled={Boolean(busy)} onClick={() => { if (["wechat_channels","wechat_official_account"].includes(item.platform)) { window.open(item.platform === "wechat_channels" ? "https://channels.weixin.qq.com/" : "https://mp.weixin.qq.com/", "_blank", "noopener,noreferrer"); } else void login(item.platform); }}>{busy === item.platform ? "正在提交…" : item.verified ? "重新打开登录窗口" : "打开登录窗口"}</Button></Card>)}</div>{jobs.length > 0 && <div className="setup-jobs">{jobs.map((job: any) => <Card key={job.id}><div><strong>平台登录任务</strong><Badge tone={job.status === "succeeded" ? "green" : job.error ? "red" : "orange"}>{job.status}</Badge></div><small>{job.stage || job.status} · {job.created_at}</small>{job.result?.login_verified && <p className="setup-success">平台登录已确认，可继续内容制作与发布准备。</p>}{job.error && <p>{job.error.message || job.error.code}{job.error.action ? ` · 怎么改：${job.error.action}` : ""}</p>}{Object.entries(job.result?.accounts || {}).filter(([key]) => key.endsWith("_error") || key.endsWith("_warning")).map(([key, value]) => <p key={key}>{key}：{String(value)}</p>)}</Card>)}</div>}<p className="setup-boundary">{data?.boundary || "扫码、短信和二次验证由本人完成；打开窗口不等于登录成功。"}</p></div>
    <div className="setup-finish"><CheckCircle2 size={20} /><div><strong>完成接入后</strong><p>从选题开始生产内容，在设置中配置 Agent。Kimi、WhisperX 和 OpenVoice 是可选能力，不影响先运行基础工作台。</p></div><div className="button-row"><Link className="button" to="/settings">配置 Agent</Link><Link className="button button-primary" to="/topics/douyin">开始选题</Link></div></div>
  </div>;
}
