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

  it("restores archived topics without exposing production actions", () => {
    const onArchive = vi.fn();
    render(<TopicCard {...props} item={base} archived onArchive={onArchive} />);
    expect(screen.queryByRole("button", { name: "创建任务" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "下载并拆解" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "恢复" }));
    expect(onArchive).toHaveBeenCalledWith(base);
  });
});
