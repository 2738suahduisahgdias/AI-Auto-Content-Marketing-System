import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import AccountAnalytics from "./AccountAnalytics";

afterEach(cleanup);

function renderPage(route = "/accounts?demo=1") {
  return render(<MemoryRouter initialEntries={[route]}><Routes><Route path="/accounts/:view?" element={<AccountAnalytics />} /></Routes></MemoryRouter>);
}

describe("AccountAnalytics demo", () => {
  it("switches aggregate ranges and opens content evidence", async () => {
    const user = userEvent.setup();
    renderPage();
    expect(screen.getByText("产品演示 · 全部指标为模拟数据")).toBeInTheDocument();
    expect(screen.getByText("55,080")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "阅读 / 播放趋势，模拟趋势图" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "有效咨询与高意向线索趋势，模拟趋势图" })).toBeInTheDocument();
    expect(screen.getByText("线索漏斗")).toBeInTheDocument();
    expect(screen.getByText("平台线索来源")).toBeInTheDocument();
    expect(screen.getByText("最近线索样例")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "昨日" }));
    expect(screen.getByText("46,267")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "企业AI别先买工具：先画一张业务流程图" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "72 小时" }));
    expect(screen.getByText("23,140")).toBeInTheDocument();
    expect(screen.getByText("评论与需求证据")).toBeInTheDocument();
  });

  it("shows trends, native quality and public competitor boundaries on a platform", () => {
    renderPage("/accounts/xiaohongshu?demo=1");
    expect(screen.getByRole("heading", { name: "小红书日报", level: 1 })).toBeInTheDocument();
    expect(screen.getByText("封面点击率")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "互动率趋势，模拟趋势图" })).toBeInTheDocument();
    expect(screen.getByText("我的表现 vs 小红书竞对")).toBeInTheDocument();
    expect(screen.getByText(/不推测竞对播放或完播/)).toBeInTheDocument();
  });
});
