import { useState, type FormEvent } from "react";
import { ExternalLink, RefreshCw, Search, X } from "lucide-react";
import { Link } from "react-router-dom";
import { useApp } from "@/AppContext";
import { Badge, Button, Card, Empty, ErrorBox, Input, PageHeader } from "@/components/ui";
import { api, errorText, jsonOptions } from "@/lib/api";
import type { Json } from "@/lib/types";
import "./Knowledge.css";

function evidenceUrl(relation: Json, entities: Json[]) {
  const direct = relation.evidence?.url;
  if (typeof direct === "string" && /^https?:\/\//.test(direct)) return direct;
  if (relation.target_type === "Evidence") {
    const target = entities.find(item => item.id === relation.target_id && item.type === "Evidence");
    if (typeof target?.summary === "string" && /^https?:\/\//.test(target.summary)) return target.summary;
  }
  return "";
}

export default function Knowledge() {
  const { resources, refresh, notify, loadError } = useApp();
  const [query, setQuery] = useState("");
  const [type, setType] = useState("");
  const [applied, setApplied] = useState({ query: "", type: "" });
  const [filteredData, setFilteredData] = useState<Json | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [busy, setBusy] = useState("");
  const [actionError, setActionError] = useState("");
  const data: Json = filteredData || resources?.knowledge || {};
  const entities: Json[] = data.entities || [];
  const relations: Json[] = data.relations || [];
  const rules: Json[] = data.rules || [];
  const allTypes = [...new Set<string>([...(resources?.knowledge.types || []), ...(data.types || [])])].sort();
  const selected = entities.find(item => item.id === selectedId) || null;
  const selectedRelations = selected ? relations.filter(relation => relation.source_id === selected.id || relation.target_id === selected.id) : [];
  const entityName = (entityType: string, id: string) => entities.find(item => item.type === entityType && item.id === id)?.name || resources?.knowledge.entities?.find((item: Json) => item.type === entityType && item.id === id)?.name || id;

  async function search(nextQuery = query, nextType = type) {
    if (busy) return;
    setBusy("search"); setActionError("");
    try {
      const result = await api(`/api/knowledge/bootstrap?q=${encodeURIComponent(nextQuery)}&type=${encodeURIComponent(nextType)}`);
      setFilteredData(result); setApplied({ query: nextQuery, type: nextType }); setSelectedId(null);
      notify("知识库筛选已更新");
    } catch (error) { const message = errorText(error); setActionError(message); notify(message, true); }
    finally { setBusy(""); }
  }
  function submitSearch(event: FormEvent) { event.preventDefault(); void search(); }
  async function backfill() {
    if (busy) return;
    setBusy("backfill"); setActionError("");
    try {
      const result = await api<Json>("/api/knowledge/backfill", jsonOptions("POST"));
      await refresh();
      const filtered = await api(`/api/knowledge/bootstrap?q=${encodeURIComponent(applied.query)}&type=${encodeURIComponent(applied.type)}`);
      setFilteredData(filtered); setSelectedId(null);
      notify(`知识库已同步：研究 ${result.research || 0} 条、候选 ${result.candidates || 0} 条、任务 ${result.tasks || 0} 条；稳定实体与关系不会重复创建`);
    } catch (error) { const message = errorText(error); setActionError(message); notify(message, true); }
    finally { setBusy(""); }
  }
  function clearFilters() {
    setQuery(""); setType(""); void search("", "");
  }

  return <>
    <PageHeader eyebrow="ACCOUNT ONTOLOGY" title="把碎片信息连成知识网络" description="定位、受众、痛点、证据与内容任务保存在本地 SQLite；每条自动关系保留来源，研究证据可以回跳原链接。" actions={<Button variant="primary" disabled={!!busy} onClick={() => void backfill()}><RefreshCw size={14} />{busy === "backfill" ? "正在回填…" : "同步现有数据到知识库"}</Button>} />
    <nav className="knowledge-tabs" aria-label="知识库视图"><Link className="active" to="/knowledge">账号 Ontology</Link><Link to="/knowledge/collection">采集知识库</Link></nav>
    {loadError && <ErrorBox>{loadError}<br /><Button size="small" onClick={() => void refresh()}>重新读取</Button></ErrorBox>}
    {actionError && <ErrorBox>{actionError}<br /><Button size="small" onClick={() => setActionError("")}>关闭错误详情</Button></ErrorBox>}
    <form className="knowledge-toolbar" onSubmit={submitSearch}><Input aria-label="搜索实体或摘要" value={query} onChange={event => setQuery(event.target.value)} placeholder="搜索实体名称或摘要" /><select aria-label="实体类型" value={type} onChange={event => setType(event.target.value)}><option value="">全部类型</option>{allTypes.map(value => <option key={value} value={value}>{value}</option>)}</select><Button type="submit" disabled={!!busy}><Search size={14} />{busy === "search" ? "搜索中…" : "搜索"}</Button><div className="knowledge-count"><Badge>{entities.length} 实体 · {relations.length} 关系</Badge></div></form>
    {(applied.query || applied.type) && <p className="knowledge-filter-note">当前筛选：{applied.query ? `“${applied.query}”` : "全部关键词"} · {applied.type || "全部类型"} <button className="button button-small" onClick={clearFilters} disabled={!!busy}>清空筛选</button></p>}

    <div className="knowledge-layout"><div className="knowledge-main"><section>{entities.length ? <div className="knowledge-entity-grid">{entities.map(entity => <button key={entity.id} className={`knowledge-entity-card ${selected?.id === entity.id ? "active" : ""}`} onClick={() => setSelectedId(entity.id)}><span>{entity.type}</span><strong>{entity.name}</strong><small>{entity.summary || "暂无摘要"}</small></button>)}</div> : <Empty title="没有匹配实体" description="可清空搜索，或点击“同步现有数据到知识库”。回填使用稳定 ID，不会重复创建相同实体。" action={(applied.query || applied.type) ? <Button onClick={clearFilters}>清空筛选</Button> : undefined} />}</section>
      <Card><h2>编辑与审批规则</h2><p className="knowledge-filter-note">由账号策略初始化，供文章、选题和审核共同复用。</p>{rules.length ? <ul className="knowledge-rules">{rules.map(rule => <li key={rule.id}>{rule.name}</li>)}</ul> : <Empty title="还没有编辑规则" description="同步现有数据后会从真实账号策略初始化。" />}</Card>
    </div><aside>{selected ? <Card className="knowledge-detail"><div className="knowledge-detail-head"><div><Badge tone="green">{selected.type}</Badge><h2>{selected.name}</h2></div><Button size="small" variant="ghost" aria-label="关闭实体详情" onClick={() => setSelectedId(null)}><X size={15} /></Button></div><p className="knowledge-detail-summary">{selected.summary || "暂无摘要"}</p><pre className="knowledge-properties">{JSON.stringify(selected.properties || {}, null, 2)}</pre><h3 className="knowledge-relations-title">关系与证据 · {selectedRelations.length}</h3>{selectedRelations.length ? selectedRelations.map(relation => {
      const url = evidenceUrl(relation, entities) || evidenceUrl(relation, resources?.knowledge.entities || []);
      return <article className="knowledge-relation" key={relation.id}><div className="knowledge-relation-flow"><strong>{entityName(relation.source_type, relation.source_id)}</strong><b>→ {relation.predicate} →</b><strong>{entityName(relation.target_type, relation.target_id)}</strong></div><pre>{JSON.stringify(relation.evidence || {}, null, 2)}</pre>{url && <a className="knowledge-evidence-link" href={url} target="_blank" rel="noreferrer">打开来源证据 <ExternalLink size={12} /></a>}</article>;
    }) : <p className="knowledge-detail-summary">该实体尚无关系。回填只会创建有真实来源支撑的关系。</p>}</Card> : <Card className="knowledge-help"><h2>查看实体详情</h2><p>选择左侧实体，查看它与受众、痛点、平台、证据及内容任务的关系。</p><p>自动回填使用稳定 ID，同一数据重复同步不会重复创建实体或相同证据关系。</p></Card>}</aside></div>
  </>;
}
