import { useEffect, useState } from "react";
import { CheckCircle2, ExternalLink, MonitorCog, RefreshCw, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";
import { useApp } from "@/AppContext";
import { Badge, Button, Card, Empty, ErrorBox, PageHeader } from "@/components/ui";
import { api, errorText, jsonOptions } from "@/lib/api";
import "./Setup.css";

interface SetupData {
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
  const { run } = useApp();
  const [data, setData] = useState<SetupData | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [os, setOs] = useState<"macOS" | "Windows">("macOS");
  const [busy, setBusy] = useState("");

  async function load() {
    setLoading(true); setError("");
    try { const result = await api<SetupData>("/api/accounts/setup"); setData(result); setOs(result.os_name === "Windows" ? "Windows" : "macOS"); }
    catch (reason) { setError(errorText(reason)); }
    finally { setLoading(false); }
  }
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, []);

  async function login(platform: string) {
    if (busy) return;
    setBusy(platform); setError("");
    try {
      const publishing = ["wechat_channels", "wechat_official_account"].includes(platform);
      const path = publishing ? `/api/publishing/connections/${platform}/login` : "/api/accounts/browser/open";
      const body = publishing ? {} : { platform: platform === "douyin" ? "douyin_publish" : platform };
      await run(() => api(path, jsonOptions("POST", body)), "登录窗口任务已提交；请本人完成扫码或验证，然后回来重新检查");
    } catch (reason) { setError(errorText(reason)); }
    finally { setBusy(""); }
  }

  return <div className="setup-page">
    <PageHeader eyebrow="FIRST RUN & CONNECTIONS" title="接入向导" description="先确认本机环境，再逐个平台完成本人登录。代码、账号凭据和浏览器数据始终留在你的电脑上。" actions={<a className="button" href={data?.local_url || "http://127.0.0.1:8765/"} target="_blank" rel="noreferrer">打开本地工作台 <ExternalLink size={14} /></a>} />
    {error && <ErrorBox>{error}</ErrorBox>}
    <Card className={`setup-status ${data?.core_ready ? "ready" : ""}`}><MonitorCog size={24} /><div><h2>{data?.core_ready ? "核心环境已就绪" : "还需要完成环境检查"}</h2><p>{data ? `${data.os_name} · Python ${data.python_version} · ${data.local_url}` : "正在读取本机依赖状态"}</p></div><Button size="small" disabled={loading} onClick={() => void load()}><RefreshCw size={14} />重新检查</Button></Card>

    <div className="setup-section"><div className="section-heading"><h2>1. 下载与启动</h2><p>选择你的操作系统</p></div><div className="setup-os-tabs">{(["macOS", "Windows"] as const).map(key => <button type="button" className={os === key ? "active" : ""} key={key} onClick={() => setOs(key)}>{key}</button>)}</div><Card className="setup-command-card"><p>需要 Git、Python 3.9+、Node.js、FFmpeg 和 Chrome。安装脚本会创建隔离环境并构建前端。</p><ol>{commands[os].map(command => <li key={command}><code>{command}</code></li>)}</ol><small>也可以直接下载 GitHub ZIP 并解压后，从第 3 条命令开始执行。Windows 使用 PowerShell。</small></Card></div>

    <div className="setup-section"><div className="section-heading"><h2>2. 核心依赖检查</h2><p>{data?.dependencies.filter(item => item.installed).length || 0} / {data?.dependencies.length || 0} 项已检测</p></div>{loading && !data ? <Card><Empty title="正在检查本机环境…" /></Card> : <div className="setup-dependency-grid">{data?.dependencies.map(item => <Card className="setup-dependency" key={item.name}><div><strong>{item.name}</strong><Badge tone={item.installed ? "green" : item.required ? "orange" : "neutral"}>{item.installed ? "已检测" : item.required ? "待安装" : "可选"}</Badge></div>{!item.installed && <p>{item.action}</p>}</Card>)}</div>}</div>

    <div className="setup-section"><div className="section-heading"><h2>3. 登录内容平台</h2><p>一次只处理一个平台，完成后重新检查</p></div><div className="setup-platform-grid">{data?.platforms.map(item => <Card className="setup-platform" key={item.platform}><div className="setup-platform-head"><ShieldCheck size={19} /><Badge tone={item.verified ? "green" : "orange"}>{item.verified ? "有真实证据" : "待本人登录"}</Badge></div><h3>{item.name}</h3><p>{item.action}</p><Button size="small" disabled={Boolean(busy)} onClick={() => void login(item.platform)}>{busy === item.platform ? "正在提交…" : item.verified ? "重新打开登录窗口" : "打开登录窗口"}</Button></Card>)}</div><p className="setup-boundary">{data?.boundary || "扫码、短信和二次验证由本人完成；打开窗口不等于登录成功。"}</p></div>
    <div className="setup-finish"><CheckCircle2 size={20} /><div><strong>完成接入后</strong><p>从选题开始生产内容，在设置中配置 Agent。Kimi、WhisperX 和 OpenVoice 是可选能力，不影响先运行基础工作台。</p></div><div className="button-row"><Link className="button" to="/settings">配置 Agent</Link><Link className="button button-primary" to="/topics/douyin">开始选题</Link></div></div>
  </div>;
}
