import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import DownloadProbeModal from "./DownloadProbeModal";
import type { Job, TopicItem } from "@/lib/types";

afterEach(cleanup);

const item = { id: "research-xhs", title: "真实作品", platform: "xiaohongshu" } as TopicItem;
const baseJob = { id: "job-probe", kind: "research.probe", aggregate_id: item.id, status: "succeeded", result: { media_kind: "video", title: "真实作品", formats: [{ id: "current", label: "1080P 高清", width: 1080, height: 1920 }] }, error: {} } as unknown as Job;

describe("DownloadProbeModal", () => {
  it("shows a terminal probe failure instead of waiting forever", () => {
    render(<DownloadProbeModal item={item} jobs={[{ ...baseJob, status: "failed", result: {}, error: { code: "XHS_PROBE_FAILED", message: "真实探测失败" } } as Job]} busy={false} onChoose={vi.fn()} onClose={vi.fn()} />);
    expect(screen.getByText("真实探测失败")).toBeInTheDocument();
    expect(screen.queryByText(/正在通过 Kimi CLI/)).not.toBeInTheDocument();
  });

  it("lets the user choose compatibility mode after real probe results", () => {
    const onChoose = vi.fn();
    render(<DownloadProbeModal item={item} jobs={[baseJob]} busy={false} onChoose={onChoose} onClose={vi.fn()} />);
    expect(screen.getByText("1080P 高清")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "兼容优先" }));
    expect(onChoose).toHaveBeenCalledWith("compat");
  });
});
