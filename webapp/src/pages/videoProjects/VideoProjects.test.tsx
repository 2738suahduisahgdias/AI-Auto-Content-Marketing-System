import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Task } from "../../lib/types";
import { AppShell } from "../../components/AppShell";
import VideoProjectHome from "./VideoProjectHome";
import OriginalProject, { CreateOriginal, NarrationStage } from "./OriginalProject";
import { MusicStage, SampleStage } from "./ProjectShared";
import { ReportStage, ShotEditor } from "./BenchmarkProject";
import { projectType, sampleApproved, shotReady, type ProjectFile, type ProjectSnapshot } from "./useVideoProject";

const state = vi.hoisted(() => ({
  resources: { core: { tasks: [] as Task[] } },
  refresh: vi.fn(),
}));

vi.mock("@/AppContext", () => ({
  useApp: () => ({ resources: state.resources, loading: false, loadError: "", notice: null, refresh: state.refresh }),
}));

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  state.resources = { core: { tasks: [] } };
  state.refresh.mockReset();
});

function makeTask(values: Partial<Task> = {}): Task {
  return {
    content_id: "project-1",
    title: "真实项目",
    state: "topic_approved",
    pillar: "enterprise_ai",
    audience: "business_owners",
    scripts: { master: "正式文案" },
    files: [],
    asset_plan: [],
    quality: {},
    publications: {},
    metrics: {},
    retrospective: "",
    events: [],
    updated_at: "2026-11-05T10:00:00",
    ...values,
  };
}

function makeSnapshot(values: Partial<ProjectSnapshot> = {}): ProjectSnapshot {
  return {
    workflow_stage: 0,
    manuscript: { title: "真实项目", text: "正式文案" },
    shots: [],
    ...values,
  };
}

function makeFile(id: number, kind = "video", values: Record<string, unknown> = {}): ProjectFile {
  return {
    id,
    kind,
    original_name: `${kind}-${id}.mp4`,
    url: `/api/files/${id}/media`,
    media_info: { duration_seconds: 4, streams: [{ codec_type: kind === "audio" ? "audio" : "video" }], ...values },
  };
}

describe("视频项目导航与首页", () => {
  it("主项进入项目首页，并提供原创和对标子菜单", async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><AppShell><div>内容</div></AppShell></MemoryRouter>);
    vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);
    expect(screen.getByRole("link", { name: "视频项目" })).toHaveAttribute("href", "/projects");
    await user.click(screen.getByRole("button", { name: "展开视频项目" }));
    expect(screen.getByRole("link", { name: "原创" })).toHaveAttribute("href", "/projects/original");
    expect(screen.getByRole("link", { name: "对标" })).toHaveAttribute("href", "/projects/benchmark");
  });

  it("按真实项目类型过滤，并链接到对应项目编号", async () => {
    const original = makeTask({ content_id: "old-001", source: { type: "manual" } });
    const benchmark = makeTask({ content_id: "benchmark-002", title: "参考项目", source: { project_type: "benchmark" } });
    state.resources = { core: { tasks: [original, benchmark] } };
    render(<MemoryRouter><VideoProjectHome /></MemoryRouter>);
    expect(projectType(original)).toBe("original");
    expect(screen.getByRole("link", { name: /old-001/ })).toHaveAttribute("href", "/projects/original/old-001");
    fireEvent.change(screen.getByLabelText("项目类型"), { target: { value: "benchmark" } });
    expect(screen.queryByText("old-001")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /benchmark-002/ })).toHaveAttribute("href", "/projects/benchmark/benchmark-002");
  });
});

describe("原创流程门槛", () => {
  it("缺少正式文案、平台或画幅时不创建项目，叙事方向可留空", async () => {
    const created = vi.fn();
    render(<CreateOriginal onCreated={created} />);
    await userEvent.click(screen.getByRole("button", { name: "确认方案，进入视频生成 →" }));
    expect(screen.getByRole("alert")).toHaveTextContent("文案、目标平台、画幅");
    expect(screen.getByRole("alert")).not.toHaveTextContent("叙事方向");
    expect(created).not.toHaveBeenCalled();
  });

  it("创建成功后先刷新真实项目列表再进入项目", async () => {
    const task = makeTask({ content_id: "new-001" });
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async () => new Response(JSON.stringify(task), { status: 200 })));
    const created = vi.fn();
    render(<CreateOriginal onCreated={created} />);
    fireEvent.change(screen.getByLabelText(/叙事方向/), { target: { value: "真实方向" } });
    fireEvent.change(screen.getByLabelText(/正式文案/), { target: { value: "真实文案" } });
    fireEvent.click(screen.getByLabelText("抖音"));
    fireEvent.click(screen.getByLabelText("竖屏 9:16 · 1080 × 1920"));
    await userEvent.click(screen.getByRole("button", { name: "确认方案，进入视频生成 →" }));
    await waitFor(() => expect(created).toHaveBeenCalledWith(task));
    expect(state.refresh).toHaveBeenCalled();
    expect(state.refresh.mock.invocationCallOrder[0]).toBeLessThan(created.mock.invocationCallOrder[0]);
    const saveCall = vi.mocked(fetch).mock.calls.find(call => String(call[0]).endsWith("/yingxu"));
    expect(JSON.parse(String(saveCall?.[1]?.body)).snapshot.workflow_stage).toBe(1);
  });

  it("完整手写文案不要求叙事方向也可以进入下一步", async () => {
    const task = makeTask({ content_id: "manual-001" });
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async () => new Response(JSON.stringify(task), { status: 200 })));
    const created = vi.fn();
    render(<CreateOriginal onCreated={created} />);
    fireEvent.change(screen.getByLabelText(/正式文案/), { target: { value: "这是一份完整的人工文案" } });
    fireEvent.click(screen.getByLabelText("抖音"));
    fireEvent.click(screen.getByLabelText("竖屏 9:16 · 1080 × 1920"));
    await userEvent.click(screen.getByRole("button", { name: "确认方案，进入视频生成 →" }));
    await waitFor(() => expect(created).toHaveBeenCalledWith(task));
  });

  it("文案为空时按方向生成，已有文案时明确为改写，候选采用后才替换", async () => {
    const task = makeTask({ content_id: "ai-001", source: { yingxu: { revision: 0 } } });
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async input => new Response(JSON.stringify(String(input).includes("yingxu-script-candidate") ? { candidate: "AI 生成文案" } : task), { status: 200 })));
    render(<CreateOriginal onCreated={vi.fn()} />);
    expect(screen.getByRole("button", { name: "根据叙事方向生成候选文案" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/正式文案/), { target: { value: "已有文案" } });
    expect(screen.getByRole("button", { name: "根据叙事方向改写当前文案" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/正式文案/), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText(/叙事方向/), { target: { value: "真实叙事方向" } });
    await userEvent.click(screen.getByRole("button", { name: "根据叙事方向生成候选文案" }));
    expect(await screen.findByLabelText("AI 候选稿")).toHaveValue("AI 生成文案");
    await userEvent.click(screen.getByRole("button", { name: "采用为正式文案" }));
    expect(screen.getByLabelText(/正式文案/)).toHaveValue("AI 生成文案");
  });

  it("项目列表未刷新时直接从原项目接口恢复页面", async () => {
    const task = makeTask({ content_id: "direct-001", title: "直接恢复项目" });
    const request = vi.fn().mockResolvedValue(new Response(JSON.stringify(task), { status: 200 }));
    vi.stubGlobal("fetch", request);
    render(<MemoryRouter initialEntries={["/projects/original/direct-001"]}><Routes><Route path="/projects/original/:id" element={<OriginalProject />} /></Routes></MemoryRouter>);
    expect(await screen.findByText("direct-001 · 直接恢复项目")).toBeInTheDocument();
    expect(request).toHaveBeenCalledWith("/api/tasks/direct-001", expect.anything());
  });

  it("未上传真人旁白时不能生成词级时间码或继续", () => {
    render(<NarrationStage task={makeTask()} snapshot={makeSnapshot()} update={vi.fn()} onBack={vi.fn()} onNext={vi.fn()} />);
    expect(screen.getByRole("button", { name: "生成词级时间码（必需）" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "确认旁白与时长 →" })).toBeDisabled();
  });

  it("只有真实适配版本存在时才允许确认音乐", async () => {
    const voice = makeFile(10, "audio");
    const originalMusic = makeFile(11, "audio");
    const adapted = makeFile(12, "audio", { adapted_from: 11, duration_seconds: 4 });
    const task = makeTask({ files: [voice, originalMusic, adapted] });
    const props = { task, update: vi.fn(), save: vi.fn(), onBack: vi.fn(), onNext: vi.fn() };
    const { rerender } = render(<MusicStage {...props} snapshot={makeSnapshot({ voiceFileId: 10, bgmFileId: 11 })} />);
    expect(screen.getByRole("button", { name: "确认适配效果" })).toBeDisabled();
    rerender(<MusicStage {...props} snapshot={makeSnapshot({ voiceFileId: 10, bgmFileId: 12, musicAdaptedFileId: 12 })} />);
    const confirm = screen.getByRole("button", { name: "确认适配效果" });
    expect(confirm).toBeEnabled();
    await userEvent.click(confirm);
    expect(props.update).toHaveBeenCalledWith(expect.objectContaining({ musicConfirmed: true }));
  });

  it("Kimi 生成配乐后选择新的真实音频文件", async () => {
    const voice = makeFile(10, "audio");
    const generated = makeFile(12, "audio", { provider: "kimi_cli", renderer: "local_score_synth" });
    const resultTask = makeTask({ files: [voice, generated] });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(resultTask), { status: 200 })));
    const props = { task: makeTask({ files: [voice] }), update: vi.fn(), save: vi.fn().mockResolvedValue(makeTask()), onBack: vi.fn(), onNext: vi.fn() };
    render(<MusicStage {...props} snapshot={makeSnapshot({ voiceFileId: 10, musicDirection: "平静" })} />);
    await userEvent.click(screen.getByRole("button", { name: "✦ AI 生成配乐（Kimi）" }));
    await waitFor(() => expect(props.update).toHaveBeenCalledWith(expect.objectContaining({ bgmFileId: 12, musicConfirmed: false })));
    expect(fetch).toHaveBeenCalledWith(expect.stringContaining("music-generate"), expect.anything());
  });

  it("多镜样片逐条真实生成，全部通过才算完成", async () => {
    const task = makeTask({ source: { yingxu: { revision: 3 } } });
    const snapshot = makeSnapshot({ shots: [
      { id: "a", title: "镜头 A", text: "A", desc: "A", duration: 1, source: "Remotion 代码" },
      { id: "b", title: "镜头 B", text: "B", desc: "B", duration: 1, source: "Remotion 代码" },
    ] });
    const update = vi.fn();
    let id = 20;
    const response = () => new Response(JSON.stringify(makeFile(id++)), { status: 200 });
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async () => response()));
    render(<SampleStage task={task} snapshot={snapshot} update={update} save={vi.fn().mockResolvedValue(task)} />);
    await userEvent.click(screen.getByLabelText("镜头 A"));
    await userEvent.click(screen.getByLabelText("镜头 B"));
    await userEvent.click(screen.getByRole("button", { name: "生成样片" }));
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    expect(update).toHaveBeenCalledWith(expect.objectContaining({ sampleFileIds: [20, 21], sampleApprovedFileIds: [] }));
    expect(sampleApproved({ ...snapshot, sampleFileIds: [20, 21], sampleApprovedFileIds: [20] })).toBe(false);
    expect(sampleApproved({ ...snapshot, sampleFileIds: [20, 21], sampleApprovedFileIds: [20, 21] })).toBe(true);
  });
});

describe("词级时间码后台进度", () => {
  it("显示真实转写百分比并在完成后保存词语", async () => {
    let finish: (value: Response) => void = () => undefined;
    const pending = new Promise<Response>(resolve => { finish = resolve; });
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async input => {
      const url = String(input);
      if (url.endsWith("/transcript") && !url.includes("jobs")) return new Response(JSON.stringify({ id: "job-1", status: "queued", progress: 0 }), { status: 202 });
      if (url.endsWith("/transcript-jobs/job-1")) {
        if (vi.mocked(fetch).mock.calls.filter(call => String(call[0]).endsWith("/transcript-jobs/job-1")).length === 1) return new Response(JSON.stringify({ id: "job-1", status: "running", stage: "transcribing", progress: 0.5 }), { status: 200 });
        return pending;
      }
      throw new Error("unexpected request " + url);
    }));
    const update = vi.fn();
    render(<NarrationStage task={makeTask({ files: [makeFile(10, "audio")] })} snapshot={makeSnapshot({ voiceFileId: 10 })} update={update} onBack={vi.fn()} onNext={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "生成词级时间码（必需）" }));
    await waitFor(() => expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "50"));
    expect(screen.getByText(/转写中 · 50% · 已用/)).toBeInTheDocument();
    finish(new Response(JSON.stringify({ id: "job-1", status: "succeeded", progress: 1, result: { words: [{ text: "真实", start: 0, end: 0.4 }] } }), { status: 200 }));
    await waitFor(() => expect(update).toHaveBeenCalledWith(expect.objectContaining({ transcript: expect.objectContaining({ words: [{ text: "真实", start: 0, end: 0.4 }] }) })));
  });
});

describe("对标报告与逐镜版本", () => {
  it("点击报告卡片跳转到该镜真实开始时间", async () => {
    const play = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(HTMLMediaElement.prototype, "play", { configurable: true, value: play });
    const reference = makeFile(1);
    const snapshot = makeSnapshot({
      workflow_stage: 1,
      transcript_runs: 1,
      benchmark_report: { source_file_id: 1, usage_boundary: "本人制作", duration_seconds: 8, transcript_status: "succeeded", scene_detection: "ffmpeg_scene_0.25" },
      shots: [{ id: "scene-1", title: "镜头 01", text: "真实转写", desc: "人工说明", visual_observation: "真实关键帧", duration: 2, source: "reference", original_start_seconds: 3.5, original_end_seconds: 5.5 }],
    });
    render(<ReportStage task={makeTask({ files: [reference] })} snapshot={snapshot} update={vi.fn()} onBack={vi.fn()} onNext={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "镜头 1，跳转到 3.5 秒" }));
    expect(screen.getByLabelText("拆解报告完整视频")).toHaveProperty("currentTime", 3.5);
    expect(play).toHaveBeenCalled();
  });

  it("原片信息只读，用户上传版本可独立切换", () => {
    const update = vi.fn();
    const files = [makeFile(1), makeFile(2), makeFile(3)];
    const snapshot = makeSnapshot({
      workflow_stage: 2,
      benchmark_report: { source_file_id: 1, usage_boundary: "本人制作", duration_seconds: 1, transcript_status: "not_applicable", scene_detection: "ffmpeg_scene_0.25" },
      shots: [{ id: "scene-1", title: "镜头 01", text: "原旁白", desc: "原说明", duration: 1, source: "user_upload", fileId: 2, uploadedFileIds: [2, 3], original_start_seconds: 0, original_end_seconds: 1, audio_source: "original", duration_choice: "original" }],
    });
    render(<ShotEditor task={makeTask({ files })} snapshot={snapshot} files={files} selected={0} update={update} save={vi.fn()} onClose={vi.fn()} />);
    expect(screen.getByText("原片时间码保持不变，原片信息只读。")).toBeInTheDocument();
    expect(screen.getByText("原片旁白：原旁白")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("用户上传版本"), { target: { value: "3" } });
    const patch = update.mock.calls.at(-1)?.[0];
    expect(patch.shots[0]).toEqual(expect.objectContaining({ fileId: 3, source: "user_upload", confirmed: false }));
  });

  it("短视频未选择补足方式、替换旁白缺少音频时不能确认", () => {
    const file = makeFile(2, "video", { duration_seconds: 1 });
    const base = { id: "one", title: "镜头", text: "", desc: "", duration: 4, source: "user_upload", fileId: 2, duration_choice: "original" as const, audio_source: "mute" as const };
    expect(shotReady(base, [file])).toBe(false);
    expect(shotReady({ ...base, fill_method: "freeze" }, [file])).toBe(true);
    expect(shotReady({ ...base, duration: 1, audio_source: "replace" }, [file])).toBe(false);
  });
});
