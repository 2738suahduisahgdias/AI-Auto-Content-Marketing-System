import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Recommendations } from "./Topics";
import type { TopicItem } from "@/lib/types";

afterEach(cleanup);

const sources = [
  { id: "research-1", source_key: "hot", title: "抖音热点原文", url: "https://www.douyin.com/hot/1", metadata: {} },
  { id: "research-2", source_key: "featured", title: "精选视频原文", url: "https://www.douyin.com/video/2", metadata: {} },
] as TopicItem[];
const recommendation = { id: "candidate-1", title: "真实推荐", reason: "真实理由", angle: "差异化切入", evidence_ids: ["research-1", "research-2"], status: "new", created_at: "今天" };

describe("Recommendations", () => {
  it("shows evidence sources and converts a recommendation", () => {
    const onConvert = vi.fn();
    render(<Recommendations items={[recommendation]} agent="douyin" sources={sources} busy={false} onConvert={onConvert} />);
    expect(screen.getByText("抖音热点榜")).toBeInTheDocument();
    expect(screen.getByText("精选收藏夹")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "抖音热点原文" })).toHaveAttribute("href", "https://www.douyin.com/hot/1");
    expect(screen.getByRole("link", { name: "精选视频原文" })).toHaveAttribute("href", "https://www.douyin.com/video/2");
    fireEvent.click(screen.getByRole("button", { name: "转为选题" }));
    expect(onConvert).toHaveBeenCalledWith(recommendation);
  });

  it("opens the existing task instead of converting twice", () => {
    const onConvert = vi.fn();
    render(<Recommendations items={[{ ...recommendation, status: "converted", task_id: "task-1" }]} agent="douyin" sources={sources} busy={false} onConvert={onConvert} />);
    fireEvent.click(screen.getByRole("button", { name: "打开选题" }));
    expect(onConvert).toHaveBeenCalledWith(expect.objectContaining({ task_id: "task-1" }));
  });
});
