import { useMemo, useState } from "react";
import { BookOpen, Braces, ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";
import { useApp } from "@/AppContext";
import { Badge, Card, Empty, PageHeader } from "@/components/ui";
import "./Knowledge.css";

interface OntologyEntity {
  id: string;
  platform: string;
  category: string;
  category_name: string;
  title: string;
  url: string;
  status: string;
  verification: string;
  capabilities: { read: boolean; write: boolean };
  fields: Record<string, string>;
  agent_usage: string[];
  errors: string[];
  refresh: string;
  version: string;
}

const platformNames: Record<string, string> = { douyin: "抖音", xiaohongshu: "小红书", wechat_channels: "视频号", wechat_official_account: "公众号" };

export default function CollectionKnowledge() {
  const { resources } = useApp();
  const data = resources?.accounts?.collection_knowledge || { entities: [], categories: [], error_types: [] };
  const entities: OntologyEntity[] = useMemo(() => data.entities || [], [data]);
  const [platform, setPlatform] = useState("");
  const [category, setCategory] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const visible = useMemo(() => entities.filter(item => (!platform || item.platform === platform) && (!category || item.category === category)), [entities, platform, category]);
  const current = visible.find(item => item.id === selected) || visible[0];
  const verifiedCount = entities.filter(item => item.status === "verified").length;

  return <div className="collection-knowledge-page">
    <PageHeader eyebrow="COLLECTION ONTOLOGY" title="采集 Ontology" description="把平台后台结构整理为 Agent 可调用的数据契约：身份权限、内容、分析、互动、热点、发布、任务、素材与导出。" actions={<Link className="button" to="/knowledge"><BookOpen size={15} />账号 Ontology</Link>} />
    <nav className="knowledge-tabs" aria-label="知识库视图"><Link to="/knowledge">账号 Ontology</Link><Link className="active" to="/knowledge/collection">采集知识库</Link></nav>
    <div className="collection-boundary"><Braces size={17} /><p>{data.boundary}</p></div>
    <div className="collection-toolbar"><label>平台<select value={platform} onChange={event => { setPlatform(event.target.value); setSelected(null); }}><option value="">全部平台</option>{Object.entries(platformNames).map(([key, name]) => <option key={key} value={key}>{name}</option>)}</select></label><label>知识类别<select value={category} onChange={event => { setCategory(event.target.value); setSelected(null); }}><option value="">全部类别</option>{data.categories.map((item: any) => <option value={item.id} key={item.id}>{item.name}</option>)}</select></label><Badge tone="blue">{visible.length} 个实体</Badge><Badge tone="green">{verifiedCount} 个已验证</Badge><Badge tone="orange">{entities.length - verifiedCount} 个待验证</Badge></div>
    {current ? <div className="collection-layout"><div className="collection-entity-list">{visible.map(item => <button key={item.id} className={current.id === item.id ? "active" : ""} onClick={() => setSelected(item.id)}><div><strong>{item.title}</strong><small>{platformNames[item.platform]} · {item.category_name}</small></div><Badge tone={item.status === "verified" ? "green" : "orange"}>{item.verification}</Badge></button>)}</div><Card className="collection-detail"><div className="collection-detail-head"><div><Badge tone="blue">{current.category_name}</Badge><h2>{current.title}</h2><p>{platformNames[current.platform]} · 适配版本 {current.version}</p></div><Badge tone={current.status === "verified" ? "green" : "orange"}>{current.verification}</Badge></div><div className="collection-info-grid"><section><h3>数据契约</h3><pre>{JSON.stringify(current.fields, null, 2)}</pre></section><section><h3>能力与用途</h3><p>读取：{current.capabilities.read ? "允许" : "不允许"} · 写入：{current.capabilities.write ? "允许" : "不允许"}</p><p>Agent 用途：{current.agent_usage.join("、")}</p><p>更新：{current.refresh}</p></section><section><h3>错误边界</h3><div className="collection-error-tags">{current.errors.map(error => <Badge key={error} tone={error === "STRUCTURE_CHANGED" ? "orange" : "neutral"}>{error}</Badge>)}</div></section><section><h3>Agent 调用</h3><p>只读接口，按平台与类别返回上述结构，不返回 Cookie、Token 或密码。</p><a className="button button-small" href={`/api/accounts/collection-knowledge/${current.platform}/${current.category}`} target="_blank" rel="noreferrer">查看机器可读 JSON <ExternalLink size={13} /></a></section></div><div className="collection-export"><strong>后台页面</strong><p>{current.url}</p>{/^https?:/.test(current.url) && <a href={current.url} target="_blank" rel="noreferrer" aria-label={`打开${current.title}`}><ExternalLink size={16} /></a>}</div></Card></div> : <Empty title="当前筛选没有知识实体" description="调整平台或类别。待验证能力不会冒充已接入。" />}
  </div>;
}
