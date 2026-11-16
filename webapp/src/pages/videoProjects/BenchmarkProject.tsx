import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useApp } from "../../AppContext";
import { api, jsonOptions } from "../../lib/api";
import { Badge, Button, Card, Empty, Modal, PageHeader } from "../../components/ui";
import type { Task } from "../../lib/types";
import { effectiveShotDuration, shotAvailableDuration, shotReady, useProjectTask, useVideoProject, type ProjectFile, type ProjectShot, type ProjectSnapshot } from "./useVideoProject";
import { FinalStage, Help, MediaSummary, MusicStage, StageNavigation, UploadButton, UploadPanel, uploadProjectFile } from "./ProjectShared";
import "./video-projects.css";

type SnapshotUpdate = (patch: Partial<ProjectSnapshot>) => void;

interface BenchmarkReport {
  source_file_id: number;
  focus?: string;
  duration_seconds: number;
  transcript_status: "succeeded" | "not_applicable" | "unavailable";
  transcript_error?: string;
  subtitle_status?: "succeeded" | "empty" | "unavailable" | "not_applicable";
  subtitle_error?: string;
  scene_detection: string;
}

async function analyzeReference(task: Task, file: File, focus: string) {
  const uploaded = await uploadProjectFile(task, file, "video");
  return api<Task>(`/api/tasks/${task.content_id}/benchmark-analyze`, jsonOptions("POST", { file_id: uploaded.id, focus }));
}

export function CreateBenchmark({ onCreated }: { onCreated: (task: Task) => void }) {
  const { refresh } = useApp();
  const [focus, setFocus] = useState("");
  const [file, setFile] = useState<File>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function create() {
    if (!file) { setError("请选择真实参考视频"); return; }
    setBusy(true); setError("");
    try {
      const task = await api<Task>("/api/tasks", jsonOptions("POST", {
        title: focus.trim().slice(0, 60) || file.name.replace(/\.[^.]+$/, "").slice(0, 60) || "对标项目",
        source_type: "benchmark", focus: focus.trim(),
      }));
      const analyzed = await analyzeReference(task, file, focus.trim());
      await refresh();
      onCreated(analyzed);
    } catch (cause) { setError(cause instanceof Error ? `${cause.message}。若项目已创建，可从项目首页继续，不会丢失已上传文件。` : "创建或拆解失败"); }
    finally { setBusy(false); }
  }

  return <Card>
    <div className="card-head"><div><h2>提供参考视频 <Help title="对标的起点"><p>输入参考视频：选择需要拆解的视频。</p><p>还原逐镜分镜：保留时间码和关键帧。</p><p>获得拆解报告：可独立完成，不必制作视频。</p></Help></h2><p className="sub">先分析原视频，报告可独立完成。</p></div><Badge>当前步骤</Badge></div>
    <UploadPanel label="选择参考视频" accept="video/*" disabled={busy} onFile={setFile} />
    {file && <p className="sub">{file.name} · {(file.size / 1024 / 1024).toFixed(2)} MB</p>}
    <div className="video-project-field"><label className="video-project-field-label" htmlFor="benchmark-focus">关注重点 <span className="quiet">可选</span></label><input id="benchmark-focus" className="input" value={focus} onChange={event => setFocus(event.target.value)} placeholder="例如：叙事结构、镜头节奏、声音" /></div>
    <div className="video-project-note">报告会真实切分场景、提取关键帧并尝试整片转写。没有音轨时读取画面字幕；可在报告中用 Kimi 分析关键帧，无法确认的信息仍需人工补充。</div>
    {error && <p className="video-project-error" role="alert">{error}</p>}
    <Button variant="primary" disabled={busy} onClick={() => void create()}>{busy ? "正在上传并真实拆解…" : "查看拆解报告 →"}</Button>
  </Card>;
}

function ReferenceStage({ task, snapshot, update, adoptTask, onNext }: { task: Task; snapshot: ProjectSnapshot; update: SnapshotUpdate; adoptTask: (task: Task) => void; onNext: () => void }) {
  const { refresh } = useApp();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const report = snapshot.benchmark_report as BenchmarkReport | undefined;
  const reference = (task.files as ProjectFile[]).find(file => file.id === report?.source_file_id);

  async function uploadAndAnalyze(file: File) {
    setBusy(true); setError("");
    try {
      const result = await analyzeReference(task, file, String(report?.focus || snapshot.focus || ""));
      await refresh();
      adoptTask(result);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "拆解失败"); }
    finally { setBusy(false); }
  }

  return <Card>
    <div className="card-head"><div><h2>提供参考视频 <Help title="对标的起点"><p>输入参考视频：选择需要拆解的视频。</p><p>还原逐镜分镜：保留时间码和关键帧。</p><p>获得拆解报告：可独立完成，不必制作视频。</p></Help></h2><p className="sub">先分析原视频，报告可独立完成。</p></div><Badge>{report ? "已有报告" : "当前步骤"}</Badge></div>
    {reference && <div className="video-project-media"><video controls src={reference.url} aria-label="当前参考视频" /><MediaSummary file={reference} /></div>}
    <div className="video-project-field"><label className="video-project-field-label" htmlFor="existing-focus">关注重点 <span className="quiet">可选</span></label><input id="existing-focus" className="input" value={report?.focus || snapshot.focus || ""} onChange={event => update({ focus: event.target.value })} placeholder="例如：叙事结构、镜头节奏、声音" /></div>
    <div className="video-project-note">当前分析在本机完成，不向外部视觉模型发送素材。</div>
    <UploadPanel label={reference ? "上传新参考并重新拆解" : "选择参考视频"} accept="video/*" disabled={busy} onFile={file => void uploadAndAnalyze(file)} />
    {busy && <p role="status">正在真实切分场景、提取关键帧并转写整片语音；请不要关闭页面。</p>}
    {error && <p className="video-project-error" role="alert">{error}</p>}
    <div className="video-project-actions"><Button variant="primary" disabled={!report || busy} onClick={onNext}>查看拆解报告 →</Button></div>
  </Card>;
}

export function seekToShot(video: HTMLVideoElement, start: number) {
  video.currentTime = start;
  return video.play();
}

export function ReportStage({ task, snapshot, update, onBack, onNext }: { task: Task; snapshot: ProjectSnapshot; update: SnapshotUpdate; onBack: () => void; onNext: () => void }) {
  const player = useRef<HTMLVideoElement>(null);
  const [error, setError] = useState("");
  const [visualBusy, setVisualBusy] = useState(false);
  const report = snapshot.benchmark_report as BenchmarkReport | undefined;
  const reference = (task.files as ProjectFile[]).find(file => file.id === report?.source_file_id);

  function playShot(shot: ProjectShot) {
    if (!player.current) return;
    setError("");
    void seekToShot(player.current, Number(shot.original_start_seconds ?? shot.start_seconds ?? 0)).catch(() => setError("浏览器未能自动播放，请在播放器中手动继续"));
  }

  function exportReport() {
    if (!report) return;
    const blob = new Blob([JSON.stringify({ project_id: task.content_id, title: task.title, report, notes: snapshot.benchmark_notes || "", shots: snapshot.shots }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${task.content_id}-拆解报告.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  async function analyzeVisual() {
    setVisualBusy(true); setError("");
    try {
      const result = await api<Task>(`/api/tasks/${task.content_id}/benchmark-visual-analysis`, jsonOptions("POST", {}));
      update({ shots: result.source?.yingxu?.snapshot?.shots || [], visual_analysis: result.source?.yingxu?.snapshot?.visual_analysis });
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Kimi 视觉分析失败"); }
    finally { setVisualBusy(false); }
  }

  if (!report || !reference) return <Card><Empty title="还没有可查看的拆解报告" description="返回上一步上传真实参考视频。" action={<Button onClick={onBack}>返回提供参考</Button>} /></Card>;
  return <>
    <Card>
      <div className="card-head"><div><h2>拆解报告 <Help title="证据与限制"><p>完整视频：点击镜头定位原片。</p><p>逐镜说明：时间码与画面特征。</p><p>缺失信息：不可获取的数据不虚构。</p></Help></h2><p className="sub">完整视频与逐镜说明；点击镜头跳转对应时间。</p></div><Badge tone={report.transcript_status === "succeeded" || report.subtitle_status === "succeeded" ? "green" : "orange"}>{report.transcript_status === "succeeded" ? "转写成功" : report.subtitle_status === "succeeded" ? "无音轨 · 画面字幕" : report.transcript_status === "not_applicable" ? "无音轨 · 不适用" : "转写不可用"}</Badge></div>
      <div className="video-project-original"><strong>完整参考视频</strong><div className="video-project-media"><video ref={player} controls src={reference.url} aria-label="拆解报告完整视频" /></div><p className="sub">{snapshot.shots.length} 镜 · {report.duration_seconds.toFixed(2)} 秒 · 整片转写 {snapshot.transcript_runs || 0} 次；点击下方镜头跳转并播放。</p></div>
      <div className="video-project-note"><strong>报告说明</strong>{report.focus && <p>关注重点：{report.focus}</p>}<p>{report.transcript_status === "unavailable" ? `转写未完成：${report.transcript_error || "原因待确认"}` : report.transcript_status === "not_applicable" ? "参考视频没有音轨，旁白不适用；画面文字通过 RapidOCR 读取，不等同于口播。" : "转写文本按词级时间与镜头范围对应。"}</p>{report.subtitle_error && <p>画面字幕读取未完成：{report.subtitle_error}</p>}</div>
      <h3>逐镜说明</h3><div className="video-project-shot-grid">{snapshot.shots.map((shot, index) => <article className="video-project-shot" key={shot.id || index} role="button" tabIndex={0} aria-label={`镜头 ${index + 1}，跳转到 ${shot.original_start_seconds ?? 0} 秒`} onClick={() => playShot(shot)} onKeyDown={event => { if (event.key === "Enter" && event.target === event.currentTarget) playShot(shot); }}>
        {shot.keyframe_file_id && <img src={`/api/files/${shot.keyframe_file_id}/media`} alt={`镜头 ${index + 1} 真实关键帧`} />}
        <strong>{shot.title || `镜头 ${index + 1}`} · {shot.original_start_seconds ?? 0}–{shot.original_end_seconds ?? shot.duration} 秒</strong>
        <small>画面特征：{shot.visual_observation || "待人工补充"}</small><small>镜头说明：{shot.desc || "待人工补充"}</small><small>旁白：{shot.text || (report.transcript_status === "not_applicable" ? "不适用" : "未识别到文本，待核实")}</small>{report.transcript_status === "not_applicable" && <small>画面字幕：{shot.subtitle_text || "未识别到画面文字"}</small>}
        <details onClick={event => event.stopPropagation()} onKeyDown={event => event.stopPropagation()}><summary>编辑本镜说明</summary><textarea className="textarea" aria-label={`镜头 ${index + 1} 报告说明`} value={shot.desc} onChange={event => update({ shots: snapshot.shots.map((item, position) => position === index ? { ...item, desc: event.target.value } : item) })} /></details>
      </article>)}</div>
      {error && <p className="video-project-error" role="alert">{error}</p>}
    </Card>
    <Card><div className="video-project-field"><label className="video-project-field-label" htmlFor="benchmark-notes">报告备注</label><textarea id="benchmark-notes" className="textarea" value={snapshot.benchmark_notes || ""} onChange={event => update({ benchmark_notes: event.target.value })} placeholder="记录可复用的结构、需要人工核实的内容…" /></div><div className="video-project-actions"><Button disabled={visualBusy} onClick={() => void analyzeVisual()}>{visualBusy ? "正在分析关键帧…" : "✦ 用 Kimi 分析关键帧"}</Button><Button onClick={onBack}>← 上一步</Button><Button onClick={exportReport}>导出报告</Button><Button variant="primary" onClick={onNext}>基于分镜继续制作 →</Button></div><p className="quiet">Kimi 只分析实际读取的关键帧；无法确认的信息仍需人工补充，不会虚构。</p></Card>
  </>;
}

async function generateBenchmarkShot(task: Task, save: (override?: ProjectSnapshot) => Promise<Task>, snapshot: ProjectSnapshot, selected: number) {
  const nextSnapshot = { ...snapshot, shots: snapshot.shots.map((item, index) => index === selected ? { ...item, source: "Remotion 代码", desc: item.replacement_description || item.desc, confirmed: false } : item) };
  const saved = await save(nextSnapshot);
  const file = await api<ProjectFile>(`/api/tasks/${task.content_id}/ai-video`, jsonOptions("POST", { revision: saved.source?.yingxu?.revision || 0, shot_index: selected }));
  const completed = { ...nextSnapshot, shots: nextSnapshot.shots.map((item, index) => index === selected ? { ...item, fileId: file.id, source: "ai_video", audio_source: undefined, aiCandidateFileIds: [...new Set([...(item.aiCandidateFileIds || []), file.id])] } : item) };
  return { file, snapshot: completed };
}

export function ShotEditor({ task, snapshot, files, selected, update, save, onClose }: { task: Task; snapshot: ProjectSnapshot; files: ProjectFile[]; selected: number; update: SnapshotUpdate; save: (override?: ProjectSnapshot) => Promise<Task>; onClose: () => void }) {
  const { refresh } = useApp();
  const originalPlayer = useRef<HTMLVideoElement>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const shot = snapshot.shots[selected];
  const report = snapshot.benchmark_report as BenchmarkReport;
  const reference = files.find(file => file.id === report.source_file_id);
  const current = files.find(file => file.id === shot.fileId);
  const narration = files.find(file => file.id === shot.narrationFileId);
  const available = shotAvailableDuration(shot, files);
  const newDuration = effectiveShotDuration(shot, files);

  useEffect(() => {
    if (originalPlayer.current) originalPlayer.current.currentTime = Number(shot.original_start_seconds || 0);
  }, [selected, shot.original_start_seconds]);

  function patch(values: Partial<ProjectShot>) {
    update({
      shots: snapshot.shots.map((item, index) => index === selected ? { ...item, confirmed: false, ...values } : item),
      musicConfirmed: false,
      musicConflictResolved: snapshot.musicConflict === "replace" ? false : snapshot.musicConflictResolved,
      sampleApprovedFileId: undefined,
      finalApprovedFileId: undefined,
    });
  }

  async function upload(kind: "video" | "narration", file: File) {
    setError("");
    try {
      const result = await uploadProjectFile(task, file, kind === "video" ? "video" : "audio");
      await refresh();
      if (kind === "video") patch({ fileId: result.id, uploadedFileIds: [...new Set([...(shot.uploadedFileIds || []), result.id])], source: "user_upload", trim_start: 0, source_start_seconds: 0, duration_choice: "original", fill_method: undefined, audio_source: undefined, narrationFileId: undefined });
      else patch({ narrationFileId: result.id, audio_source: "replace" });
    } catch (cause) { setError(cause instanceof Error ? cause.message : "文件上传失败"); }
  }

  async function generate() {
    setBusy(true); setError("");
    try {
      const result = await generateBenchmarkShot(task, save, snapshot, selected);
      update({ shots: result.snapshot.shots, musicConfirmed: false, sampleApprovedFileId: undefined, finalApprovedFileId: undefined });
      await refresh();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "AI 单镜生成失败"); }
    finally { setBusy(false); }
  }

  function keepReference() {
    if (!reference) return;
    patch({ fileId: reference.id, source: "reference", trim_start: Number(shot.original_start_seconds || 0), source_start_seconds: Number(shot.original_start_seconds || 0), duration: Number(shot.original_end_seconds || shot.duration) - Number(shot.original_start_seconds || 0), duration_choice: "original", fill_method: undefined, audio_source: "original", narrationFileId: undefined });
  }

  return <Modal open onOpenChange={onClose} title={`镜头 ${selected + 1} · 详情`} description="原片信息只读；新版本、旁白和时长由你逐项确认。" wide>
    <div className="video-project-original"><h3>原视频对照 · {shot.original_start_seconds ?? 0}–{shot.original_end_seconds ?? shot.duration} 秒</h3>{reference && <video ref={originalPlayer} controls src={reference.url} aria-label="原镜头对照视频" />}<p>原片旁白：{shot.text || "无文本 / 待核实"}</p><p>原片画面描述：{shot.desc || "待补充"}</p><p className="sub">原片时间码保持不变，原片信息只读。</p><Button onClick={keepReference} disabled={!reference}>保留原镜头</Button></div>
    <div className="video-project-original"><h3>新旁白</h3><div className="video-project-field"><label className="video-project-field-label" htmlFor="replacement-text">旁白文案</label><textarea id="replacement-text" className="textarea" value={shot.replacement_text ?? shot.text} onChange={event => patch({ replacement_text: event.target.value })} /></div><UploadButton label="上传本镜旁白" accept="audio/*" onFile={file => void upload("narration", file)} />{narration && <><audio controls src={narration.url} aria-label="本镜新旁白" /><MediaSummary file={narration} /></>}</div>
    <div className="video-project-original"><h3>上传视频</h3>{current ? <video controls src={current.url} aria-label="当前替换镜头" /> : <p className="quiet">请选择或上传画面</p>}<div className="video-project-actions"><UploadButton label="上传 / 更换视频" accept="video/*" onFile={file => void upload("video", file)} /></div><MediaSummary file={current} />{(shot.uploadedFileIds?.length || 0) > 0 && <label className="video-project-field">用户上传版本<select className="input" aria-label="用户上传版本" value={shot.source === "user_upload" ? shot.fileId : ""} onChange={event => { const id = Number(event.target.value); patch({ fileId: id, source: "user_upload", trim_start: 0, source_start_seconds: 0, confirmed: false }); }}><option value="">选择上传版本</option>{shot.uploadedFileIds?.map(id => { const file = files.find(item => item.id === id); return file ? <option key={id} value={id}>{file.original_name} · #{id}</option> : null; })}</select></label>}</div>
    <div className="video-project-original"><h3>AI 生成视频</h3><p className="sub">Kimi 生成画面方案，Remotion 输出无声单镜 MP4；上传和 AI 版本分别保留，可选择当前使用版本。</p><div className="video-project-field"><label className="video-project-field-label" htmlFor="replacement-description">新画面描述</label><textarea id="replacement-description" className="textarea" value={shot.replacement_description || ""} onChange={event => patch({ replacement_description: event.target.value })} /></div><div className="video-project-field"><label className="video-project-field-label" htmlFor="replacement-reference">视觉参考建议</label><textarea id="replacement-reference" className="textarea" value={shot.visual_reference || ""} onChange={event => patch({ visual_reference: event.target.value })} placeholder="描述参考构图、材质和运动…" /></div><div className="video-project-actions"><Button disabled={busy} onClick={() => void generate()}>{busy ? "正在生成…" : "✦ AI 生成新版本（Kimi + Remotion）"}</Button></div>{(shot.aiCandidateFileIds?.length || 0) > 0 && <label className="video-project-field">AI 生成版本<select className="input" aria-label="AI 生成版本" value={shot.source === "ai_video" ? shot.fileId : ""} onChange={event => { const id = Number(event.target.value); patch({ fileId: id, source: "ai_video", audio_source: undefined, confirmed: false }); }}><option value="">选择 AI 版本</option>{shot.aiCandidateFileIds?.map(id => { const file = files.find(item => item.id === id); return file ? <option key={id} value={id}>{file.original_name} · #{id}</option> : null; })}</select></label>}</div>
    <fieldset className="video-project-field"><legend className="video-project-field-label">声音检查</legend><div className="video-project-actions">{[["original", "使用视频自带声音"], ["replace", "替换视频旁白"], ["mute", "视频静音"]].map(([value, label]) => <label key={value}><input type="radio" name={`audio-source-${selected}`} checked={shot.audio_source === value} onChange={() => patch({ audio_source: value as ProjectShot["audio_source"] })} />{label}</label>)}</div><small>仅检测音轨是否存在；人声、音乐和音效构成需人工确认。混合音轨不能默认只去除其中一项。</small></fieldset>
    <fieldset className="video-project-field"><legend className="video-project-field-label">有效时长</legend><div className="video-project-actions"><label><input type="radio" name={`duration-${selected}`} checked={shot.duration_choice === "original"} onChange={() => patch({ duration_choice: "original" })} />保持原镜头时长 {shot.duration} 秒</label><label><input type="radio" name={`duration-${selected}`} checked={shot.duration_choice === "new"} onChange={() => patch({ duration_choice: "new" })} />使用新视频时长 {available?.toFixed(2) || "待上传"} 秒，调整后续时间线</label></div></fieldset>
    <div className="video-project-actions"><label>截取起点（秒）<input className="input" type="number" min="0" step="0.1" value={shot.trim_start || 0} onChange={event => patch({ trim_start: Number(event.target.value), source_start_seconds: Number(event.target.value) })} /></label><label>视频不足时补足方式<select className="input" value={shot.fill_method || ""} onChange={event => patch({ fill_method: (event.target.value || undefined) as ProjectShot["fill_method"] })}><option value="">请选择</option><option value="freeze">末帧静止补足</option><option value="loop">循环视频片段</option></select></label></div>
    <div className="video-project-note">原时长 {shot.duration} 秒 · 当前视频可用 {available?.toFixed(2) || "待确认"} 秒 · 新时间线本镜 {newDuration?.toFixed(2) || "待确认"} 秒。不会自动裁切或变速；时间变化后需复查字幕与音乐。</div>
    {shot.audio_source === "replace" && !narration && <p className="video-project-error">选择替换旁白后，必须上传本镜真实音频。</p>}
    {shot.duration_choice === "original" && available !== undefined && available + 0.05 < shot.duration && !shot.fill_method && <p className="video-project-error">新视频短于原时长，请选择末帧静止、循环，或改用新时长。</p>}
    {error && <p className="video-project-error" role="alert">{error}</p>}
    <div className="video-project-dialog-actions"><Button onClick={onClose}>保存本镜</Button><Button variant="primary" disabled={!shotReady(shot, files)} onClick={() => { patch({ confirmed: true }); onClose(); }}>确认本镜</Button></div>
  </Modal>;
}

function ReplacementStage({ task, snapshot, update, save, onBack, onNext }: { task: Task; snapshot: ProjectSnapshot; update: SnapshotUpdate; save: (override?: ProjectSnapshot) => Promise<Task>; onBack: () => void; onNext: () => void }) {
  const { refresh } = useApp();
  const [selected, setSelected] = useState<number | null>(null);
  const [checked, setChecked] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const files = task.files as ProjectFile[];
  const allConfirmed = snapshot.shots.length > 0 && snapshot.shots.every(shot => shot.confirmed && shotReady(shot, files));
  const timeline = snapshot.shots.reduce((total, shot) => total + (effectiveShotDuration(shot, files) || 0), 0);

  async function generateSelected() {
    setBusy(true); setError("");
    try {
      let working = snapshot;
      for (const index of [...checked].sort((a, b) => a - b)) {
        const result = await generateBenchmarkShot(task, save, working, index);
        working = result.snapshot;
        update({ shots: working.shots, musicConfirmed: false, sampleApprovedFileId: undefined, finalApprovedFileId: undefined });
      }
      await refresh();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "AI 单镜生成失败"); }
    finally { setBusy(false); }
  }
  return <Card>
    <div className="card-head"><div><h2>逐镜替换 <Help title="逐镜制作"><p>原片对照：原画面与旁白只读。</p><p>新旁白与画面：逐镜替换并对比时长。</p><p>确认本镜：确定当前使用版本。</p></Help></h2><p className="sub">点击镜头，在同一处对照原片、处理新旁白和画面。</p></div><Badge>新时间线 {timeline.toFixed(2)} 秒</Badge></div>
    <div className="video-project-note">每镜保留原视频时间码和画面对照；用户决定如何修改。</div>
    <div className="video-project-actions"><Button disabled={busy || checked.size === 0} onClick={() => void generateSelected()}>{busy ? "正在生成…" : "分别生成已选分镜（Kimi + Remotion）"}</Button><span className="quiet">已选 {checked.size} 个镜头</span></div>
    <div className="video-project-shot-grid">{snapshot.shots.map((shot, index) => { const current = files.find(file => file.id === shot.fileId); return <article className="video-project-shot" key={shot.id || index}><div className="video-project-shot-head"><label className="video-project-shot-check"><input type="checkbox" checked={checked.has(index)} onChange={event => { const next = new Set(checked); if (event.target.checked) next.add(index); else next.delete(index); setChecked(next); }} />选择分镜</label><Badge tone={shot.confirmed && shotReady(shot, files) ? "green" : "orange"}>{shot.confirmed && shotReady(shot, files) ? "已确认" : "待处理"}</Badge></div>{shot.keyframe_file_id && <img src={`/api/files/${shot.keyframe_file_id}/media`} alt={`原镜头 ${index + 1} 关键帧`} />}<strong>{shot.title || `镜头 ${index + 1}`} · 原 {shot.original_start_seconds ?? 0}–{shot.original_end_seconds ?? shot.duration} 秒</strong><small>{current?.original_name || "未选择新画面"} · {effectiveShotDuration(shot, files)?.toFixed(2) || "待确认"} 秒</small><small>{shot.audio_source === "original" ? "自带声音" : shot.audio_source === "replace" ? "替换旁白" : shot.audio_source === "mute" ? "静音" : "声音未选择"} · 音轨构成需人工确认</small><Button onClick={() => setSelected(index)}>逐镜编辑</Button></article>; })}</div>
    {!allConfirmed && <p className="video-project-note">每一镜都必须选择真实画面、声音来源和有效时长，并单独确认。</p>}
    {error && <p className="video-project-error" role="alert">{error}</p>}
    <div className="video-project-actions"><Button onClick={onBack}>← 上一步</Button><Button variant="primary" disabled={!allConfirmed} onClick={onNext}>确认镜头，继续音乐 →</Button></div>
    {selected !== null && <ShotEditor task={task} snapshot={snapshot} files={files} selected={selected} update={update} save={save} onClose={() => setSelected(null)} />}
  </Card>;
}

export default function BenchmarkProject() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { task, loading } = useProjectTask(id);
  if (!id) return <div className="video-project-workspace"><PageHeader eyebrow="REFERENCE STUDIO" title="对标" description="先还原原片分镜，再逐镜修改。原片是参照，创作决定权在你手中。" actions={<Badge>保留原片逐镜对应关系</Badge>} /><StageNavigation mode="benchmark" current={0} locked onChange={() => undefined} /><CreateBenchmark onCreated={created => navigate(`/projects/benchmark/${created.content_id}`)} /></div>;
  if (loading) return <Empty title="正在读取对标项目" description="正在从原任务恢复报告与素材，请稍候。" />;
  if (!task) return <Empty title="未找到这个对标项目" description="项目可能属于另一个工作区，或链接已经失效。" action={<Link className="button" to="/projects">返回视频项目</Link>} />;
  return <BenchmarkWorkspace key={task.content_id} task={task} />;
}

function BenchmarkWorkspace({ task }: { task: Task }) {
  const { snapshot, update, adoptTask, save, saving, message } = useVideoProject(task);
  const stage = snapshot.workflow_stage ?? 0;
  return <div className="video-project-workspace">
    <PageHeader eyebrow="REFERENCE STUDIO" title="对标" description="先还原原片分镜，再逐镜修改。原片是参照，创作决定权在你手中。" actions={<div className="actions"><Badge>保留原片逐镜对应关系</Badge><Link className="button" to="/projects">我的项目</Link><Link className="button" to={`/tasks/${task.content_id}/editor`}>原编辑器</Link></div>} />
    <StageNavigation mode="benchmark" current={stage} onChange={next => update({ workflow_stage: next })} />
    {stage === 0 && <ReferenceStage task={task} snapshot={snapshot} update={update} adoptTask={adoptTask} onNext={() => update({ workflow_stage: 1 })} />}
    {stage === 1 && <ReportStage task={task} snapshot={snapshot} update={update} onBack={() => update({ workflow_stage: 0 })} onNext={() => update({ workflow_stage: 2 })} />}
    {stage === 2 && <ReplacementStage task={task} snapshot={snapshot} update={update} save={save} onBack={() => update({ workflow_stage: 1 })} onNext={() => update({ workflow_stage: 3 })} />}
    {stage === 3 && <MusicStage task={task} snapshot={snapshot} update={update} save={save} benchmark onBack={() => update({ workflow_stage: 2 })} onNext={() => update({ workflow_stage: 4 })} />}
    {stage === 4 && <FinalStage task={task} snapshot={snapshot} update={update} save={save} onBack={() => update({ workflow_stage: 3 })} />}
    {saving && <p className="quiet">正在保存到原任务…</p>}{message && <p className="video-project-note" role="status">{message}</p>}
  </div>;
}
