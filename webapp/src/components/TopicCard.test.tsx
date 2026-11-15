import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TopicCard } from "./TopicCard";
import type { TopicItem } from "@/lib/types";

afterEach(cleanup);

const base = { id: "topic-1", platform: "douyin", title: "真实选题", url: "https://example.com/video/1", last_seen_at: "今天", analysis_status: "not_started" } as unknown as TopicItem;
const props = { onCreate: vi.fn(), onAnalyze: vi.fn(), onDetail: vi.fn() };

describe("TopicCard covers", () => {
  it("does not render covers for industry news or the Douyin hot list", () => {
    const { container, rerender } = render(<TopicCard {...props} item={{ ...base, source_key: "hot", metadata: { cover_cached: true } }} />);
    expect(container.querySelector("img")).not.toBeInTheDocument();
    rerender(<TopicCard {...props} item={{ ...base, source_key: "industry", metadata: { cover_cached: true } }} />);
    expect(container.querySelector("img")).not.toBeInTheDocument();
  });

  it("uses the original image ratio for collection research covers", () => {
    const { container } = render(<TopicCard {...props} item={{ ...base, source_key: "featured", metadata: { cover_cached: true } }} />);
    expect(screen.getByRole("img", { name: "真实选题 封面" })).toBeInTheDocument();
    expect(container.querySelector(".topic-research-cover-native")).toBeInTheDocument();
    expect(container.querySelector(".topic-research-cover")).not.toBeInTheDocument();
  });

  it("renders only hot metadata even when legacy author details exist", () => {
    const { container } = render(<TopicCard {...props} item={{ ...base, source_key: "hot", metadata: { rank: 1, heat: "772.4万热度", author_name: "历史作者", author_followers: 12000, like_count: 3456, comment_count: 789 } }} />);
    expect(container.querySelector(".topic-hot-item")).toBeInTheDocument();
    expect(screen.getByText("772.4万热度")).toBeInTheDocument();
    expect(screen.queryByText("历史作者")).not.toBeInTheDocument();
    expect(screen.queryByText(/粉丝/)).not.toBeInTheDocument();
    expect(screen.queryByText(/赞 3,456/)).not.toBeInTheDocument();
    expect(screen.queryByText(/评论 789/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "下载视频" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "转为选题" })).toBeInTheDocument();
  });

  it.each(["featured", "competitor", "high_praise"])("keeps author and engagement together in %s cards", (sourceKey) => {
    const { container } = render(<TopicCard {...props} item={{ ...base, source_key: sourceKey, metadata: { author_name: "真实作者", author_followers: 12000, like_count: 3456, comment_count: 789 } }} />);
    const card = container.querySelector(".topic-research-card");
    expect(card?.querySelector(".topic-author")).toHaveTextContent("真实作者");
    expect(card?.querySelector(".topic-engagement")).toHaveTextContent("粉丝 12,000");
    expect(card?.querySelector(".topic-engagement")).toHaveTextContent("点赞 3,456");
    expect(card?.querySelector(".topic-engagement")).toHaveTextContent("评论 789");
  });

  it("keeps Xiaohongshu hot cards as public links without collection actions", () => {
    render(<TopicCard {...props} item={{ ...base, platform: "xiaohongshu", source_key: "xhs_hot", metadata: { rank: 1, heat: "10万热度" } }} />);
    expect(screen.getByText(/小红书平台热点/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "原链接" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "转为选题" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "归档" })).not.toBeInTheDocument();
    expect(screen.queryByText(/粉丝/)).not.toBeInTheDocument();
  });

  it("uses a media download entry for Xiaohongshu collection cards", () => {
    render(<TopicCard {...props} item={{ ...base, platform: "xiaohongshu", source_key: "xhs_featured", metadata: {} }} />);
    expect(screen.getByRole("button", { name: "下载素材" })).toBeInTheDocument();
  });

  it("shows downloaded and failed states without analysis actions", () => {
    const { rerender } = render(<TopicCard {...props} item={{ ...base, source_key: "featured", metadata: { download_status: "downloaded", download_path: "/tmp/source.mp4" } }} />);
    expect(screen.getByText("已下载")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "查看下载信息" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "下载视频" })).not.toBeInTheDocument();
    rerender(<TopicCard {...props} item={{ ...base, source_key: "featured", metadata: { download_status: "failed" } }} />);
    expect(screen.getByText("下载失败")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "重试下载" })).toBeInTheDocument();
  });

  it("restores archived topics without exposing production actions", () => {
    const onArchive = vi.fn();
    render(<TopicCard {...props} item={base} archived onArchive={onArchive} />);
    expect(screen.queryByRole("button", { name: "创建任务" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "下载视频" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "恢复" }));
    expect(onArchive).toHaveBeenCalledWith(base);
  });
});
