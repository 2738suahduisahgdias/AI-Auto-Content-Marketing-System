import {useContentDraft} from "@/lib/contentDraft";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ExternalLink, LoaderCircle, LogIn, RotateCcw, Save, Send, ShieldAlert, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { useApp } from "@/AppContext";
import { Badge, Button, Card, Empty, ErrorBox, Field, Modal, Textarea } from "@/components/ui";
import { api, jsonOptions, uploadOptions } from "@/lib/api";
import { platformNames, publishStatusNames } from "@/lib/names";
import { PlatformField } from "@/components/PlatformField";
import type { ContentKind, Job, Json, PublishBatch, PublishTarget } from "@/lib/types";
import "./PublishingPanel.css";

export interface PublishingSource {
  id: string;
  title: string;
  body: string;
  fileId?: number;
  previewUrl?: string;
  variantId?: string;
}

interface TargetForm {
  enabled: boolean;
  values: Json;
  assetNames: Record<string, string>;
}

const platformsFor = (kind: ContentKind) => kind === "article"
  ? ["wechat_official_account", "xiaohongshu"]
  : ["douyin", "xiaohongshu", "wechat_channels"];
const groupNames: Record<string, string> = { basic: "基础信息", media: "媒体与封面", settings: "发布设置", advanced: "扩展信息" };
const activeStatuses = new Set(["preparing", "publishing"]);
const generationStatuses = new Set(["queued", "retry_wait", "leased", "running", "cancel_requested"]);
const lockedStatuses = new Set(["published", "unknown_remote", "preparing", "publishing"]);

function targetDefaults(source: PublishingSource, platform: string, definitions: Json[], target?: PublishTarget): TargetForm {
  const payload = target?.payload || {};
  const status = target?.status || "draft";
  const supported = platform in platformNames;
  const values = Object.fromEntries(definitions.map(definition => {
    const name = definition.name;
    let value = payload[name] ?? definition.default;
    if (name === "title" && !value) value = source.title;
    if (name === "short_title" && !value) value = String(payload.title || source.title).slice(0, definition.max_length || undefined);
    if (name === "body" && !value) value = source.body;
    if (name === "description" && !value) value = source.body.slice(0, definition.max_length || undefined);
    if (name === "author" && !value) value = "刘量";
    if (name === "summary" && !value) value = source.body.slice(0, definition.max_length || 120);
    if (name === "tags" && !value) value = "#企业AI #AI应用";
    return [name, value];
  }));
  return {
    enabled: supported && !lockedStatuses.has(status),
    values: { ...payload, ...values },
    assetNames: Object.fromEntries(definitions.filter(item => item.control === "asset" && payload[item.name]).map(item => [item.name, "已关联图片资产"])),
  };
}

function statusTone(status: string): "neutral" | "green" | "orange" | "red" | "blue" {
  if (status === "published") return "green";
  if (["failed", "unknown_remote"].includes(status)) return "red";
  if (["ready", "preparing", "publishing"].includes(status)) return "orange";
  return "neutral";
}

export function PublishingPanel(props: { kind: ContentKind; source: PublishingSource | null }) {
  return <PublishingPanelEditor key={`${props.kind}:${props.source?.id || "none"}:${props.source?.fileId || 0}`} {...props} />;
}

function PublishingPanelEditor({ kind, source }: { kind: ContentKind; source: PublishingSource | null }) {
  const { run, notify, resources } = useApp();
  const platforms = useMemo(() => platformsFor(kind), [kind]);
  const contracts = useMemo(() => Object.fromEntries((resources?.accounts?.publish_knowledge?.platforms || []).flatMap((item: any) => item.content_types.map((content: any) => [`${item.platform}:${content.content_kind}`, content]))), [resources]);
  const fieldsFor = useCallback((platform: string): Json[] => contracts[`${platform}:${kind}`]?.fields || [], [contracts, kind]);
  const [batch, setBatch] = useState<PublishBatch | null>(null);
  const [fieldJobs, setFieldJobs] = useState<Job[]>([]);
  const [generationPrompt, setGenerationPrompt,promptSaveError] = useContentDraft(`publishing:${kind}:${source?.id}:${source?.fileId||0}:prompt`, "");
  const [forms, setForms,formsSaveError] = useContentDraft<Record<string, TargetForm>>(`publishing:${kind}:${source?.id}:${source?.fileId||0}:forms`, source ? Object.fromEntries(platforms.map(platform => [platform, targetDefaults(source, platform, fieldsFor(platform))])) : {});
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [busy, setBusy] = useState("");
  const [executionEnabled,setExecutionEnabled]=useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [dirtyPlatforms, setDirtyPlatforms] = useState<Set<string>>(new Set());
  const dirty = useRef(new Set<string>());
  const [appliedSaved,setAppliedSaved] = useContentDraft(`publishing:${kind}:${source?.id}:${source?.fileId||0}:applied-job`, "");
  const appliedJob = useRef(appliedSaved);
  const sourceId = source?.id || "";
  const sourceFileId = source?.fileId;
  const sourceTitle = source?.title || "";
  const sourceBody = source?.body || "";

  const loadBatch = useCallback(async (silent = false) => {
    if (!sourceId) return;
    if (!silent) setLoading(true);
    try {
      const data = await api<{ batch: PublishBatch | null; field_jobs: Job[]; execution_enabled?: boolean }>(`/api/publishing/bootstrap?kind=${kind}&source_id=${encodeURIComponent(sourceId)}${sourceFileId ? `&source_file_id=${sourceFileId}` : ""}`);
      setBatch(data.batch);
      setExecutionEnabled(data.execution_enabled !== false);
      setFieldJobs(data.field_jobs || []);
      const currentSource = { id: sourceId, title: sourceTitle, body: sourceBody };
      setForms(current => Object.fromEntries(platforms.map(platform => {
        const target = data.batch?.targets.find(item => item.platform === platform);
        const fallback = targetDefaults(currentSource, platform, fieldsFor(platform), target);
        return [platform, (dirty.current.has(platform) || localStorage.getItem(`yingxu:content-draft:v1:publishing:${kind}:${sourceId}:${sourceFileId||0}:forms`)) && current[platform] ? current[platform] : fallback];
      })));
      setLoadError("");
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "发布批次读取失败，请重试");
    } finally {
      if (!silent) setLoading(false);
    }
  }, [fieldsFor, kind, platforms, sourceBody, sourceId, sourceTitle, sourceFileId]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadBatch(), 0);
    return () => window.clearTimeout(timer);
  }, [loadBatch]);

  const active = Boolean(batch?.targets.some(target => activeStatuses.has(target.status)));
  const generationJob = fieldJobs[0];
  const generationActive = Boolean(generationJob && generationStatuses.has(generationJob.status));
  useEffect(() => {
    if (!active && !generationActive) return;
    const timer = window.setInterval(() => void loadBatch(true), 3000);
    return () => window.clearInterval(timer);
  }, [active, generationActive, loadBatch]);

  useEffect(() => {
    if (!generationJob || generationJob.status !== "succeeded" || appliedJob.current === generationJob.id) return;
    const payloads = generationJob.result?.platforms;
    if (!payloads) return;
    appliedJob.current = generationJob.id;
    Object.keys(payloads).forEach(platform => dirty.current.add(platform));
    setDirtyPlatforms(new Set(dirty.current));
    setForms(current => Object.fromEntries(platforms.map(platform => {
      const generated = payloads[platform];
      const form = current[platform];
      if (!generated || !form) return [platform, form];
      const allowed = new Set(fieldsFor(platform).filter(item => item.agent_generated).map(item => item.name));
      const values = Object.fromEntries(Object.entries(generated).filter(([name]) => allowed.has(name)));
      return [platform, { ...form, values: { ...form.values, ...values } }];
    })));
    setAppliedSaved(generationJob.id);
    notify("发布字段已回填并自动保存本机草稿；请检查后保存正式批次，不会自动发布");
  }, [fieldsFor, generationJob, notify, platforms]);

  const update = (platform: string, patch: Partial<TargetForm>) => {
    dirty.current.add(platform);
    setDirtyPlatforms(new Set(dirty.current));
    setForms(current => ({ ...current, [platform]: { ...current[platform], ...patch } }));
  };

  const updateValue = (platform: string, name: string, value: unknown) => {
    dirty.current.add(platform);
    setDirtyPlatforms(new Set(dirty.current));
    setForms(current => ({ ...current, [platform]: { ...current[platform], values: { ...current[platform].values, [name]: value } } }));
  };

  const execute = async (key: string, action: () => Promise<unknown>, success: string) => {
    if (busy) return null;
    setBusy(key);
    try {
      const result = await run(action, success, false);
      if (result !== null) await loadBatch(true);
      return result;
    } finally { setBusy(""); }
  };

  const generatablePlatforms = platforms.filter(platform => {
    const target = batch?.targets.find(item => item.platform === platform);
    return forms[platform]?.enabled && platform in platformNames && !lockedStatuses.has(target?.status || "draft");
  });

  const generateFields = async () => {
    if (!source || !generatablePlatforms.length) {
      notify("至少选择一个可编辑的平台，发布 Agent 才能生成字段", true);
      return;
    }
    const job = await execute("generate-fields", () => api("/api/publishing/generate-fields", jsonOptions("POST", {
      content_kind: kind,
      source_id: source.id,
      source_file_id: source.fileId,
      platforms: generatablePlatforms,
      prompt: generationPrompt,
    })), "字段生成任务已提交，结果自动保留，不会自动发布") as Job | null;
    if (job?.id) setFieldJobs(current => current.some(item => item.id === job.id) ? current : [job, ...current]);
  };

  const saveBatch = async (sync = false) => {
    if (!source) return;
    const targets = platforms.filter(platform => {
      const target = batch?.targets.find(item => item.platform === platform);
      const supported = platform in platformNames;
      return forms[platform]?.enabled && supported && !lockedStatuses.has(target?.status || "draft");
    }).map(platform => ({ platform, payload: { ...Object.fromEntries(fieldsFor(platform)
      .filter(field => !["settings", "advanced"].includes(field.group))
      .map(field => [field.name, forms[platform].values[field.name]])), ...(["wechat_official_account","wechat_channels"].includes(platform) ? {manual_transfer:true} : {}) } }));
    if (!targets.length) {
      notify("至少选择一个可编辑的发布平台；待人工核对和已发布平台不能重复提交", true);
      return;
    }
    const saved = await execute("save", () => api("/api/publishing/batches", jsonOptions("POST", {
      content_kind: kind,
      source_id: source.id,
      source_file_id: source.fileId,
      targets,
    })), "发布批次已保存；下一步生成平台预览");
    if (saved) {
      targets.forEach(target => dirty.current.delete(target.platform));
      setDirtyPlatforms(new Set(dirty.current));
      if (sync) {
        const automatic = targets.filter(t => !["wechat_official_account", "wechat_channels"].includes(t.platform)).map(t => t.platform);
        if (automatic.length) await execute("prepare", () => api(`/api/publishing/batches/${(saved as PublishBatch).id}/prepare`, jsonOptions("POST", {platforms:automatic})), "同步任务已提交，请在平台后台审核后发布");
        if (automatic.length < targets.length) notify("微信平台请使用卡片中的复制内容和手动打开后台入口，内容已保存");
      }
    }
  };

  const uploadCover = async (platform: string, name: string, file?: File) => {
    if (!file || busy) return;
    setBusy(`cover:${platform}:${name}`);
    try {
      const asset = await run<Json>(() => api(`/api/v2/assets?filename=${encodeURIComponent(file.name)}&purpose=publish_cover&rights=owned`, uploadOptions(file)), "图片已保存为本地资产，保存批次时会再次校验尺寸与比例", false);
      if (asset) {
        updateValue(platform, name, String(asset.id));
        update(platform, { assetNames: { ...forms[platform].assetNames, [name]: file.name } });
      }
    } finally { setBusy(""); }
  };

  const selectedReady = batch?.targets.filter(target => target.status === "ready" && forms[target.platform]?.enabled) || [];
  const hasDirtySelection = platforms.some(platform => forms[platform]?.enabled && dirtyPlatforms.has(platform));

  if (!source) {
    return <Empty title={kind === "article" ? "没有可发布的已批准文章" : "没有可发布的已批准视频"} description={kind === "article" ? "先保存正文并完成人工审批；文章发布不会读取视频任务。" : "先完成 MP4、五项质检和人工最终审核；视频发布不会读取文章正文。"} action={<Link className="button button-primary" to={kind === "article" ? "/articles" : "/tasks"}>{kind === "article" ? "前往文章任务" : "前往视频任务"}</Link>} />;
  }

  return <section className="publishing-panel">
    <div className="publishing-panel-heading">
      <div><p className="eyebrow">{kind === "article" ? "ARTICLE DISTRIBUTION" : "VIDEO DISTRIBUTION"}</p><h2>{kind === "article" ? "文章发布批次" : "视频发布批次"}</h2><p>{source.title} · 来源 {source.id}</p></div>
      <Badge tone="orange">预览不等于已发布</Badge>
    </div>
    {(formsSaveError||promptSaveError)&&<ErrorBox>{formsSaveError||promptSaveError}</ErrorBox>}{loadError && <ErrorBox>{loadError}<br />请检查本地服务后重试；不会把读取失败当作发布结果。</ErrorBox>}
    {loading && <p className="publishing-loading"><LoaderCircle className="spin" size={15} />正在读取真实发布批次…</p>}
    <Card className="publishing-generator">
      <div className="publishing-generator-head"><div><h3><Sparkles size={17} />发布 Agent 字段生成</h3><p>根据已审核内容，生成各平台的标题、正文和话题。</p></div><Badge tone={dirtyPlatforms.size ? "orange" : "neutral"}>{dirtyPlatforms.size ? `${dirtyPlatforms.size} 个平台未保存` : "字段可编辑"}</Badge></div>
      <details className="publishing-secondary"><summary>补充生成要求（选填）</summary><Field label="补充要求（选填，最多 2000 字）"><Textarea value={generationPrompt} disabled={Boolean(busy) || generationActive} maxLength={2000} placeholder="例如：标题面向企业主，少用术语；保留原文事实，不增加案例和数字。" onChange={event => setGenerationPrompt(event.target.value)} /></Field></details>
      <div className="publishing-generator-actions"><p>只回填文本；{kind === "article" ? "封面、原创和评论选项" : "封面与视频"}由你处理。生成后请检查，再一键同步到后台。</p><Button variant="primary" disabled={Boolean(busy) || generationActive || !generatablePlatforms.length} title={!generatablePlatforms.length ? "先勾选至少一个可编辑平台" : "生成后会覆盖选中平台的当前文本字段，请检查后保存"} onClick={() => void generateFields()}><Sparkles size={15} />{busy === "generate-fields" ? "正在提交…" : generationActive ? "发布 Agent 生成中…" : "发布 Agent 生成选中平台字段"}</Button></div>
      {generationActive && <p className="publishing-loading"><LoaderCircle className="spin" size={15} />正在生成 {generatablePlatforms.map(platform => platformNames[platform]).join("、")} 的字段，页面可保留打开。</p>}
      {generationJob?.status === "failed" && <ErrorBox><strong>字段生成失败：{String(generationJob.error?.code || "MODEL_GENERATION_FAILED")}</strong><br />{String(generationJob.error?.message || "模型没有完成字段生成")}{generationJob.error?.action && <><br />怎么改：{String(generationJob.error.action)}</>}</ErrorBox>}
    </Card>
    <div className="publishing-target-grid">
      {platforms.map(platform => {
        const target = batch?.targets.find(item => item.platform === platform);
        const status = target?.status || "draft";
        const form = forms[platform] || targetDefaults(source, platform, fieldsFor(platform), target);
        const supported = platform in platformNames;
        const locked = lockedStatuses.has(status) || !supported;
        const definitions = fieldsFor(platform);
        const rawError = target?.error;
        const targetError = rawError && Object.keys(rawError).length ? ((rawError as any).error || rawError) : null;
        return <Card className={`publishing-target${target ? " has-batch" : ""}`} key={platform}>
          <div className="publishing-target-head">
            <label className="publishing-check"><input type="checkbox" checked={form.enabled} disabled={locked || Boolean(busy)} onChange={event => update(platform, { enabled: event.target.checked })} /><strong>{platformNames[platform]}{kind === "article" && platform === "xiaohongshu" ? "长文" : ""}</strong></label>
            <Badge tone={["wechat_channels","wechat_official_account"].includes(platform) && status !== "published" ? "neutral" : statusTone(status)}>{["wechat_channels","wechat_official_account"].includes(platform) && status !== "published" ? "需手动发布" : publishStatusNames[status] || status}</Badge>
          </div>
          {["wechat_channels", "wechat_official_account"].includes(platform) ? <p>此平台请手动发布：复制文案、下载素材后，在平台后台完成审核与上传。</p> : <Button size="small" variant="ghost" disabled={Boolean(busy)} onClick={() => void execute(`login:${platform}`, () => api(`/api/publishing/connections/${platform}/login`, jsonOptions("POST")), "登录窗口已提交，请完成本人扫码")}><LogIn size={14} />打开 Chrome 登录</Button>}
          <div className="button-row"><Button size="small" onClick={async()=>{const text=[form.values.title,form.values.short_title,form.values.body || form.values.description,form.values.summary,form.values.tags].filter(Boolean).join("\n\n");try{await navigator.clipboard.writeText(text);notify("已复制当前内容，请到平台后台粘贴并审核");}catch{notify("复制权限不可用，请展开手动复制并选择文本",true);}}}>复制发布内容</Button><a className="button button-small" href={({douyin:"https://creator.douyin.com/",xiaohongshu:"https://creator.xiaohongshu.com/",wechat_channels:"https://channels.weixin.qq.com/",wechat_official_account:"https://mp.weixin.qq.com/"} as Record<string,string>)[platform]} target="_blank" rel="noreferrer">手动打开后台</a>{source.previewUrl && <a className="button button-small" href={source.previewUrl} download>下载视频</a>}{kind === "article" && <Link className="button button-small" to={`/articles/${source.id}`}>下载文章配图／长图</Link>}</div>
          <details><summary>手动复制内容（剪贴板不可用时）</summary><Textarea readOnly value={[form.values.title,form.values.body || form.values.description,form.values.summary,form.values.tags].filter(Boolean).join("\n\n")} /></details>
          {Object.entries(groupNames).map(([group, groupName]) => {
            const groupFields = definitions.filter(definition => definition.group === group && definition.agent_generated);
            if (!groupFields.length) return null;
            return <section className={`publishing-field-group publishing-field-group-${group}`} key={group}><h3>{groupName}</h3>{groupFields.map(definition => {
              const dependency = definition.depends_on;
              const active = !dependency || form.values[dependency.field] === dependency.equals;
              const fieldError = targetError?.field === definition.name ? `${targetError?.message || "字段校验失败"}${targetError?.action ? `；怎么改：${targetError?.action}` : ""}` : undefined;
              const input = <PlatformField key={definition.name} compact definition={definition} value={form.values[definition.name]} disabled={locked || Boolean(busy)} active={active} assetName={busy === `cover:${platform}:${definition.name}` ? "正在上传图片…" : form.assetNames[definition.name]} error={fieldError} sourceId={source.id} onChange={value => updateValue(platform, definition.name, value)} onUpload={file => void uploadCover(platform, definition.name, file)} />;
              return ["author", "summary"].includes(definition.name) ? <details key={definition.name} className="publishing-secondary"><summary>{definition.label}（选填）</summary>{input}</details> : input;
            })}</section>;
          })}
          {targetError && <ErrorBox><strong>{String(targetError.code || "发布失败")}</strong><br />{String(targetError.message || "平台步骤未完成")}{targetError.action && <><br />怎么改：{String(targetError.action)}</>}</ErrorBox>}
          {status === "unknown_remote" && <><div className="publishing-unknown"><ShieldAlert size={17} /><p><strong>禁止直接重试</strong>平台点击后的结果无法确认。请先在平台后台核实是否已公开，避免重复发布。</p></div><Button size="small" disabled={Boolean(busy)} onClick={() => { const evidence = window.prompt("请填写平台后台的实际发布证据（时间、内容或真实链接）；不要只写已发布"); if (evidence) void execute(`reconcile:${target?.id}`, () => api(`/api/publishing/targets/${target?.id}/reconcile`, jsonOptions("POST", { evidence })), "平台实际发布结果已记录"); }}>已在后台核实为已发布</Button></>}
          {status === "ready" && !["wechat_channels","wechat_official_account"].includes(platform) && <p className="publishing-ready">后台预填已完成，等待你审核。请检查平台窗口中的账号、实际上传与文案，然后确认发布。</p>}
          {target?.external_url && <a className="button button-small publishing-external" href={target.external_url} target="_blank" rel="noreferrer">查看真实发布链接<ExternalLink size={13} /></a>}
          {status === "failed" && !["wechat_official_account","wechat_channels"].includes(platform) && <Button size="small" disabled={Boolean(busy) || dirtyPlatforms.has(platform)} title={dirtyPlatforms.has(platform) ? "先保存本平台的修改，再重试已保存内容" : "重新生成已保存内容的平台预览"} onClick={() => void execute(`retry:${target?.id}`, () => api(`/api/publishing/targets/${target?.id}/retry`, jsonOptions("POST")), "失败目标已重新加入预览队列")}><RotateCcw size={14} />重试失败预览</Button>}
        </Card>;
      })}
    </div>
    {source.previewUrl && <details className="publishing-local-preview"><summary>查看已审核成片</summary><video className="publishing-source-video" controls preload="metadata" src={source.previewUrl} /></details>}
    <p className="publishing-platform-note">封面、原创／AI 声明、评论、可见范围、合集、位置、定时、广告和付费选项，请在平台后台按实际内容确认。这里只同步文案与成品素材。</p>
    <div className="publishing-batch-bar">
      <div><strong>{batch ? "发布内容已保存" : "检查内容后同步"}</strong><p>{active ? "后台正在执行，离开页面后任务仍会保留。" : "检查内容后点击一键同步；在平台后台人工审核并发布。受限平台使用复制内容入口。"}</p></div>
      <div className="button-row">
        <Button disabled={Boolean(busy)} onClick={() => void saveBatch()}><Save size={15} />{busy === "save" ? "正在保存…" : `保存${kind === "article" ? "文章" : "视频"}批次`}</Button>
        <Button variant="primary" disabled={Boolean(busy) || generationActive || !generatablePlatforms.length} onClick={()=>void saveBatch(true)}>一键同步到后台</Button>
        {executionEnabled && <Button variant="primary" disabled={!executionEnabled || Boolean(busy) || !selectedReady.length || hasDirtySelection} title={!executionEnabled ? "当前环境未启用自动公开发布，请在平台后台人工确认" : hasDirtySelection ? "先保存修改并重新生成受影响平台预览" : !selectedReady.length ? "至少一个选中平台必须已完成真实预览" : "对所有选中的就绪平台进行一次公开确认"} onClick={() => setConfirmOpen(true)}><Send size={15} />确认公开发布{selectedReady.length ? `（${selectedReady.length}）` : ""}</Button>}
      </div>
    </div>
    <Modal open={confirmOpen} onOpenChange={setConfirmOpen} title="一次人工确认：即将公开发布" description="这不是预览。请确认你已在各平台窗口检查账号、正文、封面、上传进度和平台提示。">
      <div className="publishing-confirm-list">{selectedReady.map(target => <div key={target.id}><Badge tone="orange">{platformNames[target.platform]}</Badge><span>{forms[target.platform]?.values.title || forms[target.platform]?.values.short_title}</span></div>)}</div>
      <ErrorBox>发布后平台结果可能失败或无法确认。无法确认时必须先去平台后台核对，不能直接重试。</ErrorBox>
      <div className="button-row publishing-modal-actions"><Button onClick={() => setConfirmOpen(false)}>返回检查</Button><Button variant="primary" disabled={!executionEnabled || Boolean(busy)} onClick={() => { setConfirmOpen(false); void execute("confirm", () => api(`/api/publishing/batches/${batch?.id}/confirm`, jsonOptions("POST", { source_hash: batch?.source_hash, platforms: selectedReady.map(target => target.platform) })), "公开发布已确认，正在逐平台执行"); }}>我已完成预览检查，确认公开</Button></div>
    </Modal>
  </section>;
}
