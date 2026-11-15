import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import DownloadDetail from "./DownloadDetail";

const detail = { title: "真实视频", metadata: { download_status: "downloaded", download_path: "/Users/test/Movies/source.mp4", download_bytes: 20592217, download_duration_seconds: 94.166667, download_storage_key: "assets/v2/source.mp4" } };

afterEach(cleanup);

describe("DownloadDetail", () => {
  it("shows the real local file and working actions", () => {
    const onReveal = vi.fn();
    const onCopy = vi.fn();
    render(<DownloadDetail detail={detail} onReveal={onReveal} onCopy={onCopy} />);
    expect(screen.getByText("已下载")).toBeInTheDocument();
    expect(screen.getByText("/Users/test/Movies/source.mp4")).toBeInTheDocument();
    expect(screen.getByText(/20.59 MB/)).toBeInTheDocument();
    expect(screen.getByText(/94.166667 秒/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "打开所在文件夹" }));
    fireEvent.click(screen.getByRole("button", { name: "复制本地地址" }));
    expect(onReveal).toHaveBeenCalledOnce();
    expect(onCopy).toHaveBeenCalledOnce();
  });

  it("shows an image set with real directory and file count", () => {
    render(<DownloadDetail detail={{ title: "图文作品", metadata: { download_status: "downloaded", download_media_kind: "image_set", download_path: "/Users/test/Pictures/01.jpg", download_directory: "/Users/test/Pictures/note-1", download_file_count: 3, download_bytes: 300000 } }} onReveal={vi.fn()} onCopy={vi.fn()} />);
    expect(screen.getByText("图文素材 · 3 个文件")).toBeInTheDocument();
    expect(screen.getByText("/Users/test/Pictures/note-1")).toBeInTheDocument();
    expect(screen.queryByText(/视频时长/)).not.toBeInTheDocument();
  });

  it("shows a real failure without a fake path", () => {
    render(<DownloadDetail detail={{ title: "失败视频", metadata: { download_status: "failed", download_error: "网络连接失败" } }} onReveal={vi.fn()} onCopy={vi.fn()} />);
    expect(screen.getByText("下载失败")).toBeInTheDocument();
    expect(screen.getByText("网络连接失败")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "打开所在文件夹" })).not.toBeInTheDocument();
  });
});
