import { useEffect, useState } from "react";
import { Download, Plus, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge, Button, Field, Input, Textarea } from "@/components/ui";
import type { Json, Task } from "@/lib/types";
import { api } from "@/lib/api";
import { platformNames, scriptNames } from "@/lib/names";

export type TaskRequest = (key: string, path: string, options: RequestInit, success: string) => Promise<boolean>;
export type TaskAction = (action: string, payload?: Json) => Promise<boolean>;

interface StageProps {
  task: Task & { source?: Json; completed_at?: string };
  core: Json;
  busy: string;
  request: TaskRequest;
  action: TaskAction;
}

const scriptKeys = Object.keys(scriptNames);
const assetTypes: Record<string, string> = { own: "自有素材", screen_record: "屏幕录制", stock: "合法素材库", ai_image: "AI 图像", ai_video: "AI 视频" };
const qualityItems: Record<string, [string, string]> = {
  subtitles: ["字幕准确", "文字、时间轴与口播一致"],
  audio: ["声音清晰", "音量正常，无异常噪声或断音"],
  visual: ["画面完整", "无黑帧、错字、裁切或异常画面"],
  copyright: ["版权合规", "来源和授权均已复核"],
  platform: ["平台规格", "画幅、时长、格式满足发布要求"],
};

function formatSize(bytes: number) {
  return bytes >= 1048576 ? `${(bytes / 1048576).toFixed(2)} MB` : `${(bytes / 1024).toFixed(1)} KB`;
}

function StageHead({ title, description, badge, tone = "neutral" }: { title: string; description: string; badge: string; tone?: "neutral" | "green" | "orange" | "red" | "blue" }) {
  return <div className="task-stage-head"><div><h2>{title}</h2><p>{description}</p></div><Badge tone={tone}>{badge}</Badge></div>;
}

function ActionBar({ hint, children }: { hint: string; children: React.ReactNode }) {
  return <div className="task-action-bar"><p>{hint}</p><div className="button-row">{children}</div></div>;
}

function disabledReason(busy: boolean, reason: string) {
  return busy ? "另一项任务操作正在进行，请等待完成" : reason;
}

function VideoPreview({ task, file: selectedFile }: { task: Task; file?: Json }) {
  const file = selectedFile || task.files.find(item => item.kind === "video");
  if (!file) return <div className="task-inline-empty">尚未上传或生成成片。</div>;
  return <div className="task-video-wrap"><video className="task-video-preview" controls preload="metadata" src={file.url}>浏览器不支持视频预览，请下载后观看。</video><div className="task-file-meta"><div><strong>{file.original_name}</strong><code>{file.relative_path}</code><p>{file.media_info.duration_seconds ?? "未读取"} 秒{file.media_info.mode ? ` · ${file.media_info.mode} / ${platformNames[file.media_info.platform] || file.media_info.platform}` : ""}</p></div><a className="button button-small" href={file.download_url} download><Download size={14} />下载成片</a></div></div>;
}

function ScriptsStage({ task, core, busy, request, action }: StageProps) {
  const initial = () => Object.fromEntries(scriptKeys.map(key => [key, String(task.scripts[key] || "")]));
  const [scripts, setScripts] = useState<Record<string, string>>(initial);
  const [activeScript, setActiveScript] = useState("douyin");
  const save = () => request("save-scripts", `/api/tasks/${task.content_id}/scripts`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scripts }) }, "手填文稿已保存，其他版本未改变");
  const approve = async () => { if (await save()) await action("approve_script"); };
  const generate = (force: boolean) => request("generate-scripts", `/api/tasks/${task.content_id}/generate-scripts`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ fields: [activeScript], force }) }, force ? "AI 结果已返回；如有新编辑会保留为候选版本" : "缺失文稿已生成，手填内容未改变");
  const ai = core.ai || {};
  const meta = task.script_meta?.[activeScript] || {};
  return <>
    <StageHead title="文稿与平台改编" description="手填优先，AI 只补空缺；母稿和其他平台版本不是必填项。" badge={`脚本Agent · ${ai.ready ? "已连接" : "尚未通过真实测试"}`} tone={ai.ready ? "green" : "orange"} />
    <div className="task-script-tabs" role="tablist" aria-label="文稿版本">{scriptKeys.map(key => <button type="button" role="tab" aria-selected={activeScript === key} className={activeScript === key ? "active" : ""} key={key} onClick={() => setActiveScript(key)}>{scriptNames[key]}{key === "master" || key === "wechat_official_account" ? "（可选）" : ""}<small>{task.script_meta?.[key]?.origin === "agent" ? "AI" : scripts[key].trim() ? "手填" : "空缺"}</small></button>)}</div>
    <Field label={`${scriptNames[activeScript]}${activeScript === "douyin" ? " · 当前视频口播稿" : " · 可选版本"}`} hint={meta.revision_no ? `版本 v${meta.revision_no} · ${meta.origin === "agent" ? "AI 生成" : "人工维护"}` : "可粘贴或输入，留空时可由 AI 生成"}><Textarea className="task-script-editor" value={scripts[activeScript]} disabled={Boolean(busy)} onChange={event => setScripts(current => ({ ...current, [activeScript]: event.target.value }))} placeholder={`在这里粘贴或编辑${scriptNames[activeScript]}…`} /></Field>
    {meta.candidate?.text && <details className="task-candidate"><summary>查看 AI 候选版本（未覆盖当前文稿）</summary><p>{meta.candidate.text}</p></details>}
    <div className="task-info">批量生成只补空缺；生成期间如果再次编辑，AI 结果只保存为候选，不覆盖新内容。{!ai.ready && <strong>请先在设置中完成真实连接测试。</strong>}{ai.last_error && <span>最近错误：{ai.last_error}</span>}</div>
    <ActionBar hint="当前平台口播稿存在即可继续；母稿和其他平台版本可留空。"><Button disabled={Boolean(busy) || !ai.ready} title={disabledReason(Boolean(busy), ai.ready ? "按需生成当前字段" : "脚本Agent尚未通过真实连接测试")} onClick={() => void generate(Boolean(scripts[activeScript].trim()))}>{busy === "generate-scripts" ? "正在按需生成…" : scripts[activeScript].trim() ? "根据现有资料重写此栏" : "生成此栏"}</Button><Button disabled={Boolean(busy)} onClick={() => void save()}>{busy === "save-scripts" ? "正在保存…" : "保存手填文稿"}</Button>{task.state === "script_drafted" && <Button variant="primary" disabled={Boolean(busy)} onClick={() => void approve()}>保存并确认口播稿</Button>}</ActionBar>
  </>;
}

function AudioStage({ task, core, busy, request, action }: StageProps) {
  const voices = core.voices || { system_voices: [], clone_profiles: [], capabilities: {} };
  const mediaAI = core.media_ai || { whisperx: {} };
  const audioFiles = task.files.filter(file => file.kind === "audio");
  const srtFiles = task.files.filter(file => file.kind === "srt");
  const allVoices = [...(voices.system_voices || []), ...(voices.clone_profiles || [])].sort((a: Json, b: Json) => Number(b.id === voices.last_used_id) - Number(a.id === voices.last_used_id));
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [srtUpload, setSrtUpload] = useState<File | null>(null);
  const [sampleFile, setSampleFile] = useState<File | null>(null);
  const [sampleName, setSampleName] = useState("");
  const [authorized, setAuthorized] = useState(false);
  const [subtitleId, setSubtitleId] = useState<number | null>(srtFiles[0]?.id ?? null);
  if (subtitleId === null && srtFiles.length) setSubtitleId(srtFiles[0].id);
  const [subtitle, setSubtitle] = useState("");
  const [subtitleStatus, setSubtitleStatus] = useState(srtFiles.length ? "正在读取字幕…" : "");
  const [ttsScript, setTtsScript] = useState("master");
  const [ttsText, setTtsText] = useState(String(task.scripts.master || ""));
  const [voiceId, setVoiceId] = useState(String(voices.last_used_id || allVoices[0]?.id || ""));
  const [whisperFile, setWhisperFile] = useState<number | null>(audioFiles[0]?.id ?? null);
  const [whisperModel, setWhisperModel] = useState("small");
  const subtitleFile = srtFiles.find(item => item.id === subtitleId);
  useEffect(() => {
    if (!subtitleFile) return;
    let current = true;
    fetch(subtitleFile.url, { credentials: "same-origin" }).then(response => {
      if (!response.ok) throw new Error(`字幕读取失败（HTTP ${response.status}）`);
      return response.text();
    }).then(text => { if (current) { setSubtitle(text); setSubtitleStatus(""); } }).catch((error: unknown) => { if (current) setSubtitleStatus(error instanceof Error ? error.message : "字幕读取失败"); });
    return () => { current = false; };
  }, [subtitleFile]);
  const voice = allVoices.find((item: Json) => item.id === voiceId) || allVoices[0];
  const voiceKind = voice?.kind || "system";
  const voiceReady = voiceKind === "clone" ? voices.capabilities.clone_ready : voices.capabilities.system_ready;
  const lastUsed = allVoices.find((item: Json) => item.id === voices.last_used_id);
  const upload = (kind: string, file: File | null, success: string) => {
    if (!file) return;
    void request(`upload-${kind}`, `/api/tasks/${task.content_id}/files?kind=${kind}&filename=${encodeURIComponent(file.name)}`, { method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: file }, success);
  };
  const generateAudio = () => {
    const payload = { script_key: ttsScript, voice_id: voice?.id || "", text: ttsText };
    const endpoint = voiceKind === "clone" ? "generate-clone-audio" : "generate-audio";
    void request("generate-audio", `/api/tasks/${task.content_id}/${endpoint}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }, "AI 录音已生成并通过检查，可试听下载；仍需 SRT 字幕");
  };
  const saveSample = () => {
    if (!sampleFile) return;
    void request("voice-sample", `/api/voices/samples?name=${encodeURIComponent(sampleName)}&authorized=${authorized}&filename=${encodeURIComponent(sampleFile.name)}`, { method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: sampleFile }, "本人样本已保存；生成能力以 OpenVoice 真实测试状态为准");
  };
  return <>
    <StageHead title="录音与字幕" description="上传或生成录音后，字幕由 WhisperX 自动生成；你只需要校对并确认。" badge="字幕自动生成 · 人工校对" tone="orange" />
    {audioFiles.length > 0 && <div className="task-info">{srtFiles.length ? (srtFiles.some(file => file.media_info?.whisperx) ? "字幕已由 WhisperX 自动生成，请在下方校对后确认。" : "字幕已就绪，请在下方校对后确认。") : mediaAI.whisperx.ready ? "字幕正在自动生成（WhisperX），通常需要几十秒；页面会自动刷新，也可先试听录音。" : "WhisperX 未就绪：请在下方“高级选项”手动上传 SRT，或到设置页完成真实转写测试。"}</div>}
    <div className="task-two-columns">
      <section className="task-subpanel"><p className="eyebrow">方式一 · 真人录音</p><h3>上传真实口播</h3><p>WAV / MP3 / M4A / AAC，最大 500MB；后端通过 FFprobe 检查。</p><Input type="file" accept=".wav,.mp3,.m4a,.aac" disabled={Boolean(busy)} onChange={event => setAudioFile(event.target.files?.[0] || null)} /><Button size="small" disabled={Boolean(busy) || !audioFile} title={disabledReason(Boolean(busy), audioFile ? "上传并检查真人录音" : "请先选择录音文件")} onClick={() => upload("audio", audioFile, `${audioFile?.name} 已上传并通过检查`)}>{busy === "upload-audio" ? "正在上传并检查…" : "上传真人录音"}</Button></section>
    </div>
    <details className="tasks-history"><summary>高级选项：手动上传 SRT 或手动转写</summary>
      <section className="task-subpanel"><p className="eyebrow">单独完成</p><h3>上传 SRT 字幕</h3><p>{srtFiles.length ? "已有字幕文件，可下载、查看或继续校对。" : "当前缺少字幕；可上传或使用 WhisperX 生成。"}</p><Input type="file" accept=".srt" disabled={Boolean(busy)} onChange={event => setSrtUpload(event.target.files?.[0] || null)} /><Button size="small" disabled={Boolean(busy) || !srtUpload} title={disabledReason(Boolean(busy), srtUpload ? "上传并检查 SRT" : "请先选择 SRT 文件")} onClick={() => upload("srt", srtUpload, `${srtUpload?.name} 已上传并通过检查`)}>{busy === "upload-srt" ? "正在上传并检查…" : "上传并检查 SRT"}</Button>{srtFiles.map(file => <div className="task-download-row" key={file.id}><span>{file.original_name}<small>{formatSize(file.size)} · {file.relative_path}</small></span><a className="button button-small" href={file.download_url} download>下载 SRT</a></div>)}</section>
    <section className="task-subpanel"><div className="task-section-head"><div><h3>WhisperX 手动转写</h3><p>自动字幕失败时的备用入口；本地 CPU 转写当前任务音频。</p></div><Badge tone={mediaAI.whisperx.ready ? "green" : "orange"}>{mediaAI.whisperx.status || "未就绪"}</Badge></div><div className="task-form-grid"><Field label="源音频"><select value={whisperFile ?? ""} disabled={Boolean(busy) || !audioFiles.length} onChange={event => setWhisperFile(Number(event.target.value))}><option value="" disabled>{audioFiles.length ? "选择音频" : "尚无音频"}</option>{audioFiles.map(file => <option value={file.id} key={file.id}>{file.original_name}</option>)}</select></Field><Field label="模型"><select value={whisperModel} disabled={Boolean(busy)} onChange={event => setWhisperModel(event.target.value)}><option value="small">small（默认）</option><option value="base">base</option></select></Field></div><Button size="small" disabled={Boolean(busy) || !mediaAI.whisperx.ready || !whisperFile} title={disabledReason(Boolean(busy), !mediaAI.whisperx.ready ? "WhisperX 尚未通过真实转写测试" : !whisperFile ? "请先准备音频" : "生成真实 SRT")} onClick={() => void request("transcribe", `/api/tasks/${task.content_id}/transcribe`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ file_id: whisperFile, model: whisperModel }) }, "WhisperX 已生成 SRT，请人工校对后确认")}>{busy === "transcribe" ? "正在本地转写…" : "使用 WhisperX 生成 SRT"}</Button>{!mediaAI.whisperx.ready && <p className="task-help">{mediaAI.whisperx.last_error || "安装完成后请先在设置中做真实转写测试。"}</p>}</section>
    </details>
    <section className="task-subpanel"><div className="task-section-head"><div><h3>方式二 · AI 生成录音</h3><p>macOS 系统语音或 OpenVoice 本人克隆，成功后可试听与下载。</p></div><div className="tag-row"><Badge tone={voices.capabilities.system_ready ? "green" : "orange"}>系统 {voices.capabilities.system_status || "未就绪"}</Badge><Badge tone={voices.capabilities.clone_ready ? "green" : "orange"}>克隆 {voices.capabilities.clone_status || "未就绪"}</Badge></div></div><div className="task-form-grid"><Field label="脚本版本"><select value={ttsScript} disabled={Boolean(busy)} onChange={event => { const key = event.target.value; setTtsScript(key); setTtsText(String(task.scripts[key] || "")); }}>{scriptKeys.map(key => <option key={key} value={key}>{scriptNames[key]}</option>)}</select></Field><Field label="系统音色 / 本人克隆"><select value={voice?.id || ""} disabled={Boolean(busy) || !allVoices.length} onChange={event => setVoiceId(event.target.value)}>{allVoices.map((item: Json) => <option key={item.id} value={item.id}>{item.kind === "clone" ? "本人克隆" : "系统"} · {item.name}</option>)}</select></Field></div><p className="task-help">{lastUsed ? `上次使用：${lastUsed.name} · ${lastUsed.last_used_at} · 已使用 ${lastUsed.use_count} 次` : "还没有使用记录；系统和本人克隆共用最近使用推荐。"}</p><Field label="用于 TTS 的文本（可编辑）"><Textarea value={ttsText} disabled={Boolean(busy)} onChange={event => setTtsText(event.target.value)} /></Field><Button variant="primary" disabled={Boolean(busy) || !voice || !voiceReady || !ttsText.trim()} title={disabledReason(Boolean(busy), !voice ? "尚无可用音色" : !voiceReady ? `${voiceKind === "clone" ? "OpenVoice" : "系统语音"}尚未通过真实生成测试` : !ttsText.trim() ? "请填写朗读文本" : "生成真实 WAV")} onClick={generateAudio}>{busy === "generate-audio" ? "正在生成并验证 WAV…" : "生成 AI 录音"}</Button></section>
    <section className="task-subpanel"><div className="task-section-head"><div><h3>本人音色记忆库</h3><p>样本独立保存；只有授权样本且 OpenVoice 真实测试成功才可生成。</p></div><Badge tone={voices.capabilities.clone_ready ? "green" : "orange"}>{voices.capabilities.clone_status || "未就绪"}</Badge></div><div className="task-form-grid"><Field label="档案名"><Input maxLength={100} value={sampleName} disabled={Boolean(busy)} onChange={event => setSampleName(event.target.value)} placeholder="例如：本人安静环境样本" /></Field><Field label="本人语音样本" hint="WAV / MP3 / M4A / AAC，建议 10 秒到 5 分钟"><Input type="file" accept=".wav,.mp3,.m4a,.aac" disabled={Boolean(busy)} onChange={event => setSampleFile(event.target.files?.[0] || null)} /></Field></div><label className="task-check"><input type="checkbox" checked={authorized} disabled={Boolean(busy)} onChange={event => setAuthorized(event.target.checked)} />我确认这是本人声音，并授权用于音色克隆</label><Button size="small" disabled={Boolean(busy) || !sampleFile || !sampleName.trim() || !authorized} title={disabledReason(Boolean(busy), !sampleFile ? "请选择本人语音样本" : !sampleName.trim() ? "请填写档案名" : !authorized ? "必须明确确认本人声音与授权" : "保存真实样本")} onClick={saveSample}>{busy === "voice-sample" ? "正在检查并保存样本…" : "保存本人样本"}</Button><div className="task-clone-grid">{(voices.clone_profiles || []).map((profile: Json) => <article key={profile.id}><strong>{profile.name}</strong><span>{profile.duration_seconds} 秒 · {profile.created_at}</span><small>{profile.clone_status}</small></article>)}{!(voices.clone_profiles || []).length && <p className="task-help">尚未保存本人样本。保存样本不代表克隆已可用。</p>}</div></section>
    <section><div className="task-section-head"><div><h3>任务音频 · 位置、试听与下载</h3><p>真人和 AI 文件均在此列出。</p></div></div>{audioFiles.length ? audioFiles.map(file => <article className="task-audio-file" key={file.id}><div className="task-file-meta"><div><strong>{file.original_name}</strong><code>{file.relative_path}</code><p>{formatSize(file.size)} · 时长 {file.media_info.duration_seconds ?? "未读取"} 秒</p></div><a className="button button-small" href={file.download_url} download><Download size={14} />下载</a></div><audio controls preload="metadata" src={file.url}>浏览器不支持音频试听。</audio></article>) : <div className="task-inline-empty">尚未上传或生成录音。</div>}</section>
    <section className="task-subtitle-editor"><div className="task-section-head"><div><h3>字幕查看与人工校对</h3><p>仅“确认录音字幕”阶段可编辑；每次保存都会重新检查 SRT。</p></div>{srtFiles.length > 0 && <select className="task-subtitle-select" value={subtitleId ?? ""} onChange={event => { setSubtitle(""); setSubtitleStatus("正在读取字幕…"); setSubtitleId(Number(event.target.value)); }}>{srtFiles.map(file => <option key={file.id} value={file.id}>{file.original_name}</option>)}</select>}</div>{subtitleStatus && <p className="task-help">{subtitleStatus}</p>}{srtFiles.length ? <><Textarea className="task-subtitle-text" value={subtitle} disabled={Boolean(busy) || task.state !== "waiting_audio" || Boolean(subtitleStatus)} onChange={event => setSubtitle(event.target.value)} /><Button size="small" disabled={Boolean(busy) || task.state !== "waiting_audio" || !subtitleId || !subtitle.trim()} title={task.state !== "waiting_audio" ? "当前阶段字幕只读" : "保存并验证校对后的 SRT"} onClick={() => void request("save-subtitle", `/api/tasks/${task.content_id}/subtitles`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ file_id: subtitleId, text: subtitle }) }, "字幕校对已保存并通过检查")}>{busy === "save-subtitle" ? "正在校对检查…" : "保存字幕校对"}</Button></> : <div className="task-inline-empty">上传或生成 SRT 后，在这里逐条校对。</div>}</section>
    <div className="task-info">自动转写或 AI 录音不等于字幕人工确认。进入素材规划前，录音和有效 SRT 必须同时存在。</div>
    <ActionBar hint={!audioFiles.length || !srtFiles.length ? "请先准备至少一个录音和一个有效 SRT。" : "校对并保存字幕后，再确认录音与字幕。"}><Button variant="danger" disabled={Boolean(busy)} onClick={() => void action("revise_script")}>返回修改脚本</Button><Button variant="primary" disabled={Boolean(busy) || !audioFiles.length || !srtFiles.length} title={!audioFiles.length ? "缺少有效录音" : !srtFiles.length ? "缺少有效 SRT" : "确认进入素材规划"} onClick={() => void action("confirm_audio")}>确认录音与字幕</Button></ActionBar>
  </>;
}

function blankAsset(): Json {
  return { id: "", name: "", source: "", licensed: false, file_id: null, note: "", start_seconds: null, end_seconds: null, asset_type: "own", description: "", search_query: "", generation_prompt: "", license_risk: "" };
}

function AssetsStage({ task, core, busy, request, action }: StageProps) {
  const [plan, setPlan] = useState<Json[]>(task.asset_plan.length ? task.asset_plan : [blankAsset()]);
  const [assetFile, setAssetFile] = useState<File | null>(null);
  const [allowed, setAllowed] = useState(["own", "screen_record", "stock"]);
  const files = task.files.filter(file => file.kind === "asset");
  const srtFiles = task.files.filter(file => file.kind === "srt");
  const [srtId, setSrtId] = useState<number | null>(srtFiles[0]?.id ?? null);
  const update = (index: number, key: string, value: unknown) => setPlan(current => current.map((item, itemIndex) => itemIndex === index ? { ...item, [key]: value } : item));
  const payload = plan.map(item => ({ ...item, file_id: item.file_id ? Number(item.file_id) : null, start_seconds: item.start_seconds === "" || item.start_seconds === null ? null : Number(item.start_seconds), end_seconds: item.end_seconds === "" || item.end_seconds === null ? null : Number(item.end_seconds) }));
  const save = () => request("save-assets", `/api/tasks/${task.content_id}/assets`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ asset_plan: payload }) }, "分镜、素材来源与授权已保存");
  const approve = async () => { if (await save()) await action("approve_assets"); };
  const skip = async () => { if (window.confirm("未完成的分镜将从本任务计划中移除；全部跳过后使用全部 Remotion。是否继续？") && await save()) await action("skip_incomplete_assets"); };
  const assetAI = core.asset_ai || {};
  return <>
    <StageHead title="素材清单、来源与授权" description="AI 只生成分镜建议；每一项仍须实际上传、填写来源并由你确认授权。" badge={`素材规划Agent · ${assetAI.status || "未测试"}`} tone={assetAI.ready ? "green" : "orange"} />
    <section className="task-subpanel"><div className="task-section-head"><div><h3>素材规划Agent分镜建议</h3><p>使用当前任务 SRT、母稿和音频时长，不下载或生成媒体。</p></div><Badge tone={assetAI.ready ? "green" : "orange"}>{assetAI.status || "未测试"}</Badge></div><div className="task-form-grid"><Field label="用于分镜的 SRT"><select value={srtId ?? ""} disabled={Boolean(busy) || !srtFiles.length} onChange={event => setSrtId(Number(event.target.value))}>{srtFiles.map(file => <option key={file.id} value={file.id}>{file.original_name}</option>)}</select></Field><fieldset className="task-fieldset"><legend>允许的素材类型</legend><div className="task-check-grid">{Object.entries(assetTypes).map(([key, name]) => <label key={key}><input type="checkbox" checked={allowed.includes(key)} disabled={Boolean(busy)} onChange={event => setAllowed(current => event.target.checked ? [...current, key] : current.filter(item => item !== key))} />{name}</label>)}</div></fieldset></div><Button variant="primary" disabled={Boolean(busy) || !srtId || !core.ai?.ready || !allowed.length} title={disabledReason(Boolean(busy), !srtId ? "请先准备 SRT" : !core.ai?.ready ? "Kimi 尚未通过真实连接测试" : !allowed.length ? "至少允许一种素材类型" : "生成真实分镜建议")} onClick={() => void request("generate-assets", `/api/tasks/${task.content_id}/generate-asset-plan`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ file_id: srtId, allowed_types: allowed }) }, "分镜建议已保存；请上传真实素材并逐项确认授权")}>{busy === "generate-assets" ? "正在生成分镜建议…" : "生成分镜建议"}</Button><p className="task-help">AI 建议不等于素材已下载、已生成或已授权；失败保留原计划。{assetAI.last_error ? ` 最近错误：${assetAI.last_error}` : ""}</p></section>
    <section className="task-subpanel"><h3>上传真实素材与授权凭证</h3><p>图片、视频、音频或授权凭证；文件仅保存到此任务的素材目录。</p><Input type="file" accept=".png,.jpg,.jpeg,.webp,.gif,.mp4,.mov,.mp3,.wav,.m4a,.pdf,.txt" disabled={Boolean(busy)} onChange={event => setAssetFile(event.target.files?.[0] || null)} /><Button size="small" disabled={Boolean(busy) || !assetFile} title={disabledReason(Boolean(busy), assetFile ? "上传真实素材" : "请先选择素材或授权凭证")} onClick={() => { if (assetFile) void request("upload-asset", `/api/tasks/${task.content_id}/files?kind=asset&filename=${encodeURIComponent(assetFile.name)}`, { method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: assetFile }, `${assetFile.name} 已上传并通过检查`); }}>{busy === "upload-asset" ? "正在上传并检查…" : "上传素材"}</Button>{files.map(file => <div className="task-download-row" key={file.id}><span>{file.original_name}<small>{formatSize(file.size)}{file.media_info.duration_seconds ? ` · ${file.media_info.duration_seconds}s` : ""}</small></span><a className="button button-small" href={file.download_url} download>下载</a></div>)}</section>
    <div className="task-section-head"><div><h3>分镜与素材清单</h3><p>{plan.length} 项 · 保存后再确认或跳过未完成项</p></div><Button size="small" disabled={Boolean(busy)} onClick={() => setPlan(current => [...current, blankAsset()])}><Plus size={14} />添加一项</Button></div>
    <div className="task-asset-list">{plan.map((item, index) => <article className="task-asset-row" key={item.id || `new-${index}`}><div className="task-asset-number">{String(index + 1).padStart(2, "0")}</div><div className="task-asset-fields"><div className="task-form-grid task-form-grid-three"><Field label="素材名称 / 用途"><Input value={item.name || ""} disabled={Boolean(busy)} onChange={event => update(index, "name", event.target.value)} placeholder="例如：片头实拍" /></Field><Field label="来源"><Input value={item.source || ""} disabled={Boolean(busy)} onChange={event => update(index, "source", event.target.value)} placeholder="自己拍摄 / 已购素材库及订单" /></Field><Field label="关联上传文件"><select value={item.file_id ?? ""} disabled={Boolean(busy)} onChange={event => update(index, "file_id", event.target.value ? Number(event.target.value) : null)}><option value="">请选择文件</option>{files.map(file => <option key={file.id} value={file.id}>{file.original_name}</option>)}</select></Field></div><div className="task-form-grid task-form-grid-three"><Field label="开始秒"><Input type="number" min="0" step="0.1" value={item.start_seconds ?? ""} disabled={Boolean(busy)} onChange={event => update(index, "start_seconds", event.target.value)} /></Field><Field label="结束秒"><Input type="number" min="0" step="0.1" value={item.end_seconds ?? ""} disabled={Boolean(busy)} onChange={event => update(index, "end_seconds", event.target.value)} /></Field><Field label="素材类型"><select value={item.asset_type || "own"} disabled={Boolean(busy)} onChange={event => update(index, "asset_type", event.target.value)}>{Object.entries(assetTypes).map(([key, name]) => <option key={key} value={key}>{name}</option>)}</select></Field></div><Field label="画面与口播关系"><Textarea value={item.description || ""} disabled={Boolean(busy)} onChange={event => update(index, "description", event.target.value)} /></Field><div className="task-form-grid"><Field label="搜索词"><Input value={item.search_query || ""} disabled={Boolean(busy)} onChange={event => update(index, "search_query", event.target.value)} placeholder="素材库检索或录屏规划" /></Field><Field label="授权风险"><Input value={item.license_risk || ""} disabled={Boolean(busy)} onChange={event => update(index, "license_risk", event.target.value)} placeholder="授权、隐私、商标或客户数据风险" /></Field></div><Field label="AI 生成提示词"><Textarea value={item.generation_prompt || ""} disabled={Boolean(busy)} onChange={event => update(index, "generation_prompt", event.target.value)} /></Field><Field label="授权或备注"><Input value={item.note || ""} disabled={Boolean(busy)} onChange={event => update(index, "note", event.target.value)} placeholder="授权范围、凭证位置或使用限制" /></Field><div className="task-asset-footer"><label className="task-check"><input type="checkbox" checked={Boolean(item.licensed)} disabled={Boolean(busy)} onChange={event => update(index, "licensed", event.target.checked)} />我确认此素材来源明确且已取得所需授权</label><Button size="small" variant="danger" disabled={Boolean(busy)} onClick={() => setPlan(current => current.filter((_, itemIndex) => itemIndex !== index))}><Trash2 size={13} />移除</Button></div></div></article>)}</div>
    <ActionBar hint="可只跳过未完成分镜；全部跳过后使用全部 Remotion。"><Button disabled={Boolean(busy)} onClick={() => void save()}>{busy === "save-assets" ? "正在保存…" : "保存分镜与素材清单"}</Button>{task.state === "assets_planned" && <><Button disabled={Boolean(busy)} onClick={() => void skip()}>保存并跳过未完成项</Button><Button variant="primary" disabled={Boolean(busy)} onClick={() => void approve()}>保存并确认全部素材与授权</Button></>}</ActionBar>
  </>;
}

const activeJobStatuses = ["queued", "leased", "running", "retry_wait", "cancel_requested"];

function useProductionJob(contentId: string) {
  const [productionJob, setProductionJob] = useState<Json | null>(null);
  useEffect(() => {
    let current = true;
    let timer = 0;
    const load = async () => {
      const response = await fetch(`/api/tasks/${contentId}/jobs`, { credentials: "same-origin" });
      if (!response.ok) return;
      const data = await response.json();
      const job = data.jobs?.[0] || null;
      if (current) setProductionJob(job);
      if (current && job && activeJobStatuses.includes(job.status)) timer = window.setTimeout(load, 3000);
    };
    void load();
    return () => { current = false; window.clearTimeout(timer); };
  }, [contentId, productionJob?.status]);
  return { productionJob, productionActive: Boolean(productionJob && activeJobStatuses.includes(productionJob.status)) };
}

function startProduction(request: TaskRequest, contentId: string, payload: Json) {
  return request("render", `/api/tasks/${contentId}/produce`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }, "自动生产已提交，可离开页面；进度会持续保存");
}

const sourceTypeNames: Record<string, string> = { topic_candidate: "选题库", douyin_hotspot: "抖音热点", douyin_favorite_collection: "抖音收藏夹", topic: "输入主题", article: "粘贴文章", video: "上传视频", manual: "手动创建" };
const reviewModeNames: Record<string, string> = { agent: "审核 Agent", human: "人工审核", none: "仅机器检查" };
const publishModeNames: Record<string, string> = { manual: "人工发布", auto: "自动发布", local_only: "仅保存本地" };

function ContentStage({ task }: StageProps) {
  const source = task.source || {};
  return <>
    <StageHead title="内容与来源" description="视频生成 Agent 的统一输入；来源证据、审核方式和发布方式在此确认。" badge="选题Agent" tone="blue" />
    <div className="task-two-columns">
      <section className="task-subpanel"><p className="eyebrow">来源</p><h3>{sourceTypeNames[source.type] || source.type || "手动创建"}</h3>{source.title && source.type === "douyin_hotspot" && <p>热点 #{source.rank}「{source.title}」 · 热度 {source.heat}</p>}{source.name && <p>收藏夹「{source.name}」 · {source.usage}</p>}{source.captured_at && <p>快照时间：{source.captured_at}</p>}{source.url && <p><a href={source.url} target="_blank" rel="noreferrer">查看来源链接</a></p>}</section>
      <section className="task-subpanel"><p className="eyebrow">制作约定</p><h3>{publishModeNames[source.publish_mode] || "仅保存本地"}</h3><p>审核方式：{reviewModeNames[source.review_mode] || "审核 Agent"} · 发布方式：{publishModeNames[source.publish_mode] || "仅保存本地"}</p><p>制作方案：{source.production_preset || "默认方案"} · 目标平台：{platformNames[source.platform] || source.platform || "抖音"}</p></section>
    </div>
    {task.angle && <div className="task-info">内容角度：{task.angle}{(task as Json).pain_point ? ` · 痛点：${(task as Json).pain_point}` : ""}</div>}
    <div className="task-info">下一步：在「文稿」阶段手填或按需生成口播稿；母稿和其他平台版本均为可选。</div>
  </>;
}

function useVisualPreview(task: Task, mode: string, platform: string, template: string, burn: boolean) {
  const [preview, setPreview] = useState<Json | null>(null);
  const [job, setJob] = useState<Json | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (mode === "upload" || !template) return;
    const controller = new AbortController();
    const read = async (response: Response) => {
      const data = await response.json();
      if (!response.ok) throw new Error(data.error?.message || data.message || `预览请求失败（HTTP ${response.status}）`);
      return data;
    };
    const run = async () => {
      const payload = { mode, platform, burn_subtitles: burn, template_ids: [template] };
      let data = await api(`/api/tasks/${task.content_id}/visual-previews`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload), signal: controller.signal });
      if (controller.signal.aborted) return;
      setPreview(data.preview);
      setJob(data.job);
      while (["queued", "rendering"].includes(data.preview?.status)) {
        await new Promise(resolve => window.setTimeout(resolve, 2000));
        if (controller.signal.aborted) return;
        data = await read(await fetch(`/api/tasks/${task.content_id}/visual-previews/${data.preview.id}`, { credentials: "same-origin", signal: controller.signal }));
        setPreview(data.preview);
        setJob(data.job);
      }
      if (data.preview?.status === "failed") setError(data.preview.error || data.job?.error?.message || "预览渲染失败");
    };
    void run().catch(cause => { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "预览生成失败"); });
    return () => controller.abort();
  }, [task.content_id, task.updated_at, mode, platform, template, burn]);
  const approve = async () => {
    if (!preview) return false;
    setError("");
    try {
      const data = await api(`/api/tasks/${task.content_id}/visual-previews/${preview.id}/approve`, { method: "POST" });
      setPreview(data.preview);
      return true;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "预览确认失败");
      return false;
    }
  };
  const currentPreview = preview?.request?.template_ids?.[0] === template && preview.request.mode === mode && preview.request.platform === platform ? preview : null;
  return { preview: currentPreview, job: currentPreview ? job : null, error, approve };
}

function TemplatePlan({ task, core, busy, request }: StageProps) {
  const [mode, setMode] = useState("remotion");
  const [platform, setPlatform] = useState("douyin");
  const [burn, setBurn] = useState(true);
  const templates = (core.video_templates || []) as Json[];
  const [selectedTemplate, setSelectedTemplate] = useState<string>(() => {
    const initial = templates.find(item => item.key === "founder-ip@1.0.0") || templates[0];
    return initial?.key || "";
  });
  const renderAI = core.render_ai || {};
  const { productionActive } = useProductionJob(task.content_id);
  const { preview, job, error, approve } = useVisualPreview(task, mode, platform, selectedTemplate, burn);
  const render = async () => {
    if (mode !== "upload" && !preview?.approved && !await approve()) return;
    const payload: Json = { mode, platform, burn_subtitles: burn };
    if (mode !== "upload") payload.template_ids = [selectedTemplate];
    void startProduction(request, task.content_id, payload);
  };
  const previewActive = ["queued", "rendering"].includes(preview?.status);
  return <section className="task-subpanel">
    <div className="task-section-head"><div><h3>视觉风格 · 先看10秒效果</h3><p>每次选择一种风格都会自动生成真实内容预览；确认后才允许渲染完整成片。</p></div><Badge tone={renderAI.ready ? "green" : "orange"}>视频构建Agent · {renderAI.status || "未测试"}</Badge></div>
    <div className="task-form-grid"><Field label="生产方式"><select aria-label="渲染模式" value={mode} disabled={Boolean(busy)} onChange={event => setMode(event.target.value)}><option value="remotion">智能混合：内容动态图形，无素材也可</option><option value="mixed">素材混合：上传场景 + Remotion 动态包装</option><option value="upload">全部上传：关联视频/图片 + 音频，FFmpeg 合成</option></select></Field><Field label="目标平台"><select value={platform} disabled={Boolean(busy)} onChange={event => setPlatform(event.target.value)}>{Object.entries(platformNames).map(([key, name]) => <option key={key} value={key}>{name}</option>)}</select></Field></div>
    {mode !== "upload" && <fieldset className="task-fieldset"><legend>选择视觉风格 · 自动预览</legend><div className="task-template-grid">{templates.map(template => <label className={`task-template-card${selectedTemplate === template.key ? " selected" : ""}`} key={template.key}><input type="radio" name={`style-${task.content_id}`} checked={selectedTemplate === template.key} disabled={Boolean(busy)} onChange={() => setSelectedTemplate(template.key)} />{template.preview_url ? <img className="task-template-preview" src={template.preview_url} alt={`${template.name} 真实渲染预览`} loading="lazy" /> : <span className="task-template-preview task-template-preview-empty">预览图未生成</span>}<span><strong>{template.name}</strong><small>{template.category} · v{template.version} · 9:16</small><p>{template.description}</p></span></label>)}</div></fieldset>}
    {mode !== "upload" && <section className="task-visual-preview" aria-live="polite"><div className="task-section-head"><div><h3>10秒效果预览</h3><p>抽取真实分镜、配音和字幕；预览与正式成片共用场景和风格参数。</p></div><Badge tone={preview?.approved ? "green" : preview?.status === "failed" ? "red" : previewActive ? "orange" : "blue"}>{preview?.approved ? "已确认" : previewActive ? `生成中 ${Math.round((job?.progress ?? preview?.progress ?? 0) * 100)}%` : preview?.status === "succeeded" ? "待确认" : preview?.status === "failed" ? "失败" : "准备中"}</Badge></div>{preview?.video_url ? <video className="task-video-preview" controls preload="metadata" src={preview.video_url}>浏览器不支持视频预览。</video> : preview?.cover_url ? <img className="task-video-preview" src={preview.cover_url} alt="10秒效果预览封面" /> : <div className="task-inline-empty">{error || (previewActive ? "正在生成10秒动态效果，请稍候…" : "选择风格后自动生成预览")}</div>}{error && <p className="task-preview-error" role="alert">{error}</p>}{preview?.fingerprint && <p className="task-help">预览 {preview.id} · 内容指纹 {String(preview.fingerprint).slice(0, 12)} · 修改内容或风格后需重新确认</p>}</section>}
    <label className="task-check"><input type="checkbox" checked={burn} disabled={Boolean(busy) || mode !== "upload"} onChange={event => setBurn(event.target.checked)} />上传模式烧入 SRT 字幕{mode !== "upload" && "（仅上传模式适用）"}</label>
    <Button variant="primary" disabled={Boolean(busy) || productionActive || (mode !== "upload" && (preview?.status !== "succeeded" || !selectedTemplate))} title={productionActive ? "已有自动生产正在进行" : mode !== "upload" && preview?.status !== "succeeded" ? "等待10秒预览生成成功" : "确认当前效果并生成完整视频"} onClick={() => void render()}>{productionActive ? "自动生产进行中…" : busy === "render" ? "正在提交…" : mode === "upload" ? "开始渲染 MP4" : preview?.approved ? "开始生成完整成片" : "确认效果并生成成片"}</Button>
    <p className="task-help">上传/混合至少需要 1 个已关联且授权的视频或图片场景。相同内容与风格会复用预览；生成其他风格不会覆盖已保存成片。{renderAI.last_error ? ` 最近错误：${renderAI.last_error}` : ""}</p>
  </section>;
}

function ProduceStage({ task, busy, request, action, onNavigateGroup }: StageProps & { onNavigateGroup?: (group: number) => void }) {
  const [video, setVideo] = useState<File | null>(null);
  const [previewFileId, setPreviewFileId] = useState<number | null>(null);
  const renderRuns = task.render_runs || [];
  const videoFiles = task.files.filter(file => file.kind === "video");
  const previewFile = videoFiles.find(file => file.id === previewFileId) || videoFiles[0];
  const { productionJob, productionActive } = useProductionJob(task.content_id);
  const timings = productionJob?.result?.stage_timings || [];
  return <>
    <StageHead title="自动生产" description="一次点击后后台完成全链路；页面可刷新、任务可恢复，失败可单独重试。" badge="视频构建Agent" tone={productionActive ? "orange" : renderRuns.length ? "green" : "neutral"} />
    {productionJob && <section className="task-production-progress" aria-live="polite"><div className="task-section-head"><div><h3>视频生成 Agent · {productionJob.stage}</h3><p>任务 {productionJob.id} · 进度 {Math.round((productionJob.progress || 0) * 100)}%</p></div><Badge tone={productionJob.status === "failed" ? "red" : productionJob.status === "succeeded" ? "green" : productionActive ? "orange" : "blue"}>{productionJob.status}</Badge></div>{productionJob.error?.message && <p className="task-help">{productionJob.error.message}</p>}{timings.length > 0 && <table className="task-metric-table"><thead><tr><th>阶段</th><th>耗时</th></tr></thead><tbody>{timings.map((item: Json) => <tr key={item.stage}><th>{item.stage}</th><td>{item.seconds ?? "--"} 秒</td></tr>)}</tbody></table>}<div className="button-row">{productionActive && <Button size="small" variant="danger" onClick={() => void request("cancel-production", `/api/tasks/${task.content_id}/jobs/${productionJob.id}/cancel`, { method: "POST" }, "已请求取消生产")}>取消生产</Button>}{["failed", "cancelled"].includes(productionJob.status) && <Button size="small" onClick={() => void request("retry-production", `/api/tasks/${task.content_id}/jobs/${productionJob.id}/retry`, { method: "POST" }, "失败生产已重新排队")}>重试生产</Button>}</div></section>}
    {!productionJob && !renderRuns.length && <div className="task-inline-empty">尚未开始生产。{onNavigateGroup && <Button size="small" onClick={() => onNavigateGroup(2)}>前往制作方案选择风格</Button>}</div>}
    <VideoPreview task={task} file={previewFile} />
    {(task.visual_previews || []).length > 0 && <details className="tasks-history task-preview-history"><summary>视觉预览历史（{(task.visual_previews || []).length}）</summary>{(task.visual_previews || []).map((item: Json) => <article key={item.id}><div><strong>{item.template_key}{item.is_current ? " · 当前" : ""}</strong><p>{item.created_at} · {item.status}{item.error ? ` · ${item.error}` : ""}</p></div><Badge tone={item.approved ? "green" : item.status === "failed" ? "red" : "neutral"}>{item.approved ? "已确认" : item.status}</Badge>{item.video_url && <a className="button button-small" href={item.video_url} target="_blank" rel="noreferrer">查看预览</a>}</article>)}</details>}
    {renderRuns.length > 0 && <section className="task-render-history"><div className="task-section-head"><div><h3>渲染历史</h3><p>模板版本和输入快照均保存在本地；缓存命中不会重复渲染。</p></div><Badge>{renderRuns.length}</Badge></div><div className="task-render-run-list">{renderRuns.map(run => { const file = videoFiles.find(item => item.id === run.output_file_id); const tone = run.status === "failed" ? "red" : run.status === "cached" ? "blue" : run.status === "succeeded" ? "green" : "orange"; return <article className="task-render-run" key={run.id}><div><strong>{run.template_id} <small>v{run.template_version}</small></strong><p>{run.created_at}{run.error ? ` · ${run.error}` : ""}</p></div><Badge tone={tone}>{run.status === "cached" ? "缓存" : run.status === "succeeded" ? "已生成" : run.status === "failed" ? "失败" : "渲染中"}</Badge>{file && <Button size="small" variant={file.id === previewFile?.id ? "primary" : "default"} onClick={() => setPreviewFileId(file.id)}>查看</Button>}</article>; })}</div></section>}
    <section className="task-subpanel"><h3>也可以手动上传成片</h3><p>MP4 / MOV / WebM，最大 500MB。重复上传会清除旧质检结果。</p><Input type="file" accept=".mp4,.mov,.webm" disabled={Boolean(busy)} onChange={event => setVideo(event.target.files?.[0] || null)} /><Button size="small" disabled={Boolean(busy) || !video} title={disabledReason(Boolean(busy), video ? "上传并检查真实成片" : "请先选择成片文件")} onClick={() => { if (video) void request("upload-video", `/api/tasks/${task.content_id}/files?kind=video&filename=${encodeURIComponent(video.name)}`, { method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: video }, `${video.name} 已上传并通过检查`); }}>{busy === "upload-video" ? "正在上传并检查…" : "上传并检查成片"}</Button></section>
    <ActionBar hint="渲染成功后可在「结果与发布」预览、下载并进入五项质检。"><Button variant="danger" disabled={Boolean(busy)} onClick={() => void action("revise_assets")}>返回修改素材</Button></ActionBar>
  </>;
}

function CoverSection({ task, busy, request }: StageProps) {
  const covers = task.files.filter(file => file.kind === "cover");
  const latest = covers[covers.length - 1];
  const [coverFile, setCoverFile] = useState<File | null>(null);
  const hasVideo = task.files.some(file => file.kind === "video");
  return <section className="task-subpanel">
    <div className="task-section-head"><div><h3>发布封面</h3><p>文案确认后，封面可按模板风格 AI 生成，也可从成片抽帧或手动上传；每个平台发布时使用。</p></div>{latest && <Badge tone="green">已有封面</Badge>}</div>
    {latest && <div className="task-cover-preview"><img src={latest.url} alt="当前封面预览" /><div className="task-file-meta"><div><strong>{latest.original_name}</strong><p>{latest.media_info.width}×{latest.media_info.height} · {formatSize(latest.size)}</p></div><a className="button button-small" href={latest.download_url} download>下载</a></div></div>}
    <div className="button-row">
      <Button size="small" disabled={Boolean(busy)} onClick={() => void request("cover-ai", `/api/tasks/${task.content_id}/cover`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ source: "ai" }) }, "AI 封面已生成")}>{busy === "cover-ai" ? "正在渲染封面…" : "AI 生成封面"}</Button>
      <Button size="small" disabled={Boolean(busy) || !hasVideo} title={hasVideo ? "从最新成片抽取封面帧" : "还没有成片，可先 AI 生成或上传"} onClick={() => void request("cover-frame", `/api/tasks/${task.content_id}/cover`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ source: "frame" }) }, "已从成片抽取封面")}>{busy === "cover-frame" ? "正在抽帧…" : "从成片抽帧"}</Button>
    </div>
    <div className="task-form-grid"><Input type="file" accept=".png,.jpg,.jpeg,.webp" disabled={Boolean(busy)} onChange={event => setCoverFile(event.target.files?.[0] || null)} /><Button size="small" disabled={Boolean(busy) || !coverFile} title={coverFile ? "上传封面图片" : "请先选择图片"} onClick={() => { if (coverFile) void request("upload-cover", `/api/tasks/${task.content_id}/files?kind=cover&filename=${encodeURIComponent(coverFile.name)}`, { method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: coverFile }, "封面已上传"); }}>{busy === "upload-cover" ? "正在上传…" : "上传封面"}</Button></div>
  </section>;
}

function ResultStage(props: StageProps & { onNavigateGroup?: (group: number) => void }) {
  const { task, busy, request, onNavigateGroup } = props;
  const variants = task.variants || [];
  const [variantId, setVariantId] = useState(variants[0]?.id || "");
  const regenerate = (variant: Json) => {
    const template = `${variant.template_id}@${variant.template_version}`;
    if (window.confirm(`将为「${template}」重新生成10秒效果预览。预览完成后，请在上方确认效果再生成新成片；旧文件不会覆盖。是否继续？`))
      void request("regenerate-preview", `/api/tasks/${task.content_id}/visual-previews`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ mode: "remotion", platform: "douyin", burn_subtitles: true, template_ids: [template] }) }, "新预览已提交，请在上方选择同一风格查看并确认");
  };
  return <>
    <StageHead title="结果与发布" description="同一内容的每个风格独立质检、独立审批、独立发布；全部文件保存在本地。" badge="真实 MP4 交付" tone="green" />
    {variants.length > 0 ? <>
      <div className="task-result-bar"><span>共享内容：{[task.script_meta?.douyin?.revision_no ? `文稿 v${task.script_meta.douyin.revision_no}` : null, task.files.some(file => file.kind === "audio") ? "音频" : null, task.files.some(file => file.kind === "srt") ? "字幕" : null].filter(Boolean).join(" / ") || "文稿与音频"}</span><div className="button-row"><a className="button button-small" href={`/api/tasks/${task.content_id}/download.zip`} download><Download size={14} />全部下载 ZIP</a>{onNavigateGroup && <Button size="small" onClick={() => onNavigateGroup(2)}>追加一种风格</Button>}</div></div>
      <div className="task-variant-grid">{variants.map(variant => { const file = task.files.find(item => item.id === variant.file_id); const quality = variant.quality || {}; return <article className={`task-variant-card${variant.id === variantId ? " selected" : ""}`} key={variant.id}>
        {file ? <video className="task-variant-video" controls preload="metadata" src={file.url}>浏览器不支持视频预览。</video> : <div className="task-inline-empty">文件缺失</div>}
        <div className="task-variant-meta"><strong>{variant.template_id} <small>v{variant.template_version}</small></strong><div className="tag-row"><Badge tone={quality.passed ? "green" : quality.checked_at ? "red" : "neutral"}>{quality.passed ? "质检通过" : quality.checked_at ? "质检未通过" : "未质检"}</Badge>{variant.approved_at && <Badge tone="blue">已批准</Badge>}</div></div>
        <div className="button-row">{file && <a className="button button-small" href={file.download_url} download>下载</a>}<Button size="small" variant={variant.id === variantId ? "primary" : "default"} onClick={() => setVariantId(variant.id)}>质检 / 审批</Button><Button size="small" disabled={Boolean(busy)} onClick={() => regenerate(variant)}>重新生成</Button></div>
      </article>; })}</div>
      <CoverSection {...props} />
      <QualityStage {...props} variantId={variantId} onVariantChange={setVariantId} />
      {["review_required", "approved", "published", "analyzed"].includes(task.state) && <ReviewStage {...props} variantId={variantId} onVariantChange={setVariantId} />}
      {["approved", "published", "analyzed"].includes(task.state) && <PublicationsStage {...props} />}
      {["published", "analyzed"].includes(task.state) && <RetroStage {...props} />}
    </> : task.files.some(file => file.kind === "video") ? <>
      <div className="task-info">该任务来自旧流程，成片没有独立的版本记录；仍可质检、审批和交付。</div>
      <CoverSection {...props} />
      <QualityStage {...props} />
      {["review_required", "approved", "published", "analyzed"].includes(task.state) && <ReviewStage {...props} />}
      {["approved", "published", "analyzed"].includes(task.state) && <PublicationsStage {...props} />}
      {["published", "analyzed"].includes(task.state) && <RetroStage {...props} />}
    </> : <div className="task-inline-empty">尚未生成视频版本。{onNavigateGroup && <Button size="small" onClick={() => onNavigateGroup(2)}>前往自动生产</Button>}</div>}
  </>;
}

interface VariantSelectProps {
  variantId?: string;
  onVariantChange?: (id: string) => void;
}

function useVariantId(variants: Json[], controlled?: VariantSelectProps): [string, (id: string) => void] {
  const [inner, setInner] = useState(variants[0]?.id || "");
  const variantId = controlled?.variantId ?? inner;
  return [variantId, controlled?.onVariantChange ?? setInner];
}

function QualityStage({ task, busy, request, action, ...controlled }: StageProps & VariantSelectProps) {
  const variants = task.variants || [];
  const [variantId, setVariantId] = useVariantId(variants, controlled);
  const currentVariant = variants.find(item => item.id === variantId) || variants[0];
  const currentQuality = currentVariant?.quality || task.quality || {};
  const initialChecks = (quality: Json) => Object.fromEntries(Object.keys(qualityItems).map(key => [key, Boolean(quality.checks?.[key])]));
  const [checks, setChecks] = useState<Record<string, boolean>>(() => initialChecks(currentQuality));
  const [note, setNote] = useState(() => String(currentQuality.note || ""));
  const [syncedVariant, setSyncedVariant] = useState(currentVariant?.id);
  if (currentVariant?.id !== syncedVariant) {
    setSyncedVariant(currentVariant?.id);
    setChecks(initialChecks(currentQuality));
    setNote(String(currentQuality.note || ""));
  }
  const previewFile = task.files.find(file => file.id === currentVariant?.file_id);
  const save = () => request("save-quality", `/api/tasks/${task.content_id}/quality`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ checks, note, variant_id: currentVariant?.id }) }, "当前视频版本的质检结果已保存");
  const submit = async () => { if (Object.values(checks).every(Boolean) && await save()) await action("submit_review", { variant_id: currentVariant?.id }); };
  return <>
    <StageHead title="成片五项质检" description="每个模板版本独立质检、独立审批；保存未通过结果后必须返修。" badge="质检Agent · 未接入，人工检查" tone="orange" />
    {variants.length > 0 && <Field label="当前质检版本"><select value={variantId} onChange={event => setVariantId(event.target.value)}>{variants.map(variant => <option key={variant.id} value={variant.id}>{variant.template_id} · v{variant.template_version} · 文件 {variant.file_id}</option>)}</select></Field>}
    <VideoPreview task={task} file={previewFile} />
    <div className="task-quality-grid">{Object.entries(qualityItems).map(([key, [name, hint]]) => <label className="task-quality-item" key={key}><input type="checkbox" checked={Boolean(checks[key])} disabled={Boolean(busy)} onChange={event => setChecks(current => ({ ...current, [key]: event.target.checked }))} /><span><strong>{name}</strong><small>{hint}</small></span></label>)}</div>
    <Field label="质检备注 / 返修原因"><Textarea value={note} disabled={Boolean(busy)} onChange={event => setNote(event.target.value)} placeholder="记录发现的问题、时间点或平台规格说明" /></Field>
    {currentQuality.checked_at && <div className="task-info">当前版本上次结果：<strong>{currentQuality.passed ? "通过" : "未通过"}</strong> · {currentQuality.checked_at}</div>}
    <ActionBar hint="自动检查不等于人工最终审核；提交前会保存当前勾选与备注。"><Button disabled={Boolean(busy)} onClick={() => void save()}>{busy === "save-quality" ? "正在保存…" : "保存质检结果"}</Button>{["quality_checked", "review_required", "approved"].includes(task.state) && <><Button variant="danger" disabled={Boolean(busy)} onClick={() => void action("revise_assets")}>返回素材返修</Button><Button variant="danger" disabled={Boolean(busy)} onClick={() => void action("revise_render")}>仅重做成片</Button><Button variant="primary" disabled={Boolean(busy) || !Object.values(checks).every(Boolean)} title={!Object.values(checks).every(Boolean) ? "五项全部通过后才能提交人工审核" : "保存结果并提交人工终审"} onClick={() => void submit()}>保存并提交人工审核</Button></>}</ActionBar>
  </>;
}

function ReviewStage({ task, busy, action, ...controlled }: StageProps & VariantSelectProps) {
  const variants = task.variants || [];
  const [variantId, setVariantId] = useVariantId(variants, controlled);
  const currentVariant = variants.find(item => item.id === variantId) || variants[0];
  const previewFile = task.files.find(file => file.id === currentVariant?.file_id);
  return <><StageHead title="人工最终审核" description="请完整观看当前选中的成片。此确认与之后的发布确认是两个独立检查点。" badge="用户 · 最终人工确认" tone="orange" />{variants.length > 0 && <Field label="当前审核版本"><select value={variantId} onChange={event => setVariantId(event.target.value)}>{variants.map(variant => <option key={variant.id} value={variant.id}>{variant.template_id} · v{variant.template_version} · 文件 {variant.file_id}</option>)}</select></Field>}<VideoPreview task={task} file={previewFile} /><div className="task-info">当前版本五项质检已通过，但仍需你本人确认最终内容、表达与发布风险。</div><ActionBar hint="审核要求修改时，可返回脚本或素材，后续审批会清除。"><Button variant="danger" disabled={Boolean(busy)} onClick={() => void action("revise_script")}>返回脚本返修</Button><Button variant="danger" disabled={Boolean(busy)} onClick={() => void action("revise_assets")}>返回素材返修</Button><Button variant="primary" disabled={Boolean(busy)} onClick={() => void action("approve_final", { variant_id: currentVariant?.id })}>我已看当前成片，批准此版本</Button></ActionBar></>;
}

function PublicationsStage({ task }: StageProps) {
  return <>
    <StageHead title="交付视频" description="这里只展示真实生成的成片；平台预览与公开发布统一在发布中心完成。" badge="真实 MP4 交付" tone="green" />
    <VideoPreview task={task} />
    <ActionBar hint="下载检查交付文件后，如需公开发布，请前往发布中心选择对应平台。"><Link className="button button-primary" to={`/publish?kind=video&id=${encodeURIComponent(task.content_id)}`}>前往发布中心</Link></ActionBar>
  </>;
}

const metricFields: [string, string][] = [["views", "播放 / 阅读"], ["likes", "点赞"], ["comments", "评论"], ["shares", "分享"], ["followers", "新增关注"], ["leads", "有效咨询"]];
const periods: Record<string, string> = { "2h": "2 小时", "1d": "1 天", "3d": "3 天", "7d": "7 天" };

function RetroStage({ task, busy, request, action }: StageProps) {
  const initial = () => Object.fromEntries(Object.keys(periods).map(period => [period, Object.fromEntries(metricFields.map(([key]) => [key, task.metrics[period]?.[key] ?? ""]))]));
  const [metrics, setMetrics] = useState<Record<string, Record<string, number | string>>>(initial);
  const [retrospective, setRetrospective] = useState(task.retrospective || "");
  const payload = Object.fromEntries(Object.entries(metrics).map(([period, values]) => [period, Object.fromEntries(Object.entries(values).map(([key, value]) => [key, value === "" ? null : Number(value)]))]));
  const save = () => request("save-metrics", `/api/tasks/${task.content_id}/metrics`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ metrics: payload, retrospective }) }, "四窗口复盘数据已保存");
  const complete = async () => { if (await save()) await action("complete_retro"); };
  return <>
    <StageHead title={task.state === "analyzed" ? "复盘已完成" : "数据回收与复盘"} description="分四个时间点录入真实数据；暂时没读到的单项可留空，不会自动变成 0。" badge={task.state === "analyzed" ? "发布复盘Agent · 已归档" : "等待四窗口真实数据"} tone={task.state === "analyzed" ? "green" : "orange"} />
    <div className="task-metric-scroll"><table className="task-metric-table"><thead><tr><th>时间点</th>{metricFields.map(([, name]) => <th key={name}>{name}</th>)}</tr></thead><tbody>{Object.entries(periods).map(([period, label]) => <tr key={period}><th>{label}</th>{metricFields.map(([key]) => <td key={key}><Input aria-label={`${label}${metricFields.find(([field]) => field === key)?.[1]}`} type="number" min="0" step="1" value={metrics[period][key]} disabled={Boolean(busy)} placeholder="未读取" onChange={event => setMetrics(current => ({ ...current, [period]: { ...current[period], [key]: event.target.value } }))} /></td>)}</tr>)}</tbody></table></div>
    <Field label="复盘结论"><Textarea value={retrospective} disabled={Boolean(busy)} onChange={event => setRetrospective(event.target.value)} placeholder="哪些信号值得复测？下次保留、修改或停止什么？不要只看播放量。" /></Field>
    {task.state === "analyzed" && <div className="task-info">这条内容已于 {task.completed_at || "已记录时间"} 完成复盘。仍可补充更正数据。</div>}
    <ActionBar hint="完成需四个时间点的播放/阅读数据和复盘结论；完成前会保存当前输入。"><Button disabled={Boolean(busy)} onClick={() => void save()}>{busy === "save-metrics" ? "正在保存…" : "保存复盘数据"}</Button>{task.state === "published" && <Button variant="primary" disabled={Boolean(busy) || !retrospective.trim() || Object.keys(periods).some(period => metrics[period].views === "")} title={!retrospective.trim() ? "请填写复盘结论" : Object.keys(periods).some(period => metrics[period].views === "") ? "四个窗口均需填写播放/阅读数据" : "保存并归档复盘"} onClick={() => void complete()}>保存并完成复盘归档</Button>}</ActionBar>
  </>;
}

export default function VideoStages(props: StageProps & { group: number; readOnly?: boolean; onNavigateGroup?: (group: number) => void }) {
  const { group, readOnly = false } = props;
  const content = (() => {
    if (group === 0) return <><ContentStage {...props} /><ScriptsStage {...props} /></>;
    if (group === 1) return <AudioStage {...props} />;
    if (group === 2) return <>
      <details className="tasks-history"><summary>素材清单（可选；全部 Remotion 模板无需素材，混合/上传模式在此管理）</summary><AssetsStage {...props} /></details>
      <TemplatePlan {...props} />
      <ProduceStage {...props} />
      <ResultStage {...props} />
    </>;
    return <div className="task-inline-empty">当前选题尚未进入视频工作流，请先在选题库确认。</div>;
  })();
  return <fieldset className="task-stage-readonly" disabled={readOnly}>{content}</fieldset>;
}
