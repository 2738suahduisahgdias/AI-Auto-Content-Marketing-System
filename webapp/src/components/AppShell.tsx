import { useState, type ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { NavLink, useLocation } from "react-router-dom";
import * as Dialog from "@radix-ui/react-dialog";
import { Bot, BookOpen, CalendarDays, FileText, Home, Library, Menu, Newspaper, PenTool, Play, Settings, Share2, ShieldCheck, TrendingUp, Video, X } from "lucide-react";
import { useApp } from "@/AppContext";
import { Busy, ErrorBox } from "@/components/ui";
import { cn } from "@/components/ui";

const groups: { label: string; items: { to: string; label: string; icon: LucideIcon; end?: boolean }[] }[] = [
  { label: "工作", items: [{ to: "/", label: "今天", icon: Home, end: true }] },
  { label: "选题", items: [
    { to: "/topics/industry", label: "行业热点", icon: Newspaper },
    { to: "/topics/douyin", label: "抖音选题", icon: TrendingUp },
    { to: "/topics/wechat", label: "视频号选题", icon: Play },
    { to: "/topics/xiaohongshu", label: "小红书选题", icon: BookOpen },
  ] },
  { label: "生产", items: [
    { to: "/articles", label: "文章任务", icon: FileText },
    { to: "/tasks", label: "视频任务", icon: Video },
  ] },
  { label: "发布", items: [
    { to: "/review", label: "审核中心", icon: ShieldCheck },
    { to: "/publish", label: "发布中心", icon: Share2 },
  ] },
  { label: "数据", items: [
    { to: "/accounts", label: "账号日报", icon: CalendarDays },
    { to: "/retrospective", label: "内容复盘", icon: TrendingUp },
  ] },
  { label: "系统", items: [
    { to: "/knowledge", label: "知识库", icon: Library },
    { to: "/settings", label: "设置", icon: Settings },
  ] },
];
const titles: Record<string, string> = { "/": "今天", "/topics/industry": "行业热点", "/topics/douyin": "抖音选题", "/topics/wechat": "视频号选题", "/topics/xiaohongshu": "小红书选题", "/accounts": "账号日报", "/retrospective": "内容复盘", "/articles": "文章任务", "/tasks": "视频任务", "/review": "短视频审核", "/publish": "发布中心", "/knowledge": "Ontology 知识库", "/settings": "设置" };

function Navigation({ onNavigate }: { onNavigate?: () => void }) {
  return <nav className="main-nav" aria-label="主导航">{groups.map(group => <div className="nav-group" key={group.label}><p>{group.label}</p>{group.items.map(({ to, label, icon: Icon, end }) => <NavLink key={to} to={to} end={end} onClick={onNavigate} className={({ isActive }) => cn("nav-link", isActive && "active")}><Icon size={16} /><span>{label}</span></NavLink>)}</div>)}</nav>;
}

export function AppShell({ children }: { children: ReactNode }) {
  const { resources, loading, loadError, notice } = useApp();
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  const basePath = "/" + location.pathname.split("/")[1];
  const title = titles[location.pathname] || titles[basePath] || "内容工作台";
  return <div className="app-shell">
    <aside className="sidebar"><NavLink to="/" className="brand"><span className="brand-symbol">L</span><span><strong>刘量</strong><small>内容增长工作台</small></span></NavLink><div className="workspace-label"><Bot size={16} /><span>多 Agent 本地工作区<small>真实数据 · 人工终审</small></span></div><Navigation /><div className="sidebar-foot"><span className="live-dot" />本地数据由你掌控<NavLink to="/legacy">打开旧版 ↗</NavLink></div></aside>
    <div className="main-shell"><header className="topbar"><Dialog.Root open={menuOpen} onOpenChange={setMenuOpen}><Dialog.Trigger className="icon-button mobile-menu" aria-label="打开导航"><Menu size={20} /></Dialog.Trigger><Dialog.Portal><Dialog.Overlay className="modal-overlay" /><Dialog.Content className="mobile-drawer"><div className="drawer-head"><strong>内容增长工作台</strong><Dialog.Close className="icon-button" aria-label="关闭"><X size={18} /></Dialog.Close></div><Navigation onNavigate={() => setMenuOpen(false)} /><NavLink to="/legacy" className="legacy-link">打开旧版 ↗</NavLink></Dialog.Content></Dialog.Portal></Dialog.Root><div><p className="topbar-date">{new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", weekday: "long" }).format(new Date())}</p><h2>{title}</h2></div><div className="topbar-meta"><PenTool size={15} /><span>Agent 生产，你来判断</span></div></header>
      <main className="page-container">{loading ? <Busy /> : loadError && !resources ? <ErrorBox>{loadError}</ErrorBox> : children}</main>
    </div>
    <nav className="mobile-bottom" aria-label="高频导航">{[{ to: "/", label: "今天", icon: Home, end: true }, { to: "/topics/douyin", label: "选题", icon: TrendingUp }, { to: "/tasks", label: "制作", icon: Video }, { to: "/publish", label: "发布", icon: Share2 }].map(({ to, label, icon: Icon, end }) => <NavLink key={to} to={to} end={end} className={({ isActive }) => cn(isActive && "active")}><Icon size={18} /><span>{label}</span></NavLink>)}</nav>
    {notice && <div className={cn("toast", notice.error && "toast-error")} role="status">{notice.text}</div>}
  </div>;
}
