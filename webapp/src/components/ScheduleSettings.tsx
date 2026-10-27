import { useCallback, useEffect, useState } from "react";
import { CalendarClock, Pause, Play, X } from "lucide-react";
import { useApp } from "@/AppContext";
import { Badge, Button, Card, ErrorBox, Field, Input } from "@/components/ui";
import { api, errorText, jsonOptions } from "@/lib/api";
import { platformNames } from "@/lib/names";
import type { ContentKind, PublishBatch } from "@/lib/types";
import type { PublishingSource } from "@/components/PublishingPanel";
import "./ScheduleSettings.css";

export function ScheduleSettings({ kind, source }: { kind: ContentKind; source: PublishingSource | null }) {
  const { notify } = useApp();
  const [batch, setBatch] = useState<PublishBatch | null>(null);
  const [schedules, setSchedules] = useState<any[]>([]);
  const [firstRun, setFirstRun] = useState(() => new Date(Date.now() + 3600000).toISOString().slice(0, 16));
  const [interval, setIntervalValue] = useState(30);
  const [dailyLimit, setDailyLimit] = useState(20);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    if (!source || kind !== "video") return;
    try {
      const [batchData, scheduleData] = await Promise.all([
        api(`/api/publishing/bootstrap?kind=video&source_id=${encodeURIComponent(source.id)}`),
        api("/api/schedule/bootstrap"),
      ]);
      setBatch(batchData.batch); setSchedules(scheduleData.schedules || []); setError("");
    } catch (err) { setError(errorText(err)); }
  }, [kind, source]);
  useEffect(() => { const timer = window.setTimeout(() => void load(), 0); return () => window.clearTimeout(timer); }, [load]);
  const active = schedules.some(schedule => schedule.queue?.some((item: any) => item.status === "running"));
  useEffect(() => { if (!active) return; const timer = window.setInterval(() => void load(), 5000); return () => window.clearInterval(timer); }, [active, load]);
  if (kind !== "video") return null;
  const ready = batch?.targets.filter(target => target.status === "ready") || [];
  const execute = async (action: () => Promise<any>, success: string) => {
    if (busy) return;
    setBusy(true); setError("");
    try { await action(); await load(); notify(success); }
    catch (err) { setError(errorText(err)); }
    finally { setBusy(false); }
  };
  const create = () => execute(() => api("/api/schedule", jsonOptions("POST", {
    batches: [{ batch_id: batch?.id, source_hash: batch?.source_hash, target_ids: ready.map(target => target.id) }],
    first_run_at: new Date(firstRun).toISOString(), interval_minutes: interval, daily_limit: dailyLimit,
  })), "定时队列已创建；只有已预览目标会执行");
  const update = (schedule: any, status?: string) => execute(() => api(`/api/schedule/${schedule.id}`, jsonOptions("PUT", {
    first_run_at: new Date(firstRun).toISOString(), interval_minutes: interval, daily_limit: dailyLimit, status,
  })), "未开始的队列已按新设置重排");
  return <Card className="schedule-settings"><div className="schedule-head"><div><h2>批量定时发布</h2><p>只对预览就绪的视频与平台生效。修改只影响未开始任务。</p></div><CalendarClock size={22} /></div>{error && <ErrorBox>{error}</ErrorBox>}<div className="schedule-form"><Field label="首次发布时间（本地）"><Input type="datetime-local" value={firstRun} onChange={event => setFirstRun(event.target.value)} /></Field><Field label="全局间隔（分钟）"><Input type="number" min={1} value={interval} onChange={event => setIntervalValue(Number(event.target.value))} /></Field><Field label="每日发布上限"><Input type="number" min={1} value={dailyLimit} onChange={event => setDailyLimit(Number(event.target.value))} /></Field><Button variant="primary" disabled={!ready.length || busy} onClick={create}>创建定时队列（{ready.length} 个目标）</Button></div>{!ready.length && <p className="muted small">先完成平台预览，才能批量定时发布。</p>}<div className="schedule-list">{schedules.map(schedule => <article className="schedule-item" key={schedule.id}><div className="schedule-item-head"><div><strong>{schedule.first_run_at}</strong><p>间隔 {schedule.interval_minutes} 分钟 · 每日 {schedule.daily_limit} 条</p></div><Badge tone={schedule.status === "active" ? "green" : "orange"}>{schedule.status}</Badge></div><div className="schedule-actions"><Button size="small" disabled={busy} onClick={() => update(schedule, schedule.status === "active" ? "paused" : "active")}>{schedule.status === "active" ? <Pause size={13} /> : <Play size={13} />}{schedule.status === "active" ? "暂停" : "恢复"}</Button><Button size="small" disabled={busy} onClick={() => update(schedule)}>应用上方设置</Button><Button size="small" variant="danger" disabled={busy || !schedule.queue.some((item: any) => item.status === "queued")} onClick={() => execute(() => api(`/api/schedule/${schedule.id}/cancel`, jsonOptions("POST")), "未开始任务已取消，运行中任务不变")}><X size={13} />取消未开始</Button></div><div className="queue-list">{schedule.queue.map((item: any) => <div className="queue-row" key={item.id}><span>{platformNames[item.platform]}</span><span>{item.scheduled_for}</span><Badge tone={item.status === "published" ? "green" : item.status === "failed" || item.status === "unknown_remote" ? "red" : "orange"}>{item.status}</Badge></div>)}</div></article>)}</div></Card>;
}
