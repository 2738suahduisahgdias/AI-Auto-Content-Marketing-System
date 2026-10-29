import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import CollectionKnowledge from "./CollectionKnowledge";

vi.mock("@/AppContext", () => ({
  useApp: () => ({ resources: { accounts: { collection_knowledge: {
    boundary: "不保存凭据",
    categories: [{ id: "content_management", name: "内容管理" }, { id: "analytics", name: "数据分析" }],
    error_types: ["LOGIN_REQUIRED", "STRUCTURE_CHANGED"],
    entities: [
      { id: "wechat_channels:content_management", platform: "wechat_channels", category: "content_management", category_name: "内容管理", title: "视频内容管理", url: "https://channels.weixin.qq.com/platform/post/list", status: "verified", verification: "已验证", capabilities: { read: true, write: false }, fields: { title: "string" }, agent_usage: ["account_daily"], errors: ["STRUCTURE_CHANGED"], refresh: "增量", version: "2026-10-29" },
      { id: "douyin:analytics", platform: "douyin", category: "analytics", category_name: "数据分析", title: "创作者数据中心", url: "https://creator.douyin.com", status: "unverified", verification: "待验证", capabilities: { read: true, write: false }, fields: { views: "number|null" }, agent_usage: ["quality_analysis"], errors: ["PARSING_FAILED"], refresh: "增量", version: "2026-10-29" },
    ],
  } } } }),
}));

describe("CollectionKnowledge", () => {
  it("shows ontology contracts, verification states and agent links", () => {
    render(<MemoryRouter><CollectionKnowledge /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: "采集 Ontology" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "视频内容管理" })).toBeInTheDocument();
    expect(screen.getByText("2 个实体")).toBeInTheDocument();
    expect(screen.getByText("1 个已验证")).toBeInTheDocument();
    expect(screen.getByText("1 个待验证")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "查看机器可读 JSON" })).toHaveAttribute("href", "/api/accounts/collection-knowledge/wechat_channels/content_management");
  });
});
