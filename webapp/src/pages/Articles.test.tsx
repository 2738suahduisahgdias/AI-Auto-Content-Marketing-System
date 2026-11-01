import { fireEvent, render, screen, cleanup } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { describe, expect, it, vi, afterEach } from "vitest";
import Articles from "./Articles";

const revision = (id: string, kind: string, text = "正文") => ({ id, kind, payload: { text, markdown_asset_id: undefined as string | undefined, html_asset_id: undefined as string | undefined } });
const makeItem = (index: number) => ({
  id: `article-${index}`, state: index === 0 ? "exported" : "draft", version: 1,
  campaign: { title: `文章 ${index}`, brief: { text: "真实需求" } },
  active_revisions: index === 0 ? { outline: "outline-0", draft: "draft-0", export: "export-0" } : { draft: `draft-${index}` },
  revisions: index === 0 ? [revision("outline-0", "outline", "一、第一段\n\n二、第二段"), revision("draft-0", "draft", "完整正文"), revision("export-0", "export", "", )] : [revision(`draft-${index}`, "draft")],
  publications: [], manifest: { hash: "hash" },
});
const items = Array.from({ length: 12 }, (_, index) => makeItem(index));
items[0].revisions[2].payload = { text: "", markdown_asset_id: "markdown-1", html_asset_id: "html-1" };

vi.mock("@/AppContext", () => ({
  useApp: () => ({
    resources: { articles: { items, jobs: [] }, core: { tasks: [] } },
    refresh: vi.fn(), run: vi.fn(), notify: vi.fn(),
  }),
}));

afterEach(()=>{cleanup();vi.restoreAllMocks()});
const renderArticles=(path="/articles/article-0")=>render(<MemoryRouter initialEntries={[path]}><Routes><Route path="/articles/:id?" element={<Articles/>}/></Routes></MemoryRouter>);
describe("Articles delivery and pagination", () => {
  it("keeps real exports in delivery and paginates the task list", () => {
    const { container } = renderArticles();
    fireEvent.click(screen.getByRole("button", { name: "排版交付" }));
    expect(screen.getByText("交付文档")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "下载 Markdown" })).toHaveAttribute("href", "/api/v2/assets/markdown-1/content?download=1");
    expect(screen.getByRole("link", { name: "下载 HTML" })).toHaveAttribute("href", "/api/v2/assets/html-1/content?download=1");
    fireEvent.click(screen.getByRole("button", { name: "写文案" }));
    expect(container.querySelector(".article-outline-editor")).toHaveValue("一、第一段\n\n二、第二段");
    expect(container.querySelector(".article-outline-editor")).toHaveClass("textarea");
    expect(container.querySelector(".article-draft-editor")).toHaveClass("textarea");
    expect(screen.getByText("5 交付文档")).toHaveAttribute("aria-current", "step");
    expect(screen.queryByRole("button", { name: "记录真实发布" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "← 返回文章列表" }));
    fireEvent.click(screen.getByRole("button", { name: "下一页" }));
    expect(screen.getByText("2 / 2 页")).toBeInTheDocument();
    expect(screen.getByText("文章 11")).toBeInTheDocument();
  });
});

it("filters titles and protects unsaved text on return",()=>{
 const {container}=renderArticles();
 fireEvent.change(container.querySelector('.article-draft-editor')!,{target:{value:'未保存正文'}});
 const confirm=vi.spyOn(window,'confirm').mockReturnValue(false);
 fireEvent.click(screen.getByRole('button',{name:'← 返回文章列表'}));
 expect(confirm).toHaveBeenCalled();
 expect(container.querySelector('.article-draft-editor')).toHaveValue('未保存正文');
 confirm.mockReturnValue(true);
 fireEvent.click(screen.getByRole('button',{name:'← 返回文章列表'}));
 fireEvent.change(screen.getByRole('textbox',{name:'搜索文章'}),{target:{value:'文章 11'}});
 expect(screen.getByText('文章 11')).toBeInTheDocument();
 expect(screen.queryByText('文章 0')).not.toBeInTheDocument();
});
