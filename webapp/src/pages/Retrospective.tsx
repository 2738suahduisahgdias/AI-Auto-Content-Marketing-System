import { useEffect, useState } from "react";
import { ExternalLink, FileText, Film, TrendingUp } from "lucide-react";
import { Link } from "react-router-dom";
import { api, errorText } from "@/lib/api";
import { platformNames } from "@/lib/names";
import { Badge, Button, Card, Empty, ErrorBox, PageHeader } from "@/components/ui";
import "./Retrospective.css";

interface PublishedItem {
  target_id: string;
  batch_id: string;
  source_id: string;
  content_kind: "article" | "video";
  title: string;
  verified_at: string;
  external_url?: string | null;
  evidence?: string | null;
}

interface PlatformReview {
  platform_name: string;
  items: PublishedItem[];
  suggestion: string;
  suggestion_kind: string;
  data_boundary: string;
}

interface RetrospectiveData {
  platforms: Record<string, PlatformReview>;
  total_published: number;
  note: string;
}

const platforms = ["douyin", "xiaohongshu", "wechat_channels", "wechat_official_account"];

export default function Retrospective() {
  const [platform, setPlatform] = useState("douyin");
  const [data, setData] = useState<RetrospectiveData | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    api<RetrospectiveData>("/api/publishing/retrospective")
      .then(result => { if (active) { setData(result); setError(""); } })
      .catch(reason => { if (active) setError(errorText(reason)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const review = data?.platforms[platform];
  const items = review?.items || [];
  return <div className="retrospective-page">
    <PageHeader eyebrow="VERIFIED PUBLICATION REVIEW" title="内容复盘" description="汇总最近各平台已核验发布内容。发布事实、传播指标和提升建议分开呈现，不把即时零数据当作效果结论。" actions={<Link className="button" to="/accounts">查看账号日报</Link>} />
    {error && <ErrorBox>{error}<br /><Button size="small" onClick={() => window.location.reload()}>重新读取</Button></ErrorBox>}
    <div className="retro-summary">
      <Card><span>已核验发布</span><strong>{data?.total_published ?? 0}</strong><small>条真实内容记录</small></Card>
      <Card><span>覆盖平台</span><strong>{platforms.length}</strong><small>小红书 · 抖音 · 视频号 · 公众号</small></Card>
      <Card className="retro-boundary-card"><span>数据边界</span><strong>效果待观察</strong><small>{data?.note || "只读取已核验记录，不补造传播指标。"}</small></Card>
    </div>
    <div className="retro-tabs" role="tablist" aria-label="复盘平台">{platforms.map(key => <button role="tab" aria-selected={platform === key} className={`retro-tab${platform === key ? " active" : ""}`} key={key} onClick={() => setPlatform(key)}>{platformNames[key]}<Badge>{data?.platforms[key]?.items.length ?? 0}</Badge></button>)}</div>
    {loading ? <Card><Empty title="正在读取真实发布记录…" /></Card> : <div className="retro-layout">
      <section className="retro-list-section"><div className="section-heading"><h2>{platformNames[platform]}最近发布</h2><p>仅展示已核验内容，最多保留最近 8 条</p></div>
        {items.length ? <div className="retro-list">{items.slice(0, 8).map(item => <Card className="retro-item" key={item.target_id}>
          <div className="retro-item-head"><Badge tone={item.content_kind === "article" ? "blue" : "green"}>{item.content_kind === "article" ? <><FileText size={12} /> 文章</> : <><Film size={12} /> 视频</>}</Badge><time>{item.verified_at}</time></div>
          <h3>{item.title}</h3>
          <p className="retro-id">批次 {item.batch_id} · 来源 {item.source_id}</p>
          {item.evidence && <p className="retro-evidence">{item.evidence}</p>}
          <div className="retro-item-foot"><Badge tone="green">已核验发布</Badge>{item.external_url && <a href={item.external_url} target="_blank" rel="noreferrer">查看平台记录 <ExternalLink size={13} /></a>}</div>
        </Card>)}</div> : <Card><Empty title={`${platformNames[platform]}暂无已核验发布`} description="待核对、失败或仅预览内容不会进入复盘。可先从发布中心完成一条真实内容。" action={<Link className="button button-primary" to="/publish">前往发布中心</Link>} /></Card>}
      </section>
      <aside className="retro-insights">
        <Card className="retro-data-boundary"><div className="retro-insight-icon"><TrendingUp size={18} /></div><h2>当前能判断什么</h2><p>{review?.data_boundary || "发布记录已核验；互动与分时间窗口指标未关联到本条内容，暂不能判断传播效果。"}</p><Badge>不生成虚假效果结论</Badge></Card>
        <Card className="retro-suggestion"><p className="eyebrow">IMPROVEMENT</p><h2>下一步提升建议</h2><p>{review?.suggestion}</p><Badge tone="orange">{review?.suggestion_kind || "流程建议，不是平台效果结论"}</Badge></Card>
        <Card><h3>继续完善数据</h3><p>账号日报用于读取账号与公开内容快照；发布中心用于处理下一条内容。真实互动积累后，再比较选题、标题与平台形式。</p><div className="button-row"><Link className="button button-small" to="/accounts">账号日报</Link><Link className="button button-small" to="/publish">发布中心</Link></div></Card>
      </aside>
    </div>}
  </div>;
}
