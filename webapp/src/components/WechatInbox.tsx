import { useEffect, useState, type FormEvent } from "react";
import { Archive, ArchiveRestore, ExternalLink, FileText, Plus } from "lucide-react";
import { useApp } from "@/AppContext";
import { Badge, Button, Card, Empty, ErrorBox, Field, Input, Modal, Textarea } from "@/components/ui";
import { api, errorText, jsonOptions } from "@/lib/api";
import type { Json } from "@/lib/types";

export interface WechatMessage {
  id: string;
  research_item_id: string;
  message_type: string;
  raw_text: string;
  original_url: string | null;
  title: string;
  note: string;
  category: "unclassified" | "featured" | "competitor" | "high_praise" | "industry";
  category_name: string;
  received_at: string;
  source_name: string;
  archived: boolean;
  snapshot_status: "not_started" | "queued" | "running" | "succeeded" | "failed";
  snapshot: Json;
  snapshot_error: string | null;
}

const categories = [
  { id: "unclassified", label: "待分类" },
  { id: "featured", label: "精选" },
  { id: "competitor", label: "竞品" },
  { id: "high_praise", label: "高赞" },
  { id: "industry", label: "行业" },
] as const;

export default function WechatInbox({ messages, connection, onCreateTask }: { messages: WechatMessage[]; connection?: Json; onCreateTask: (researchItemId: string) => void }) {
  const { refresh, notify } = useApp();
  const [category, setCategory] = useState("unclassified");
  const [editing, setEditing] = useState<WechatMessage | null>(null);
  const [manual, setManual] = useState({ text: "", original_url: "" });
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const visible = messages.filter(item => category === "archived" ? item.archived : !item.archived && item.category === category);
  const hasPendingSnapshots = messages.some(item => ["queued", "running"].includes(item.snapshot_status));
  useEffect(() => {
    if (!hasPendingSnapshots) return;
    const timer = window.setInterval(() => { void refresh(); }, 3000);
    return () => window.clearInterval(timer);
  }, [hasPendingSnapshots, refresh]);

  async function perform(key: string, action: () => Promise<unknown>, success: string) {
    if (busy) return null;
    setBusy(key); setError("");
    try {
      const result = await action();
      await refresh();
      notify(success);
      return result;
    } catch (reason) {
      const message = errorText(reason); setError(message); notify(message, true); return null;
    } finally { setBusy(""); }
  }

  async function submitManual(event: FormEvent) {
    event.preventDefault();
    const saved = await perform("manual", () => api("/api/topics/wechat/messages", jsonOptions("POST", manual)), "已保存到待分类");
    if (saved) { setManual({ text: "", original_url: "" }); setCategory("unclassified"); }
  }

  async function saveEdit(event: FormEvent) {
    event.preventDefault();
    if (!editing) return;
    const saved = await perform(`edit-${editing.id}`, () => api(`/api/topics/wechat/messages/${encodeURIComponent(editing.id)}`, jsonOptions("PUT", {
      title: editing.title, note: editing.note, original_url: editing.original_url || "", category: editing.category,
    })), "修改已保存");
    if (saved) setEditing(null);
  }

  async function refreshSnapshot(item: WechatMessage) {
    await perform(`snapshot-${item.id}`, () => api(`/api/topics/wechat/messages/${encodeURIComponent(item.id)}/snapshot`, jsonOptions("POST")), "链接快照已开始解析");
  }

  async function archive(item: WechatMessage) {
    await perform(`archive-${item.id}`, () => api(`/api/topics/items/${encodeURIComponent(item.research_item_id)}/archive`, jsonOptions("POST", { archived: !item.archived })), item.archived ? "已恢复到当前分类" : "已归档，可随时恢复");
  }

  return <div className="wechat-inbox">
    <div className="wechat-inbox-grid">
      <Card className="wechat-connection-card"><div className="wechat-connection-head"><div><Badge tone={connection?.status === "connected" ? "green" : "orange"}>{connection?.label || "本机入库可用，OpenClaw 待接入"}</Badge><h3>微信随手记，后台再分类</h3></div><a className="button button-small" href="https://docs.openclaw.ai/channels/wechat" target="_blank" rel="noreferrer">接入文档 <ExternalLink size={13} /></a></div><p>{connection?.detail || "当前可用手动录入；微信插件完成真实消息验收后才显示已连接。"}</p><ol className="topic-guide"><li>微信里直接发送链接、视频或一句想法，不需要输入分类标签。</li><li>所有消息先进入待分类，你在后台修改标题、备注和分类。</li><li>原始消息只读；保存成功才回执，不自动下载或发布。</li></ol></Card>
      <Card><form onSubmit={submitManual}><h3>手动记录一条想法</h3><p className="topic-boundary">先验证后台流程；保存后默认进入待分类。</p><Field label="原始链接（可选）"><Input type="url" value={manual.original_url} onChange={event => setManual({ ...manual, original_url: event.target.value })} placeholder="https://" /></Field><Field label="内容或当时的想法"><Textarea required maxLength={12000} value={manual.text} onChange={event => setManual({ ...manual, text: event.target.value })} placeholder="例如：这个开头很好，可以做成一期企业AI案例" /></Field><Button variant="primary" type="submit" disabled={!!busy}><Plus size={14} />{busy === "manual" ? "正在保存…" : "保存到待分类"}</Button></form></Card>
    </div>
    {error && <ErrorBox>{error}</ErrorBox>}
    <nav className="topic-subtabs wechat-category-tabs" aria-label="微信消息分类">{[...categories, { id: "archived", label: "已归档" }].map(item => <button type="button" key={item.id} className={`topic-filter ${category === item.id ? "active" : ""}`} aria-pressed={category === item.id} onClick={() => setCategory(item.id)}>{item.label}{item.id === "archived" ? ` ${messages.filter(message => message.archived).length}` : ` ${messages.filter(message => !message.archived && message.category === item.id).length}`}</button>)}</nav>
    <div className="section-heading"><h2>{category === "archived" ? "已归档" : categories.find(item => item.id === category)?.label}</h2><p>{visible.length} 条 · 原始消息与后台编辑分开保存</p></div>
    {visible.length ? <div className="wechat-message-list topic-grid topic-video-grid-compact">{visible.map(item => <article className="wechat-message-card" key={item.id}>
      <div className="wechat-snapshot-cover">
        {item.snapshot_status === "succeeded" && item.snapshot.cover_url ? <img src={item.snapshot.cover_url} alt="链接封面" loading="lazy" /> : <span className="wechat-snapshot-placeholder">{!item.original_url ? "文本想法" : item.snapshot_status === "failed" ? "解析失败" : item.snapshot_status === "succeeded" ? "公开页无封面" : "等待快照"}</span>}
        <div className="wechat-snapshot-cover-meta"><Badge tone="orange">{item.snapshot.platform_label || item.snapshot.site_name || item.category_name}</Badge><span>{item.message_type}</span></div>
        <span className="wechat-snapshot-mark">{item.snapshot_status === "succeeded" ? "已解析" : item.snapshot_status === "failed" ? "解析失败" : ["queued", "running"].includes(item.snapshot_status) ? "解析中" : "仅链接"}</span>
      </div>
      <div className="wechat-message-main">
        <button type="button" className="wechat-message-title" onClick={() => setEditing(item)}>{item.title}</button>
        {item.snapshot.title && <h4 className="wechat-snapshot-title">{item.snapshot.title}</h4>}
        <div className="wechat-snapshot-source"><span>{String(item.snapshot.author || item.snapshot.site_name || item.source_name).slice(0, 1)}</span><div><strong>{item.snapshot.author || item.snapshot.site_name || item.source_name}</strong><small>{item.snapshot.author_followers ? `粉丝 ${item.snapshot.author_followers}` : item.snapshot.captured_at || item.received_at}{item.snapshot.published_at ? ` · 发布 ${item.snapshot.published_at}` : ""}{item.snapshot.limited ? " · 公开页信息有限" : ""}</small></div></div>
        {(item.snapshot.description || item.snapshot.excerpt) && <p className="wechat-snapshot-description">{item.snapshot.description || item.snapshot.excerpt}</p>}
        <p className="wechat-message-note"><strong>我的想法：</strong>{item.note || "还没有备注"}</p>
        {item.snapshot_status === "failed" && <p className="wechat-snapshot-error">{item.snapshot_error || "公开页面未能读取"}</p>}
        {item.snapshot.dynamic_error && <p className="wechat-snapshot-error">{item.snapshot.dynamic_error}</p>}
        <div className="wechat-message-meta"><Badge>{item.category_name}</Badge><span>{item.source_name}</span></div>
        <div className="wechat-message-actions">{item.original_url && <a className="button button-small" href={item.original_url} target="_blank" rel="noreferrer"><ExternalLink size={13} />原链接</a>}<Button size="small" onClick={() => setEditing(item)}><FileText size={13} />整理</Button>{!item.archived && <Button size="small" variant="primary" onClick={() => onCreateTask(item.research_item_id)}>转为内容任务</Button>}{item.snapshot_status === "failed" || item.snapshot_status === "not_started" ? <Button size="small" disabled={!!busy} onClick={() => void refreshSnapshot(item)}>{item.snapshot_status === "failed" ? "重新解析" : "生成快照"}</Button> : null}<Button size="small" variant="ghost" onClick={() => void archive(item)}>{item.archived ? <><ArchiveRestore size={13} />恢复</> : <><Archive size={13} />归档</>}</Button></div>
      </div>
    </article>)}</div> : <Empty title={category === "archived" ? "没有已归档消息" : "这个分类还没有消息"} description={category === "unclassified" ? "使用上方表单保存一条想法，或等待微信私聊接入后自动入库。" : "切换到其他分类查看，或在待分类中整理消息。"} />}

    <Modal open={!!editing} onOpenChange={open => { if (!open) setEditing(null); }} title="整理这条灵感" description="微信原文只读；标题、备注和分类仅修改后台记录。" wide>{editing && <form onSubmit={saveEdit}><div className="wechat-raw-message"><strong>原始消息 · 只读</strong><pre>{editing.raw_text || "非文本消息，原始元数据已保留"}</pre></div><Field label="后台标题"><Input required maxLength={200} value={editing.title} onChange={event => setEditing({ ...editing, title: event.target.value })} /></Field><Field label="原始链接（可选）"><Input type="url" value={editing.original_url || ""} onChange={event => setEditing({ ...editing, original_url: event.target.value })} placeholder="没有链接时可留空" /></Field><Field label="当时的想法 / 备注"><Textarea rows={5} maxLength={12000} value={editing.note} onChange={event => setEditing({ ...editing, note: event.target.value })} /></Field><Field label="分类"><select value={editing.category} onChange={event => setEditing({ ...editing, category: event.target.value as WechatMessage["category"] })}>{categories.map(item => <option value={item.id} key={item.id}>{item.label}</option>)}</select></Field><div className="button-row"><Button variant="primary" type="submit" disabled={!!busy}>{busy.startsWith("edit-") ? "正在保存…" : "保存修改"}</Button><Button type="button" onClick={() => setEditing(null)}>取消</Button></div></form>}</Modal>
  </div>;
}
