import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PublishingPanel } from "./PublishingPanel";

const { apiMock, notifyMock, publishKnowledge } = vi.hoisted(() => {
  const field = (name: string, label: string, values: Record<string, any> = {}) => ({ name, label, control: "text", group: "basic", required: false,
    max_length: null, default: "", agent_generated: false, sync_status: "connected", verification: "verified", description: "", options: [], ...values });
  const officialFields = [
    field("title", "文章标题", { required: true, max_length: 64, agent_generated: true }),
    field("author", "作者", { max_length: 8, default: "刘量", agent_generated: true }),
    field("body", "文章正文", { control: "textarea", required: true, agent_generated: true }),
    field("summary", "摘要", { control: "textarea", max_length: 120, agent_generated: true }),
    field("cover_asset_id", "正文封面", { control: "asset", group: "media", required: true }),
    field("original", "声明原创", { control: "boolean", group: "settings", default: false, sync_status: "stored" }),
    field("comments_enabled", "开启留言", { control: "boolean", group: "settings", default: true, sync_status: "stored" }),
  ];
  return { apiMock: vi.fn(), notifyMock: vi.fn(), publishKnowledge: { platforms: [
    { platform: "wechat_official_account", content_types: [{ content_kind: "article", fields: officialFields, media: {} }] },
    { platform: "douyin", content_types: [{ content_kind: "video", media: { evidence: "1 小时、16GB" }, fields: [
      field("title", "作品标题", { required: true, max_length: 30, agent_generated: true }),
      field("description", "作品描述", { control: "textarea", required: true, max_length: 1000, agent_generated: true }),
      field("video_path", "已审核视频", { control: "source", group: "media", required: true }),
      field("cover_asset_id", "竖版封面（3:4）", { control: "asset", group: "media", sync_status: "stored" }),
      field("collection_name", "合集名称", { group: "settings", sync_status: "stored" }),
    ] }] },
    { platform: "xiaohongshu", content_types: [{ content_kind: "article", media: {}, fields: [
      field("title", "长文标题", { required: true, max_length: 20, agent_generated: true }),
      field("body", "长文正文", { control: "textarea", required: true, max_length: 6000, agent_generated: true }),
    ] }, { content_kind: "video", media: {}, fields: [
      field("title", "笔记标题", { required: true, max_length: 20, agent_generated: true }),
      field("description", "笔记正文", { control: "textarea", required: true, max_length: 1000, agent_generated: true }),
      field("original", "原创声明", { control: "boolean", group: "settings", default: false, sync_status: "stored" }),
    ] }] },
    { platform: "wechat_channels", content_types: [{ content_kind: "video", media: {}, fields: [
      field("short_title", "短标题", { required: true, max_length: 16, agent_generated: true }),
      field("description", "视频描述", { control: "textarea", required: true, max_length: 2000, agent_generated: true }),
      field("location_name", "位置", { group: "settings", sync_status: "stored" }),
      field("link_url", "链接", { control: "url", group: "settings", sync_status: "stored" }),
      field("scheduled_at", "定时发布", { control: "datetime", group: "settings", sync_status: "stored" }),
    ] }] },
  ] } };
});

vi.mock("@/AppContext", () => ({
  useApp: () => ({ run: (action: () => Promise<unknown>) => action(), notify: notifyMock,
    resources: { accounts: { publish_knowledge: publishKnowledge } } }),
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

afterEach(async()=>{await act(async()=>{cleanup()})});

describe("PublishingPanel", () => {
  beforeEach(() => {
    cleanup();
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
    expect(screen.queryByRole("checkbox", { name: /声明原创/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("checkbox", { name: /开启留言/ })).not.toBeInTheDocument();
    await user.click(generate);
    expect(await screen.findByDisplayValue("生成后的公众号标题")).toBeInTheDocument();
    expect(screen.getByDisplayValue("生成后的正文")).toBeInTheDocument();
    expect(screen.getByText("1 个平台未保存")).toBeInTheDocument();
    expect(notifyMock).toHaveBeenCalledWith("发布字段已回填并自动保存本机草稿；请检查后保存正式批次，不会自动发布");
    expect(apiMock).not.toHaveBeenCalledWith(expect.stringContaining("/confirm"), expect.anything());
    await user.click(screen.getByRole("button", { name: "保存文章批次" }));
    await waitFor(() => expect(apiMock).toHaveBeenCalledWith("/api/publishing/batches", expect.anything()));
    const call = apiMock.mock.calls.find(([path]) => path === "/api/publishing/batches");
    if (!call) throw new Error("没有保存发布批次");
    const request = JSON.parse(call[1].body);
    const official = request.targets.find((target: any) => target.platform === "wechat_official_account");
    expect(official.payload.original).toBeUndefined();
    expect(official.payload.comments_enabled).toBeUndefined();
    expect(official.payload.manual_transfer).toBe(true);
    expect(official.payload.title).toBe("生成后的公众号标题");
    await waitFor(()=>expect(screen.getByRole("button",{name:"保存文章批次"})).toBeEnabled());
  });

  it("renders independent video fields and limits for each platform", async () => {
    render(<MemoryRouter><PublishingPanel kind="video" source={{ id: "video-1", title: "视频标题", body: "视频简介" }} /></MemoryRouter>);
    await waitFor(() => expect(apiMock).toHaveBeenCalledWith(expect.stringContaining("/api/publishing/bootstrap")));
    expect(screen.getByText("作品标题（必填） · 最多 30 字")).toBeInTheDocument();
    expect(screen.getByText("笔记标题（必填） · 最多 20 字")).toBeInTheDocument();
    expect(screen.getByText("短标题（必填） · 最多 16 字")).toBeInTheDocument();
    expect(screen.queryByText("1 小时、16GB")).not.toBeInTheDocument();
    expect(screen.queryByText("竖版封面（3:4）")).not.toBeInTheDocument();
    expect(screen.queryByText("链接")).not.toBeInTheDocument();

    expect(screen.queryByText(/最多 300 字/)).not.toBeInTheDocument();
    expect(screen.queryByText(/最多 5000 字/)).not.toBeInTheDocument();
  });
  it("blocks public confirmation when the runtime executor is disabled", async () => {
    apiMock.mockResolvedValue({execution_enabled:false,field_jobs:[],batch:{id:"batch",source_hash:"hash",targets:[{id:"target",platform:"xiaohongshu",status:"ready",payload:{title:"验收",body:"正文"}}]}});
    render(<MemoryRouter><PublishingPanel kind="article" source={{id:"article-1",title:"验收",body:"正文"}} /></MemoryRouter>);
    await screen.findByRole("button",{name:"一键同步到后台"});
    expect(screen.queryByRole("button",{name:/确认公开发布/})).not.toBeInTheDocument();

  });

  it("saves before syncing and excludes restricted WeChat targets", async () => {
    const user = userEvent.setup();
    apiMock.mockImplementation((path:string)=>Promise.resolve(path.includes("bootstrap") ? {batch:null,field_jobs:[]} : {id:"batch-1",targets:[]}));
    render(<MemoryRouter><PublishingPanel kind="article" source={{id:"article-1",title:"测试",body:"正文"}} /></MemoryRouter>);
    await user.click(await screen.findByRole("button",{name:"一键同步到后台"}));
    await waitFor(()=>expect(apiMock).toHaveBeenCalledWith("/api/publishing/batches/batch-1/prepare",expect.anything()));
    const calls=apiMock.mock.calls;
    expect(calls.findIndex(c=>c[0]==="/api/publishing/batches")).toBeLessThan(calls.findIndex(c=>c[0].endsWith("/prepare")));
    expect(JSON.parse(calls.find(c=>c[0].endsWith("/prepare"))![1].body).platforms).toEqual(["xiaohongshu"]);
    expect(screen.getAllByRole("button",{name:"复制发布内容"})).toHaveLength(2);
    await waitFor(()=>expect(screen.getByRole("button",{name:"一键同步到后台"})).toBeEnabled());
  });

});

it("显示旧结构嵌套错误中的具体原因与处理建议",async()=>{
 apiMock.mockResolvedValue({field_jobs:[],batch:{id:"failure",source_hash:"hash",targets:[{id:"t1",platform:"douyin",status:"failed",payload:{title:"验收",description:"正文"},error:{error:{code:"UPLOAD_NOT_READY",message:"平台仍在处理上传视频",action:"处理完成后重试续填"}}}]}});
 render(<MemoryRouter><PublishingPanel kind="video" source={{id:"video-1",title:"验收",body:"正文"}}/></MemoryRouter>);
 expect(await screen.findByText(/平台仍在处理上传视频/)).toBeInTheDocument();
 expect(screen.getByText(/处理完成后重试续填/)).toBeInTheDocument();
});
