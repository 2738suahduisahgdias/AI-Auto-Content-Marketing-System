import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import PublishKnowledge from "./PublishKnowledge";

vi.mock("@/AppContext", () => ({
  useApp: () => ({ resources: { accounts: { publish_knowledge: {
    boundary: "不代表已发布",
    platforms: [{ platform: "douyin", platform_name: "抖音", prepare_supported: true, verification: "已验证发布字段",
      content_types: [{ content_kind: "video", media: { required: true, format: "MP4", approval: "人工终审" },
        fields: [{ name: "title", required: true, max_length: 300, source: "口播稿", description: "视频短标题" }, { name: "video_path", required: true, max_length: null, source: "已批准成片", description: "MP4 文件" }] }],
      workflow: ["生成字段", "创建预览", "人工确认", "后台核验"] },
    { platform: "wechat_official_account", platform_name: "公众号", prepare_supported: true, verification: "已验证发布字段",
      content_types: [{ content_kind: "article", media: { required: true, format: "封面图片资产", approval: "正文人工批准" },
        fields: [{ name: "author", required: false, max_length: 8, source: "人工填写", description: "作者名" }] }],
      workflow: ["生成字段", "创建预览", "人工确认", "后台核验"] }],
  } } } }),
}));

describe("PublishKnowledge", () => {
  it("shows publish fields and agent machine contract", async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><PublishKnowledge /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: "发布知识库" })).toBeInTheDocument();
    expect(screen.getByText("视频短标题")).toBeInTheDocument();
    expect(screen.getByText("300")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Agent JSON" })).toHaveAttribute("href", "/api/publishing/knowledge/douyin/video");
    expect(screen.getByText(/必须 · MP4 · 人工终审/)).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("平台"), "wechat_official_account");
    expect(screen.getByText("作者名")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Agent JSON" })).toHaveAttribute("href", "/api/publishing/knowledge/wechat_official_account/article");
  });
});
