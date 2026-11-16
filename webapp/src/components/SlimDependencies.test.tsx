import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import SlimDependencies from "./SlimDependencies";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({ api: vi.fn(), errorText: (error: unknown) => String(error), jsonOptions: (method: string) => ({ method }) }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

const pending = {
  slim: true,
  edition: "精简版",
  required: true,
  complete: false,
  running: false,
  items: [{ id: "whisper", label: "Whisper 字幕模型", estimate: "约 1.2 GB", status: "pending" }],
  completed: 0,
  total: 1,
  error: null,
};

describe("SlimDependencies", () => {
  it("starts the real download request and shows progress", async () => {
    vi.mocked(api).mockImplementation(async (_path, options) => options?.method === "POST" ? { ...pending, running: true, active: "whisper", items: [{ ...pending.items[0], status: "running" }] } : pending);
    render(<SlimDependencies />);
    expect(await screen.findByText("首次使用需要下载本地资源")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "下载全部本地资源" }));
    expect(await screen.findByText("正在下载全部资源")).toBeInTheDocument();
    expect(vi.mocked(api)).toHaveBeenCalledWith("/api/slim-dependencies", { method: "POST" });
  });

  it("does not show the prompt after all resources are ready", async () => {
    vi.mocked(api).mockResolvedValue({ ...pending, required: false, complete: true, items: [{ ...pending.items[0], status: "succeeded" }], completed: 1 });
    const { container } = render(<SlimDependencies />);
    await waitFor(() => expect(vi.mocked(api)).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});
