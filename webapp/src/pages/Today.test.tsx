import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import Today from "./Today";

vi.mock("@/AppContext", () => ({
  useApp: () => ({
    resources: { core: { tasks: [{ content_id: "20261027-003", title: "真实任务", state: "topic_approved", pillar: "enterprise_ai", audience: "business_owners" }] } },
  }),
}));

describe("Today", () => {
  it("links the real project to its workflow", () => {
    render(<MemoryRouter><Today /></MemoryRouter>);
    expect(screen.getByText("今天，先推进最重要的一步")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /继续这条内容/ })).toHaveAttribute("href", "/tasks/20261027-003");
    expect(screen.getAllByText("真实任务")).toHaveLength(2);
  });
});
