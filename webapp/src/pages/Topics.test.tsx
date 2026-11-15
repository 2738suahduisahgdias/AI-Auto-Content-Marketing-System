import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Topics from "./Topics";

const mocks = vi.hoisted(() => ({ api: vi.fn(), refresh: vi.fn(), notify: vi.fn() }));
vi.mock("@/lib/api", async importOriginal => ({ ...await importOriginal<typeof import("@/lib/api")>(), api: mocks.api }));
vi.mock("@/AppContext", () => ({
  useApp: () => ({
    resources: {
      core: { topics: [], favorites: { items: [] } },
      accounts: { jobs: [] },
      topics: {
        settings: {
          industry_scope: "企业 AI", industry_prompt: "行业规则", douyin_prompt: "抖音规则", xiaohongshu_prompt: "小红书规则",
          daily_time: "09:00", daily_enabled: false, featured_collection: "选题", competitor_collection: "竞对", high_praise_collection: "高赞",
          xhs_hot_collection: "热点", xhs_featured_collection: "精选", xhs_competitor_collection: "竞对", xhs_high_praise_collection: "高赞",
        },
        sources: {
          featured: [
            { id: "complete-1", source_key: "featured", platform: "douyin", title: "完整作品", url: "https://example.com/1", metadata: { author_name: "作者", author_followers: 100, like_count: 20, comment_count: 3 }, last_seen_at: "今天" },
            { id: "partial-1", source_key: "featured", platform: "douyin", title: "待补作品", url: "https://example.com/2", metadata: { like_count: 30 }, last_seen_at: "今天" },
          ],
          competitor: [{ id: "complete-2", source_key: "competitor", platform: "douyin", title: "竞对作品", url: "https://example.com/3", metadata: { author_name: "竞对", author_followers: 200, like_count: 40, comment_count: 5 }, last_seen_at: "今天" }],
          high_praise: [],
          xhs_hot: [
            { id: "hot-2", source_key: "xhs_hot", platform: "xiaohongshu", title: "第二名", url: "https://www.xiaohongshu.com/explore/hot2", metadata: { rank: 2 }, last_seen_at: "今天" },
            { id: "hot-1", source_key: "xhs_hot", platform: "xiaohongshu", title: "第一名", url: "https://www.xiaohongshu.com/explore/hot1", metadata: { rank: 1 }, last_seen_at: "今天" },
          ],
          xhs_featured: [{ id: "featured-1", source_key: "xhs_featured", platform: "xiaohongshu", title: "精选笔记", url: "https://www.xiaohongshu.com/explore/featured1", metadata: {}, last_seen_at: "今天" }],
          xhs_competitor: [{ id: "competitor-1", source_key: "xhs_competitor", platform: "xiaohongshu", title: "竞品笔记", url: "https://www.xiaohongshu.com/explore/competitor1", metadata: {}, last_seen_at: "今天" }],
          xhs_high_praise: [{ id: "praise-1", source_key: "xhs_high_praise", platform: "xiaohongshu", title: "高赞笔记", url: "https://www.xiaohongshu.com/explore/praise1", metadata: {}, last_seen_at: "今天" }],
          xhs_notes: [],
        },
        recommendations: { xiaohongshu: [] }, archived: [], archived_count: 0, jobs: [{ id: "metadata-job", kind: "topics.metadata_backfill", status: "running", stage: "kimi_browser_collect_details_batch", progress: 0.3, result: {}, created_at: "today" }, { id: "metadata-complete", kind: "topics.metadata_backfill", status: "succeeded", stage: "succeeded", progress: 1, result: { provider: "kimi_cli", processed: 25, total: 25, succeeded: 25, errors: [] }, created_at: "today" }, { id: "probe-job", kind: "research.probe", aggregate_id: "featured-1", status: "succeeded", stage: "succeeded", result: { media_kind: "video", title: "精选笔记", formats: [{ id: "1", label: "720p H.264" }], errors: [] }, created_at: "today" }, { id: "dy-job", kind: "topics.sync", status: "succeeded", stage: "succeeded", result: { status: "partial", stats: { provider: "kimi_cli", finished_sources: 2, source_total: 4, hot: 20, featured: 0, errors: [{ source: "featured", message: "收藏夹不存在", action: "核对收藏夹名称" }] } }, created_at: "today" }, { id: "xhs-job", kind: "topics.xhs_sync", status: "succeeded", stage: "succeeded", result: { status: "partial" }, created_at: "today" }],
      },
    },
    refresh: mocks.refresh,
    notify: mocks.notify,
    loadError: "",
  }),
}));

afterEach(cleanup);
beforeEach(() => {
  mocks.api.mockReset().mockResolvedValue({});
  mocks.refresh.mockReset().mockResolvedValue(undefined);
  mocks.notify.mockReset();
});

function renderPage() {
  return render(<MemoryRouter initialEntries={["/topics/xiaohongshu"]}><Routes><Route path="/topics/:source" element={<Topics />} /></Routes></MemoryRouter>);
}

describe("Xiaohongshu topic research", () => {
  it("uses the four personal collection tabs and switches real snapshots", async () => {
    const user = userEvent.setup();
    renderPage();
    expect(screen.queryByText("同步抖音快照")).not.toBeInTheDocument();
    expect(screen.queryByText("部分完成")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", {name:"同步记录"}));
    expect(screen.getByText("部分完成")).toBeInTheDocument();
    await user.click(screen.getByRole("button", {name:"关闭"}));
    await user.click(screen.getByRole("button", { name: /热点选题/ }));
    expect(screen.queryByRole("heading", { name: "小红书今日推荐" })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "第一名" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "精选笔记" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", {name:"采集与自动化"}));
    expect(screen.queryByLabelText(/热点收藏夹/)).not.toBeInTheDocument();
    expect(screen.getByLabelText("精选收藏夹")).toHaveValue("精选");
    await user.click(screen.getByRole("button", {name:"关闭"}));

    await user.click(screen.getByRole("button", { name: /精选选题/ }));
    expect(screen.getByRole("heading", { name: "精选笔记" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "热点笔记" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /竞对选题/ }));
    expect(screen.getByRole("heading", { name: "竞品笔记" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /高赞选题/ }));
    expect(screen.getByRole("heading", { name: "高赞笔记" })).toBeInTheDocument();
  });

  it("syncs collections and keeps recommendation in Today", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("button", { name: "同步内容" }));
    await waitFor(() => expect(mocks.api).toHaveBeenCalledWith("/api/topics/xiaohongshu/sync", expect.objectContaining({ method: "POST" })));
    expect(screen.queryByRole("button", {name:"生成今日推荐"})).not.toBeInTheDocument();
  });

  it("shows Kimi collection progress and source errors in Douyin records", async () => {
    const user = userEvent.setup();
    render(<MemoryRouter initialEntries={["/topics/douyin"]}><Routes><Route path="/topics/:source" element={<Topics />} /></Routes></MemoryRouter>);
    await user.click(screen.getByRole("button", {name:"同步记录"}));
    expect(screen.getAllByText(/Kimi CLI 浏览器操作/)).toHaveLength(2);
    expect(screen.getByText(/已处理 2\/4 个来源/)).toBeInTheDocument();
    expect(screen.getByText(/收藏夹不存在/)).toBeInTheDocument();
    expect(screen.getByText("当前阶段：Kimi 正在批量读取作者与互动数据")).toBeInTheDocument();
    expect(screen.getByText(/已检查 25\/25 个作品 · 四项完整 25 个/)).toBeInTheDocument();
    expect(screen.queryByText(/当前阶段：kimi_browser_collect_details_batch/)).not.toBeInTheDocument();
  });

  it("starts author and engagement backfill from collection settings", async () => {
    const user = userEvent.setup();
    render(<MemoryRouter initialEntries={["/topics/douyin"]}><Routes><Route path="/topics/:source" element={<Topics />} /></Routes></MemoryRouter>);
    await user.click(screen.getByRole("button", {name:"采集与自动化"}));
    expect(screen.getByText("收藏作品作者与互动：2/3 完整")).toBeInTheDocument();
    expect(screen.getByText("精选 1/2 · 竞对 1/1 · 高赞 0/0")).toBeInTheDocument();
    await user.click(screen.getByRole("button", {name:"补全作者与互动"}));
    await waitFor(() => expect(mocks.api).toHaveBeenCalledWith("/api/topics/metadata-backfill", expect.objectContaining({ method: "POST" })));
  });

  it("orders Xiaohongshu platform hot items by their real rank", async () => {
    const user = userEvent.setup();
    const { container } = renderPage();
    await user.click(screen.getByRole("button", { name: /热点选题/ }));
    expect(Array.from(container.querySelectorAll(".topic-hot-rank")).map(node => node.textContent)).toEqual(["#1", "#2"]);
  });

  it("probes Xiaohongshu media before the user chooses a download mode", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("button", { name: "下载素材" }));
    await waitFor(() => expect(mocks.api).toHaveBeenCalledWith("/api/topics/items/featured-1/download/probe", expect.objectContaining({ method: "POST" })));
    expect(screen.getByText("720p H.264")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "兼容优先" }));
    await waitFor(() => expect(mocks.api).toHaveBeenCalledWith("/api/topics/items/featured-1/analyze", expect.objectContaining({ method: "POST", body: JSON.stringify({ mode: "compat" }) })));
  });
});
