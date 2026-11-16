import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { api, jsonOptions } from "../../lib/api";
import { useApp } from "../../AppContext";
import { Badge, Button, Card, Modal } from "../../components/ui";
import type { Task } from "../../lib/types";
import { effectiveShotDuration, fileAudioPresent, fileDuration, sampleApproved, stageNames, type ProjectFile, type ProjectSnapshot, type ProjectType } from "./useVideoProject";

type SnapshotUpdate = (patch: Partial<ProjectSnapshot> | ((value: ProjectSnapshot) => ProjectSnapshot)) => void;

export function StageNavigation({ mode, current, onChange, locked = false }: { mode: ProjectType; current: number; onChange: (stage: number) => void; locked?: boolean }) {
  return <nav className="card video-project-stage-nav" aria-label="视频项目阶段">{stageNames[mode].map((name, index) => <span key={name} style={{ display: "contents" }}>{index > 0 && <i className="video-project-stage-line" />}<button type="button" aria-label={`查看${name}页面`} disabled={locked && index > current} className={`video-project-stage-button ${index === current ? "active" : index < current ? "done" : ""}`} onClick={() => onChange(index)}><strong>{index < current ? "✓" : String(index + 1).padStart(2, "0")}</strong>{name}</button></span>)}</nav>;
}

export function Help({ title, children }: { title: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return <span className="video-project-help"><Button size="small" variant="ghost" aria-label={`查看${title}提示`} aria-expanded={open} onClick={() => setOpen(value => !value)}>?</Button>{open && <div className="video-project-help-content"><strong>{title}</strong>{children}</div>}</span>;
}

export function UploadButton({ label, accept, onFile, disabled = false }: { label: string; accept: string; onFile: (file: File) => void; disabled?: boolean }) {
  const id = useId();
  return <label className="button" htmlFor={id} aria-disabled={disabled}>{label}<input id={id} type="file" accept={accept} hidden disabled={disabled} onChange={event => {
    const file = event.target.files?.[0];
    if (file) onFile(file);
    event.target.value = "";
  }} /></label>;
}

export function UploadPanel({ label, accept, onFile, disabled = false }: { label: string; accept: string; onFile: (file: File) => void; disabled?: boolean }) {
  const id = useId();
  const [fileName, setFileName] = useState("");
  return <div className="empty video-project-upload"><div className="video-project-upload-icon">↥</div><strong>{label}</strong><p>选择文件后可在此查看文件名</p><label className="button" htmlFor={id} aria-disabled={disabled}>选择文件<input id={id} type="file" accept={accept} hidden disabled={disabled} onChange={event => {
    const file = event.target.files?.[0];
    if (file) { setFileName(file.name); onFile(file); }
    event.target.value = "";
  }} /></label><p>{fileName || "尚未选择文件"}</p></div>;
}

export async function uploadProjectFile(task: Task, file: File, kind: string): Promise<ProjectFile> {
  return api<ProjectFile>(`/api/tasks/${task.content_id}/yingxu-files?kind=${encodeURIComponent(kind)}&filename=${encodeURIComponent(file.name)}`, {
    method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: file,
  });
}

export function MediaSummary({ file }: { file?: ProjectFile }) {
  if (!file) return <p className="quiet">尚未选择文件</p>;
  const duration = fileDuration(file);
  return <div className="video-project-note"><strong>{file.original_name}</strong><p>{duration === undefined ? "时长待读取" : `时长 ${duration.toFixed(2)} 秒`} · {fileAudioPresent(file) ? "检测到音轨，人声、音乐和音效需人工确认" : "未检测到音轨"}</p></div>;
}

export function MusicStage({ task, snapshot, update, save, onBack, onNext, benchmark = false }: {
  task: Task;
  snapshot: ProjectSnapshot;
  update: SnapshotUpdate;
  save: () => Promise<Task>;
  onBack: () => void;
  onNext: () => void;
  benchmark?: boolean;
}) {
  const { refresh } = useApp();
  const folderId = useId();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [separationStatus, setSeparationStatus] = useState("");
  const [mixing, setMixing] = useState(false);
  const [folderStatus, setFolderStatus] = useState("首次使用：请先选择音乐库文件夹");
  const voiceRef = useRef<HTMLAudioElement>(null);
  const musicRef = useRef<HTMLAudioElement>(null);
  const files = task.files as ProjectFile[];
  const voice = files.find(file => file.id === snapshot.voiceFileId);
  const music = files.find(file => file.id === snapshot.bgmFileId);
  const adapted = files.find(file => file.id === snapshot.musicAdaptedFileId);
  const musicConfirmed = Boolean(snapshot.musicConfirmed);
  const targetDuration = benchmark ? snapshot.shots.reduce((total, shot) => total + (effectiveShotDuration(shot, files) || 0), 0) : fileDuration(voice);
  const replacementReady = snapshot.shots.every(shot => {
    const file = files.find(item => item.id === shot.fileId);
    return !fileAudioPresent(file) || shot.audio_source !== "original";
  });
  const conflictResolved = !benchmark || (snapshot.musicConflict === "replace" ? replacementReady : Boolean(snapshot.musicConflictResolved));
  const confirmationReady = benchmark
    ? conflictResolved && (snapshot.musicConflict === "original" || Boolean(adapted))
    : Boolean(adapted);
  const audioFiles = files.filter(file => file.kind === "audio" && file.id !== snapshot.voiceFileId && !snapshot.shots.some(shot => shot.narrationFileId === file.id));

  async function uploadMusic(file: File) {
    setBusy(true); setError("");
    try {
      const result = await uploadProjectFile(task, file, "audio");
      await refresh();
      update({ bgmFileId: result.id, musicAdaptedFileId: undefined, musicConfirmed: false, finalApprovedFileId: undefined });
    } catch (cause) { setError(cause instanceof Error ? cause.message : "音乐上传失败"); }
    finally { setBusy(false); }
  }

  async function generateMusic() {
    if (!targetDuration) { setError("请先确认视频时长"); return; }
    setBusy(true); setError("");
    try {
      await save();
      const result = await api<Task>(`/api/tasks/${task.content_id}/music-generate`, jsonOptions("POST", {
        duration_seconds: targetDuration, direction: snapshot.musicDirection || "克制、清晰、轻柔，不遮挡旁白",
      }));
      const generated = [...result.files].reverse().find(file => file.media_info.provider === "kimi_cli" && file.media_info.renderer === "local_score_synth");
      if (!generated) throw new Error("服务未返回 Kimi 配乐文件");
      await refresh();
      update({ bgmFileId: generated.id, musicAdaptedFileId: undefined, musicConfirmed: false, finalApprovedFileId: undefined });
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Kimi 配乐生成失败"); }
    finally { setBusy(false); }
  }

  async function separateMusic() {
    if (!music) { setError("请先选择要分离的音频"); return; }
    setBusy(true); setError(""); setSeparationStatus("");
    try {
      await api<Task>(`/api/tasks/${task.content_id}/audio-separate`, jsonOptions("POST", { file_id: music.id }));
      await refresh();
      setSeparationStatus("已生成独立人声和伴奏文件；原音频未修改，请在音乐库中试听选择。");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "声音分离失败"); }
    finally { setBusy(false); }
  }

  async function importFolder(fileList: FileList | null) {
    if (!fileList?.length) return;
    const audio = Array.from(fileList).filter(file => file.type.startsWith("audio/") || /\.(mp3|wav|m4a|aac|ogg|flac)$/i.test(file.name));
    setFolderStatus(`正在导入 ${audio.length} 首音乐…`);
    setBusy(true); setError("");
    try {
      for (const file of audio) await uploadProjectFile(task, file, "audio");
      await refresh();
      const folder = (fileList[0] as File & { webkitRelativePath?: string }).webkitRelativePath?.split("/")[0] || "已选择文件夹";
      setFolderStatus(`当前文件夹：${folder} · 已导入 ${audio.length} 首`);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "音乐库导入失败"); setFolderStatus("导入失败，请重试"); }
    finally { setBusy(false); }
  }

  async function adapt() {
    if (!music || !targetDuration) { setError(benchmark ? "请先完成逐镜时长处理并选择音乐" : "请先上传旁白并选择音乐"); return; }
    setBusy(true); setError("");
    try {
      const saved = await save();
      const requested = snapshot.musicAdaptMethod || "suggest";
      const method = requested === "suggest" ? (Number(fileDuration(music)) > targetDuration ? "trim_fade" : "loop") : requested;
      const result = await api<Task>(`/api/tasks/${task.content_id}/music-adapt`, jsonOptions("POST", {
        file_id: music.id, method, duration_seconds: targetDuration,
      }));
      const adaptedFile = (result.files as ProjectFile[]).find(file => file.media_info.adapted_from === music.id);
      if (!adaptedFile) throw new Error("服务未返回可识别的音乐适配版本");
      await refresh();
      update({ bgmFileId: adaptedFile.id, musicAdaptedFileId: adaptedFile.id, musicConfirmed: false, finalApprovedFileId: undefined });
      if (saved.content_id !== task.content_id) throw new Error("项目编号发生变化，请停止操作并检查");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "适配失败"); }
    finally { setBusy(false); }
  }

  function playMix() {
    if (!music || (!voice && !benchmark)) { setError("请先上传旁白并选择音乐"); return; }
    if (mixing) {
      voiceRef.current?.pause(); musicRef.current?.pause(); setMixing(false); return;
    }
    if (musicRef.current) musicRef.current.volume = 0.35;
    const players = [voiceRef.current?.play(), musicRef.current?.play()].filter(Boolean) as Promise<void>[];
    void Promise.all(players).catch(() => setError("无法试听，请检查音频格式"));
    setMixing(true);
  }

  return <div className="video-project-layout music-layout">
    <Card>
      <div className="card-head"><div><h2>{benchmark ? "单独替换背景音乐" : "确定音乐"} <Help title="音乐与旁白"><p>分别试听声音和音乐，确认时长与适配版本。原曲不会被覆盖。</p></Help></h2><p className="sub">{benchmark ? "按逐镜旁白的当前时间线选择音乐；画面时长确定后需重新检查适配。" : "根据已确认的旁白与全片时长，确定配乐。"}</p></div><Badge>真实音频</Badge></div>
      {benchmark && <div className="video-project-note"><strong>视频自带声音检查</strong><p>{snapshot.shots.some(shot => shot.audio_source === "original") ? "有镜头使用视频自带声音，可能包含音乐。请选择处理方式后继续。" : "当前没有标记使用自带声音的镜头；仍应检查实际音轨。"}</p><div className="video-project-actions">{[["original", "保留视频自带声音，不另加背景音乐"], ["replace", "使用新背景音乐，先处理原视频声音"], ["mix", "保留自带声音并叠加新音乐（由我试听确认）"]].map(([value, label]) => <label key={value}><input type="radio" name="music-conflict" checked={snapshot.musicConflict === value} onChange={() => update({ musicConflict: value as ProjectSnapshot["musicConflict"], musicConflictResolved: value !== "replace", musicConfirmed: false, finalApprovedFileId: undefined })} />{label}</label>)}</div><p>混合音轨不能默认只去除音乐；需要静音或可靠分离后由用户确认。</p>{snapshot.musicConflict === "replace" && !replacementReady && <p className="video-project-error">仍有镜头使用自带声音。请返回逐镜替换，将这些镜头改为替换旁白或静音。</p>}</div>}
      <div className="video-project-original"><strong>旁白与配乐对比</strong><div className="video-project-compare">
        <section><h3>{benchmark ? "当前时间线" : "旁白"} · {targetDuration ? `${targetDuration.toFixed(2)} 秒` : "待确认"}</h3>{voice ? <audio ref={voiceRef} controls src={voice.url} /> : <p className="quiet">{benchmark ? "逐镜声音在上一页逐镜试听" : "尚未上传旁白，返回上一步添加"}</p>}</section>
        <section><h3>当前配乐 · {music ? `${music.original_name} · ${fileDuration(music)?.toFixed(2) || "待获取"} 秒` : "尚未选择"}</h3>{music ? <audio ref={musicRef} controls src={music.url} /> : <p className="quiet">从音乐库选择或上传</p>}{adapted && <p className="sub">适配版本 #{adapted.id} · 原曲 #{adapted.media_info.adapted_from} 不变</p>}</section>
      </div><p>时长差异：{targetDuration && music ? `${(fileDuration(music)! - targetDuration).toFixed(2)} 秒` : "选择有时长的旁白与配乐后显示差异"}；不会静默裁切或变速。</p></div>
      {snapshot.musicConflict !== "original" && <>
        <div className="video-project-field"><label className="video-project-field-label" htmlFor="adapt-method">音乐时长适配</label><select id="adapt-method" className="input" value={snapshot.musicAdaptMethod || "suggest"} onChange={event => update({ musicAdaptMethod: event.target.value, musicAdaptedFileId: undefined, musicConfirmed: false })}><option value="suggest">AI 建议适配方式</option><option value="trim_fade">音乐较长：选择结束点并淡出</option><option value="loop">音乐较短：循环衔接</option><option value="keep_silence">音乐较短：保留无音乐段落</option><option disabled>音乐较短：补充音乐（未接入）</option></select><p className="sub">适配当前视频，音乐库原曲不变。</p><div className="video-project-actions"><Button disabled={busy || !music || !targetDuration} onClick={() => void adapt()}>✦ AI 适配时长</Button><Button disabled={!music || (!voice && !benchmark)} onClick={playMix}>{mixing ? "暂停试听" : "▶ 试听适配后配乐与旁白"}</Button><Button disabled={!confirmationReady || musicConfirmed} onClick={() => update({ musicConfirmed: true, finalApprovedFileId: undefined })}>确认适配效果</Button></div></div>
        <UploadPanel label="上传音乐或一次导入音乐库" accept="audio/*" disabled={busy} onFile={file => void uploadMusic(file)} />
        <div className="video-project-field"><label className="video-project-field-label" htmlFor="music-direction">音乐方向</label><input id="music-direction" className="input" value={snapshot.musicDirection || ""} onChange={event => update({ musicDirection: event.target.value })} placeholder="例如：克制的钢琴，情绪逐渐明朗" /></div>
        <div className="video-project-actions"><Button disabled={busy || !targetDuration} onClick={() => void generateMusic()}>{busy ? "正在生成…" : "✦ AI 生成配乐（Kimi）"}</Button><Button disabled={busy || !music} onClick={() => void separateMusic()}>分离当前音频人声 / 伴奏</Button><p className="sub">Kimi 创作原创音符谱，客户端本地合成为真实 WAV；不是外部音乐大模型。分离由 Kimi 规划、本地 Demucs 执行。</p>{separationStatus && <p className="sub" role="status">{separationStatus}</p>}</div>
        {adapted && <div className="video-project-note">适配版本已生成，请试听后确认。更换曲目、镜头声音或时长会要求重新确认。</div>}
      </>}
      {benchmark && snapshot.musicConflict === "original" && <div className="video-project-actions"><Button disabled={!confirmationReady || musicConfirmed} onClick={() => update({ musicConfirmed: true, finalApprovedFileId: undefined })}>确认不另加音乐</Button></div>}
      {error && <p className="video-project-error" role="alert">{error}</p>}
      <div className="video-project-actions"><Button onClick={onBack}>← 上一步</Button><Button variant="primary" disabled={!musicConfirmed || !conflictResolved} onClick={onNext}>{benchmark ? "确认音乐，继续合成 →" : "确认音乐 →"}</Button></div>
    </Card>
    <Card>
      <div className="card-head"><div><h2>音乐库</h2><p className="sub">首次使用先设置本地音乐文件夹，再浏览和选择音乐。</p></div><Badge>真实曲库</Badge></div>
      <label className="button" htmlFor={folderId} aria-disabled={busy}>选择 / 更换本地文件夹<input id={folderId} type="file" accept="audio/*" multiple hidden disabled={busy} {...{ webkitdirectory: "" }} onChange={event => { void importFolder(event.target.files); event.target.value = ""; }} /></label>
      <p className="sub">{folderStatus}</p>
      <div className="video-project-note">{music ? `当前选择：${music.original_name}` : "尚未选择音乐"}</div>
      <div className="video-project-library">{audioFiles.map(file => <div className="video-project-track" key={file.id}><div><strong>{file.original_name}</strong><small>#{file.id} · {fileDuration(file)?.toFixed(2) || "待获取"} 秒 · {file.media_info.adapted_from ? "适配版本" : "原始文件"}</small></div><audio controls src={file.url} aria-label={`试听${file.original_name}`} /><Button size="small" variant={snapshot.bgmFileId === file.id ? "primary" : "default"} onClick={() => update({ bgmFileId: file.id, musicAdaptedFileId: file.media_info.adapted_from ? file.id : undefined, musicConfirmed: false, finalApprovedFileId: undefined })}>{snapshot.bgmFileId === file.id ? "已选择" : "选择"}</Button></div>)}</div>
      <p className="sub">文件夹中的音乐会真实复制到当前项目；Kimi 原创配乐也会保存到当前项目音乐库。</p>
    </Card>
  </div>;
}

export function SampleStage({ task, snapshot, update, save }: { task: Task; snapshot: ProjectSnapshot; update: SnapshotUpdate; save: () => Promise<Task> }) {
  const { refresh } = useApp();
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const files = task.files as ProjectFile[];
  const sampleIds = snapshot.sampleFileIds?.length ? snapshot.sampleFileIds : snapshot.sampleFileId ? [snapshot.sampleFileId] : [];
  const approvedIds = snapshot.sampleApprovedFileIds || (snapshot.sampleApprovedFileId ? [snapshot.sampleApprovedFileId] : []);
  const samples = sampleIds.map(id => files.find(file => file.id === id)).filter((file): file is ProjectFile => Boolean(file));
  const approved = sampleApproved(snapshot);

  async function render() {
    setBusy(true); setError("");
    try {
      const saved = await save();
      const indices = selected.size ? [...selected] : [undefined];
      const generated: number[] = [];
      for (const index of indices) {
        const file = await api<ProjectFile>(`/api/tasks/${task.content_id}/yingxu-render`, jsonOptions("POST", {
          revision: saved.source?.yingxu?.revision || 0, preview: true, shot_index: index,
        }));
        generated.push(file.id);
      }
      await refresh();
      update({ sampleFileIds: generated, sampleFileId: generated.at(-1), sampleApprovedFileIds: [], sampleApprovedFileId: undefined, finalApprovedFileId: undefined });
    } catch (cause) { setError(cause instanceof Error ? cause.message : "样片生成失败"); }
    finally { setBusy(false); }
  }

  function approve(id: number) {
    const nextApproved = [...new Set([...approvedIds, id])];
    const nextSnapshot = { ...snapshot, sampleFileIds: sampleIds, sampleApprovedFileIds: nextApproved };
    update({ sampleApprovedFileIds: nextApproved, sampleApprovedFileId: sampleApproved(nextSnapshot) ? id : undefined, finalApprovedFileId: undefined });
  }

  return <div className="video-project-sample">
    <div className="card-head"><div><h3>样片检查</h3><p className="sub">手动选镜或自动选取不超过 10 秒的片段。</p></div><Button disabled={busy || !snapshot.shots.length} onClick={() => void render()}>{busy ? `正在生成 ${selected.size || 1} 条样片…` : "生成样片"}</Button></div>
    <div className="video-project-actions">{snapshot.shots.map((shot, index) => <label key={shot.id || index}><input type="checkbox" checked={selected.has(index)} onChange={event => { const next = new Set(selected); if (event.target.checked) next.add(index); else next.delete(index); setSelected(next); }} />{shot.title || `镜头 ${index + 1}`}</label>)}<span className="quiet">不选择时自动生成一条 ≤10 秒样片</span></div>
    {samples.map((sample, index) => <section key={sample.id}><video controls src={sample.url} aria-label={`真实渲染样片 ${index + 1}`} /><p className="sub">{sample.original_name} · 文件 #{sample.id}</p><Button variant="primary" disabled={approvedIds.includes(sample.id)} onClick={() => approve(sample.id)}>{approvedIds.includes(sample.id) ? "样片已通过" : "样片通过"}</Button></section>)}
    {approved && <p className="video-project-note">所选样片均已人工通过，可以进入完整成片。</p>}
    {error && <p className="video-project-error" role="alert">{error}</p>}
  </div>;
}

export function FinalStage({ task, snapshot, update, save, onBack, requireSample = false }: {
  task: Task;
  snapshot: ProjectSnapshot;
  update: SnapshotUpdate;
  save: () => Promise<Task>;
  onBack: () => void;
  requireSample?: boolean;
}) {
  const navigate = useNavigate();
  const { refresh } = useApp();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const files = task.files as ProjectFile[];
  const deliveredId = Number(task.source?.yingxu_handoff?.file_id || 0);
  const finalCandidates = files.filter(file => file.kind === "video" && (file.id === snapshot.finalFileId || file.id === deliveredId || /yingxu-final/i.test(file.original_name)));
  const final = finalCandidates.find(file => file.id === snapshot.finalFileId) || finalCandidates.find(file => file.id === deliveredId);
  const finalApproved = Boolean(final && snapshot.finalApprovedFileId === final.id);
  const sampleApprovedForRender = !requireSample || sampleApproved(snapshot);

  async function render() {
    setBusy(true); setError("");
    try {
      const saved = await save();
      const file = await api<ProjectFile>(`/api/tasks/${task.content_id}/yingxu-render`, jsonOptions("POST", {
        revision: saved.source?.yingxu?.revision || 0, preview: false,
      }));
      await refresh();
      update({ finalFileId: file.id, finalApprovedFileId: undefined });
    } catch (cause) { setError(cause instanceof Error ? cause.message : "渲染失败"); }
    finally { setBusy(false); }
  }

  async function handoff() {
    if (!final || !finalApproved) return;
    setBusy(true); setError("");
    try {
      const saved = await save();
      const result = await api<Task>(`/api/tasks/${task.content_id}/yingxu-handoff`, jsonOptions("POST", {
        file_id: final.id, revision: saved.source?.yingxu?.revision || 0,
      }));
      const batch = result.source?.yingxu_handoff?.review_batch_id;
      navigate(batch ? `/review?batch_id=${batch}` : "/review");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "交付失败"); }
    finally { setBusy(false); }
  }

  return <Card>
    <div className="card-head"><div><h2>合成与验收 <Help title="最后检查"><p>先检查镜头、字幕、旁白和音乐，再生成、预览并人工验收完整成片。</p></Help></h2><p className="sub">先检查时间线，再生成、预览并验收完整成片。</p></div><Badge tone={finalApproved ? "green" : "orange"}>{finalApproved ? "已验收" : "待验收"}</Badge></div>
    <div className="video-project-original"><strong>1 · 检查 Remotion 时间线</strong><p className="sub">检查镜头、字幕、旁白与音乐。</p><div className="video-project-actions"><Button disabled>↗ 打开 Remotion 时间线（未配置）</Button><Button variant="primary" disabled={busy || !snapshot.shots.length || !sampleApprovedForRender} onClick={() => void render()}>{busy ? "正在生成…" : "时间线检查完成，生成完整成片"}</Button></div>{!sampleApprovedForRender && <p className="sub">请返回生产画面，先生成并确认真实样片。</p>}</div>
    <section><h3>2 · 完整成片预览</h3><p className="sub">检查画面、声音、字幕和整片节奏</p>{finalCandidates.length > 0 && <label className="video-project-field">成片版本<select className="input" aria-label="成片版本" value={final?.id || ""} onChange={event => update({ finalFileId: Number(event.target.value), finalApprovedFileId: undefined })}>{finalCandidates.map(file => <option value={file.id} key={file.id}>{file.original_name} · #{file.id}</option>)}</select></label>}{final ? <><video controls src={final.url} aria-label="当前项目成片" /><p className="sub">{final.original_name} · 文件 #{final.id}</p></> : <p className="quiet">完整成片生成后在此预览；不会把上传的单镜素材误当成成片。</p>}<div className="video-project-actions"><Button onClick={onBack}>返回修改</Button><Button variant="primary" disabled={!final || finalApproved} onClick={() => final && update({ finalApprovedFileId: final.id })}>验收通过</Button></div></section>
    {finalApproved && <div className="video-project-note"><strong>3 · 成片已验收</strong><p>选择下载或推送到发布中心。推送发布中心不等于公开发布。</p><div className="video-project-actions">{final && <a className="button" href={final.download_url || `${final.url}?download=1`} download>下载成片</a>}<Button variant="primary" onClick={() => void handoff()}>推送到发布中心</Button></div></div>}
    <div className="video-project-actions"><Button onClick={onBack}>← 上一步</Button></div>
    {error && <p className="video-project-error" role="alert">{error}</p>}
  </Card>;
}

interface VideoTemplate {
  key: string;
  name: string;
  category: string;
  status: string;
  preview_url: string;
  preview_video_url?: string;
  description: string;
}

export function StyleLibrary({ snapshot, update }: { snapshot: ProjectSnapshot; update: (patch: Partial<ProjectSnapshot>) => void }) {
  const [templates, setTemplates] = useState<VideoTemplate[]>([]);
  const [preview, setPreview] = useState<VideoTemplate | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    void api<{ templates: VideoTemplate[] }>("/api/video-templates").then(result => setTemplates(result.templates || [])).catch(cause => setError(cause instanceof Error ? cause.message : "模板读取失败"));
  }, []);

  function choose(generateSuggestions: boolean) {
    if (!preview) return;
    update({
      style: preview.key,
      template: preview.key,
      previousStyle: snapshot.style,
      styleSuggestionRequested: generateSuggestions,
      storyboardHistory: snapshot.shots.length ? [...(snapshot.storyboardHistory || []), snapshot.shots] : snapshot.storyboardHistory,
      shots: snapshot.shots.map(shot => ({ ...shot, confirmed: false })),
      sampleApprovedFileId: undefined,
      finalApprovedFileId: undefined,
    });
    setPreview(null);
  }

  const changing = Boolean(preview && snapshot.style && preview.key !== snapshot.style && snapshot.shots.length);
  return <Card>
    <div className="card-head"><div><h2>画风选择 <Help title="画面风格"><p>查看参考视频和图片，再选择画风。自定义风格包的渲染接入仍待验证。</p></Help></h2><p className="sub">查看并选择画风；点击卡片预览参考视频和图片。</p></div><Badge>{snapshot.style || "未选择"}</Badge></div>
    <div className="video-project-actions"><Button disabled>设置 / 更换风格库文件夹（待确认）</Button><Button disabled>＋ 添加风格（待确认）</Button></div>
    {error && <p className="video-project-error">{error}</p>}
    <div className="video-project-shot-grid">{templates.map(template => <button className={`video-project-shot ${snapshot.style === template.key ? "active" : ""}`} key={template.key} onClick={() => setPreview(template)}><img src={template.preview_url} alt={`${template.name}真实渲染预览`} /><strong>{template.name}</strong><small>{template.category} · {template.status === "stable" ? "稳定" : "草稿"}</small>{snapshot.style === template.key && <span className="video-project-required">✓ 当前选择</span>}</button>)}</div>
    {snapshot.styleSuggestionRequested && <div className="video-project-note">画风已保留。点击“生成分镜”生成新建议；采用前原分镜历史仍保留。</div>}
    {preview && <Modal open onOpenChange={() => setPreview(null)} title={preview.name} description="真实模板预览">
      <h3>参考视频</h3>{preview.preview_video_url ? <video controls src={preview.preview_video_url} style={{ width: "100%" }} /> : <div className="video-project-shot-preview">当前模板没有独立参考视频，真实渲染预览如下图</div>}
      <h3>参考图片</h3><img src={preview.preview_url} alt={`${preview.name}预览`} style={{ width: "100%" }} />
      <p>{preview.description}</p>
      {changing && <div className="video-project-note"><strong>更换画风会影响已有内容</strong><p>旁白、时间码和镜头顺序保留；画面描述、视觉参考、样片和已生成画面需要检查。旧版本保留供对比。</p></div>}
      <div className="video-project-actions"><Button variant="primary" onClick={() => choose(false)}>{changing ? "保留现有内容，逐镜检查" : "使用这个画风"}</Button>{changing && <Button onClick={() => choose(true)}>按新风格提出修改建议</Button>}</div>
    </Modal>}
  </Card>;
}
