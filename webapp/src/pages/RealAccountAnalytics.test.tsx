import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import RealAccountAnalytics from "./RealAccountAnalytics";

afterEach(cleanup);

const metrics = { originals: 1, publications: 1, articles: 0, videos: 1, reach: null, likes: null, comments: null, shares: null, favorites: null };
const ranges = { today: metrics, yesterday: metrics, "7d": metrics, "30d": metrics };
const platform = { metrics: ranges, snapshot: null };

vi.mock("@/AppContext", () => ({
  useApp: () => ({
    resources: { accounts: { analytics: {
      generated_at: "2026-10-28T10:00:00+08:00", totals: ranges,
      platforms: { douyin: platform, wechat_channels: platform, xiaohongshu: platform, wechat_official_account: platform },
      contents: [{ id: "verified-1", platform: "douyin", title: "已核验真实视频", kind: "video", published_at: new Date().toISOString(), url: "https://example.com/real", verified: true }],
      trends: { publications: { labels: ["10/22", "10/23", "10/24", "10/25", "10/26", "10/27", "10/28"], values: [0, 0, 0, 0, 0, 0, 1] } },
      sync: [{ platform: "douyin", status: "not_connected", captured_at: null, detail: "尚无真实账号快照" }],
      competitor_analytics: { items: [] }, data_boundaries: ["缺失不等于零"],
    } } }, refresh: vi.fn(), notify: vi.fn(),
  }),
}));

describe("RealAccountAnalytics", () => {
  it("shows verified production and leaves unavailable acquisition and reach empty", () => {
    render(<MemoryRouter initialEntries={["/accounts"]}><Routes><Route path="/accounts/:view?" element={<RealAccountAnalytics />} /></Routes></MemoryRouter>);
    expect(screen.getByText("真实数据")).toBeInTheDocument();
    expect(screen.getByText("已核验真实视频")).toBeInTheDocument();
    expect(screen.getByText("暂无可计算的新增传播指标")).toBeInTheDocument();
    expect(screen.getByText("当前维度没有私信线索记录")).toBeInTheDocument();
    expect(screen.queryByText("55,080")).not.toBeInTheDocument();
    expect(screen.queryByText("产品演示 · 全部指标为模拟数据")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "查看演示" })).toHaveAttribute("href", "/accounts?demo=1");
  });
});
