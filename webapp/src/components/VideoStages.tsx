import { useEffect, useState } from "react";
import { Download, Plus, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge, Button, Field, Input, Textarea } from "@/components/ui";
import type { Json, Task } from "@/lib/types";
import { platformNames, scriptNames } from "@/lib/names";

export type TaskRequest = (key: string, path: string, options: RequestInit, success: string) => Promise<boolean>;
export type TaskAction = (action: string) => Promise<boolean>;

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

function VideoPreview({ task }: { task: Task }) {
  const file = task.files.find(item => item.kind === "video");
  if (!file) return <div className="task-inline-empty">尚未上传或生成成片。</div>;
  return <div className="task-video-wrap"><video className="task-video-preview" controls preload="metadata" src={file.url}>浏览器不支持视频预览，请下载后观看。</video><div className="task-file-meta"><div><strong>{file.original_name}</strong><code>{file.relative_path}</code><p>{file.media_info.duration_seconds ?? "未读取"} 秒{file.media_info.mode ? ` · ${file.media_info.mode} / ${platformNames[file.media_info.platform] || file.media_info.platform}` : ""}</p></div><a className="button button-small" href={file.download_url} download><Download size={14} />下载成片</a></div></div>;
}

function ScriptsStage({ task, core, busy, request, action }: StageProps) {
  const initial = () => Object.fromEntries(scriptKeys.map(key => [key, String(task.scripts[key] || "")]));
  const [scripts, setScripts] = useState<Record<string, string>>(initial);
  const save = () => request("save-scripts", `/api/tasks/${task.content_id}/scripts`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scripts }) }, "五个脚本版本已保存");
  const approve = async () => { if (await save()) await action("approve_script"); };
  const ai = core.ai || {};
  return <>
    <StageHead title="脚本与平台改编" description="编辑母稿、三个短视频版本和公众号文章；生成或保存后仍需人工确认。" badge={`脚本Agent · ${ai.ready ? "已连接" : "尚未通过真实测试"}`} tone={ai.ready ? "green" : "orange"} />
    <div className="task-script-grid">{scriptKeys.map(key => <Field key={key} label={`${scriptNames[key]}${key === "master" ? " · 90–180 秒" : key === "wechat_official_account" ? " · 完整方法，不是逐字转录" : " · 独立成立的平台版本"}`}><Textarea className="task-script-editor" value={scripts[key]} disabled={Boolean(busy)} onChange={event => setScripts(current => ({ ...current, [key]: event.target.value }))} placeholder={`在这里粘贴或编辑${scriptNames[key]}…`} /></Field>)}</div>
    <div className="task-info">生成会实际调用本地 CLI 当前默认模型，成功后覆盖五版草稿，失败保留原稿。{!ai.ready && <strong>请先在设置中完成真实连接测试。</strong>}{ai.last_error && <span>最近错误：{ai.last_error}</span>}</div>
    <ActionBar hint="五个版本齐全后才能人工确认；生成可能需要一些时间。"><Button disabled={Boolean(busy) || !ai.ready} title={disabledReason(Boolean(busy), ai.ready ? "生成五版真实草稿" : "脚本Agent尚未通过真实连接测试")} onClick={() => void request("generate-scripts", `/api/tasks/${task.content_id}/generate-scripts`, { method: "POST" }, "五版草稿已生成，请逐版核对后人工确认")}>{busy === "generate-scripts" ? "正在生成五版草稿…" : "生成五版草稿"}</Button><Button disabled={Boolean(busy)} onClick={() => void save()}>{busy === "save-scripts" ? "正在保存…" : "保存脚本"}</Button>{task.state === "script_drafted" && <Button variant="primary" disabled={Boolean(busy)} onClick={() => void approve()}>保存并确认脚本</Button>}</ActionBar>
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
    <StageHead title="录音与字幕" description="真人、系统语音或本人克隆；音频与 SRT 分开完成，均可试听、下载和人工校对。" badge="录音、字幕均需人工确认" tone="orange" />
    <div className="task-two-columns">
      <section className="task-subpanel"><p className="eyebrow">方式一 · 真人录音</p><h3>上传真实口播</h3><p>WAV / MP3 / M4A / AAC，最大 500MB；后端通过 FFprobe 检查。</p><Input type="file" accept=".wav,.mp3,.m4a,.aac" disabled={Boolean(busy)} onChange={event => setAudioFile(event.target.files?.[0] || null)} /><Button size="small" disabled={Boolean(busy) || !audioFile} title={disabledReason(Boolean(busy), audioFile ? "上传并检查真人录音" : "请先选择录音文件")} onClick={() => upload("audio", audioFile, `${audioFile?.name} 已上传并通过检查`)}>{busy === "upload-audio" ? "正在上传并检查…" : "上传真人录音"}</Button></section>
      <section className="task-subpanel"><p className="eyebrow">单独完成</p><h3>上传 SRT 字幕</h3><p>{srtFiles.length ? "已有字幕文件，可下载、查看或继续校对。" : "当前缺少字幕；可上传或使用 WhisperX 生成。"}</p><Input type="file" accept=".srt" disabled={Boolean(busy)} onChange={event => setSrtUpload(event.target.files?.[0] || null)} /><Button size="small" disabled={Boolean(busy) || !srtUpload} title={disabledReason(Boolean(busy), srtUpload ? "上传并检查 SRT" : "请先选择 SRT 文件")} onClick={() => upload("srt", srtUpload, `${srtUpload?.name} 已上传并通过检查`)}>{busy === "upload-srt" ? "正在上传并检查…" : "上传并检查 SRT"}</Button>{srtFiles.map(file => <div className="task-download-row" key={file.id}><span>{file.original_name}<small>{formatSize(file.size)} · {file.relative_path}</small></span><a className="button button-small" href={file.download_url} download>下载 SRT</a></div>)}</section>
    </div>
    <section className="task-subpanel"><div className="task-section-head"><div><h3>WhisperX 自动 SRT</h3><p>本地 CPU 转写当前任务音频；首次可能需要下载模型。</p></div><Badge tone={mediaAI.whisperx.ready ? "green" : "orange"}>{mediaAI.whisperx.status || "未就绪"}</Badge></div><div className="task-form-grid"><Field label="源音频"><select value={whisperFile ?? ""} disabled={Boolean(busy) || !audioFiles.length} onChange={event => setWhisperFile(Number(event.target.value))}><option value="" disabled>{audioFiles.length ? "选择音频" : "尚无音频"}</option>{audioFiles.map(file => <option value={file.id} key={file.id}>{file.original_name}</option>)}</select></Field><Field label="模型"><select value={whisperModel} disabled={Boolean(busy)} onChange={event => setWhisperModel(event.target.value)}><option value="small">small（默认）</option><option value="base">base</option></select></Field></div><Button size="small" disabled={Boolean(busy) || !mediaAI.whisperx.ready || !whisperFile} title={disabledReason(Boolean(busy), !mediaAI.whisperx.ready ? "WhisperX 尚未通过真实转写测试" : !whisperFile ? "请先准备音频" : "生成真实 SRT")} onClick={() => void request("transcribe", `/api/tasks/${task.content_id}/transcribe`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ file_id: whisperFile, model: whisperModel }) }, "WhisperX 已生成 SRT，请人工校对后确认")}>{busy === "transcribe" ? "正在本地转写…" : "使用 WhisperX 生成 SRT"}</Button>{!mediaAI.whisperx.ready && <p className="task-help">{mediaAI.whisperx.last_error || "安装完成后请先在设置中做真实转写测试。"}</p>}</section>
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

function VideoStage({ task, core, busy, request, action }: StageProps) {
  const [mode, setMode] = useState("remotion");
  const [platform, setPlatform] = useState("douyin");
  const [burn, setBurn] = useState(true);
  const [video, setVideo] = useState<File | null>(null);
  const renderAI = core.render_ai || {};
  return <>
    <StageHead title="视频构建与成片" description="三种真实渲染方式；成功并验证 MP4 后才进入质检，失败保留旧成片。" badge={`视频构建Agent · ${renderAI.status || "未测试"}`} tone={renderAI.ready ? "green" : "orange"} />
    <section className="task-subpanel"><div className="task-section-head"><div><h3>视频构建Agent自动渲染</h3><p>1080×1920 / 30fps · 音频与 SRT 同步。</p></div><Badge tone={renderAI.ready ? "green" : "orange"}>{renderAI.status || "未测试"}</Badge></div><div className="task-form-grid"><Field label="渲染模式"><select value={mode} disabled={Boolean(busy)} onChange={event => setMode(event.target.value)}><option value="remotion">全部 Remotion：文字卡、字幕、背景与音频，无素材也可</option><option value="mixed">混合：上传场景 + Remotion 标题、字幕与画幅</option><option value="upload">全部上传：关联视频/图片 + 音频，FFmpeg 合成</option></select></Field><Field label="目标平台"><select value={platform} disabled={Boolean(busy)} onChange={event => setPlatform(event.target.value)}>{Object.entries(platformNames).map(([key, name]) => <option key={key} value={key}>{name}</option>)}</select></Field></div><label className="task-check"><input type="checkbox" checked={burn} disabled={Boolean(busy) || mode !== "upload"} onChange={event => setBurn(event.target.checked)} />上传模式烧入 SRT 字幕{mode !== "upload" && "（仅上传模式适用）"}</label><Button variant="primary" disabled={Boolean(busy)} onClick={() => void request("render", `/api/tasks/${task.content_id}/render`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ mode, platform, burn_subtitles: burn }) }, "真实 MP4 渲染完成，可预览、下载并进入质检")}>{busy === "render" ? "正在真实渲染 MP4…" : "开始渲染 MP4"}</Button><p className="task-help">上传/混合至少需要 1 个已关联且授权的视频或图片场景。渲染可能持续数分钟，失败会展示后端错误。{renderAI.last_error ? ` 最近错误：${renderAI.last_error}` : ""}</p></section>
    <section className="task-subpanel"><h3>也可以手动上传成片</h3><p>MP4 / MOV / WebM，最大 500MB。重复上传会清除旧质检结果。</p><Input type="file" accept=".mp4,.mov,.webm" disabled={Boolean(busy)} onChange={event => setVideo(event.target.files?.[0] || null)} /><Button size="small" disabled={Boolean(busy) || !video} title={disabledReason(Boolean(busy), video ? "上传并检查真实成片" : "请先选择成片文件")} onClick={() => { if (video) void request("upload-video", `/api/tasks/${task.content_id}/files?kind=video&filename=${encodeURIComponent(video.name)}`, { method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: video }, `${video.name} 已上传并通过检查`); }}>{busy === "upload-video" ? "正在上传并检查…" : "上传并检查成片"}</Button></section>
    <VideoPreview task={task} />
    <ActionBar hint="渲染成功后可预览、下载并进入五项质检。"><Button variant="danger" disabled={Boolean(busy)} onClick={() => void action("revise_assets")}>返回修改素材</Button></ActionBar>
  </>;
}

function QualityStage({ task, busy, request, action }: StageProps) {
  const [checks, setChecks] = useState<Record<string, boolean>>(() => Object.fromEntries(Object.keys(qualityItems).map(key => [key, Boolean(task.quality.checks?.[key])])));
  const [note, setNote] = useState(String(task.quality.note || ""));
  const save = () => request("save-quality", `/api/tasks/${task.content_id}/quality`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ checks, note }) }, "质检结果已保存");
  const submit = async () => { if (Object.values(checks).every(Boolean) && await save()) await action("submit_review"); };
  return <>
    <StageHead title="成片五项质检" description="逐项实际观看和检查；保存未通过结果后必须返修，不能提交人工审核。" badge="质检Agent · 未接入，人工检查" tone="orange" />
    <VideoPreview task={task} />
    <div className="task-quality-grid">{Object.entries(qualityItems).map(([key, [name, hint]]) => <label className="task-quality-item" key={key}><input type="checkbox" checked={checks[key]} disabled={Boolean(busy)} onChange={event => setChecks(current => ({ ...current, [key]: event.target.checked }))} /><span><strong>{name}</strong><small>{hint}</small></span></label>)}</div>
    <Field label="质检备注 / 返修原因"><Textarea value={note} disabled={Boolean(busy)} onChange={event => setNote(event.target.value)} placeholder="记录发现的问题、时间点或平台规格说明" /></Field>
    {task.quality.checked_at && <div className="task-info">上次结果：<strong>{task.quality.passed ? "通过" : "未通过"}</strong> · {task.quality.checked_at}</div>}
    <ActionBar hint="自动检查不等于人工最终审核；提交前会保存当前勾选与备注。"><Button disabled={Boolean(busy)} onClick={() => void save()}>{busy === "save-quality" ? "正在保存…" : "保存质检结果"}</Button>{task.state === "quality_checked" && <><Button variant="danger" disabled={Boolean(busy)} onClick={() => void action("revise_assets")}>返回素材返修</Button><Button variant="danger" disabled={Boolean(busy)} onClick={() => void action("revise_render")}>仅重做成片</Button><Button variant="primary" disabled={Boolean(busy) || !Object.values(checks).every(Boolean)} title={!Object.values(checks).every(Boolean) ? "五项全部通过后才能提交人工审核" : "保存结果并提交人工终审"} onClick={() => void submit()}>保存并提交人工审核</Button></>}</ActionBar>
  </>;
}

function ReviewStage({ task, busy, action }: StageProps) {
  return <><StageHead title="人工最终审核" description="请完整观看最终成片。此确认与之后的发布确认是两个独立检查点。" badge="用户 · 最终人工确认" tone="orange" /><VideoPreview task={task} /><div className="task-info">当前五项质检已通过，但仍需你本人确认最终内容、表达与发布风险。</div><ActionBar hint="审核要求修改时，可返回脚本或素材，后续审批会清除。"><Button variant="danger" disabled={Boolean(busy)} onClick={() => void action("revise_script")}>返回脚本返修</Button><Button variant="danger" disabled={Boolean(busy)} onClick={() => void action("revise_assets")}>返回素材返修</Button><Button variant="primary" disabled={Boolean(busy)} onClick={() => void action("approve_final")}>我已看成片，批准最终版本</Button></ActionBar></>;
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

export default function VideoStages(props: StageProps & { stage: number }) {
  const { stage } = props;
  if (stage === 1) return <ScriptsStage {...props} />;
  if (stage === 2) return <AudioStage {...props} />;
  if (stage === 3) return <AssetsStage {...props} />;
  if (stage === 4) return <VideoStage {...props} />;
  if (stage === 5) return <QualityStage {...props} />;
  if (stage === 6) return <ReviewStage {...props} />;
  if (stage === 7) return <PublicationsStage {...props} />;
  if (stage === 8) return <RetroStage {...props} />;
  return <div className="task-inline-empty">当前选题尚未进入视频脚本工作流，请先在选题库确认。</div>;
}
