import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api";
import Retrospective from "./Retrospective";

vi.mock("@/lib/api", async importOriginal => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, api: vi.fn() };
});

const platform = (items: unknown[], suggestion: string) => ({
  platform_name: "平台", items, suggestion,
  suggestion_kind: "流程建议，不是平台效果结论",
  data_boundary: "发布记录已核验；曝光、互动及分时间窗口指标未关联到本条内容，暂不能判断传播效果。",
});

const item = (title: string, kind = "video") => ({
  target_id: `target-${title}`, batch_id: "batch-1", source_id: "source-1",
  content_kind: kind, title, verified_at: "2026-10-28T01:00:00Z",
  external_url: null, evidence: "平台后台已核验",
});

describe("Retrospective", () => {
  beforeEach(() => {
    vi.mocked(api).mockResolvedValue({
      platforms: {
        douyin: platform([item("抖音真实视频")], "用内容管理核验"),
        xiaohongshu: platform([item("小红书真实长文", "article")], "控制长文图片数量"),
        wechat_channels: platform([], "保留人工选文件"),
        wechat_official_account: platform([], "预留管理员验证"),
      },
      total_published: 2,
      note: "仅包含已核验发布记录",
    });
  });

  it("shows verified records, platform filters and evidence boundaries", async () => {
    render(<MemoryRouter><Retrospective /></MemoryRouter>);
    expect(await screen.findByText("抖音真实视频")).toBeInTheDocument();
    expect(screen.getAllByText("已核验发布").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/暂不能判断传播效果/).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("tab", { name: /小红书/ }));
    expect(await screen.findByText("小红书真实长文")).toBeInTheDocument();
    expect(screen.getByText("控制长文图片数量")).toBeInTheDocument();
    expect(screen.getAllByText("流程建议，不是平台效果结论").length).toBeGreaterThan(0);
  });
});
