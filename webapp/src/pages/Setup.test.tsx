import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import Setup from "./Setup";

vi.mock("@/AppContext", () => ({ useApp: () => ({ run: vi.fn() }) }));
vi.mock("@/lib/api", async importOriginal => ({ ...await importOriginal<typeof import("@/lib/api")>(), api: vi.fn().mockResolvedValue({
  os_name: "macOS", python_version: "3.9.6", local_url: "http://127.0.0.1:8765/", core_ready: true,
  boundary: "不读取账号凭据",
  dependencies: [{ name: "Python 3.9+", installed: true, required: true, action: "安装 Python" }],
  platforms: ["douyin", "xiaohongshu", "wechat_channels", "wechat_official_account"].map(platform => ({ platform, name: { douyin: "抖音", xiaohongshu: "小红书", wechat_channels: "视频号", wechat_official_account: "公众号" }[platform], status: "not_verified", verified: false, action: "本人扫码" })),
}) }));
afterEach(cleanup);

describe("Setup", () => {
  it("shows environment and all four platform login entries", async () => {
    render(<MemoryRouter><Setup /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText("核心环境已就绪")).toBeInTheDocument());
    for (const name of ["抖音", "小红书", "视频号", "公众号"]) expect(screen.getByText(name)).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "打开登录窗口" })).toHaveLength(4);
    expect(screen.getByText("不读取账号凭据")).toBeInTheDocument();
  });
});
