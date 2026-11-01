import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { Database, Play, RefreshCw, Search, Server, SquareTerminal } from "lucide-react";
import { Badge, Busy, Button, Card, Empty, ErrorBox, Field, Input, PageHeader } from "@/components/ui";
import { api, errorText, jsonOptions } from "@/lib/api";
import "./SocialData.css";

type Capability = {
  id: string;
  platform: string;
  platform_label: string;
  path: string;
  kind: string;
  status: "supported" | "adapter_required";
  executor: "douyin_hot" | "browser_model" | "local_download" | "local_transcript" | null;
};
type Provider = { id: string; label: string; available: boolean; reason?: string | null };
type SocialRun = {
  id: string;
  operation_id: string;
  status: string;
  provider: string;
  input: Record<string, any>;
  result: Record<string, any>;
  error?: Record<string, any> | null;
  created_at: string;
  updated_at: string;
};
type Bootstrap = {
  platforms: { id: string; label: string }[];
  items: Capability[];
  coverage: { total: number; supported: number; adapter_required: number };
  providers: { default: string; items: Provider[] };
  runs: SocialRun[];
};

const kindNames: Record<string, string> = {
  search: "搜索", detail: "详情", comments: "评论", profile: "作者资料", user_content: "作者内容",
  hot_list: "热榜", download_links: "下载解析", transcript: "口播转写", commerce: "商品",
  creator_analytics: "创作者分析", suggestions: "搜索建议", share: "分享", engagement: "互动", utility: "工具",
};
const activeStatuses = ["queued", "running", "leased", "retry_wait"];

function RunDetail({ run }: { run: SocialRun }) {
  const result = run.result || {};
  const items = Array.isArray(result.items) ? result.items : [];
  const transcript = result.transcript;
  const tracks = result.download_manifest?.tracks || [];
  return <Card className="social-run-detail">
    <div className="social-section-title"><div><p className="eyebrow">RUN RESULT</p><h2>运行结果</h2></div><Badge tone={run.status === "succeeded" ? "green" : run.status === "failed" ? "red" : "orange"}>{run.status}</Badge></div>
    <p className="social-run-id">{run.operation_id} · {run.id}</p>
    {run.error && Object.keys(run.error).length > 0 && <ErrorBox>{run.error.message || run.error.code}{run.error.action ? `\n怎么改：${run.error.action}` : ""}</ErrorBox>}
    {activeStatuses.includes(run.status) && <Busy label="本地任务正在执行，页面会自动刷新…" />}
    {transcript && <div className="social-transcript"><strong>口播全文</strong><p>{transcript.text}</p><small>{transcript.segments?.length || 0} 个时间片段 · {result.provider} / {result.model}</small></div>}
    {tracks.length > 0 && <div className="social-transcript"><strong>真实下载轨道</strong><p>{tracks.length} 条音视频轨道已解析，下载地址保留在本地运行记录中。</p></div>}
    {result.profile && Object.keys(result.profile).length > 0 && <pre className="social-json">{JSON.stringify(result.profile, null, 2)}</pre>}
    {items.length > 0 ? <div className="social-result-items">{items.slice(0, 30).map((item: Record<string, any>, index: number) => <article key={`${item.canonical_url || item.title}-${index}`}>
      <h3>{item.title || item.text || "未命名条目"}</h3>
      {item.title && item.text && <p>{item.text}</p>}
      <small>{[item.author, item.published_at].filter(Boolean).join(" · ")}</small>
      {item.canonical_url && <a href={item.canonical_url} target="_blank" rel="noreferrer">打开原始页面</a>}
    </article>)}</div> : run.status === "succeeded" && !transcript && !tracks.length && <Empty title="本次没有可展示条目" description="接口已真实执行；空结果不会被补造成成功数据。" />}
  </Card>;
}

export default function SocialData() {
  const [data, setData] = useState<Bootstrap | null>(null);
  const [error, setError] = useState("");
  const [platform, setPlatform] = useState("all");
  const [status, setStatus] = useState("supported");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState("douyin:video/search");
  const [selectedRunId, setSelectedRunId] = useState("");
  const [keyword, setKeyword] = useState("企业AI");
  const [url, setUrl] = useState("");
  const [mediaPath, setMediaPath] = useState("");
  const [model, setModel] = useState("base");
  const [provider, setProvider] = useState("kimi_cli");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const result = await api<Bootstrap>("/api/social/bootstrap");
      setData(result); setError("");
      setSelectedRunId(current => current || result.runs[0]?.id || "");
    } catch (reason) { setError(errorText(reason)); }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);
  const hasActive = !!data?.runs.some(run => activeStatuses.includes(run.status));
  useEffect(() => {
    if (!hasActive) return;
    const timer = window.setInterval(() => void load(), 3000);
    return () => window.clearInterval(timer);
  }, [hasActive, load]);

  const filtered = useMemo(() => (data?.items || []).filter(item =>
    (platform === "all" || item.platform === platform) &&
    (status === "all" || item.status === status) &&
    (!query.trim() || `${item.id} ${item.kind} ${item.platform_label}`.toLowerCase().includes(query.trim().toLowerCase()))
  ), [data, platform, status, query]);
  const selected = data?.items.find(item => item.id === selectedId) || null;
  const selectedRun = data?.runs.find(run => run.id === selectedRunId) || null;

  async function execute(event: FormEvent) {
    event.preventDefault();
    if (!selected || selected.status !== "supported" || busy) return;
    setBusy(true); setError("");
    const input = selected.kind === "search" ? { keyword } : selected.executor === "local_transcript" ? { media_path: mediaPath, model } : selected.executor === "douyin_hot" ? {} : { url };
    try {
      const result = await api<{ run: SocialRun }>("/api/social/execute", jsonOptions("POST", { operation_id: selected.id, input, provider }));
      setSelectedRunId(result.run.id);
      await load();
    } catch (reason) { setError(errorText(reason)); }
    finally { setBusy(false); }
  }

  return <div className="social-page">
    <PageHeader eyebrow="LOCAL SOCIAL DATA" title="社媒能力" description="统一使用本地浏览器、SQLite、yt-dlp、faster-whisper 和模型 Provider；不接外部社媒数据 API，也没有积分扣费。" actions={<Button onClick={() => void load()}><RefreshCw size={14} />刷新</Button>} />
    {error && <ErrorBox>{error}<br /><Button size="small" onClick={() => void load()}>重新读取</Button></ErrorBox>}
    {!data ? <Busy /> : <>
      <div className="social-coverage">
        <Card><strong>{data.coverage.total}</strong><span>能力目录</span></Card>
        <Card><strong>{data.coverage.supported}</strong><span>本地可执行</span></Card>
        <Card><strong>{data.coverage.adapter_required}</strong><span>待平台适配</span></Card>
        <Card className="social-providers"><Server size={18} /><div>{data.providers.items.map(item => <p key={item.id}><Badge tone={item.available ? "green" : "orange"}>{item.label}</Badge><small>{item.available ? "已连接" : item.reason}</small></p>)}</div></Card>
      </div>

      <div className="social-workspace">
        <Card className="social-catalog">
          <div className="social-section-title"><div><p className="eyebrow">CAPABILITY CATALOG</p><h2>能力目录</h2></div><Badge>{filtered.length} 项</Badge></div>
          <div className="social-filters">
            <label className="social-search"><Search size={14} /><Input value={query} onChange={event => setQuery(event.target.value)} placeholder="搜索平台或接口" /></label>
            <select aria-label="平台筛选" value={platform} onChange={event => setPlatform(event.target.value)}><option value="all">全部平台</option>{data.platforms.map(item => <option value={item.id} key={item.id}>{item.label}</option>)}</select>
            <select aria-label="状态筛选" value={status} onChange={event => setStatus(event.target.value)}><option value="supported">本地可执行</option><option value="adapter_required">待适配</option><option value="all">全部状态</option></select>
          </div>
          <div className="social-capability-list">{filtered.map(item => <button type="button" key={item.id} className={selectedId === item.id ? "active" : ""} onClick={() => setSelectedId(item.id)}>
            <span><Badge tone={item.status === "supported" ? "green" : "orange"}>{item.status === "supported" ? "可执行" : "待适配"}</Badge><Badge>{item.platform_label}</Badge><Badge>{kindNames[item.kind] || item.kind}</Badge></span>
            <code>{item.id}</code>
          </button>)}</div>
        </Card>

        <div className="social-side">
          <Card className="social-execute">
            <div className="social-section-title"><div><p className="eyebrow">LOCAL EXECUTION</p><h2>执行能力</h2></div><SquareTerminal size={20} /></div>
            {selected ? <form onSubmit={execute}>
              <code className="social-selected-id">{selected.id}</code>
              <p className="social-selected-meta">{selected.platform_label} · {kindNames[selected.kind] || selected.kind} · {selected.status === "supported" ? "本地执行" : "平台专用适配器尚未完成"}</p>
              {selected.status === "adapter_required" && <Empty title="这项能力还没有本地适配器" description="目录保留不代表已验收；不会调用 SocialDataX，也不会返回伪造结果。" />}
              {selected.path.endsWith("/get") && <Empty title="转写结果在运行记录中查询" description="提交转写后，在“最近运行”中选择对应记录即可查看全文和时间码。" />}
              {selected.kind === "search" && <Field label="公开内容关键词"><Input required value={keyword} onChange={event => setKeyword(event.target.value)} /></Field>}
              {selected.executor === "local_transcript" && !selected.path.endsWith("/get") && <>
                <Field label="项目目录内音视频路径" hint="例如 data/input.mp4；只使用本地 faster-whisper"><Input required value={mediaPath} onChange={event => setMediaPath(event.target.value)} placeholder="data/input.mp4" /></Field>
                <Field label="转写模型"><select value={model} onChange={event => setModel(event.target.value)}><option value="base">base</option><option value="small">small</option></select></Field>
              </>}
              {selected.status === "supported" && !["search", "hot_list"].includes(selected.kind) && selected.executor !== "local_transcript" && <Field label="公开页面 URL"><Input required type="url" value={url} onChange={event => setUrl(event.target.value)} placeholder="https://…" /></Field>}
              {selected.executor === "browser_model" && <Field label="结构化模型"><select value={provider} onChange={event => setProvider(event.target.value)}>{data.providers.items.map(item => <option key={item.id} value={item.id} disabled={!item.available}>{item.label}{item.available ? "" : "（未启用）"}</option>)}</select></Field>}
              {selected.status === "supported" && !selected.path.endsWith("/get") && <Button type="submit" variant="primary" disabled={busy}><Play size={14} />{busy ? "正在加入本地队列…" : "执行并记录结果"}</Button>}
            </form> : <Empty title="选择一项能力" description="从左侧目录选择后要执行的本地任务。" />}
          </Card>
          {selectedRun && <RunDetail run={selectedRun} />}
        </div>
      </div>

      <Card className="social-runs">
        <div className="social-section-title"><div><p className="eyebrow">LOCAL RUNS</p><h2>最近运行</h2></div><Database size={20} /></div>
        {data.runs.length ? <div className="social-run-list">{data.runs.map(run => <button type="button" key={run.id} className={selectedRunId === run.id ? "active" : ""} onClick={() => setSelectedRunId(run.id)}>
          <span><strong>{run.operation_id}</strong><small>{run.created_at} · {run.provider}</small></span><Badge tone={run.status === "succeeded" ? "green" : run.status === "failed" ? "red" : "orange"}>{run.status}</Badge>
        </button>)}</div> : <Empty title="还没有本地运行记录" description="选择 supported 能力并执行后，结果会保存在本机 SQLite。" />}
      </Card>
    </>}
  </div>;
}
