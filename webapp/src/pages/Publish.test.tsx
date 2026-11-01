import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import Publish from "./Publish";

const target = { id: "target-1", platform: "douyin", platform_name: "抖音", status: "ready", payload: { title: "企业 AI 案例", description: "发布描述", tags: "#企业AI" }, preview: {}, error: null, payload_hash: "abc123" };
const batch = { id: "batch-1", content_kind: "video", source_id: "20261029-001", source_file_id: 3, source_hash: "hash-1", status: "ready", targets: [target] };
const queueItem = { id: "20261029-001", title: "企业 AI 案例", body: "发布描述", file_id: 3, variant_id: "variant-1", preview_url: "/api/files/3/media", status: "ready", batch };

vi.mock("@/lib/api", () => ({
  api: vi.fn((path: string) => {
    if (path === "/api/review/bootstrap") return Promise.resolve({ batch: { items: [] } });
    if (path === "/api/publishing/queue") return Promise.resolve({ items: [queueItem] });
    if (path.startsWith("/api/publishing/bootstrap")) return Promise.resolve({ batch, field_jobs: [] });
    return Promise.resolve({});
  }),
  jsonOptions: (method: string, payload: unknown) => ({ method, body: JSON.stringify(payload) }),
}));

vi.mock("@/AppContext", () => ({
  useApp: () => ({
    resources: { core: { tasks: [] }, accounts: { publish_knowledge: { platforms: [] } }, articles: { items: [] } },
    run: vi.fn((action: () => unknown) => action()), refresh: vi.fn(), notify: vi.fn(),
  }),
}));

describe("Publication queue", () => {
  it("lists variant targets and shares preview metadata", async () => {
    render(<MemoryRouter><Publish /></MemoryRouter>);
    expect((await screen.findAllByText("企业 AI 案例")).length).toBeGreaterThan(0);
    expect(screen.getByText("发布目标队列")).toBeInTheDocument();
    expect(screen.getByText("本地发布预览")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "全选当前筛选" }));
    expect(screen.getByText("发布选中就绪项")).toBeInTheDocument();
    expect(screen.getByText("#企业AI")).toBeInTheDocument();
  });
});
