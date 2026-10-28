import { useState, type FormEvent } from "react";
import { Check, ExternalLink, Pencil, Plus, Trash2 } from "lucide-react";
import { useApp } from "@/AppContext";
import { Badge, Button, Card, Empty, ErrorBox, Field, Input, Modal, Textarea } from "@/components/ui";
import { api, errorText, jsonOptions } from "@/lib/api";
import { platformLabels, platformOrder, type PlatformKey } from "@/lib/analyticsDemo";

export interface LeadRecord {
  id: string;
  platform: PlatformKey;
  author_alias: string;
  profile_text: string;
  message_text: string;
  need_text: string;
  source_content_id: string | null;
  source_url: string | null;
  occurred_at: string;
  stage: "inquiry" | "qualified" | "high_intent" | "meeting" | "deal" | "not_qualified";
  notes: string;
  revenue: number | null;
  deal_at: string | null;
  created_at: string;
  updated_at: string;
}

interface LeadMetrics {
  inquiries: number | null;
  qualifiedLeads: number | null;
  highIntentLeads: number | null;
  meetings?: number | null;
  deals: number | null;
  revenue?: number | null;
}

const stageNames: Record<LeadRecord["stage"], string> = { inquiry: "待判断", qualified: "有效线索", high_intent: "高意向", meeting: "深度沟通", deal: "已成交", not_qualified: "暂无效" };
const validStages = new Set(["qualified", "high_intent", "meeting", "deal"]);

function localInputTime(value?: string) {
  const date = value ? new Date(value) : new Date();
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function blankForm(platform?: PlatformKey) {
  return { platform: platform || "douyin", author_alias: "", profile_text: "", message_text: "", need_text: "", source_content_id: "", source_url: "", occurred_at: localInputTime(), stage: "inquiry" as LeadRecord["stage"], notes: "", revenue: "", deal_at: "" };
}

export function LeadPanel({ leads, metrics, contents, platform }: { leads: LeadRecord[]; metrics: LeadMetrics; contents: { id: string; title: string; platform: PlatformKey }[]; platform?: PlatformKey }) {
  const { refresh, notify } = useApp();
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<LeadRecord | null>(null);
  const [detail, setDetail] = useState<LeadRecord | null>(null);
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [form, setForm] = useState(blankForm(platform));
  const visibleLeads = platform ? leads.filter(lead => lead.platform === platform) : leads;
  const selectedVisible = visibleLeads.filter(lead => selected.has(lead.id));
  const stages = [
    { label: "私信咨询", value: metrics.inquiries ?? 0, note: "本地人工记录" },
    { label: "有效线索", value: metrics.qualifiedLeads ?? 0, note: "目标用户 + 明确需求" },
    { label: "高意向", value: metrics.highIntentLeads ?? 0, note: "项目或合作意向" },
    { label: "深度沟通", value: metrics.meetings ?? 0, note: "会议、诊断或方案" },
    { label: "成交", value: metrics.deals ?? 0, note: "按实际成交时间" },
  ];

  function update(key: string, value: string) { setForm(current => ({ ...current, [key]: value })); }
  function openCreate() { setEditing(null); setForm(blankForm(platform)); setOpen(true); setError(""); }
  function openEdit(lead: LeadRecord) {
    setEditing(lead);
    setForm({ platform: lead.platform, author_alias: lead.author_alias, profile_text: lead.profile_text, message_text: lead.message_text,
      need_text: lead.need_text, source_content_id: lead.source_content_id || "", source_url: lead.source_url || "",
      occurred_at: localInputTime(lead.occurred_at), stage: lead.stage, notes: lead.notes, revenue: lead.revenue?.toString() || "",
      deal_at: lead.deal_at ? localInputTime(lead.deal_at) : "" });
    setOpen(true); setError("");
  }
  function toggle(id: string) {
    setSelected(current => { const next = new Set(current); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  }
  function toggleAll() {
    setSelected(current => {
      const next = new Set(current);
      if (selectedVisible.length === visibleLeads.length) visibleLeads.forEach(lead => next.delete(lead.id));
      else visibleLeads.forEach(lead => next.add(lead.id));
      return next;
    });
  }

  async function quickStage(lead: LeadRecord, stage: LeadRecord["stage"]) {
    if (busy) return;
    setBusy(lead.id); setError("");
    try {
      await api(`/api/accounts/leads/${lead.id}`, jsonOptions("POST", { stage, expected_updated_at: lead.updated_at }));
      await refresh(); notify(stage === "qualified" ? "已人工标为有效线索" : "已取消有效标记，回到待判断");
    } catch (reason) { const message = errorText(reason); setError(message); notify(message, true); }
    finally { setBusy(""); }
  }

  async function remove(ids: string[]) {
    if (!ids.length || busy) return;
    if (!window.confirm(`确定删除选中的 ${ids.length} 条本地私信记录吗？此操作只影响本机，且无法撤销。`)) return;
    setBusy("delete"); setError("");
    try {
      await api("/api/accounts/leads/delete", jsonOptions("POST", { ids }));
      setSelected(current => { const next = new Set(current); ids.forEach(id => next.delete(id)); return next; });
      setDetail(null); await refresh(); notify(`已删除 ${ids.length} 条本地私信记录`);
    } catch (reason) { const message = errorText(reason); setError(message); notify(message, true); }
    finally { setBusy(""); }
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy("save"); setError("");
    const payload = { ...form, occurred_at: new Date(form.occurred_at).toISOString(), revenue: form.revenue || null,
      deal_at: form.deal_at ? new Date(form.deal_at).toISOString() : null,
      ...(editing ? { expected_updated_at: editing.updated_at } : {}) };
    try {
      await api(editing ? `/api/accounts/leads/${editing.id}` : "/api/accounts/leads", jsonOptions("POST", payload));
      await refresh(); setOpen(false); notify(editing ? "私信详情和人工阶段已保存" : "私信线索已保存到本机");
    } catch (reason) { const message = errorText(reason); setError(message); notify(message, true); }
    finally { setBusy(""); }
  }

  return <div className="lead-panel">
    {error && <ErrorBox>{error}</ErrorBox>}
    <div className="lead-funnel">{stages.map((stage, index) => <Card key={stage.label} className={index === 0 ? "lead-funnel-primary" : ""}><span>{stage.label}</span><strong>{stage.value}</strong><small>{stage.note}</small></Card>)}</div>
    <div className="lead-list-head"><div><h3>私信线索表</h3><p>{visibleLeads.length} 条当前维度记录 · 详情二次点击打开 · 状态由你人工标注</p></div><div className="button-row">{selectedVisible.length > 0 && <Button size="small" variant="danger" disabled={busy === "delete"} onClick={() => void remove(selectedVisible.map(lead => lead.id))}><Trash2 size={14} />删除所选（{selectedVisible.length}）</Button>}<Button size="small" variant="primary" onClick={openCreate}><Plus size={14} />记录私信</Button></div></div>
    {visibleLeads.length ? <Card className="lead-table-card"><div className="lead-table-scroll"><table className="lead-table"><thead><tr><th><input type="checkbox" aria-label="选择全部私信" checked={visibleLeads.length > 0 && selectedVisible.length === visibleLeads.length} onChange={toggleAll} /></th><th>用户</th><th>平台</th><th>发生时间</th><th>明确需求</th><th>阶段</th><th>操作</th></tr></thead><tbody>{visibleLeads.map(lead => <tr key={lead.id} className={selected.has(lead.id) ? "selected" : ""}><td><input type="checkbox" aria-label={`选择 ${lead.author_alias}`} checked={selected.has(lead.id)} onChange={() => toggle(lead.id)} /></td><td><strong>{lead.author_alias}</strong><small>{lead.profile_text || "画像未填写"}</small></td><td>{platformLabels[lead.platform]}</td><td>{lead.occurred_at.replace("T", " ").slice(0, 16)}</td><td className="lead-need-cell">{lead.need_text || "未填写"}</td><td><Badge tone={validStages.has(lead.stage) ? "green" : lead.stage === "not_qualified" ? "red" : "orange"}>{stageNames[lead.stage]}</Badge></td><td><div className="lead-row-actions"><Button size="small" onClick={() => setDetail(lead)}>详情</Button>{validStages.has(lead.stage) ? <Button size="small" disabled={Boolean(busy)} onClick={() => void quickStage(lead, "inquiry")}>取消有效</Button> : <Button size="small" disabled={Boolean(busy)} onClick={() => void quickStage(lead, "qualified")}><Check size={12} />标为有效</Button>}<Button size="small" disabled={Boolean(busy)} onClick={() => openEdit(lead)}><Pencil size={12} />编辑</Button><Button size="small" variant="danger" disabled={Boolean(busy)} aria-label={`删除 ${lead.author_alias}`} onClick={() => void remove([lead.id])}><Trash2 size={12} /></Button></div></td></tr>)}</tbody></table></div></Card> : <Empty title="当前维度没有私信线索记录" description="可切换平台或时间周期，也可以点击“记录私信”新增本地记录。不会从外部平台自动读取或发送私信。" />}
    <div className="lead-revenue">人工确认成交金额：<strong>{metrics.revenue == null ? "未填写" : `¥${new Intl.NumberFormat("zh-CN").format(metrics.revenue)}`}</strong><span>AI 不自动修改线索阶段</span></div>

    <Modal open={Boolean(detail)} onOpenChange={open => { if (!open) setDetail(null); }} title={detail?.author_alias || "私信详情"} description={detail ? `${platformLabels[detail.platform]} · ${stageNames[detail.stage]} · 本地记录` : undefined}><div className="lead-detail">{detail && <><dl><dt>用户画像</dt><dd>{detail.profile_text || "未填写"}</dd><dt>明确需求</dt><dd>{detail.need_text || "未填写"}</dd><dt>私信原文</dt><dd className="lead-detail-message">{detail.message_text}</dd>{detail.notes && <><dt>跟进备注</dt><dd>{detail.notes}</dd></>}{detail.deal_at && <><dt>实际成交时间</dt><dd>{detail.deal_at.replace("T", " ").slice(0, 16)}</dd></>}{detail.revenue !== null && <><dt>成交金额</dt><dd>¥{new Intl.NumberFormat("zh-CN").format(detail.revenue)}</dd></>}</dl>{detail.source_url && <a className="button button-small" href={detail.source_url} target="_blank" rel="noreferrer">打开来源内容 <ExternalLink size={13} /></a>}<div className="button-row lead-detail-actions"><Button size="small" onClick={() => { const current = detail; setDetail(null); openEdit(current); }}><Pencil size={13} />编辑这条记录</Button></div></>}</div></Modal>

    <Modal open={open} onOpenChange={setOpen} title={editing ? "编辑私信线索" : "记录私信线索"} description="只保存到本机，不回写外部平台。请勿填写密码、证件号等不必要的敏感信息。" wide><form className="lead-form" onSubmit={save}><div className="lead-form-grid"><Field label="来源平台"><select value={form.platform} onChange={event => update("platform", event.target.value)}>{platformOrder.map(key => <option value={key} key={key}>{platformLabels[key]}</option>)}</select></Field><Field label="用户别名（必填）"><Input required maxLength={80} value={form.author_alias} onChange={event => update("author_alias", event.target.value)} placeholder="例如：制造业老板，不必写真名" /></Field><Field label="私信发生时间"><Input type="datetime-local" required value={form.occurred_at} onChange={event => update("occurred_at", event.target.value)} /></Field><Field label="人工阶段"><select value={form.stage} onChange={event => update("stage", event.target.value)}>{Object.entries(stageNames).map(([key, name]) => <option value={key} key={key}>{name}</option>)}</select></Field></div><Field label="用户画像（可选）"><Input value={form.profile_text} onChange={event => update("profile_text", event.target.value)} placeholder="行业、团队规模、岗位等用户主动提供的信息" /></Field><Field label="私信详情（必填）"><Textarea required maxLength={12000} value={form.message_text} onChange={event => update("message_text", event.target.value)} placeholder="粘贴需要本地保存的私信原文或摘要" /></Field><Field label="明确需求（可选）"><Textarea value={form.need_text} onChange={event => update("need_text", event.target.value)} placeholder="用户的真实业务场景、问题和计划" /></Field><div className="lead-form-grid"><Field label="关联内容（可选）"><select value={form.source_content_id} onChange={event => { const item = contents.find(content => content.id === event.target.value); setForm(current => ({ ...current, source_content_id: event.target.value, source_url: item && "url" in item ? String(item.url || "") : current.source_url })); }}><option value="">不关联内容</option>{contents.filter(item => !platform || item.platform === platform).map(item => <option value={item.id} key={item.id}>{item.title}</option>)}</select></Field><Field label="成交金额（可选，元）"><Input type="number" min="0" step="0.01" value={form.revenue} onChange={event => update("revenue", event.target.value)} placeholder="仅成交后人工填写" /></Field></div>{form.stage === "deal" && <Field label="实际成交时间（可选）" hint="成交数量和金额按此时间归入周期；留空则不计入任何周期成交"><Input type="datetime-local" value={form.deal_at} onChange={event => update("deal_at", event.target.value)} /></Field>}<Field label="跟进备注（可选）"><Textarea value={form.notes} onChange={event => update("notes", event.target.value)} placeholder="下一步跟进、会议或方案记录" /></Field><div className="button-row lead-form-actions"><Button type="button" onClick={() => setOpen(false)}>取消</Button><Button variant="primary" type="submit" disabled={busy === "save"}>{busy === "save" ? "正在保存…" : editing ? "保存修改" : "保存到本机"}</Button></div></form></Modal>
  </div>;
}
