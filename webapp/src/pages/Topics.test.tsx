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
          xhs_hot: [{ id: "hot-1", source_key: "xhs_hot", platform: "xiaohongshu", title: "热点笔记", url: "https://www.xiaohongshu.com/explore/hot1", metadata: {}, last_seen_at: "今天" }],
          xhs_featured: [{ id: "featured-1", source_key: "xhs_featured", platform: "xiaohongshu", title: "精选笔记", url: "https://www.xiaohongshu.com/explore/featured1", metadata: {}, last_seen_at: "今天" }],
          xhs_competitor: [{ id: "competitor-1", source_key: "xhs_competitor", platform: "xiaohongshu", title: "竞品笔记", url: "https://www.xiaohongshu.com/explore/competitor1", metadata: {}, last_seen_at: "今天" }],
          xhs_high_praise: [{ id: "praise-1", source_key: "xhs_high_praise", platform: "xiaohongshu", title: "高赞笔记", url: "https://www.xiaohongshu.com/explore/praise1", metadata: {}, last_seen_at: "今天" }],
          xhs_notes: [],
        },
        recommendations: { xiaohongshu: [] }, archived: [], archived_count: 0, jobs: [],
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
    expect(screen.getByRole("heading", { name: "小红书今日推荐" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "热点笔记" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "精选笔记" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("热点收藏夹")).toHaveValue("热点");

    await user.click(screen.getByRole("button", { name: /精选选题/ }));
    expect(screen.getByRole("heading", { name: "精选笔记" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "热点笔记" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /竞品选题/ }));
    expect(screen.getByRole("heading", { name: "竞品笔记" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /高赞选题/ }));
    expect(screen.getByRole("heading", { name: "高赞笔记" })).toBeInTheDocument();
  });

  it("syncs personal collections and calls the Xiaohongshu recommendation agent", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("button", { name: "同步收藏夹" }));
    await waitFor(() => expect(mocks.api).toHaveBeenCalledWith("/api/topics/xiaohongshu/sync", expect.objectContaining({ method: "POST" })));
    await user.click(screen.getByRole("button", { name: "生成今日推荐" }));
    await waitFor(() => expect(mocks.api).toHaveBeenCalledWith("/api/topics/recommend", expect.objectContaining({ body: JSON.stringify({ agent: "xiaohongshu" }) })));
  });
});
