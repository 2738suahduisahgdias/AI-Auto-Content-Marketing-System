import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LeadPanel, type LeadRecord } from "./LeadPanel";
import { api } from "@/lib/api";

vi.mock("@/AppContext", () => ({ useApp: () => ({ refresh: vi.fn().mockResolvedValue(undefined), notify: vi.fn() }) }));
vi.mock("@/lib/api", async importOriginal => ({ ...await importOriginal<typeof import("@/lib/api")>(), api: vi.fn().mockResolvedValue({}) }));
afterEach(cleanup);

const lead: LeadRecord = { id: "lead-1", platform: "douyin", author_alias: "制造业老板", profile_text: "40 人企业",
  message_text: "想评估AI报价流程，下个月启动", need_text: "报价流程试点", source_content_id: null, source_url: null,
  occurred_at: "2026-10-28T02:00:00Z", stage: "inquiry", notes: "", revenue: null, deal_at: null, created_at: "2026-10-28T02:00:00Z", updated_at: "2026-10-28T02:00:00Z" };
const metrics = { inquiries: 1, qualifiedLeads: 0, highIntentLeads: 0, meetings: 0, deals: 0, revenue: null };

describe("LeadPanel", () => {
  it("records details and marks a real lead through the API", async () => {
    const user = userEvent.setup();
    render(<LeadPanel leads={[lead]} metrics={metrics} contents={[]} platform="douyin" />);
    expect(screen.getByText("制造业老板")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "详情" }));
    expect(screen.getByText("想评估AI报价流程，下个月启动")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "关闭" }));
    await user.click(screen.getByRole("button", { name: "标为有效" }));
    expect(api).toHaveBeenCalledWith("/api/accounts/leads/lead-1", expect.objectContaining({ body: expect.stringContaining('"stage":"qualified"') }));

    await user.click(screen.getByRole("button", { name: "记录私信" }));
    await user.type(screen.getByLabelText("用户别名（必填）"), "本地验收用户");
    await user.type(screen.getByLabelText("私信详情（必填）"), "希望了解企业AI落地");
    await user.click(screen.getByRole("button", { name: "保存到本机" }));
    expect(api).toHaveBeenCalledWith("/api/accounts/leads", expect.objectContaining({ body: expect.stringContaining("本地验收用户") }));
  });

  it("multi-selects and bulk deletes only chosen local leads", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<LeadPanel leads={[lead, { ...lead, id: "lead-2", author_alias: "第二条线索" }]} metrics={metrics} contents={[]} />);
    await user.click(screen.getByRole("checkbox", { name: "选择全部私信" }));
    await user.click(screen.getByRole("button", { name: "删除所选（2）" }));
    expect(api).toHaveBeenCalledWith("/api/accounts/leads/delete", expect.objectContaining({ body: expect.stringContaining("lead-2") }));
  });
});
