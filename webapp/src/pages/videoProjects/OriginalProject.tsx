import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useApp } from "../../AppContext";
import { api, jsonOptions } from "../../lib/api";
import { Badge, Button, Card, Empty, Modal, PageHeader, Progress } from "../../components/ui";
import type { Task } from "../../lib/types";
import { initialSnapshot, sampleApproved, useProjectTask, useVideoProject, type ProjectFile, type ProjectShot, type ProjectSnapshot } from "./useVideoProject";
import { FinalStage, Help, MediaSummary, MusicStage, SampleStage, StageNavigation, StyleLibrary, UploadButton, UploadPanel, uploadProjectFile } from "./ProjectShared";
import "./video-projects.css";

type SnapshotUpdate = (patch: Partial<ProjectSnapshot>) => void;
type Snapshot = ReturnType<typeof initialSnapshot>;

const resetProduction: Partial<ProjectSnapshot> = {
  musicConfirmed: false,
  sampleApprovedFileId: undefined,
  finalApprovedFileId: undefined,
};

function originalSnapshot(form: { direction: string; text: string; platforms: string[]; aspect: string }, stage: number, versions: { text: string; created_at?: string }[] = []): ProjectSnapshot {
  return {
    workflow_stage: stage,
    manuscript: { title: form.direction.trim().slice(0, 60) || "原创项目", text: form.text, versions },
    direction: form.direction,
    target_platforms: form.platforms,
    aspect: form.aspect,
    format: form.aspect === "1920x1080" ? "1920 × 1080 · 横屏" : "1080 × 1920 · 竖屏",
    rhythm: "旁白驱动",
    shots: [],
  };
}

export function CreateOriginal({ onCreated }: { onCreated: (task: Task) => void }) {
  const { refresh } = useApp();
  const [form, setForm] = useState({ direction: "", text: "", platforms: [] as string[], aspect: "" });
  const [custom, setCustom] = useState({ width: "", height: "" });
  const [createdTask, setCreatedTask] = useState<Task>();
  const [candidate, setCandidate] = useState("");
  const [versions, setVersions] = useState<{ text: string; created_at?: string }[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function aspectValue() {
    return form.aspect === "other" ? `${Number(custom.width)}x${Number(custom.height)}` : form.aspect;
  }

  function validate() {
    const missing = [];
    if (!form.text.trim()) missing.push("文案");
    if (!form.platforms.length) missing.push("目标平台");
    if (!form.aspect) missing.push("画幅");
    if (form.aspect === "other" && (!(Number(custom.width) > 0) || !(Number(custom.height) > 0))) missing.push("自定义画幅宽度和高度");
    if (missing.length) { setError(`请填写或选择：${missing.join("、")}`); return false; }
    return true;
  }

  async function ensureProject(stage: number) {
    let task = createdTask;
    if (!task) {
      task = await api<Task>("/api/tasks", jsonOptions("POST", {
        title: form.direction.trim().slice(0, 60) || "原创项目",
        content: form.text,
        source_type: "original",
        direction: form.direction,
        target_platforms: form.platforms,
        aspect: aspectValue() || "1080x1920",
      }));
    }
    const saved = await api<Task>(`/api/tasks/${task.content_id}/yingxu`, jsonOptions("PUT", {
      revision: task.source?.yingxu?.revision || 0,
      snapshot: originalSnapshot({ ...form, aspect: aspectValue() }, stage, versions),
    }));
    setCreatedTask(saved);
    return saved;
  }

  async function suggest() {
    if (!form.direction.trim()) { setError("请先填写叙事方向，再生成或改写文案"); return; }
    setBusy(true); setError("");
    try {
      const task = await ensureProject(0);
      const result = await api<{ candidate: string }>(`/api/tasks/${task.content_id}/yingxu-script-candidate`, jsonOptions("POST", { revision: task.source?.yingxu?.revision || 0 }));
      setCandidate(result.candidate);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "AI 建议生成失败"); }
    finally { setBusy(false); }
  }

  async function create() {
    if (!validate()) return;
    setBusy(true); setError("");
    try {
      const task = await ensureProject(1);
      await refresh();
      onCreated(task);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "创建失败"); }
    finally { setBusy(false); }
  }

  return <Card>
    <div className="card-head"><div><h2>文案创作 <Help title="创作路径"><p>文案与方向：可手写完整文案，也可由 AI 按叙事方向生成。</p><p>真人旁白：上传、修改并确定时长。</p><p>音乐与画面：先音乐，再逐场制作画面。</p></Help></h2><p className="sub">可直接粘贴完整文案，也可只填写叙事方向生成候选；候选采用后才成为正式文案。</p></div><Badge>当前步骤</Badge></div>
    <div className="video-project-field"><label className="video-project-field-label" htmlFor="direction">叙事方向 <span className="quiet">AI 生成时必填</span></label><textarea id="direction" className="textarea" value={form.direction} onChange={event => setForm({ ...form, direction: event.target.value })} placeholder="想对谁说？希望观众感受到什么？" /></div>
    <div className="video-project-field"><label className="video-project-field-label" htmlFor="script">正式文案 <span className="video-project-required">*</span> <span className="quiet">可手写或由 AI 生成</span></label><div className="video-project-actions"><Button size="small" disabled={busy} onClick={() => void suggest()}>{form.text.trim() ? "根据叙事方向改写当前文案" : "根据叙事方向生成候选文案"}</Button></div><textarea id="script" className="textarea" value={form.text} onChange={event => setForm({ ...form, text: event.target.value })} placeholder="在这里粘贴完整文案，或留空后由 AI 生成…" /></div>
    {candidate && <div className="video-project-original"><strong>AI 候选稿 · 尚未采用</strong><textarea className="textarea" aria-label="AI 候选稿" value={candidate} onChange={event => setCandidate(event.target.value)} /><div className="video-project-actions"><Button onClick={() => { setVersions(form.text.trim() ? [...versions, { text: form.text, created_at: new Date().toISOString() }] : versions); setForm({ ...form, text: candidate }); setCandidate(""); }}>采用为正式文案</Button><Button onClick={() => setCandidate("")}>保留当前文案</Button></div></div>}
    <fieldset className="video-project-field"><legend className="video-project-field-label">目标平台 <span className="video-project-required">*</span> <span className="quiet">可多选</span></legend><div className="video-project-actions">{["抖音", "B站", "视频号", "小红书"].map(platform => <label key={platform}><input type="checkbox" checked={form.platforms.includes(platform)} onChange={event => setForm({ ...form, platforms: event.target.checked ? [...form.platforms, platform] : form.platforms.filter(item => item !== platform) })} />{platform}</label>)}</div></fieldset>
    <fieldset className="video-project-field"><legend className="video-project-field-label">画幅 <span className="video-project-required">*</span> <span className="quiet">单选</span></legend><div className="video-project-actions">{[["1920x1080", "横屏 16:9 · 1920 × 1080"], ["1080x1920", "竖屏 9:16 · 1080 × 1920"], ["other", "其他"]].map(([value, label]) => <label key={value}><input type="radio" name="aspect" checked={form.aspect === value} onChange={() => setForm({ ...form, aspect: value })} />{label}</label>)}</div>{form.aspect === "other" && <div className="video-project-actions"><input className="input" type="number" min="1" aria-label="自定义画幅宽度" placeholder="宽度（px）" value={custom.width} onChange={event => setCustom({ ...custom, width: event.target.value })} /><input className="input" type="number" min="1" aria-label="自定义画幅高度" placeholder="高度（px）" value={custom.height} onChange={event => setCustom({ ...custom, height: event.target.value })} /></div>}</fieldset>
    {error && <p className="video-project-error" role="alert">{error}</p>}
    <Button variant="primary" disabled={busy} onClick={() => void create()}>{busy ? "正在保存方案…" : "确认方案，进入视频生成 →"}</Button>
  </Card>;
}

function ManuscriptStage({ task, snapshot, update, save, onNext }: { task: Task; snapshot: Snapshot; update: SnapshotUpdate; save: () => Promise<Task>; onNext: () => void }) {
  const [candidate, setCandidate] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const manuscript = snapshot.manuscript;

  function patch(values: Partial<ProjectSnapshot>) {
    update({ ...values, ...resetProduction, transcriptStale: true });
  }

  async function suggest() {
    if (!snapshot.direction?.trim()) { setError("请先填写叙事方向，再生成或改写文案"); return; }
    setBusy(true); setError("");
    try {
      const saved = await save();
      const result = await api<{ candidate: string }>(`/api/tasks/${task.content_id}/yingxu-script-candidate`, jsonOptions("POST", { revision: saved.source?.yingxu?.revision || 0 }));
      setCandidate(result.candidate);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "AI 建议生成失败"); }
    finally { setBusy(false); }
  }

  const valid = Boolean(manuscript.text.trim() && snapshot.target_platforms?.length && snapshot.aspect);
  return <Card>
    <div className="card-head"><div><h2>文案创作 <Help title="创作路径"><p>文案与方向：可手写完整文案，也可由 AI 按叙事方向生成。</p><p>真人旁白：上传、修改并确定时长。</p><p>音乐与画面：先音乐，再逐场制作画面。</p></Help></h2><p className="sub">可直接粘贴完整文案，也可只填写叙事方向生成候选；候选采用后才成为正式文案。</p></div><Badge>当前步骤</Badge></div>
    <p className="sub">{task.content_id} · {task.title}</p>
    <div className="video-project-field"><label className="video-project-field-label" htmlFor="existing-direction">叙事方向 <span className="quiet">AI 生成时必填</span></label><textarea id="existing-direction" className="textarea" value={snapshot.direction || ""} onChange={event => patch({ direction: event.target.value })} placeholder="想对谁说？希望观众感受到什么？" /></div>
    <div className="video-project-field"><label className="video-project-field-label" htmlFor="existing-script">正式文案 <span className="video-project-required">*</span> <span className="quiet">可手写或由 AI 生成</span></label><div className="video-project-actions"><Button size="small" disabled={busy} onClick={() => void suggest()}>{manuscript.text.trim() ? "根据叙事方向改写当前文案" : "根据叙事方向生成候选文案"}</Button></div><textarea id="existing-script" className="textarea video-project-manuscript" value={manuscript.text} onChange={event => patch({ manuscript: { ...manuscript, text: event.target.value } })} placeholder="在这里粘贴完整文案，或留空后由 AI 生成…" /></div>
    {candidate && <div className="video-project-original"><strong>AI 候选稿 · 尚未采用</strong><textarea className="textarea" aria-label="AI 候选稿" value={candidate} onChange={event => setCandidate(event.target.value)} /><div className="video-project-actions"><Button onClick={() => { patch({ manuscript: { ...manuscript, text: candidate, versions: manuscript.text.trim() ? [...(manuscript.versions || []), { text: manuscript.text, created_at: new Date().toISOString() }] : (manuscript.versions || []) } }); setCandidate(""); }}>采用为正式文案</Button><Button onClick={() => setCandidate("")}>保留当前文案</Button></div></div>}
    <fieldset className="video-project-field"><legend className="video-project-field-label">目标平台 <span className="video-project-required">*</span> <span className="quiet">可多选</span></legend><div className="video-project-actions">{["抖音", "B站", "视频号", "小红书"].map(platform => <label key={platform}><input type="checkbox" checked={snapshot.target_platforms?.includes(platform) || false} onChange={event => patch({ target_platforms: event.target.checked ? [...(snapshot.target_platforms || []), platform] : (snapshot.target_platforms || []).filter(item => item !== platform) })} />{platform}</label>)}</div></fieldset>
    <fieldset className="video-project-field"><legend className="video-project-field-label">画幅 <span className="video-project-required">*</span> <span className="quiet">单选</span></legend><div className="video-project-actions"><select className="input" aria-label="画幅" value={snapshot.aspect || ""} onChange={event => patch({ aspect: event.target.value, format: event.target.value === "1920x1080" ? "1920 × 1080 · 横屏" : "1080 × 1920 · 竖屏" })}><option value="">请选择</option><option value="1920x1080">横屏 16:9 · 1920 × 1080</option><option value="1080x1920">竖屏 9:16 · 1080 × 1920</option>{snapshot.aspect && !["1920x1080", "1080x1920"].includes(snapshot.aspect) && <option value={snapshot.aspect}>其他 · {snapshot.aspect}</option>}</select></div></fieldset>
    {snapshot.transcriptStale && snapshot.transcript && <p className="video-project-note">文案已变化，进入下一步后需重新生成对应旁白的词级时间码。</p>}
    {error && <p className="video-project-error" role="alert">{error}</p>}
    <div className="video-project-actions"><Button variant="primary" disabled={!valid} onClick={onNext}>确认方案，进入视频生成 →</Button></div>
  </Card>;
}

type TranscriptJob = {
  id: string;
  status: string;
  stage: string;
  progress: number;
  result?: { words: { text: string; start: number; end: number }[] };
  error?: { message?: string };
};

const transcriptStageNames: Record<string, string> = {
  queued: "等待转写",
  leased: "等待转写",
  running: "准备转写",
  model_loading: "加载模型",
  model_ready: "模型已就绪",
  transcribing: "转写中",
  writing: "写出字幕",
  succeeded: "已完成",
  failed: "转写失败",
};

export function NarrationStage({ task, snapshot, update, onBack, onNext }: { task: Task; snapshot: Snapshot; update: SnapshotUpdate; onBack: () => void; onNext: () => void }) {
  const { refresh } = useApp();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [job, setJob] = useState<(TranscriptJob & { elapsed: number }) | null>(null);
  const voice = (task.files as ProjectFile[]).find(file => file.id === snapshot.voiceFileId);

  async function upload(file: File) {
    setBusy(true); setError("");
    try {
      const result = await uploadProjectFile(task, file, "audio");
      await refresh();
      update({ voiceFileId: result.id, voiceDuration: result.media_info.duration_seconds, rhythm: "旁白驱动", transcript: undefined, transcriptStale: false, ...resetProduction });
    } catch (cause) { setError(cause instanceof Error ? cause.message : "旁白上传失败"); }
    finally { setBusy(false); }
  }

  async function transcribe() {
    if (!voice) { setError("请先上传真人旁白"); return; }
    const started = Date.now();
    setBusy(true); setError(""); setJob(null);
    try {
      let current = await api<TranscriptJob>(`/api/tasks/${task.content_id}/transcript`, jsonOptions("POST", { file_id: voice.id }));
      setJob({ ...current, elapsed: 0 });
      while (!["succeeded", "failed", "cancelled"].includes(current.status)) {
        await new Promise(resolve => setTimeout(resolve, 1000));
        current = await api<TranscriptJob>(`/api/tasks/${task.content_id}/transcript-jobs/${current.id}`);
        setJob({ ...current, elapsed: Math.floor((Date.now() - started) / 1000) });
      }
      if (current.status !== "succeeded") throw new Error(current.error?.message || "词级时间码生成失败");
      const words = current.result?.words || [];
      if (!words.length) throw new Error("转写完成但没有可用词语，请检查旁白内容");
      await refresh();
      update({ transcript: { words, status: "succeeded" }, transcriptStale: false, workflow_stage: 2 });
    } catch (cause) { setError(cause instanceof Error ? cause.message : "词级时间码生成失败"); }
    finally { setBusy(false); }
  }

  const ready = Boolean(snapshot.transcript?.words?.length) && !snapshot.transcriptStale;
  return <Card>
    <div className="card-head"><div><h2>确定旁白与全片时长 <Help title="声音决定时间"><p>上传录音：以定稿文案为准。</p><p>AI 协助修改：清理、修复与调整。</p><p>词级时间码：分镜切分和字幕同步的依据。</p></Help></h2><p className="sub">上传并确认真人旁白；生成词级时间码，为后续分镜切分和字幕同步提供依据。</p></div><Badge>{ready ? "已生成" : "待生成"}</Badge></div>
    <UploadPanel label="上传真人旁白" accept="audio/*" disabled={busy} onFile={file => void upload(file)} />
    {voice && <><MediaSummary file={voice} /><audio controls src={voice.url} aria-label="当前旁白" /></>}
    <div className="video-project-actions"><Button disabled>✦ AI 修改旁白（未接入）</Button><Button variant="primary" disabled={busy || !voice} onClick={() => void transcribe()}>{busy ? "正在生成…" : "生成词级时间码（必需）"}</Button><span className="quiet">必需：上传旁白后生成，用于分镜切分与字幕同步</span></div>
    {busy && job && <div className="video-project-note" aria-live="polite"><Progress value={job.progress || 0} /><p className="sub">{transcriptStageNames[job.stage] || job.stage} · {Math.round((job.progress || 0) * 100)}% · 已用 {job.elapsed} 秒</p></div>}
    {snapshot.transcriptStale && <p className="video-project-note">当前时间码对应旧文案，必须重新生成。</p>}
    {snapshot.transcript?.words?.length ? <div className="video-project-original"><strong>词级时间码 · 真实转写</strong><p className="sub">用于分镜切分与字幕同步；当前共 {snapshot.transcript.words.length} 个词/片段。</p>{snapshot.transcript.words.map((word, index) => <div className="video-project-actions" key={`${word.text}-${index}`}><input className="input" aria-label={`词语 ${index + 1}`} value={word.text} readOnly /><input className="input" aria-label={`开始 ${index + 1}`} type="number" value={word.start} readOnly /><input className="input" aria-label={`结束 ${index + 1}`} type="number" value={word.end} readOnly /></div>)}</div> : <p className="quiet">未成功生成当前旁白版本的词级时间码不可继续。</p>}
    <div className="video-project-timing"><strong>{voice?.media_info.duration_seconds?.toFixed(2) || "待确认"}</strong><span>秒 · 全片总时长<br />最终旁白确定后显示</span></div>
    {error && <p className="video-project-error" role="alert">{error}</p>}
    <div className="video-project-actions"><Button onClick={onBack}>← 上一步</Button><Button variant="primary" disabled={!ready} onClick={onNext}>确认旁白与时长 →</Button></div>
  </Card>;
}

function StoryboardStage({ task, snapshot, update, save, onBack, onNext }: { task: Task; snapshot: Snapshot; update: SnapshotUpdate; save: (override?: ProjectSnapshot) => Promise<Task>; onBack: () => void; onNext: () => void }) {
  const { refresh } = useApp();
  const [selected, setSelected] = useState<number | null>(null);
  const [checked, setChecked] = useState<Set<number>>(new Set());
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const files = task.files as ProjectFile[];
  const shot = selected === null ? null : snapshot.shots[selected];

  async function plan() {
    setBusy(true); setError("");
    try {
      const saved = await save();
      const result = await api<{ candidate: { shots: ProjectShot[] } }>(`/api/tasks/${task.content_id}/yingxu-director-candidate`, jsonOptions("POST", { revision: saved.source?.yingxu?.revision || 0 }));
      update({ shots: result.candidate.shots, directorPlan: result.candidate, storyboardHistory: [...(snapshot.storyboardHistory || []), snapshot.shots], ...resetProduction });
    } catch (cause) { setError(cause instanceof Error ? cause.message : "编导方案生成失败"); }
    finally { setBusy(false); }
  }

  function patchShot(index: number, patch: Partial<ProjectShot>) {
    update({ shots: snapshot.shots.map((item, position) => position === index ? { ...item, confirmed: false, ...patch } : item), ...resetProduction });
  }

  async function uploadShot(index: number, file: File) {
    setError("");
    try {
      const result = await uploadProjectFile(task, file, "video");
      await refresh();
      patchShot(index, { fileId: result.id, duration: result.media_info.duration_seconds, source: "user_upload" });
    } catch (cause) { setError(cause instanceof Error ? cause.message : "画面文件上传失败"); }
  }

  async function generateShot(index: number, base: ProjectSnapshot) {
    const nextSnapshot = { ...base, shots: base.shots.map((item, position) => position === index ? { ...item, source: "Remotion 代码", confirmed: false } : item) };
    const saved = await save(nextSnapshot);
    const result = await api<ProjectFile>(`/api/tasks/${task.content_id}/ai-video`, jsonOptions("POST", {
      revision: saved.source?.yingxu?.revision || 0, shot_index: index,
    }));
    await refresh();
    const completed = { ...nextSnapshot, shots: nextSnapshot.shots.map((item, position) => position === index ? { ...item, fileId: result.id, source: "ai_video", aiCandidateFileIds: [...new Set([...(item.aiCandidateFileIds || []), result.id])] } : item) };
    update({ shots: completed.shots, ...resetProduction });
    return completed;
  }

  async function generateSelected(index?: number) {
    setBusy(true); setError("");
    try {
      let working = snapshot;
      const indexes = index === undefined ? [...checked].sort((a, b) => a - b) : [index];
      for (const current of indexes) working = await generateShot(current, working);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "AI 单镜生成失败"); }
    finally { setBusy(false); }
  }

  const allConfirmed = snapshot.shots.length > 0 && snapshot.shots.every(item => item.confirmed && (item.fileId || item.source === "Remotion 代码"));
  const sampleApprovedForRender = sampleApproved(snapshot);
  return <>
    <StyleLibrary snapshot={snapshot} update={update} />
    <Card>
      <div className="card-head"><div><h2>分镜工作台 <Help title="画面制作"><p>选择风格：查看参考视频并确定风格。</p><p>逐镜制作：编辑描述、素材并检查画面。</p><p>样片检查：选择片段并确认。</p></Help></h2><p className="sub">编辑每个镜头，再生成和检查样片。</p></div><Badge>{snapshot.shots.length} 镜</Badge></div>
      <div className="video-project-actions"><strong>当前风格：{snapshot.style || "未选择"}</strong><Button disabled={busy || !snapshot.style || !snapshot.transcript?.words?.length || snapshot.transcriptStale} onClick={() => void plan()}>{busy ? "正在生成…" : "✦ 生成分镜"}</Button></div>
      <div className="video-project-actions"><Button disabled={busy || checked.size === 0} onClick={() => void generateSelected()}>{busy ? "正在生成…" : "分别生成已选分镜（Kimi + Remotion）"}</Button><span className="quiet">已选 {checked.size} 个镜头</span></div>
      {(!snapshot.style || !snapshot.transcript?.words?.length || snapshot.transcriptStale) && <p className="video-project-note">生成方案前需选择画风，并具有当前文案与旁白对应的有效时间码。</p>}
      {error && <p className="video-project-error" role="alert">{error}</p>}
      {snapshot.shots.length ? <div className="video-project-shot-grid">{snapshot.shots.map((item, index) => <article className="video-project-shot" key={item.id || index}><div className="video-project-shot-head"><label className="video-project-shot-check"><input type="checkbox" checked={checked.has(index)} onChange={event => { const next = new Set(checked); if (event.target.checked) next.add(index); else next.delete(index); setChecked(next); }} />选择分镜</label><Badge>{item.confirmed ? "已确认" : item.fileId ? "已上传" : "待处理"}</Badge></div>{item.keyframe_file_id && <img src={`/api/files/${item.keyframe_file_id}/media`} alt={`镜头 ${index + 1} 关键帧`} />}<strong>{item.title || `镜头 ${index + 1}`}</strong><small>{item.start_seconds ?? 0}–{item.end_seconds ?? item.duration} 秒 · {item.text || "无旁白"}</small><small>{item.desc || item.visual_observation || "画面描述待补充"}</small><Button size="small" onClick={() => setSelected(index)}>逐镜编辑</Button></article>)}</div> : <Empty title="还没有分镜" description="先选择画风并生成真实编导方案，或在原编辑器中手工添加。" action={<Link className="button" to={`/tasks/${task.content_id}/editor`}>打开原编辑器</Link>} />}
      <SampleStage task={task} snapshot={snapshot} update={update} save={save} />
      <div className="video-project-actions"><Button onClick={onBack}>← 上一步</Button><Button variant="primary" disabled={!allConfirmed || !sampleApprovedForRender} onClick={onNext}>进入合成验收 →</Button></div>
    </Card>
    {shot && selected !== null && <Modal open onOpenChange={() => setSelected(null)} title={`镜头 ${selected + 1} · 详情`} description="修改不会自动改变其他镜头；上传与 AI 版本分开保留。" wide>
      <div className="video-project-field"><label className="video-project-field-label" htmlFor="shot-time">起止时间（秒）</label><div className="video-project-actions"><input id="shot-time" className="input" aria-label="镜头开始时间" type="number" min="0" value={shot.start_seconds ?? 0} onChange={event => patchShot(selected, { start_seconds: Number(event.target.value) })} /><input className="input" aria-label="镜头结束时间" type="number" min="0.1" value={shot.end_seconds ?? shot.duration} onChange={event => patchShot(selected, { end_seconds: Number(event.target.value), duration: Number(event.target.value) - Number(shot.start_seconds ?? 0) })} /></div></div>
      <div className="video-project-field"><label className="video-project-field-label" htmlFor="shot-text">旁白文字</label><textarea id="shot-text" className="textarea" value={shot.text} onChange={event => patchShot(selected, { text: event.target.value })} /><Button disabled={!snapshot.voiceFileId}>▶ 试听对应旁白（未接入分段播放）</Button></div>
      <div className="video-project-original"><strong>上传视频</strong>{shot.fileId ? <video controls src={files.find(file => file.id === shot.fileId)?.url} aria-label="当前镜头画面" /> : <p className="quiet">请选择或上传视频</p>}<MediaSummary file={files.find(file => file.id === shot.fileId)} /><UploadButton label="上传 / 更换视频" accept="video/*" onFile={file => void uploadShot(selected, file)} /></div>
      <div className="video-project-original"><strong>AI 生成视频</strong><p className="sub">Kimi 生成画面方案，Remotion 输出无声单镜 MP4；上传和 AI 版本分别保留，可选择当前使用版本。</p><div className="video-project-field"><label className="video-project-field-label" htmlFor="shot-description">新画面描述</label><textarea id="shot-description" className="textarea" value={shot.desc} onChange={event => patchShot(selected, { desc: event.target.value })} /></div><div className="video-project-field"><label className="video-project-field-label" htmlFor="shot-reference">视觉参考建议</label><textarea id="shot-reference" className="textarea" value={shot.visual_reference || ""} onChange={event => patchShot(selected, { visual_reference: event.target.value })} placeholder="描述参考构图、材质和运动…" /></div><div className="video-project-actions"><Button disabled={busy} onClick={() => void generateSelected(selected)}>{busy ? "正在生成…" : "✦ AI 生成新版本（Kimi + Remotion）"}</Button></div>{(shot.aiCandidateFileIds?.length || 0) > 0 && <label className="video-project-field">AI 生成版本<select className="input" aria-label="AI 生成版本" value={shot.source === "ai_video" ? shot.fileId : ""} onChange={event => patchShot(selected, { fileId: Number(event.target.value), source: "ai_video" })}><option value="">选择 AI 版本</option>{shot.aiCandidateFileIds?.map(id => { const file = files.find(item => item.id === id); return file ? <option key={id} value={id}>{file.original_name} · #{id}</option> : null; })}</select></label>}</div>
      <div className="video-project-dialog-actions"><Button onClick={() => setSelected(null)}>保存本镜</Button><Button variant="primary" disabled={!shot.fileId && shot.source !== "Remotion 代码"} onClick={() => { patchShot(selected, { confirmed: true }); setSelected(null); }}>确认本镜</Button></div>
    </Modal>}
  </>;
}

export default function OriginalProject() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { task, loading } = useProjectTask(id);
  if (!id) return <div className="video-project-workspace"><PageHeader eyebrow="ORIGINAL STUDIO" title="原创" description="从你的文案和叙事方向出发，让声音、音乐与画面逐步成形。" actions={<Badge>你的表达，由你决定</Badge>} /><StageNavigation mode="original" current={0} locked onChange={() => undefined} /><CreateOriginal onCreated={created => navigate(`/projects/original/${created.content_id}`)} /></div>;
  if (loading) return <Empty title="正在读取视频项目" description="正在从原任务恢复内容，请稍候。" />;
  if (!task) return <Empty title="未找到这个视频项目" description="项目可能属于另一个工作区，或链接已经失效。" action={<Link className="button" to="/projects">返回视频项目</Link>} />;
  return <OriginalWorkspace key={task.content_id} task={task} />;
}

function OriginalWorkspace({ task }: { task: Task }) {
  const { snapshot, update, save, saving, message } = useVideoProject(task);
  const stage = snapshot.workflow_stage ?? 0;
  return <div className="video-project-workspace">
    <PageHeader eyebrow="ORIGINAL STUDIO" title="原创" description="从你的文案和叙事方向出发，让声音、音乐与画面逐步成形。" actions={<div className="actions"><Badge>你的表达，由你决定</Badge><Link className="button" to="/projects">我的项目</Link><Link className="button" to={`/tasks/${task.content_id}/editor`}>原编辑器</Link></div>} />
    <StageNavigation mode="original" current={stage} onChange={next => update({ workflow_stage: next })} />
    {stage === 0 && <ManuscriptStage task={task} snapshot={snapshot} update={update} save={save} onNext={() => update({ workflow_stage: 1 })} />}
    {stage === 1 && <NarrationStage task={task} snapshot={snapshot} update={update} onBack={() => update({ workflow_stage: 0 })} onNext={() => update({ workflow_stage: 2 })} />}
    {stage === 2 && <MusicStage task={task} snapshot={snapshot} update={update} save={save} onBack={() => update({ workflow_stage: 1 })} onNext={() => update({ workflow_stage: 3 })} />}
    {stage === 3 && <StoryboardStage task={task} snapshot={snapshot} update={update} save={save} onBack={() => update({ workflow_stage: 2 })} onNext={() => update({ workflow_stage: 4 })} />}
    {stage === 4 && <FinalStage task={task} snapshot={snapshot} update={update} save={save} requireSample onBack={() => update({ workflow_stage: 3 })} />}
    {saving && <p className="quiet">正在保存到原任务…</p>}{message && <p className="video-project-note" role="status">{message}</p>}
  </div>;
}
