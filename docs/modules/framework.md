# 全局框架、导航与 Mac 客户端

更新：2026-11-10。状态：已验证，除特别注明外。逐页卡片、按钮与弹窗见 `docs/FUNCTION_MAP.md`；页面—卡片—功能—技术调用关系见 `docs/FUNCTION_MATRIX.md`。

## 作用与入口

- 新版单页工作台使用 React 19、React Router、Vite；`webapp/src/main.tsx` 以 `/demo` 为 basename，初始化本地草稿和 `AppProvider`。
- `App.tsx` 负责懒加载页面和路由；`AppShell.tsx` 负责侧栏、顶部栏、移动导航、旧版入口和全局提示；`AppContext.tsx` 聚合核心、选题、Agent、账号、文章和知识数据。
- `desktop/entry.py` 启动本地服务、工作区、Worker、调度器和随包媒体缓存。`desktop/launcher.m` 使用 APP 自己的 WebKit 窗口打开工作台；当前源码的账号采集、平台登录与发布预填使用映序专用 Chrome，固定资料保存在工作区。

## 共享代码与真实依赖

| 位置 | 责任 | 修改风险 |
|---|---|---|
| `webapp/src/App.tsx` | 页面路由、视频工作区选择、未知路由回退 | 路由变化可能影响所有深链 |
| `webapp/src/components/AppShell.tsx` | 全局导航、标题、滚动、旧版入口 | 任何修改都要跨页面回归 |
| `webapp/src/AppContext.tsx` | 数据加载、刷新、通知 | 可能改变各页数据口径和加载错误 |
| `webapp/src/components/LicenseGate.tsx` | 授权门禁 | 可能导致页面不可访问 |
| `desktop/entry.py` | 工作区、运行时、端口、锁、启动与恢复 | 影响整个客户端和数据位置 |
| `desktop/launcher.m` | WebKit 主窗口与原生文件选择 | 影响客户端可达性和文件上传 |
| `accounts/dedicated_browser.py` | 专用 Chrome 的固定资料、启动、复用、状态与正常关闭 | 影响选题、四平台登录和发布预填；不得操作日常 Chrome |
| `accounts/local_browser.py`、`topics/browser_worker.py` | CDP 页面上下文与任务结束后的连接处理 | 不得关闭共享窗口或连接非本机地址 |

## 数据与文件

- 工作区指针：`~/Library/Application Support/Yingxu/workspace.json`。
- 当前数据库：`/Volumes/CodexData/YingxuWorkspace/data/content-agent.db`。
- 会话：`data/desktop-session.json`，当前端口 8848。
- 客户端日志：`logs/desktop.log`；启动器日志：`~/Library/Application Support/Yingxu/launcher.log`。
- 页面本身可能自动保存本地草稿，不能只把“浏览页面”理解为绝对无写入；本次未主动编辑业务内容。

## 检查方法

- 自动：`webapp/src/components/AppShell.test.tsx`、其他全局测试、`npm test`、`npm run build`。
- 客户端：launcher `--root <新工作区> --port 0 --no-browser --smoke-test`，再检查页面和日志。
- 人工只读：逐个打开主要路由、刷新、前后退，检查侧栏、顶部标题、旧版入口、滚动位置和页面错误。
- 数据保护：只读连接查询数据库；不在真实工作区测试切换、恢复、清理缓存或新建项目。

## 状态与待确认

- 已验证：所有主要路由可打开；全局测试通过；新 UI 已检查首页、选题、文章、视频和设置。
- 已验证：统一 Python、真实媒体输出和内置 Chromium 可运行；最终自包含 APP 的 smoke 与原生窗口另列验收状态。
- 待确认：最终 APP 重复启动、外置盘断开重连、安装版覆盖升级及干净客户 Mac。
