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
    expect(screen.getByRole("link", { name: "微信选题" })).toHaveAttribute("href", "/topics/wechat");
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

describe("AppShell retired analytics navigation", () => {
 it("removes analytics while retaining topic and publishing access", () => {
  renderShell("/accounts/douyin");
  expect(screen.queryByRole("button",{name:"账号日报"})).not.toBeInTheDocument();
  expect(screen.queryByRole("link",{name:"日报总览"})).not.toBeInTheDocument();
  expect(screen.getByRole("button",{name:"选题中心"})).toBeInTheDocument();
  expect(screen.getAllByRole("link",{name:"发布中心"}).length).toBeGreaterThan(0);
 });
});
