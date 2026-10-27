import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, Check, FileVideo, FolderOpen, RotateCcw, ShieldCheck, Upload, Wrench, X } from "lucide-react";
import { Link } from "react-router-dom";
import { useApp } from "@/AppContext";
import { Badge, Button, Card, Empty, ErrorBox, Field, Input, PageHeader, Textarea } from "@/components/ui";
import { api, errorText, jsonOptions, uploadOptions } from "@/lib/api";
import "./Review.css";

const activeJobs = new Set(["queued", "leased", "running", "retry_wait"]);
const severityTone = (severity: string) => severity === "error" || severity === "high" ? "red" : severity === "warning" ? "orange" : "blue";

export default function Review() {
  const { notify } = useApp();
  const [batch, setBatch] = useState<any>(null);
  const [jobs, setJobs] = useState<any[]>([]);
  const [folder, setFolder] = useState("");
  const [rules, setRules] = useState<any>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);

  const load = useCallback(async (batchId?: string) => {
    try {
      const data = await api(`/api/review/bootstrap${batchId ? `?batch_id=${batchId}` : ""}`);
      setBatch(data.batch);
      setJobs(data.jobs || []);
      setRules((current: any) => current || data.default_rules);
      setError("");
    } catch (err) { setError(errorText(err)); }
  }, []);
  useEffect(() => { const timer = window.setTimeout(() => void load(), 0); return () => window.clearTimeout(timer); }, [load]);
  const active = Boolean(batch?.status === "reviewing" || jobs.some(job => activeJobs.has(job.status) && job.aggregate_id === batch?.id));
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => void load(batch?.id), 3000);
    return () => window.clearInterval(timer);
  }, [active, batch?.id, load]);

  const execute = async (key: string, action: () => Promise<any>, success: string) => {
    if (busy) return null;
    setBusy(key); setError("");
    try {
      const result = await action();
      if (result?.id && !batch?.id) await load(result.id); else await load(batch?.id);
      notify(success);
      return result;
    } catch (err) { setError(errorText(err)); return null; }
    finally { setBusy(""); }
  };
  const create = (upload: boolean) => execute("create", () => api("/api/review/batches", jsonOptions("POST", { folder, upload, rules }),), upload ? "上传批次已创建，请选择视频" : "已读取文件夹，开始选择审核方式");
  const uploadFiles = async () => {
    if (!batch || !files.length) return;
    for (const file of files) {
      const result = await execute("upload-" + file.name, () => api(`/api/review/uploads?batch_id=${batch.id}&filename=${encodeURIComponent(file.name)}`, uploadOptions(file)), `${file.name} 已上传`);
      if (!result) return;
    }
    setFiles([]); if (fileInput.current) fileInput.current.value = "";
  };
  const start = () => execute("start", () => api(`/api/review/batches/${batch.id}/start`, jsonOptions("POST")), "机器预审已开始，完成后请人工终审");
  const decide = (item: any, decision: string) => execute(decision + item.id, () => api(`/api/review/items/${item.id}/decide`, jsonOptions("POST", { decision })), decision === "approved" ? "已人工通过并复制到审核通过目录" : "已驳回并保留原文件");
  const approveEligible = async () => {
    for (const item of batch.items) {
      if (item.decision === "approved") continue;
      const blocking = (item.report?.issues || []).some((issue: any) => issue.severity === "error");
      if (!blocking && item.report) {
        const result = await execute("batch-" + item.id, () => api(`/api/review/items/${item.id}/decide`, jsonOptions("POST", { decision: "approved" })), "无阻断项视频已人工通过");
        if (!result) return;
      }
    }
  };
  const repair = (item: any) => execute("repair-" + item.id, () => api(`/api/review/items/${item.id}/repair`, jsonOptions("POST")), "安全转码完成，已重新预审，请终审");
  const counts = batch?.counts || {};
  return <div className="review-page">
    <PageHeader eyebrow="VIDEO REVIEW AGENT" title="短视频审核中心" description="批量读取上传文件或本地文件夹。机器给证据，你做终审；原文件始终不变。" actions={batch?.items?.some((item: any) => item.decision === "approved") ? <Link className="button button-primary" to="/publish?kind=video">发布通过视频</Link> : undefined} />
    <div className="review-layout"><aside className="review-controls">
      <Card><h2>1. 选择内容来源</h2><Field label="本地文件夹 A" hint="只扫描当前目录的视频，不递归，不修改原文件"><Input value={folder} onChange={event => setFolder(event.target.value)} placeholder="例如：/Volumes/EXTERNAL_USB/kimi/videos" /></Field><div className="button-row"><Button disabled={!folder || Boolean(busy)} onClick={() => void create(false)}><FolderOpen size={15} />读取文件夹</Button><Button disabled={Boolean(busy)} onClick={() => void create(true)}><Upload size={15} />新建上传批次</Button></div>{batch?.source_folder?.includes("review-uploads") && <div className="upload-panel"><input ref={fileInput} type="file" multiple accept=".mp4,.mov,.webm,.mkv" onChange={event => setFiles([...(event.target.files || [])])} /><Button disabled={!files.length || Boolean(busy)} onClick={() => void uploadFiles()}>上传 {files.length || ""} 个视频</Button></div>}<p className="muted small">{batch?.source_folder || "尚未选择来源"}</p></Card>
      {rules && <Card><h2>2. 审核规则</h2><div className="form-grid"><Field label="目标宽"><Input type="number" value={rules.target_width} onChange={event => setRules({ ...rules, target_width: Number(event.target.value) })} /></Field><Field label="目标高"><Input type="number" value={rules.target_height} onChange={event => setRules({ ...rules, target_height: Number(event.target.value) })} /></Field></div><Field label="最长时长（秒）"><Input type="number" value={rules.max_duration} onChange={event => setRules({ ...rules, max_duration: Number(event.target.value) })} /></Field><Field label="黑帧阈值（秒）"><Input type="number" step="0.1" value={rules.black_min_duration} onChange={event => setRules({ ...rules, black_min_duration: Number(event.target.value) })} /></Field><Field label="静音阈值（秒）"><Input type="number" step="0.1" value={rules.silence_min_duration} onChange={event => setRules({ ...rules, silence_min_duration: Number(event.target.value) })} /></Field><label className="check-row"><input type="checkbox" checked={rules.check_ocr} onChange={event => setRules({ ...rules, check_ocr: event.target.checked })} />OCR 字幕越界检查</label><label className="check-row"><input type="checkbox" checked={rules.ai_risk} onChange={event => setRules({ ...rules, ai_risk: event.target.checked })} />AI 风险证据分析</label><Button variant="primary" disabled={!batch?.items?.length || active || Boolean(busy)} onClick={() => void start()}><RotateCcw size={15} />{active ? "机器预审中…" : "开始机器预审"}</Button></Card>}
      <Card><h2>批次进度</h2><div className="review-counts"><span>总数 <strong>{counts.total || 0}</strong></span><span>待终审 <strong>{counts.needs_review || 0}</strong></span><span>通过 <strong>{counts.approved || 0}</strong></span><span>驳回/失败 <strong>{(counts.rejected || 0) + (counts.failed || 0)}</strong></span></div><Button disabled={!batch?.items?.some((item: any) => item.report && item.decision !== "approved" && !(item.report.issues || []).some((issue: any) => issue.severity === "error")) || Boolean(busy)} onClick={() => void approveEligible()}><ShieldCheck size={15} />通过全部无阻断项</Button></Card>
    </aside><section className="review-items">{error && <ErrorBox>{error}</ErrorBox>}{jobs.slice(0, 4).map(job => <div className="review-job" key={job.id}><span>{job.kind} · {job.stage}</span><Badge tone={job.status === "failed" ? "red" : job.status === "succeeded" ? "green" : "orange"}>{job.status}</Badge>{job.error?.message && <p>{job.error.message}<br />{job.error.action}</p>}</div>)}{!batch?.items?.length ? <Empty title="先选择文件夹或上传视频" description="机器预审完成后，这里会显示每个视频的问题、时间点与修复建议。" /> : batch.items.map((item: any) => <ReviewItem key={item.id} item={item} busy={busy} onDecide={decide} onRepair={repair} />)}</section></div>
  </div>;
}

function ReviewItem({ item, busy, onDecide, onRepair }: { item: any; busy: string; onDecide: (item: any, decision: string) => void; onRepair: (item: any) => void }) {
  const [expanded, setExpanded] = useState(false);
  const issues = item.report?.issues || [];
  const risks = item.ai_risk?.risks || [];
  return <Card className={`review-item ${item.decision}`}><div className="review-item-head"><div><FileVideo size={18} /><div><h3>{item.source_path.split("/").pop()}</h3><p>{item.source_path}</p></div></div><Badge tone={item.decision === "approved" ? "green" : item.decision === "rejected" || item.status === "failed" ? "red" : "orange"}>{item.decision === "approved" ? "人工已通过" : item.decision === "rejected" ? "已驳回" : item.status === "reviewing" ? "预审中" : "待人工终审"}</Badge></div><div className="review-metrics"><span>技术检查 <strong>{item.report?.status || "未执行"}</strong></span><span>问题 <strong>{issues.length}</strong></span><span>AI 风险 <strong>{risks.length}</strong></span></div>{issues.length > 0 && <div className="issue-list">{issues.map((issue: any, index: number) => <div className="issue-row" key={index}><Badge tone={severityTone(issue.severity)}>{issue.severity}</Badge><div><strong>{issue.type}{issue.timestamp_seconds !== null && issue.timestamp_seconds !== undefined ? ` · ${issue.timestamp_seconds}s` : ""}</strong><p>{issue.recommendation}</p>{issue.evidence && <code>{JSON.stringify(issue.evidence)}</code>}</div></div>)}</div>}{risks.length > 0 && <div className="risk-list"><h4>AI 风险证据（不等同合规结论）</h4>{risks.map((risk: any, index: number) => <div className="issue-row" key={index}><Badge tone={severityTone(risk.severity)}>{risk.category}</Badge><div><strong>{risk.evidence}</strong><p>{risk.reason}</p><p>{risk.action}</p></div></div>)}</div>}{item.ai_risk?.evidence_scope && <p className="muted small">证据范围：{item.ai_risk.evidence_scope}</p>}{item.error && <ErrorBox>{item.error.message}<br />{item.error.action}</ErrorBox>}<button className="text-button" onClick={() => setExpanded(!expanded)}>{expanded ? "收起证据" : "查看检查详情"}</button>{expanded && <Textarea readOnly value={JSON.stringify({ report: item.report, ai_risk: item.ai_risk }, null, 2)} rows={10} />}<div className="review-item-actions"><Button size="small" disabled={!item.report?.safe_transcode_candidate?.eligible || Boolean(busy)} onClick={() => onRepair(item)}><Wrench size={14} />安全转码并复审</Button><Button size="small" disabled={!item.report || item.decision === "approved" || Boolean(busy)} onClick={() => onDecide(item, "rejected")}><X size={14} />驳回</Button><Button size="small" variant="primary" disabled={!item.report || item.decision === "approved" || issues.some((issue: any) => issue.severity === "error") || Boolean(busy)} onClick={() => onDecide(item, "approved")}><Check size={14} />人工通过</Button></div>{item.output_path && <p className="approved-path"><AlertTriangle size={14} />审核通过文件：{item.output_path}</p>}</Card>;
}
