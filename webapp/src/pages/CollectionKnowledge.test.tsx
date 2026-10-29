import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import CollectionKnowledge from "./CollectionKnowledge";

vi.mock("@/AppContext", () => ({
  useApp: () => ({ resources: { accounts: { collection_knowledge: {
    boundary: "不保存凭据",
    error_types: ["LOGIN_REQUIRED", "STRUCTURE_CHANGED"],
    platforms: [{ platform: "wechat_channels", name: "视频号", version: "2026-10-29", page: "视频内容管理", url: "https://channels.weixin.qq.com/platform/post/list",
      login_check: { text_contains: "登录视频号助手" }, selectors: { container: ".post-feed-item" }, validation: { required: ["title"] },
      incremental: { cursor: "platform_item_id", overlap: 20, history: "仅首次全量" }, export: { priority: ["official_export", "dom"], status: "unverified" } }],
  } } } }),
}));

describe("CollectionKnowledge", () => {
  it("shows adapter structure, incremental rules and typed errors", () => {
    render(<MemoryRouter><CollectionKnowledge /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: "采集知识库" })).toBeInTheDocument();
    expect(screen.getByText("视频内容管理")).toBeInTheDocument();
    expect(screen.getByText("游标：platform_item_id")).toBeInTheDocument();
    expect(screen.getByText("STRUCTURE_CHANGED")).toBeInTheDocument();
    expect(screen.getByText("不保存凭据")).toBeInTheDocument();
  });
});
