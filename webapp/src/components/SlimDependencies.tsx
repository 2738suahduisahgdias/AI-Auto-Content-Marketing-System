import { useCallback, useEffect, useState } from "react";
import { Download, RefreshCw, X } from "lucide-react";
import { api, errorText, jsonOptions } from "@/lib/api";
import { Button, Progress } from "@/components/ui";

interface DependencyItem {
  id: string;
  label: string;
  estimate: string;
  status: "pending" | "running" | "succeeded" | "failed";
  error?: string | null;
}

interface DependencyStatus {
  slim: boolean;
  edition: string;
  required: boolean;
  complete: boolean;
  running: boolean;
  active?: string | null;
  items: DependencyItem[];
  completed: number;
  total: number;
  error?: string | null;
}

const statusLabels = { pending: "等待", running: "下载中", succeeded: "已完成", failed: "失败" } as const;

export default function SlimDependencies() {
  const [status, setStatus] = useState<DependencyStatus | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const [loadError, setLoadError] = useState("");
  const load = useCallback(async () => {
    try {
      const result = await api<DependencyStatus>("/api/slim-dependencies");
      setStatus(result);
      setLoadError("");
    } catch (error) {
      setLoadError(errorText(error));
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);
  useEffect(() => {
    if (!status?.running) return;
    const timer = window.setInterval(() => void load(), 2500);
    return () => window.clearInterval(timer);
  }, [load, status?.running]);
  async function start() {
    try {
      const result = await api<DependencyStatus>("/api/slim-dependencies", jsonOptions("POST"));
      setStatus(result);
      setDismissed(false);
      setLoadError("");
    } catch (error) {
      setLoadError(errorText(error));
    }
  }
  if (!status?.slim || status.complete || dismissed) return null;
  const active = status.items.find(item => item.id === status.active);
  return <section className="slim-dependencies" aria-label="精简版资源下载">
    <div className="slim-dependencies-heading"><div><p className="eyebrow">映序工作台 · 精简版</p><h2>首次使用需要下载本地资源</h2><p>安装包只包含核心程序。媒体 Python、Node、FFmpeg、Remotion、浏览器和模型等可下载资源将保存到当前工作区，完成后可离线使用；下载期间可以继续处理文案。</p></div><button className="icon-button" aria-label="稍后再下载" onClick={() => setDismissed(true)} disabled={status.running}><X size={18} /></button></div>
    <div className="slim-dependencies-progress"><span>已完成 {status.completed} / {status.total} 组</span><Progress value={status.completed / status.total} /></div>
    <div className="slim-dependencies-items">{status.items.map(item => <div key={item.id} className={item.status === "failed" ? "slim-dependency-failed" : ""}><span>{item.label}<small>{item.estimate}</small></span><strong>{statusLabels[item.status]}</strong></div>)}</div>
    {active && <p role="status">正在下载：{active.label}。大文件可能需要较长时间，请保持网络连接。</p>}
    {(status.error || loadError) && <div className="slim-dependencies-error" role="alert">{status.error || loadError}</div>}
    <div className="button-row"><Button variant="primary" onClick={() => void start()} disabled={status.running}>{status.running ? <RefreshCw className="spin" size={16} /> : <Download size={16} />}{status.running ? "正在下载全部资源" : status.error ? "重试下载" : "下载全部本地资源"}</Button><span className="muted small">未下载完成前，相关媒体功能会明确显示未就绪。</span></div>
  </section>;
}
