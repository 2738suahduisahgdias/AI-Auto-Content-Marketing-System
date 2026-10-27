import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import Tasks from "./Tasks";

const tasks = Array.from({ length: 12 }, (_, index) => ({
  content_id: `video-${index}`, title: `视频 ${index}`, state: "approved",
  pillar: "enterprise_ai", audience: "business_owners", angle: "真实任务",
  scripts: { master: "口播" }, files: [{ id: index + 1, kind: "video", original_name: "final.mp4", relative_path: `renders/video-${index}.mp4`, url: `/api/files/${index + 1}/media`, download_url: `/api/files/${index + 1}/media?download=1`, media_info: { duration_seconds: 118 } }],
  asset_plan: [], quality: {}, publications: {}, metrics: {}, retrospective: "", events: [], updated_at: "2026-10-28",
}));

vi.mock("@/AppContext", () => ({
  useApp: () => ({
    resources: { core: { tasks }, articles: { items: [], jobs: [] } },
    refresh: vi.fn(), run: vi.fn(),
  }),
}));

describe("Video delivery and pagination", () => {
  it("shows only the real video delivery and paginates tasks", () => {
    render(<MemoryRouter><Tasks /></MemoryRouter>);
    expect(screen.getByText("交付视频")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "下载成片" })).toHaveAttribute("href", "/api/files/1/media?download=1");
    expect(screen.getByRole("link", { name: "前往发布中心" })).toHaveAttribute("href", "/publish?kind=video&id=video-0");
    fireEvent.click(screen.getByRole("button", { name: "下一页" }));
    expect(screen.getByText("2 / 2 页")).toBeInTheDocument();
    expect(screen.getByText("视频 11")).toBeInTheDocument();
  });
});
