import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import WechatInbox, { type WechatMessage } from "./WechatInbox";
import { api } from "@/lib/api";

vi.mock("@/AppContext", () => ({ useApp: () => ({ refresh: vi.fn().mockResolvedValue(undefined), notify: vi.fn() }) }));
vi.mock("@/lib/api", async importOriginal => ({ ...await importOriginal<typeof import("@/lib/api")>(), api: vi.fn() }));

const messages: WechatMessage[] = [{
  id: "message-1", research_item_id: "research-1", message_type: "text", raw_text: "原始想法 https://example.com/1",
  original_url: "https://example.com/1", title: "待整理灵感", note: "原始想法", category: "unclassified", category_name: "待分类",
  received_at: "今天", source_name: "微信私聊", archived: false, snapshot_status: "not_started", snapshot: {}, snapshot_error: null,
}, {
  id: "message-2", research_item_id: "research-2", message_type: "text", raw_text: "已分类想法", original_url: null,
  title: "已分类灵感", note: "已分类想法", category: "featured", category_name: "精选", received_at: "昨天", source_name: "本机手动", archived: false, snapshot_status: "not_started", snapshot: {}, snapshot_error: null,
}];

beforeEach(() => { vi.mocked(api).mockResolvedValue({ id: "saved" }); });
afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("WechatInbox", () => {
  it("edits title, note and category without changing the raw message", async () => {
    render(<WechatInbox messages={messages} onCreateTask={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "整理" }));
    expect(screen.getByText("原始想法 https://example.com/1")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("后台标题"), { target: { value: "修改后的标题" } });
    fireEvent.change(screen.getByLabelText("当时的想法 / 备注"), { target: { value: "修改后的备注" } });
    fireEvent.change(screen.getByLabelText("分类"), { target: { value: "featured" } });
    fireEvent.click(screen.getByRole("button", { name: "保存修改" }));
    await screen.findByRole("button", { name: "整理" });
    expect(vi.mocked(api)).toHaveBeenCalledWith("/api/topics/wechat/messages/message-1", expect.objectContaining({ method: "PUT" }));
    const options = vi.mocked(api).mock.calls.find(([path])=>path==="/api/topics/wechat/messages/message-1")![1] as RequestInit;
    expect(JSON.parse(String(options.body))).toEqual(expect.objectContaining({ title: "修改后的标题", note: "修改后的备注", category: "featured" }));
  });

  it("creates manual notes as unclassified and reuses the research task flow", () => {
    const onCreateTask = vi.fn();
    render(<WechatInbox messages={messages} onCreateTask={onCreateTask} />);
    fireEvent.click(screen.getByRole("button", { name: "手动记录" }));
    fireEvent.change(screen.getByLabelText("内容或当时的想法"), { target: { value: "新的随手记" } });
    fireEvent.click(screen.getByRole("button", { name: "保存到待分类" }));
    expect(vi.mocked(api)).toHaveBeenCalledWith("/api/topics/wechat/messages", expect.objectContaining({ method: "POST" }));
    fireEvent.click(screen.getByRole("button", { name: "关闭" }));
    fireEvent.click(screen.getByRole("button", { name: "转为内容任务" }));
    expect(onCreateTask).toHaveBeenCalledWith("research-1");
  });

  it("shows public link snapshots and retries failed parsing", () => {
    const snapshot = { title: "公开页标题", description: "公开页摘要", site_name: "公开媒体", cover_url: "https://example.com/cover.jpg", captured_at: "今天", limited: false };
    const { rerender } = render(<WechatInbox messages={[{ ...messages[0], snapshot_status: "succeeded", snapshot }]} onCreateTask={vi.fn()} />);
    expect(screen.getByText("公开页标题")).toBeInTheDocument();
    expect(screen.getByText("公开页摘要")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "链接封面" })).toHaveAttribute("src", snapshot.cover_url);
    rerender(<WechatInbox messages={[{ ...messages[0], snapshot_status: "failed", snapshot_error: "公开页无法读取" }]} onCreateTask={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "重新解析" }));
    expect(vi.mocked(api)).toHaveBeenCalledWith("/api/topics/wechat/messages/message-1/snapshot", expect.objectContaining({ method: "POST" }));
  });
});
