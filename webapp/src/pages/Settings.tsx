import { useState, type ReactNode } from "react";
import { Bot, Film, LoaderCircle, Mic2, RefreshCw, RotateCcw, Save, Settings2, Subtitles, Volume2, WandSparkles } from "lucide-react";
import { useApp } from "@/AppContext";
import { Badge, Button, Card, Empty, ErrorBox, Field, Input, PageHeader, Textarea, Busy } from "@/components/ui";
import { api, errorText, jsonOptions } from "@/lib/api";
import "./Settings.css";

interface AgentDefinition {
  name: string;
  description: string;
  engines: string[];
  engine: string;
  model: string;
  timeout: number;
  attempts: number;
  concurrency: number;
  prompt: boolean;
  connected: boolean;
  variants?: string[];
}

interface AgentConfig {
  enabled: boolean;
  engine: string;
  model: string;
  prompt: string;
  timeout_seconds: number;
  max_attempts: number;
  concurrency: number;
}

type DraftNumber = number | string;
interface AgentDraft extends Omit<AgentConfig, "timeout_seconds" | "max_attempts" | "concurrency"> {
  timeout_seconds: DraftNumber;
  max_attempts: DraftNumber;
  concurrency: DraftNumber;
}

interface AgentResource {
  agents: Record<string, AgentDefinition>;
  configs: Record<string, AgentConfig>;
}

interface CapabilityStatus {
  installed?: boolean;
  ready: boolean;
  status?: string;
  last_success?: string | null;
  last_error?: string | null;
}

interface CoreResource {
  ai: CapabilityStatus & {
    version?: string | null;
    model?: string;
    oauth_status?: string;
  };
  asset_ai: CapabilityStatus;
  render_ai: CapabilityStatus;
  voices: {
    last_success?: string | null;
    last_error?: string | null;
    capabilities: {
      system_ready: boolean;
      system_status: string;
    };
  };
  media_ai: {
    whisperx: CapabilityStatus & { default_model?: string };
    openvoice: CapabilityStatus & { missing_files?: string[] };
  };
}

type TestId = "kimi" | "assets" | "remotion" | "voice" | "whisperx" | "openvoice";

const tests: Record<TestId, { path: string; success: string; progress: string }> = {
  kimi: { path: "/api/ai/test", success: "Kimi 真实连接测试成功，脚本生成能力已验证", progress: "正在实际调用 Kimi，并验证五个 JSON 字符串字段…" },
  assets: { path: "/api/assets/test", success: "素材规划 Agent 的真实分镜 JSON 测试成功", progress: "正在实际生成分镜 JSON，并检查时间轴与素材类型…" },
  remotion: { path: "/api/render/test", success: "Remotion 真实 MP4 自测成功", progress: "正在执行真实 Remotion 渲染并验证 MP4，可能需要数分钟…" },
  voice: { path: "/api/voices/test", success: "系统语音生成、WAV 转换和媒体检查均已通过", progress: "正在使用 macOS 系统语音生成并检查临时 WAV…" },
  whisperx: { path: "/api/whisperx/test", success: "WhisperX 真实转写测试成功", progress: "正在进行本地 CPU 转写；首次运行可能需要下载模型…" },
  openvoice: { path: "/api/voices/clone/test", success: "OpenVoice 本人授权参考音色的真实克隆测试成功", progress: "正在使用本地 OpenVoice V2 和授权参考样本执行真实克隆…" },
};

function toDraft(config: AgentConfig): AgentDraft {
  return {
    enabled: config.enabled,
    engine: config.engine,
    model: config.model,
    prompt: config.prompt,
    timeout_seconds: config.timeout_seconds,
    max_attempts: config.max_attempts,
    concurrency: config.concurrency,
  };
}

function validateDraft(draft: AgentDraft): AgentConfig {
  if (!draft.model.trim()) throw new Error("模型或变体不能为空");
  if (draft.model.length > 100) throw new Error("模型或变体不能超过 100 个字符");
  if (draft.prompt.length > 12000) throw new Error("补充提示词不能超过 12000 个字符");
  const limits = [
    ["timeout_seconds", "超时", 30, 3600],
    ["max_attempts", "最多尝试次数", 1, 5],
    ["concurrency", "并发上限", 1, 2],
  ] as const;
  const numbers = {} as Pick<AgentConfig, "timeout_seconds" | "max_attempts" | "concurrency">;
  for (const [key, label, minimum, maximum] of limits) {
    const value = Number(draft[key]);
    if (draft[key] === "" || !Number.isInteger(value) || value < minimum || value > maximum) {
      throw new Error(`${label}必须是 ${minimum}～${maximum} 之间的整数`);
    }
    numbers[key] = value;
  }
  return { enabled: draft.enabled, engine: draft.engine, model: draft.model.trim(), prompt: draft.prompt, ...numbers };
}

function ConnectionCard({
  icon,
  eyebrow,
  title,
  description,
  ready,
  status,
  lastSuccess,
  lastError,
  testError,
  testing,
  blocked,
  disabledReason,
  onTest,
  buttonLabel,
  progress,
  footnote,
  children,
}: {
  icon: ReactNode;
  eyebrow: string;
  title: string;
  description: string;
  ready: boolean;
  status: string;
  lastSuccess?: string | null;
  lastError?: string | null;
  testError?: string;
  testing: boolean;
  blocked: boolean;
  disabledReason?: string;
  onTest: () => void;
  buttonLabel: string;
  progress: string;
  footnote: string;
  children?: ReactNode;
}) {
  const error = testError || lastError;
  const disabled = testing || blocked || Boolean(disabledReason);
  const reason = disabledReason || (blocked ? "请等待当前真实测试完成" : undefined);
  return <Card className="settings-connection-card">
    <div className="settings-connection-head">
      <span className="settings-connection-icon">{icon}</span>
      <div><p className="eyebrow">{eyebrow}</p><h2>{title}</h2></div>
      <Badge tone={ready ? "green" : "orange"}>{status}</Badge>
    </div>
    <p className="settings-connection-description">{description}</p>
    {children}
    <div className="settings-last-success"><span>最近真实成功</span><strong>{lastSuccess || "尚未验证"}</strong></div>
    {error && <ErrorBox><strong>最近连接 / 测试错误</strong><p>{error}</p></ErrorBox>}
    {testing && <p className="settings-test-progress" role="status"><LoaderCircle className="spin" size={15} />{progress}</p>}
    <Button variant="primary" size="small" onClick={onTest} disabled={disabled} title={reason} aria-busy={testing}>
      {testing ? <LoaderCircle className="spin" size={14} /> : null}{testing ? "真实测试进行中…" : buttonLabel}
    </Button>
    {disabledReason && <p className="settings-disabled-reason">{disabledReason}</p>}
    <p className="settings-connection-footnote">{footnote}</p>
  </Card>;
}

export default function Settings() {
  const { resources, loading, loadError, refresh, notify } = useApp();
  const agentData = resources?.agents as AgentResource | undefined;
  const core = resources?.core as CoreResource | undefined;
  const definitions = agentData?.agents || {};
  const configs = agentData?.configs || {};
  const entries = Object.entries(definitions);
  const [selected, setSelected] = useState("industry_topic_agent");
  const [drafts, setDrafts] = useState<Record<string, AgentDraft>>({});
  const [dirty, setDirty] = useState<Set<string>>(new Set());
  const [configBusy, setConfigBusy] = useState<string | null>(null);
  const [configError, setConfigError] = useState("");
  const [activeTest, setActiveTest] = useState<TestId | null>(null);
  const [testErrors, setTestErrors] = useState<Partial<Record<TestId, string>>>({});
  const [refreshing, setRefreshing] = useState(false);
  const selectedId = definitions[selected] ? selected : entries[0]?.[0] || "";
  const definition = definitions[selectedId];
  const config = configs[selectedId];
  const draft = drafts[selectedId] || (config ? toDraft(config) : undefined);
  const enabledCount = Object.values(configs).filter(item => item.enabled).length;

  function selectAgent(id: string) {
    setSelected(id);
    setConfigError("");
  }

  function updateDraft<K extends keyof AgentDraft>(key: K, value: AgentDraft[K]) {
    if (!selectedId) return;
    setDrafts(current => ({ ...current, [selectedId]: { ...(current[selectedId] || toDraft(configs[selectedId])), [key]: value } }));
    setDirty(current => current.has(selectedId) ? current : new Set(current).add(selectedId));
    setConfigError("");
  }

  function clearDraft(id: string) {
    setDrafts(current => { const next = { ...current }; delete next[id]; return next; });
    setDirty(current => { const next = new Set(current); next.delete(id); return next; });
  }

  async function saveAgent() {
    if (!selectedId || !draft || configBusy) return;
    let payload: AgentConfig;
    try {
      payload = validateDraft(draft);
    } catch (error) {
      const message = errorText(error);
      setConfigError(message);
      notify(message, true);
      return;
    }
    setConfigBusy(`save:${selectedId}`);
    setConfigError("");
    try {
      await api<AgentConfig>(`/api/agents/config/${selectedId}`, jsonOptions("PUT", payload));
      await refresh();
      clearDraft(selectedId);
      notify(`${definition.name}配置已保存，之后的新任务生效`);
    } catch (error) {
      const message = errorText(error);
      setConfigError(message);
      notify(message, true);
    } finally {
      setConfigBusy(null);
    }
  }

  async function resetAgent() {
    if (!selectedId || configBusy) return;
    setConfigBusy(`reset:${selectedId}`);
    setConfigError("");
    try {
      await api<AgentConfig>(`/api/agents/config/${selectedId}`, jsonOptions("PUT", { reset: true }));
      await refresh();
      clearDraft(selectedId);
      notify(`已恢复${definition.name}默认配置，其他 Agent 未改变`);
    } catch (error) {
      const message = errorText(error);
      setConfigError(message);
      notify(message, true);
    } finally {
      setConfigBusy(null);
    }
  }

  async function runTest(id: TestId) {
    if (activeTest) return;
    setActiveTest(id);
    setTestErrors(current => { const next = { ...current }; delete next[id]; return next; });
    try {
      await api(tests[id].path, jsonOptions("POST"));
      await refresh();
      notify(tests[id].success);
    } catch (error) {
      const message = errorText(error);
      setTestErrors(current => ({ ...current, [id]: message }));
      await refresh();
      notify(message, true);
    } finally {
      setActiveTest(null);
    }
  }

  async function reload() {
    if (refreshing) return;
    setRefreshing(true);
    await refresh();
    setRefreshing(false);
  }

  const connectionProps = (id: TestId) => ({
    testing: activeTest === id,
    blocked: activeTest !== null && activeTest !== id,
    testError: testErrors[id],
    progress: tests[id].progress,
    onTest: () => { void runTest(id); },
  });

  return <div className="settings-page">
    <PageHeader eyebrow="LOCAL SYSTEM / CONTROL ROOM" title="Agent 与本地能力" description="逐个管理独立 Agent；真实测试连接，不把文件存在或接口返回当作能力已验收。" actions={<div className="settings-page-actions"><Badge tone="blue">{entries.length} 个独立 Agent · {enabledCount} 个已启用</Badge><Button size="small" onClick={() => { void reload(); }} disabled={refreshing}><RefreshCw className={refreshing ? "spin" : ""} size={14} />{refreshing ? "正在刷新" : "刷新真实状态"}</Button></div>} />
    {loadError && <ErrorBox>{resources ? `刷新失败：${loadError}\n当前仍显示上一次成功读取的数据。` : loadError}</ErrorBox>}
    {!resources ? (loading ? <Busy label="正在读取 Agent 配置与本地能力状态…" /> : <Empty title="设置数据尚未读取" description="请检查本地服务后点击“刷新真实状态”。" />) : <>
      <Card className="settings-agent-card">
        <div className="settings-agent-heading"><div className="settings-agent-title"><Settings2 size={20} /><div><h2>Agent 配置中心</h2><p>每个 Agent 单独保存；只影响之后的新任务，历史产物和运行中任务不变。</p></div></div>{definition && config && <Badge tone={config.enabled ? "green" : definition.connected ? "orange" : "red"}>{config.enabled ? "已启用" : definition.connected ? "已停用" : "未接入"}</Badge>}</div>
        {definition && config && draft ? <div className="settings-agent-layout">
          <aside className="settings-agent-list" aria-label="独立 Agent 列表">{entries.map(([id, item]) => <button type="button" key={id} className={`settings-agent-item${id === selectedId ? " active" : ""}`} onClick={() => selectAgent(id)} aria-pressed={id === selectedId}>
            <span className="settings-agent-item-top"><strong>{item.name}</strong>{dirty.has(id) && <i title="有未保存修改">未保存</i>}</span>
            <small>{item.description}</small>
            <span className="settings-agent-item-meta">{configs[id]?.engine} · {configs[id]?.enabled ? "启用" : item.connected ? "停用" : "未接入"}</span>
          </button>)}</aside>
          <section className="settings-agent-editor" aria-label={`${definition.name}配置`}>
            <div className="settings-editor-title"><div><p className="eyebrow">AGENT / {selectedId}</p><h3>{definition.name}</h3><p>{definition.description}</p></div>{dirty.has(selectedId) ? <Badge tone="orange">有未保存修改</Badge> : <Badge>已读取本地配置</Badge>}</div>
            <fieldset className="settings-agent-fieldset" disabled={configBusy !== null}>
              <label className="settings-switch"><input type="checkbox" checked={draft.enabled} onChange={event => updateDraft("enabled", event.target.checked)} disabled={!definition.connected} /><span><strong>允许该 Agent 接收新任务</strong><small>{definition.connected ? "停用只阻止新任务，不删除历史配置和产物。" : "该 Agent 的连接器尚未接入并通过验收，后端不允许启用；其余配置仍可保存。"}</small></span></label>
              <div className="form-grid">
                <Field label="执行引擎"><select value={draft.engine} onChange={event => updateDraft("engine", event.target.value)}>{definition.engines.map(engine => <option value={engine} key={engine}>{engine}</option>)}</select></Field>
                <Field label="模型 / 变体" hint={definition.variants ? "仅可选择后端已验证的变体。" : "可填写当前引擎支持的变体，最多 100 字符。"}>{definition.variants ? <select value={draft.model} onChange={event => updateDraft("model", event.target.value)}>{definition.variants.map(model => <option value={model} key={model}>{model}</option>)}</select> : <Input value={draft.model} maxLength={100} onChange={event => updateDraft("model", event.target.value)} />}</Field>
              </div>
              <div className="form-grid form-grid-3">
                <Field label="超时（秒）" hint="30～3600"><Input type="number" min={30} max={3600} step={1} value={draft.timeout_seconds} onChange={event => updateDraft("timeout_seconds", event.target.value)} /></Field>
                <Field label="最多尝试次数" hint="1～5，含首次尝试"><Input type="number" min={1} max={5} step={1} value={draft.max_attempts} onChange={event => updateDraft("max_attempts", event.target.value)} /></Field>
                <Field label="并发上限" hint="1～2"><Input type="number" min={1} max={2} step={1} value={draft.concurrency} onChange={event => updateDraft("concurrency", event.target.value)} /></Field>
              </div>
              {definition.prompt ? <Field label="补充提示词" hint={`只追加到该 Agent，不覆盖原有安全约束，不影响其他 Agent。${draft.prompt.length} / 12000 字符`}><Textarea rows={5} maxLength={12000} value={draft.prompt} onChange={event => updateDraft("prompt", event.target.value)} /></Field> : <p className="settings-no-prompt">该 Agent 是确定性工具或调度器，没有可编辑提示词。</p>}
              {configError && <ErrorBox>{configError}</ErrorBox>}
              <div className="settings-editor-actions"><Button variant="primary" onClick={() => { void saveAgent(); }}><Save size={14} />{configBusy === `save:${selectedId}` ? "正在保存…" : `保存${definition.name}`}</Button><Button onClick={() => { void resetAgent(); }}><RotateCcw size={14} />{configBusy === `reset:${selectedId}` ? "正在恢复…" : "恢复该 Agent 默认"}</Button><span>保存与恢复均只调用当前 Agent 的配置接口。</span></div>
            </fieldset>
          </section>
        </div> : <Empty title="没有可配置的 Agent" description="后端注册表当前没有返回 Agent 定义。" />}
      </Card>

      {core && <section className="settings-connections" aria-label="真实连接测试">
        <div className="section-heading"><div><h2>真实连接与媒体能力</h2><p>测试只使用临时自测文件，不加入内容任务，不公开发布，也不会自动启用 Agent。</p></div></div>
        <div className="settings-connection-grid">
          <ConnectionCard icon={<Bot size={19} />} eyebrow="SCRIPT / KIMI CLI" title="本地 Kimi" description="本地 CLI 调用云端模型，使用当前默认模型与共享会员额度；脚本生成后仍需人工确认。" ready={core.ai.ready} status={core.ai.ready ? "已连接" : core.ai.installed ? "未测试" : "未安装"} lastSuccess={core.ai.last_success} lastError={core.ai.last_error} buttonLabel="测试本地连接" footnote="测试会实际调用一次 Kimi，并验证五个 JSON 字符串；不会固定或伪造模型 ID。" disabledReason={!core.ai.installed ? "未找到 Kimi CLI，安装并确保本地服务可发现后刷新。" : undefined} {...connectionProps("kimi")}>
            <div className="settings-kimi-metrics"><div><span>CLI 安装</span><strong>{core.ai.installed ? "已安装" : "未找到"}</strong></div><div><span>版本</span><strong>{core.ai.version || "未读取"}</strong></div><div><span>OAuth / 连接状态</span><strong>{core.ai.oauth_status || "未读取"}</strong></div><div><span>模型</span><strong>{core.ai.model || "使用 CLI 当前默认模型"}</strong></div></div>
          </ConnectionCard>
          <ConnectionCard icon={<WandSparkles size={19} />} eyebrow="ASSET / JSON" title="素材规划 Agent" description="使用真实 Kimi 分镜 JSON 测试，并验证镜头时长与允许的素材类型。" ready={core.asset_ai.ready} status={core.asset_ai.status || (core.asset_ai.ready ? "已连接" : "未测试")} lastSuccess={core.asset_ai.last_success} lastError={core.asset_ai.last_error} buttonLabel="测试素材规划 Agent" footnote="不下载素材、不生成媒体，也不代表任何素材已获得授权。" {...connectionProps("assets")} />
          <ConnectionCard icon={<Film size={19} />} eyebrow="VIDEO / MP4" title="Remotion 视频构建" description="执行真实 Remotion 渲染并验证输出 MP4，不以项目文件存在作为连接成功。" ready={core.render_ai.ready} status={core.render_ai.status || (core.render_ai.ready ? "已连接" : "未测试")} lastSuccess={core.render_ai.last_success} lastError={core.render_ai.last_error} buttonLabel="测试 Remotion 视频构建" footnote="自测音频和 MP4 仅用于验证，临时文件由后端清理。" {...connectionProps("remotion")} />
          <ConnectionCard icon={<Volume2 size={19} />} eyebrow="AUDIO / MACOS" title="系统语音" description="使用 macOS say 生成语音，再经 FFmpeg 转换和 FFprobe 检查真实 WAV。" ready={core.voices.capabilities.system_ready} status={core.voices.capabilities.system_status} lastSuccess={core.voices.last_success} lastError={core.voices.last_error} buttonLabel="测试系统语音" footnote="测试使用 Tingting 系统音色和临时目录，不会加入任务音频或音色库。" {...connectionProps("voice")} />
          <ConnectionCard icon={<Subtitles size={19} />} eyebrow="CAPTION / LOCAL CPU" title="WhisperX" description="在本地 CPU 上转写真实测试音频，验证自动 SRT 能力。" ready={core.media_ai.whisperx.ready} status={core.media_ai.whisperx.status || (core.media_ai.whisperx.ready ? "已连接" : "未测试")} lastSuccess={core.media_ai.whisperx.last_success} lastError={core.media_ai.whisperx.last_error} buttonLabel="测试 WhisperX" footnote={`默认模型 ${core.media_ai.whisperx.default_model || "small"}；自测固定使用 base，首次运行可能需要下载模型。`} disabledReason={core.media_ai.whisperx.installed === false ? "未找到可执行的 WhisperX 环境，请安装后刷新；也可在后端日志查看具体路径。" : undefined} {...connectionProps("whisperx")} />
          <ConnectionCard icon={<Mic2 size={19} />} eyebrow="VOICE / OPENVOICE V2" title="OpenVoice 本人音色" description="使用官方 OpenVoice V2、checkpoints_v2 和本人授权参考样本进行本地真实克隆。" ready={core.media_ai.openvoice.ready} status={core.media_ai.openvoice.status || (core.media_ai.openvoice.ready ? "已连接" : "未测试")} lastSuccess={core.media_ai.openvoice.last_success} lastError={core.media_ai.openvoice.last_error} buttonLabel="测试 OpenVoice" footnote="自测文件自动清理；保存样本不等于克隆能力已通过测试。" {...connectionProps("openvoice")}>
            {Boolean(core.media_ai.openvoice.missing_files?.length) && <div className="settings-missing"><strong>尚缺模型 / 参考文件</strong><ul>{core.media_ai.openvoice.missing_files?.map(path => <li key={path}>{path}</li>)}</ul><p>仍可运行测试以获取后端返回的具体错误；不会显示连接成功。</p></div>}
          </ConnectionCard>
        </div>
      </section>}

      <Card className="settings-boundary"><div><p className="eyebrow">SAFETY / LOCAL FIRST</p><h2>数据与自动化边界</h2></div><ul><li>任务、设置和审批保存在本机 SQLite，服务只监听 127.0.0.1；页面不会读取凭据文件。</li><li>生成输入仅包含当前任务、候选 / 热点证据和必要账号策略，不发送全库历史文章。</li><li>生成成功不会自动人工批准；连接测试不会自动发布任何内容。</li><li>未接入的质检、发布复盘和数据分析 Agent 不能启用；发布助手仅做预览填充，公开发布始终需要人工确认。</li></ul></Card>
    </>}
  </div>;
}
