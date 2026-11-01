import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import VideoStages from "./VideoStages";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const templates = [
  { key: "founder-ip@1.0.0", id: "founder-ip", version: "1.0.0", name: "创始人·口播金句", category: "创始人 IP", description: "深绿商务风", status: "stable", preview_url: "/api/video-templates/founder-ip@1.0.0/preview" },
  { key: "enterprise-explainer@1.0.0", id: "enterprise-explainer", version: "1.0.0", name: "企业 AI·流程解说", category: "企业 AI 落地", description: "浅色清晰风格", status: "stable" },
];

const task = {
  content_id: "20261029-001", title: "模板测试", state: "assets_approved", pillar: "enterprise_ai", audience: "business_owners",
  scripts: { master: "口播" }, asset_plan: [], quality: {}, publications: {}, metrics: {}, retrospective: "", events: [], updated_at: "2026-10-29",
  files: [{ id: 9, kind: "video", original_name: "founder.mp4", relative_path: "renders/founder.mp4", url: "/api/files/9/media", download_url: "/api/files/9/media?download=1", media_info: { duration_seconds: 2 } }],
  render_runs: [{ id: "run-1", template_id: "founder-ip", template_version: "1.0.0", status: "cached", output_file_id: 9, created_at: "2026-10-29" }],
};

function preview(template: string, approved = false) {
  return { id: `vp-${template}`, status: "succeeded", approved, approved_at: approved ? "2026-10-30" : null, video_url: "/api/files/10/media", fingerprint: "a".repeat(64), request: { mode: "remotion", platform: "douyin", template_ids: [template] } };
}

function setup(group = 2) {
  const fetchMock = vi.fn().mockImplementation(async (url: string, options?: RequestInit) => {
    if (url.endsWith("/jobs")) return { ok: true, json: async () => ({ jobs: [] }) };
    if (url.includes("/visual-previews/") && url.endsWith("/approve")) {
      const template = url.includes("enterprise") ? "enterprise-explainer@1.0.0" : "founder-ip@1.0.0";
      return { ok: true, json: async () => ({ preview: preview(template, true), job: null }) };
    }
    if (url.endsWith("/visual-previews")) {
      const body = JSON.parse(String(options?.body));
      return { ok: true, json: async () => ({ preview: preview(body.template_ids[0]), job: null }) };
    }
    return { ok: true, json: async () => ({}) };
  });
  vi.stubGlobal("fetch", fetchMock);
  const request = vi.fn().mockResolvedValue(true);
  const action = vi.fn().mockResolvedValue(true);
  render(<VideoStages group={group} task={task} core={{ render_ai: { ready: true, status: "已连接" }, video_templates: templates }} busy="" request={request} action={action} />);
  return { request, action, fetchMock };
}

describe("Video visual preview workflow", () => {
  it("automatically previews the selected style and only produces after approval", async () => {
    const { request, fetchMock } = setup(2);
    expect(screen.getByAltText("创始人·口播金句 真实渲染预览")).toHaveAttribute("src", "/api/video-templates/founder-ip@1.0.0/preview");
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/tasks/20261029-001/visual-previews", expect.objectContaining({ method: "POST" })));
    fireEvent.click(screen.getByRole("radio", { name: /企业 AI·流程解说/ }));
    await waitFor(() => expect(fetchMock.mock.calls.some(([, options]) => JSON.parse(String(options?.body || "{}")).template_ids?.[0] === "enterprise-explainer@1.0.0")).toBe(true));
    fireEvent.click(await screen.findByRole("button", { name: "确认效果并生成成片" }));
    await waitFor(() => expect(request).toHaveBeenCalled());
    const [, path, options] = request.mock.calls[0];
    expect(path).toBe("/api/tasks/20261029-001/produce");
    expect(JSON.parse(options.body).template_ids).toEqual(["enterprise-explainer@1.0.0"]);
  });

  it("hides template selection for FFmpeg upload mode", () => {
    setup(2);
    fireEvent.change(screen.getByLabelText("渲染模式"), { target: { value: "upload" } });
    expect(screen.queryByText("选择视觉风格 · 自动预览")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "开始渲染 MP4" })).toBeInTheDocument();
  });

  it("shows render history in the production stage", () => {
    setup(2);
    expect(screen.getByText("渲染历史")).toBeInTheDocument();
    expect(screen.getByText("缓存")).toBeInTheDocument();
  });
});
