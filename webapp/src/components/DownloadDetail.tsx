import { Badge, Button, Empty } from "@/components/ui";
import type { Json } from "@/lib/types";

export default function DownloadDetail({ detail, onReveal, onCopy }: { detail: Json; onReveal: () => void; onCopy: () => void }) {
  const metadata: Json = detail.metadata || {};
  const downloaded = metadata.download_status === "downloaded" && metadata.download_path;
  if (!downloaded) {
    return <Empty title={metadata.download_status === "failed" ? "下载失败" : "尚未下载"} description={metadata.download_error || (detail.platform === "xiaohongshu" ? "点击“下载素材”后先探测真实内容，再由你选择下载模式。" : "点击“下载视频”后，由 Kimi CLI 下载真实文件并显示本地地址。")} />;
  }
  const megabytes = Number(metadata.download_bytes || 0) / 1000000;
  const imageSet = metadata.download_media_kind === "image_set";
  return <div className="download-detail">
    <div className="evidence-status-row"><Badge tone="green">已下载</Badge><strong>{detail.title}</strong>{imageSet && <Badge>图文素材 · {metadata.download_file_count} 个文件</Badge>}</div>
    <section className="evidence-section"><h3>{imageSet ? "本地素材" : "本地文件"}</h3><dl className="evidence-fields">
      <div><dt>完整路径</dt><dd><code>{metadata.download_path}</code></dd></div>
      {metadata.download_directory && <div><dt>素材目录</dt><dd><code>{metadata.download_directory}</code></dd></div>}
      <div><dt>文件大小</dt><dd>{megabytes.toFixed(2)} MB（{metadata.download_bytes} 字节）</dd></div>
      {!imageSet && <div><dt>视频时长</dt><dd>{metadata.download_duration_seconds} 秒</dd></div>}
      <div><dt>资产索引</dt><dd><code>{metadata.download_storage_key || "未记录"}</code></dd></div>
    </dl></section>
    <div className="topic-detail-meta"><Button variant="primary" onClick={onReveal}>打开所在文件夹</Button><Button onClick={onCopy}>复制本地地址</Button></div>
  </div>;
}
