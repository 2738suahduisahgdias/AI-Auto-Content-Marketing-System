import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PublishingPanel } from "./PublishingPanel";

const { apiMock, notifyMock } = vi.hoisted(() => ({ apiMock: vi.fn(), notifyMock: vi.fn() }));

vi.mock("@/AppContext", () => ({
  useApp: () => ({ run: (action: () => Promise<unknown>) => action(), notify: notifyMock }),
}));

vi.mock("@/lib/api", () => ({
  api: apiMock,
  jsonOptions: (method: string, payload?: unknown) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload ?? {}) }),
  uploadOptions: vi.fn(),
}));

const generatedJob = {
  id: "job-fields-1",
  kind: "publish.fields",
  status: "succeeded",
  stage: "succeeded",
  created_at: "2026-10-29T00:00:00Z",
  result: { platforms: { wechat_official_account: { title: "生成后的公众号标题", body: "生成后的正文", author: "刘量", summary: "生成后的摘要" } } },
};

describe("PublishingPanel", () => {
  beforeEach(() => {
    apiMock.mockReset();
    notifyMock.mockReset();
    let generated = false;
    apiMock.mockImplementation((path: string) => {
      if (path === "/api/publishing/generate-fields") {
        generated = true;
        return Promise.resolve({ ...generatedJob, status: "queued", result: null });
      }
      if (path.startsWith("/api/publishing/bootstrap")) {
        return Promise.resolve({ batch: null, field_jobs: generated ? [generatedJob] : [] });
      }
      if (path === "/api/publishing/batches") {
        return Promise.resolve({ id: "batch-1", content_kind: "article", source_id: "article-1", source_hash: "hash", status: "draft", targets: [] });
      }
      return Promise.reject(new Error(`未模拟接口：${path}`));
    });
  });

  it("fills generated fields without publishing and saves official account options", async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><PublishingPanel kind="article" source={{ id: "article-1", title: "原始标题", body: "原始正文" }} /></MemoryRouter>);
    const generate = await screen.findByRole("button", { name: "发布 Agent 生成选中平台字段" });
    await waitFor(() => expect(apiMock).toHaveBeenCalledWith(expect.stringContaining("/api/publishing/bootstrap")));
    expect(screen.getByRole("checkbox", { name: /声明原创/ })).not.toBeChecked();
    expect(screen.getByRole("checkbox", { name: "开启评论" })).toBeChecked();
    await user.click(generate);
    expect(await screen.findByDisplayValue("生成后的公众号标题")).toBeInTheDocument();
    expect(screen.getByDisplayValue("生成后的正文")).toBeInTheDocument();
    expect(screen.getByText("1 个平台未保存")).toBeInTheDocument();
    expect(notifyMock).toHaveBeenCalledWith("发布字段已回填，尚未保存或发布；请逐平台检查后保存批次");
    expect(apiMock).not.toHaveBeenCalledWith(expect.stringContaining("/confirm"), expect.anything());
    await user.click(screen.getByRole("checkbox", { name: /声明原创/ }));
    await user.click(screen.getByRole("checkbox", { name: "开启评论" }));
    await user.click(screen.getByRole("button", { name: "保存文章批次" }));
    await waitFor(() => expect(apiMock).toHaveBeenCalledWith("/api/publishing/batches", expect.anything()));
    const call = apiMock.mock.calls.find(([path]) => path === "/api/publishing/batches");
    if (!call) throw new Error("没有保存发布批次");
    const request = JSON.parse(call[1].body);
    const official = request.targets.find((target: any) => target.platform === "wechat_official_account");
    expect(official.payload.original).toBe(true);
    expect(official.payload.comments_enabled).toBe(false);
    expect(official.payload.title).toBe("生成后的公众号标题");
  });
});
