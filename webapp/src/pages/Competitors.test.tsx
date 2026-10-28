import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import Competitors from "./Competitors";

afterEach(cleanup);

describe("Competitors demo", () => {
  it("filters public accounts and inspects content without inventing metrics", async () => {
    const user = userEvent.setup();
    render(<MemoryRouter initialEntries={["/competitors?demo=1"]}><Competitors /></MemoryRouter>);
    await user.click(screen.getByRole("tab", { name: "小红书" }));
    expect(screen.getByText("FDE观察室")).toBeInTheDocument();
    expect(screen.queryByText("AI落地研究所")).not.toBeInTheDocument();
    expect(screen.getByText("企业AI试点复盘：我们砍掉了这3个场景")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "研究 企业AI试点复盘：我们砍掉了这3个场景" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("无公开数据，不推测")).toBeInTheDocument();
    expect(screen.getByText("策略拆解")).toBeInTheDocument();
  });
});
