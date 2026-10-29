import { useState } from "react";
import { BookOpen, ExternalLink, FileDown, GitBranch } from "lucide-react";
import { Link } from "react-router-dom";
import { useApp } from "@/AppContext";
import { Badge, Card, Empty, PageHeader } from "@/components/ui";
import "./Knowledge.css";

export default function CollectionKnowledge() {
  const { resources } = useApp();
  const data = resources?.accounts?.collection_knowledge || { platforms: [], error_types: [] };
  const [selected, setSelected] = useState<string | null>(null);
  const current = data.platforms.find((item: any) => item.platform === selected) || data.platforms[0];

  return <div className="collection-knowledge-page">
    <PageHeader eyebrow="COLLECTION ADAPTERS" title="采集知识库" description="只保存后台结构、指标口径和适配版本。首次建库后做增量更新，结构变化按类型报错，不反复重试。" actions={<Link className="button" to="/knowledge"><BookOpen size={15} />账号 Ontology</Link>} />
    <nav className="knowledge-tabs" aria-label="知识库视图"><Link to="/knowledge">账号 Ontology</Link><Link className="active" to="/knowledge/collection">采集知识库</Link></nav>
    <div className="collection-boundary"><GitBranch size={17} /><p>{data.boundary}</p></div>
    {current ? <div className="collection-layout"><div className="collection-platform-list">{data.platforms.map((item: any) => <button key={item.platform} className={current.platform === item.platform ? "active" : ""} onClick={() => setSelected(item.platform)}><strong>{item.name}</strong><small>{item.version}</small></button>)}</div><Card className="collection-detail"><div className="collection-detail-head"><div><Badge tone="blue">{current.name}</Badge><h2>{current.page}</h2><p>{current.url}</p></div><Badge tone="orange">导出待验证</Badge></div><div className="collection-info-grid"><section><h3>页面与登录检查</h3><pre>{JSON.stringify(current.login_check, null, 2)}</pre></section><section><h3>字段与指标映射</h3><pre>{JSON.stringify(current.selectors, null, 2)}</pre>{current.metric_map && <pre>{JSON.stringify(current.metric_map, null, 2)}</pre>}</section><section><h3>结构校验</h3><pre>{JSON.stringify(current.validation, null, 2)}</pre></section><section><h3>增量更新</h3><p>游标：{current.incremental.cursor}</p><p>重叠校验：{current.incremental.overlap} 条</p><p>{current.incremental.history}</p></section></div><div className="collection-export"><FileDown size={17} /><div><strong>导出优先级</strong><p>{current.export.priority.join(" → ")}。尚无真实导出验证时显示 EXPORT_NOT_FOUND，不伪造导出结果。</p></div><a href={current.url} target="_blank" rel="noreferrer" aria-label={`打开${current.name}后台`}><ExternalLink size={16} /></a></div></Card></div> : <Empty title="还没有采集知识定义" description="请先加载真实账号数据，不会生成空平台定义。" />}
    <Card className="collection-errors"><h2>同步错误类型</h2><div>{data.error_types.map((type: string) => <Badge key={type} tone={type === "STRUCTURE_CHANGED" ? "orange" : "neutral"}>{type}</Badge>)}</div><p>每种错误都包含平台、原因、处理动作和时间；只暂停对应平台，不自动重试。</p></Card>
  </div>;
}
