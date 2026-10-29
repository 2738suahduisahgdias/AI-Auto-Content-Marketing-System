import { useMemo, useState } from "react";
import { Braces, ExternalLink, Send } from "lucide-react";
import { Link } from "react-router-dom";
import { useApp } from "@/AppContext";
import { Badge, Card, Empty, PageHeader } from "@/components/ui";
import "./Knowledge.css";

const kindNames: Record<string, string> = { video: "视频", article: "文章" };

export default function PublishKnowledge() {
  const { resources } = useApp();
  const data = useMemo(() => resources?.accounts?.publish_knowledge || { platforms: [] }, [resources]);
  const [platform, setPlatform] = useState("douyin");
  const [kind, setKind] = useState("video");
  const current = useMemo(() => data.platforms.find((item: any) => item.platform === platform), [data, platform]);
  const content = current?.content_types.find((item: any) => item.content_kind === kind);

  return <div className="collection-knowledge-page">
    <PageHeader eyebrow="PUBLISH CONTRACTS" title="发布知识库" description="发布 Agent 按各平台独立字段与限制生成内容；仅保存字段未实际写入时，不能通过发布预览。" actions={<Link className="button" to="/knowledge/collection"><Braces size={15} />采集 Ontology</Link>} />
    <nav className="knowledge-tabs" aria-label="知识库视图"><Link to="/knowledge">账号 Ontology</Link><Link to="/knowledge/collection">采集知识库</Link><Link className="active" to="/knowledge/publishing">发布知识库</Link></nav>
    <div className="collection-boundary"><Send size={17} /><p>{data.boundary}</p></div>
    <div className="collection-toolbar"><label>平台<select value={platform} onChange={event => {
      const nextPlatform = event.target.value;
      const next = data.platforms.find((item: any) => item.platform === nextPlatform);
      setPlatform(nextPlatform);
      if (!next?.content_types.some((item: any) => item.content_kind === kind)) setKind(next?.content_types[0]?.content_kind || "");
    }}>{data.platforms.map((item: any) => <option key={item.platform} value={item.platform}>{item.platform_name}</option>)}</select></label><label>内容类型<select value={kind} onChange={event => setKind(event.target.value)}>{current?.content_types.map((item: any) => <option key={item.content_kind} value={item.content_kind}>{kindNames[item.content_kind]}</option>)}</select></label>{current && <Badge tone={current.prepare_supported ? "green" : "orange"}>{current.verification}</Badge>}</div>
    {current && content ? <Card className="collection-detail"><div className="collection-detail-head"><div><Badge tone="blue">{current.platform_name} · {kindNames[kind]}</Badge><h2>发布 Agent 生成规范</h2><p>{current.workflow.join(" → ")}</p></div><a className="button button-small" href={`/api/publishing/knowledge/${platform}/${kind}`} target="_blank" rel="noreferrer">Agent JSON <ExternalLink size={13} /></a></div><div className="publish-field-table-wrap"><table className="publish-field-table"><thead><tr><th>字段</th><th>必填</th><th>最大长度</th><th>写入状态</th><th>内容来源</th><th>生成与验证规则</th></tr></thead><tbody>{content.fields.map((field: any) => <tr key={field.name}><td><code>{field.name}</code><small className="publish-field-label">{field.label}</small></td><td><Badge tone={field.required ? "orange" : "neutral"}>{field.required ? "必填" : "选填"}</Badge></td><td>{field.max_length ?? "按平台/文件"}</td><td><Badge tone={field.sync_status === "connected" ? "green" : "orange"}>{field.sync_status === "connected" ? "已接入" : "仅保存"}</Badge></td><td>{field.source}</td><td>{field.description}</td></tr>)}</tbody></table></div><div className="collection-export"><strong>媒体与审批</strong><p>{content.media.required ? "必须" : "可选"} · {content.media.format} · {content.media.approval}</p><p>{content.media.evidence}</p></div></Card> : <Empty title="该平台暂不支持此内容类型" description="请切换平台或内容类型，不会生成不支持的发布字段。" />}
  </div>;
}
