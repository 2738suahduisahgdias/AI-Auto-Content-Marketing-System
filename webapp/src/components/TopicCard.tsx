import { ExternalLink, FileSearch, Plus, ScanText } from "lucide-react";
import { Badge, Button, Card } from "@/components/ui";
import { formatNumber } from "@/lib/api";
import type { Json, TopicItem } from "@/lib/types";

interface TopicCardProps {
  item: TopicItem;
  busy?: boolean;
  allowAnalyze?: boolean;
  onCreate: (item: TopicItem) => void;
  onAnalyze?: (item: TopicItem) => void;
  onDetail: (item: TopicItem) => void;
}

export function TopicCard({ item, busy = false, allowAnalyze = true, onCreate, onAnalyze, onDetail }: TopicCardProps) {
  const metadata: Json = item.metadata || {};
  const author = metadata.author_name || metadata.author || "作者未读取";
  const likes = metadata.like_count ?? metadata.visible_metrics?.like_count;
  const hasOriginalUrl = /^https?:\/\//.test(item.url) && !item.url.startsWith("https://wechat.local/");
  const source = item.source_key || metadata.source_key;
  const showCover = !["hot", "industry"].includes(String(source || ""));
  return <Card className="topic-research-card">
    {showCover && <div className="topic-research-cover-native">
      {metadata.cover_cached ? <img src={`/api/topics/items/${encodeURIComponent(item.id)}/cover`} alt={`${item.title} 封面`} loading="lazy" /> : <span className="topic-cover-pending">封面待同步</span>}
      <div className="topic-cover-meta">
        <Badge tone="orange">{metadata.rank ? `#${metadata.rank}` : metadata.source_name || metadata.tag || item.platform}</Badge>
        <span>赞 {formatNumber(likes)}</span>
      </div>
      <span className="topic-analysis-mark">{item.analysis_status === "succeeded" ? "已拆解" : "仅快照"}</span>
    </div>}
    <div className="topic-research-body">
      <h3>{item.title}</h3>
      <div className="topic-author"><span>{String(author).slice(0, 1)}</span><div><strong>{author}</strong><small>{metadata.author_followers != null ? `粉丝 ${formatNumber(metadata.author_followers)}` : "粉丝未读取"}</small></div></div>
      <p className="topic-captured">采集于 {item.last_seen_at || "未读取"} · 同步不下载视频</p>
      <div className="topic-card-actions">
        {hasOriginalUrl ? <a className="button button-small" href={item.url} target="_blank" rel="noreferrer"><ExternalLink size={13} />原链接</a> : <Button size="small" disabled title="纯文本微信消息没有原链接">无原链接</Button>}
        <Button size="small" disabled={busy} onClick={() => onCreate(item)}><Plus size={13} />创建任务</Button>
        {allowAnalyze && onAnalyze && <Button size="small" disabled={busy} onClick={() => onAnalyze(item)}><ScanText size={13} />{item.analysis_status === "succeeded" ? "重新检查拆解" : "下载并拆解"}</Button>}
        <Button size="small" variant="ghost" disabled={busy} onClick={() => onDetail(item)}><FileSearch size={13} />{item.analysis_status === "succeeded" ? "查看拆解" : "详情"}</Button>
      </div>
    </div>
  </Card>;
}
