import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppShell } from "./AppShell";

afterEach(cleanup);

vi.mock("@/AppContext", () => ({
  useApp: () => ({ resources: {}, loading: false, loadError: "", notice: null }),
}));

function renderShell(route = "/") {
  return render(<MemoryRouter initialEntries={[route]}><AppShell><div>页面内容</div></AppShell></MemoryRouter>);
}

describe("AppShell topic navigation", () => {
  it("reveals platform links only after expanding the topic center", async () => {
    const user = userEvent.setup();
    renderShell();
    const trigger = screen.getByRole("button", { name: "选题中心" });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("link", { name: "行业热点" })).not.toBeInTheDocument();

    await user.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("link", { name: "行业热点" })).toHaveAttribute("href", "/topics/industry");
    expect(screen.getByRole("link", { name: "抖音选题" })).toHaveAttribute("href", "/topics/douyin");
    expect(screen.getByRole("link", { name: "视频号选题" })).toHaveAttribute("href", "/topics/wechat");
    expect(screen.getByRole("link", { name: "小红书选题" })).toHaveAttribute("href", "/topics/xiaohongshu");

    await user.click(trigger);
    expect(screen.queryByRole("link", { name: "抖音选题" })).not.toBeInTheDocument();
  });

  it("opens the topic center on a platform page and marks its active link", () => {
    renderShell("/topics/douyin");
    expect(screen.getByRole("button", { name: "选题中心" })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("link", { name: "抖音选题" })).toHaveClass("active");
  });
});

describe("AppShell analytics navigation", () => {
  it("expands account platforms and links to independent competitor analysis", async () => {
    const user = userEvent.setup();
    renderShell("/accounts/douyin");
    expect(screen.getByRole("button", { name: "账号日报" })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("link", { name: "日报总览" })).toHaveAttribute("href", "/accounts");
    expect(screen.getByRole("link", { name: "公众号" })).toHaveAttribute("href", "/accounts/wechat_official_account");
    expect(screen.getByRole("link", { name: "竞对分析" })).toHaveAttribute("href", "/competitors");

    await user.click(screen.getByRole("button", { name: "账号日报" }));
    expect(screen.queryByRole("link", { name: "日报总览" })).not.toBeInTheDocument();
  });
});
