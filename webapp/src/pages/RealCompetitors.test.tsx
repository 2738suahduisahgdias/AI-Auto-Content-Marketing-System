import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import RealCompetitors from "./RealCompetitors";

afterEach(cleanup);

const items = [
  { id: "real-1", platform: "douyin", title: "真实竞对视频", author: "真实作者", url: "https://example.com/competitor", source: "competitor", likes: 126, comments: null, shares: null, favorites: null, visible_interactions: 126, captured_at: "2026-10-28T01:00:00Z", published_at: null, completeness: "partial" },
  { id: "real-2", platform: "xiaohongshu", title: "真实高赞笔记", author: "笔记作者", url: "https://example.com/note", source: "high_praise", likes: 88, comments: 4, shares: null, favorites: null, visible_interactions: 92, captured_at: "2026-10-28T01:00:00Z", published_at: null, completeness: "complete" },
];

vi.mock("@/AppContext", () => ({
  useApp: () => ({ resources: { accounts: { competitor_analytics: { items, summary: { total: 2, authors: 2, complete: 1, partial: 1 } } } } }),
}));

describe("RealCompetitors", () => {
  it("filters actual public snapshots without demo accounts", async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><RealCompetitors /></MemoryRouter>);
    expect(screen.getByText("真实公开快照")).toBeInTheDocument();
    expect(screen.getByText("真实竞对视频")).toBeInTheDocument();
    expect(screen.queryByText("AI落地研究所")).not.toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "小红书" }));
    expect(screen.queryByText("真实竞对视频")).not.toBeInTheDocument();
    expect(screen.getByText("真实高赞笔记")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "查看原文" })).toHaveAttribute("href", "https://example.com/note");
  });
});
