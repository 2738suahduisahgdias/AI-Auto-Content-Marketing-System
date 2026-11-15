import { Badge, Busy, Button, Empty, ErrorBox, Modal } from "@/components/ui";
const activeJobStatuses = ["queued", "leased", "running", "retry_wait"];
import type { Job, Json, TopicItem } from "@/lib/types";

export default function DownloadProbeModal({ item, jobs, busy, onChoose, onClose }: { item: TopicItem; jobs: Job[]; busy: boolean; onChoose: (mode: string) => void; onClose: () => void }) {
  const job = jobs.find(candidate => candidate.kind === "research.probe" && (candidate as Json).aggregate_id === item.id);
  const result = job?.result;
  const running = !job || activeJobStatuses.includes(job.status);
  return <Modal open onOpenChange={open => { if (!open) onClose(); }} title="下载小红书素材" description="先读取真实作品和档位，再由你选择下载方式；探测不会下载文件。" wide>
    {!job || running ? <Busy label="正在通过 Kimi CLI 读取真实素材与档位…" /> : <>
      {job.error && <ErrorBox>{job.error.message || job.error.code}</ErrorBox>}
      {result?.media_kind ? <div className="topic-download-probe">
        <div className="button-row"><Badge tone="green">{result.media_kind === "image_set" ? "图文素材" : "视频"}</Badge><strong>{result.title || item.title}</strong></div>
        {result.formats?.length ? <div className="topic-download-formats">{result.formats.map((format: Json) => <div key={format.id || format.label}><strong>{format.label || format.id}</strong><small>{[format.width && format.height ? `${format.width}×${format.height}` : "", format.filesize_human || "", format.note || ""].filter(Boolean).join(" · ")}</small></div>)}</div> : <Empty title="这是图文素材" description="没有视频档位；选择下载方式后会保存实际读取到的图片组。" />}
        <p className="topic-boundary">画质优先可能申请读取浏览器登录态；速度优先选择较低负载档位；兼容优先用于通用播放。只有点击以下按钮才会下载。</p>
        <div className="topic-download-modes"><Button disabled={busy} onClick={() => onChoose("quality")}>画质优先</Button><Button disabled={busy} onClick={() => onChoose("speed")}>速度优先</Button><Button variant="primary" disabled={busy} onClick={() => onChoose("compat")}>兼容优先</Button></div>
      </div> : !job.error && <Empty title="没有取得素材信息" description="请检查原链接和同步记录，不会创建下载任务。" />}
    </>}
  </Modal>;
}
