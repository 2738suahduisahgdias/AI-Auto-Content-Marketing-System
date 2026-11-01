import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import SocialData from "./SocialData";

const { apiMock } = vi.hoisted(() => ({ apiMock: vi.fn() }));
vi.mock("@/lib/api", () => ({
  api: apiMock,
  jsonOptions: (method: string, payload: unknown) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }),
  errorText: (error: unknown) => error instanceof Error ? error.message : String(error),
}));

const supported = { id: "douyin:video/search", platform: "douyin", platform_label: "抖音", path: "video/search", kind: "search", status: "supported", executor: "browser_model" };
const unsupported = { id: "xhs:pgy/creator/profile", platform: "xhs", platform_label: "小红书", path: "pgy/creator/profile", kind: "creator_analytics", status: "adapter_required", executor: null };
const completedRun = { id: "social_1", operation_id: "douyin:video/search", status: "succeeded", provider: "kimi_cli", input: { keyword: "企业AI" },
  result: { items: [{ title: "企业 AI 为什么落不了地？", text: "真实作品摘要", author: "公开作者", canonical_url: "https://www.douyin.com/video/1" }] },
  error: {}, created_at: "2026-11-01", updated_at: "2026-11-01" };
const bootstrap = {
  platforms: [{ id: "douyin", label: "抖音" }, { id: "xhs", label: "小红书" }], items: [supported, unsupported],
  coverage: { total: 167, supported: 32, adapter_required: 135 },
  providers: { default: "kimi_cli", items: [{ id: "kimi_cli", label: "本机 Kimi CLI", available: true }, { id: "codex_cli", label: "Codex CLI（预留）", available: false, reason: "待验收" }] },
  runs: [completedRun],
};

afterEach(cleanup);
beforeEach(() => {
  apiMock.mockReset();
  apiMock.mockImplementation((path: string) => {
    if (path === "/api/social/bootstrap") return Promise.resolve(bootstrap);
    if (path === "/api/social/execute") return Promise.resolve({ run: { ...completedRun, id: "social_2", status: "queued", result: {} } });
    return Promise.reject(new Error("unexpected " + path));
  });
});

describe("SocialData", () => {
  it("shows local coverage, providers and run results", async () => {
    render(<SocialData />);
    expect(await screen.findByText("167")).toBeInTheDocument();
    expect(screen.getByText("32")).toBeInTheDocument();
    expect(screen.getByText("135")).toBeInTheDocument();
    expect(screen.getAllByText("本机 Kimi CLI").length).toBeGreaterThan(0);
    expect(screen.getByText("企业 AI 为什么落不了地？")).toBeInTheDocument();
    expect(screen.getByText("不接外部社媒数据 API，也没有积分扣费。", { exact: false })).toBeInTheDocument();
  });

  it("submits a local search and distinguishes unsupported adapters", async () => {
    const user = userEvent.setup();
    render(<SocialData />);
    const submit = await screen.findByRole("button", { name: "执行并记录结果" });
    await user.click(submit);
    await waitFor(() => expect(apiMock).toHaveBeenCalledWith("/api/social/execute", expect.objectContaining({ method: "POST" })));
    const options = apiMock.mock.calls.find(call => call[0] === "/api/social/execute")?.[1];
    expect(JSON.parse(options.body)).toMatchObject({ operation_id: "douyin:video/search", input: { keyword: "企业AI" }, provider: "kimi_cli" });

    await user.selectOptions(screen.getByLabelText("状态筛选"), "adapter_required");
    await user.click(screen.getByText("xhs:pgy/creator/profile"));
    expect(screen.getByText("这项能力还没有本地适配器")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "执行并记录结果" })).not.toBeInTheDocument();
  });
});
