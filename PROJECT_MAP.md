# 刘量现有系统项目地图

更新：2026-11-06。证据状态统一为：**已验证**（本次实际代码、只读数据、页面或测试证据）、**推断**（只读代码可确定但本次未实际运行）、**待确认**（需要现场账号、模型或进一步检查）、**无法访问**（当前条件不能读取）。

## 1. 阅读顺序与事实边界

- 新功能或修改前先读本图、涉及模块说明、`docs/CHECKS.md`，再核对当前代码是否仍一致。
- 两个真实关联案例见 `docs/CASES.md`：视频任务到审核/成片/发布，文章到版本/导出/发布。
- 当前运行页 `http://127.0.0.1:8848/` 是已安装的 **映序工作台 0.1.3.6**，工作区为 `/Volumes/CodexData/YingxuWorkspace`。本仓库另有未提交修复；因此“运行版行为”和“当前源码”必须分开记录，不能把源码新变化当作安装版已生效。
- `SYSTEM_AUDIT.md` 是旧架构审计，保留作历史参考，不用它证明当前功能。
- `product-design/PRD.md`、`video-workflow-prd-v2.md`、原型与交互说明属于**目标设计**。即使其中出现“已实施”字样，也只有被当前代码和运行证据确认的能力才写成现状。
- 本图不记录密钥、Cookie、Token、申请码、授权编号、账号密码或私人正文。

## 2. 系统与命名

| 项目 | 实际名称与使用位置 | 状态与依据 |
|---|---|---|
| 产品界面 | “刘量 内容增长工作台”，浏览器标题为“全自动AI内容营销平台” | 已验证：`webapp/src/components/AppShell.tsx`、`web/index.html`、8848 页面 |
| Mac 客户端 | “映序工作台”，bundle id `com.yingxu.workbench` | 已验证：安装版 Info.plist、`desktop/launcher.m` |
| 视频工作区 | “视频项目”，包含原创、对标；原“映序 · 视频制作”编辑器保留 | 已验证：`webapp/src/pages/videoProjects/`、`webapp/src/migration/YingxuVideoWorkspace.tsx`、8765 实际页面 |
| 旧版界面 | “全自动内容营销 / Multi-Agent Workspace”，入口 `/legacy` | 已验证：`web/index.html`、`web/app.js`、HTTP 200 |
| 简易启动壳 | `ContentWorkflow.app` 显示“内容工作流”，只负责启动 8765 服务并打开浏览器 | 已验证：`ContentWorkflow.app/Contents/MacOS/launcher` |
| 仓库基线 | 指定提交 `fd9e2785cf530a2df0063f04bc726e6a491647d0`，本地分支有未提交修复 | 已验证：Git 状态；不要假设安装版包含这些修复 |

## 3. 架构与模块索引

```text
APP WebKit 工作台 / 映序专用 Chrome 采集、登录与预填
        │ HTTP，本机地址
        ▼
Python ThreadingHTTPServer（app.py）
        ├── React/Vite 单页工作台（/demo/*）
        ├── 旧版原生 JS 工作台（/legacy）
        └── V2Application
              ├── 选题、文章、账号、社媒与微信
              ├── 视频审核与发布
              ├── 知识、设置、授权
              ├── Worker / 调度器
              └── SQLite + 本地素材与成片
                         │
                         ├── Remotion / FFmpeg / Playwright
                         ├── faster-whisper / RapidOCR / Demucs / OpenVoice
                         └── Kimi/Codex CLI 或模型 API（外部账号与网络）
```

| 模块 | 说明文档 | 主要实现 | 状态 |
|---|---|---|---|
| 全局框架、导航与客户端 | `docs/modules/framework.md` | `webapp/src/App.tsx`、`AppContext.tsx`、`components/AppShell.tsx`、`desktop/entry.py` | 已验证 |
| 选题与微信线索 | `docs/modules/topics.md` | `webapp/src/pages/Topics.tsx`、`content_workbench/topics/` | 已验证 |
| 文章与版本 | `docs/modules/articles.md` | `webapp/src/pages/Articles.tsx`、`content_workbench/articles/`、`domain/services.py` | 已验证 |
| 视频项目与成片 | `docs/modules/video.md` | `app.py`、`webapp/src/pages/videoProjects/`、`webapp/src/migration/`、`content_workbench/media/`、`remotion-app/` | 已验证 |
| 审核与交付 | `docs/modules/review.md` | `content_workbench/review/`、`webapp/src/pages/Review.tsx` | 已验证 |
| 发布与平台同步 | `docs/modules/publishing.md` | `content_workbench/publishing/`、`webapp/src/pages/Publish.tsx` | 已验证 |
| 记忆与设置 | `docs/modules/knowledge-settings.md` | `pages/Knowledge*.tsx`、`pages/Settings.tsx`、`agents/` | 已验证 |
| 账号、社媒、授权与集成 | `docs/modules/integrations.md` | `accounts/`、`social/`、`licensing/`、`topics/wechat*` | 已验证 |
| 旧版与数据兼容 | `docs/modules/legacy.md` | `web/`、`migrations/`、`ContentWorkflow.app` | 已验证 |
| 检查与案例 | `docs/CHECKS.md`、`docs/CASES.md` | 启动、模块、跨模块、旧数据检查 | 已验证；限制逐项注明 |

## 4. 页面和路由

新版由 `BrowserRouter basename="/demo"` 承载；`webapp/src/App.tsx` 中 `/accounts/*` 会重定向首页，未知路由也回首页，不应写成独立账号分析路由仍在使用。

| 入口 | 路由 | 实现与真实功能 | 状态 |
|---|---|---|---|
| 今天 | `/demo/` | 今日推荐及内容、审核、发布工作汇总 | 已验证：8848 页面、`overview.py` |
| 选题 | `/demo/topics/{industry|douyin|wechat|xiaohongshu}` | 行业、抖音、微信、小红书研究快照与推荐 | 已验证 |
| 文章 | `/demo/articles`、`/demo/articles/:id` | 大纲、正文、配图、排版与导出 | 已验证 |
| 视频项目 | `/demo/projects`、`/demo/projects/{original|benchmark}/:id?` | 项目首页、原创和对标完整流程；真实样片、成片与审核交付 | 已验证：8765 两条真实流程 |
| 旧视频兼容 | `/demo/tasks`、`/demo/tasks/:id`、`/demo/tasks/:id/editor` | 原项目链接与原六阶段编辑器；旧任务按原创兼容，不迁移 | 已验证：20261103-001 数据库副本 |
| 审核 | `/demo/review` | 本地技术预审、人工终审与交付关联 | 已验证 |
| 发布 | `/demo/publish` | 文章/视频发布批次、平台字段与预览 | 已验证 |
| 记忆 | `/demo/knowledge`、`collection`、`publishing` | 增长记忆、采集契约、发布契约 | 已验证 |
| 设置 | `/demo/settings/{agents|models|media|templates|data}` | Agent、模型、媒体、模板与隐私 | 已验证 |
| 接入/授权/引导 | `/demo/setup`、`activation`、`welcome` | 依赖与账号接入、离线授权、新手引导 | 已验证 |
| 旧版 | `/legacy` | 旧版任务、账号、发布和设置 | 已验证：HTTP 200 与页面导航 |

## 5. 启动、依赖与检查

### 开发源码

```bash
cd /Volumes/Samsung_T5/kimicode/AI-Auto-Content-Marketing-System
bash scripts/setup.sh --check
PATH="/usr/local/opt/openssl@3/bin:$PATH" bash scripts/start.sh
```

- 默认开发端口为 8765；`scripts/start.sh` 调 `python3 app.py --port 8765`。APFS 新库存在时默认使用该库，显式 `CONTENT_AGENT_DB` 可覆盖；迁移和回滚见 `docs/APFS_MIGRATION.md`。
- 主后端使用 Python 标准库 + SQLite；`requirements-topics.txt` 增加 Playwright、RapidOCR、Pillow，`requirements-accounts.txt` 增加 xlrd。
- React 工作台在 `webapp/`，Remotion 在 `remotion-app/`；锁文件已存在。系统默认 OpenSSL 是 LibreSSL 时，授权测试需显式选择 OpenSSL 3。
- 已验证：Python 3.9.6、Node 22.22.0、FFmpeg 9.0.2；WebBridge 服务与扩展均可用。

### Mac 客户端

- 启动 `/Applications/映序工作台.app`。新构建客户端在 APP 自己的 WebKit 窗口显示工作台；当前源码把选题采集、四平台登录和发布预填统一接入映序专用 Chrome，固定资料保存在工作区，不再重启日常 Chrome 或要求 WebBridge 扩展。依据：`accounts/dedicated_browser.py`、`topics/browser_worker.py`、`accounts/browser_connection.py`。现有安装包尚未包含本次修改。
- 工作区由 `~/Library/Application Support/Yingxu/workspace.json` 指向，当前为 `/Volumes/CodexData/YingxuWorkspace`；会话文件记录 8848 端口。本次验收使用 `--root` 或 `--ui-root` 隔离目录，没有修改该指针。
- 客户端固定使用授权必需模式，平台执行只到预填，最终发布由用户在平台后台完成。依据：`desktop/entry.py`。
- 冒烟命令：`/path/映序工作台.app/Contents/MacOS/launcher --root /path/new-empty-workspace --port 0 --no-browser --smoke-test`。
- 早期独立构建的 APP 签名、引擎、smoke 和 DMG 校验曾通过；最终 `mac-self-contained` 包必须重新验收，不能沿用旧结果。未覆盖安装现有版本。

### 已有测试与本次结果

| 检查 | 命令 | 结果与限制 |
|---|---|---|
| 后端 | `PATH="/usr/local/opt/openssl@3/bin:$PATH" python3 -m unittest discover -s tests -v` | 已验证：372 项通过，1 项因无真实备份跳过 |
| React | `cd webapp && npm test -- --maxWorkers=2 && npm run build` | 已验证：42 个文件、106 项测试通过，生产构建通过 |
| Remotion | `cd remotion-app && npm run lint` | 已验证：ESLint + TypeScript 通过 |
| 前端全量 lint | `cd webapp && npm run lint` | 未全通过：既有 314 errors、16 warnings；新增页面功能检查不以此冒充全绿 |
| 客户端 | launcher `--smoke-test` | 已验证：页面、授权配置、示例图和打包运行时可执行文件通过；未激活新工作区属预期 |
| 页面 | 8765 原创/对标真实流程、8766 全新工作区全 Kimi CLI 新手到文章/原创/对标/审核/记忆流程、8848 主要路由、旧项目副本、媒体 ffprobe | 已验证；8766 为隔离数据，安装版升级和公开发布未执行，不能仅凭 HTTP 200 宣称生成或发布通过 |

完整清单见 `docs/CHECKS.md`。

## 6. 数据与文件

| 数据/文件 | 真实位置与关系 | 状态 |
|---|---|---|
| 主数据库 | 客户端：`/Volumes/CodexData/YingxuWorkspace/data/content-agent.db`；当前开发库：`/Volumes/EXTERNAL_USB/kimi/storage/YingxuDevWorkspace/data/content-agent.db`；可用 `CONTENT_AGENT_DB` 指定 | 已验证：开发库已迁移到 APFS，详见 `docs/APFS_MIGRATION.md`；客户端配置未改。本次收尾时 CodexData 卷未挂载，正式库当前无法访问 |
| 旧任务 | `tasks`、`files`、`video_variants`；`source_json` 保存映序交付信息 | 已验证 |
| V2 内容 | `wb_campaigns`、`wb_content_items`、`wb_revisions`、`wb_assets`、`wb_approvals` | 已验证：`migrations/001_workbench_v2.sql`、`domain/services.py` |
| 审核交付 | `review_deliveries` 将原任务、文件、制作版本和 SHA-256 绑定到 `review_items` | 已验证：真实任务 20261103-001 |
| 发布 | `publish_batches`、`publish_targets` 按 `content_kind + source_id + source_hash` 关联内容版本与平台 | 已验证：视频和文章两个案例 |
| 媒体 | `renders/<任务>/`、`assets/v2/<hash>/`、`previews/`、`voice/`、`subtitles/`；文件记录与 SHA-256 用来检测变化 | 已验证：成片和文章导出文件存在 |
| 配置 | 工作区 `config/`；模板注册表、媒体工具路径、模型与 Agent 设置。敏感配置不写入文档 | 已验证 |
| 运行资源 | 工作区 `runtime/remotion-0.1.1`；客户端刷新代码但不覆盖业务媒体、缓存和模板 | 已验证：`desktop/entry.py` |
| 迁移 | `migrations/*.sql` 与 `storage/migrate.py`；正式迁移前必须备份、dry-run、幂等检查 | 已验证：`migrations/README.md` |

## 7. 真实依赖关系

- 选题推荐或研究条目通过 `TopicAPI` 创建旧视频任务，并把 `candidate_id` 或 `research_item_id` 写入 `tasks.source_json`；这保留了来源，不意味着文章与视频共享一个状态机。
- 文章在 `wb_content_items` 下保存多版本和当前活动版本；`Workbench.approve` 绑定 manifest，导出读取已审批正文，`PublishingService.source("article")` 再交给发布批次。
- 视频交付通过 `handoff_yingxu` 记录文件和制作版本，`ReviewService.receive_delivery` 建立审核项；人工批准后 `source_for_publish` 验证输出路径与哈希，发布中心再读取。
- 后台任务在 `wb_jobs`，Worker 按执行器分发；客户端限制 `publish.execute`，因此“字段已准备/预览”与“公开发布”是不同状态。
- 模型、OCR、语音、Remotion 和 WebBridge 都是独立能力。某一项“已连接”不能证明整条生产或发布链已通过。

## 8. 修改风险与回归原则

- **全局导航/AppShell**：影响所有新版页面，必须扩大检查到路由、滚动、设置分组和旧版入口。
- **共享数据/状态**：`tasks` 与 `wb_*` 并存，不可把旧 `tasks.state` 当成新审核状态，也不可绕过 `review_deliveries`。
- **版本与文件**：修改正文、素材或制作方案可能使审批、预览和发布哈希失效；旧文件不得静默替换。
- **接口兼容**：检查 `/demo/tasks/:id`、`/demo/articles/:id`、刷新、前后退和 `/legacy`；新路由必须回退到真实页面而不是错误页。
- **外部依赖**：真实模型、账号同步和平台预填必须单独验收，不能用 mock 通过替代现场结果。
- **迁移与备份**：不直接对正式库执行 SQL。先备份、副本 dry-run、连续第二次 `changed=0`，再决定是否切换。

## 9. 目标设计与待确认事项

- 原创/对标原型、`product-design/prototypes/mac-studio/` 的演示项目、固定分镜、手动看板和 CSS 动效均为目标设计，不写成真实媒体能力。
- PRD 中的自动编排、更多平台能力、性能目标和未来模板不能仅凭文档写成已实现；逐项对照当前代码。
- 已验证：Kimi 文章 SVG→PNG、音符谱→WAV、场景代码→MP4、关键帧视觉分析，以及 Demucs 人声/伴奏、OpenVoice、OCR、Playwright 的真实输出。Kimi 负责创作和判断，本地引擎负责执行，不把这些混写成单一模型能力。
- 已验证：抖音热点 20/20、17 条快照并转为项目 `20261106-002`；小红书三个真实收藏夹各同步 1 条，共新增 3 条。抖音与小红书登录、审核视频上传、字段读回和 ready 预填通过；视频号仍手动上传，没有公开发布。
- 已验证：隔离压力项目 `20261106-004` 的 12 镜、69.013 秒、H.264/AAC 成片和后段抽帧；不代表其他硬件或更长视频已通过。
- 仍待确认：不同机器首次模型准备、长文本稳定性、安装版覆盖升级、真实备份第二次 `changed=0`、Apple Silicon 构建、Developer ID 签名公证和干净客户 Mac。没有证书和第二台机器时不得标为通过。
- 旧版与新版数据口径曾不一致；当前源码有未提交修复，安装版是否升级后的表现为**待确认**。

## 9.1 词级时间码后台进度与模型复用（2026-11-15）

- **已验证**：原创 P10-C04-F02 改为 `project.transcript` 后台任务，页面轮询真实任务，不再让浏览器等待整个转写请求。
- **已验证**：small/base 按模型保持常驻 faster-whisper worker；同一模型连续转写复用进程，模型加载、开始识别、实际分段和写出结果分别上报，不使用匀速模拟。
- **已验证**：项目 `20261115-001`、17.85 秒真人中文旁白；复用后任务 `job_eae57fe633a84b7e932a` 耗时 12.450 秒，`job_97b4cd3e8f0b48699626` 耗时 6.997 秒，页面显示“转写中 · 8% · 已用 4 秒”，证据 `docs/acceptance/transcript-progress.png`。
- **已验证**：相关 Python 27 项、React 相关 15 项和生产构建通过；本次 Python 文件 Ruff format/check 通过。真实 worker 55503 调用 `stop()` 后返回码 0，主服务退出时也会关闭复用进程。完整后端 434 项通过、1 项跳过；最终单 worker 前端 45 个文件、127 项全部通过。
- **已验证**：最终精简 DMG 的原生窗口生成 66 个词/片段，主服务 66954 和 worker 67213 均退出；运行后签名与镜像校验通过。DMG 位于 `mac-slim-transcript-progress`，SHA-256 `ff9f5acfbea9ddf1d4cf6dd2f8876069249cf0a55f0f40a335538ba2f49a5c0e`。
- **边界**：当前是本机短视频实测；长音频、大量并发、Apple Silicon 和其他机器性能未验证。词级转写不是 Kimi CLI 文本生成，仍由本地 faster-whisper 执行。

## 10. UI、Agent 与自包含客户端迭代（2026-11-06）

- **已验证**：佐藤式留白、少边框和文字层级覆盖首页、选题、文章、视频项目和 Agent 配置；浏览器无控件重叠，证据 `docs/acceptance/video-projects/ui-sato-*.png`。
- **已验证**：26 个独立 Agent 中 16 个生成型 Agent 均可独立配置服务和模型，模型参数进入真实调用；后端 372 项通过、1 项跳过，前端 106 项通过。
- **已验证**：统一可迁移 Python、Whisper、OCR、Demucs、OpenVoice、Playwright 和模型缓存；真实 Demucs 分轨、OpenVoice WAV 和内置 Chromium 启动。
- **已验证**：最终 `mac-self-contained` APP smoke 通过，包含 26 个 Agent、本地媒体导入和 Chromium 1223 实际启动；原生 WebKit 的授权页与“今天”均已打开，证据 `client-smoke.json`、`client-native-*.jpg`。
- **已验证**：修复版完整媒体复验通过，Whisper、OCR、Demucs、OpenVoice 和真实 Kimi CLI 结果见 `client-media.json`；运行后的签名深检通过，APP 未再写入字节码。
- **已验证**：最终 DMG 为 `/Volumes/EXTERNAL_USB/kimi/storage/YingxuBuilds/mac-self-contained/Yingxu-Mac-x86_64.dmg`，约 6.04 GB；镜像校验 VALID，只读挂载后的 APP 冷启动通过并已卸载。
- **未验证**：Apple Silicon、Developer ID 公证、干净客户 Mac、安装版覆盖升级和公开发布。

## 11. 真正精简版与签发身份轮换（2026-11-09）

- **已验证**：独立「映序工作台·精简版」约 175 MB，DMG 约 78.3 MB，路径 `/Volumes/EXTERNAL_USB/kimi/storage/YingxuBuilds/mac-slim/Yingxu-Mac-x86_64-Slim.dmg`。
- **已验证**：九组可下载资源全部改为安装后获取；包内只有启动器、业务后台、界面和 OpenSSL。首次下载页支持状态、失败原因和重试，截图 `client-slim-download-guide.png`。
- **已验证**：后端 379 项通过、1 项跳过，前端 108 项通过；最终完整启动、真实媒体、Kimi CLI、OpenVoice、冷缓存 Remotion 和十二镜长视频均通过。
- **已验证**：APP 运行后签名深检、DMG VALID 及只读挂载启动通过。安装包同时包含新旧公钥，旧授权继续有效。
- **未验证**：Apple Silicon、Windows、Developer ID 公证、干净客户 Mac、安装版覆盖升级和公开发布。


## 12. 专用 Chrome 与详细功能地图（2026-11-10）

- 逐页控件表位于 `docs/FUNCTION_MAP.md`：覆盖 22 个新版主要路由、原创／对标阶段、旧编辑器、弹窗、条件按钮与旧版入口。文末 A～K 控件级说明书复核 534 个控件节点，写明每个按钮的真实效果，以及输入框的内容、必填、长度／范围、格式、文件类型和禁用条件；同类动态控件合并。后续改卡片、按钮、输入框或路由时同步更新。
- `docs/FUNCTION_MATRIX.md` 是五列结构化矩阵：一级页面、二级卡片、三级卡片元素和功能、功能描述、技术方案，共 268 条功能行。技术列记录真实 API、后端服务、SQLite 表／本地文件和 Chrome／模型／媒体引擎，供迭代时判断修改影响。
- **已验证**：映序专用 Chrome 使用工作区 `data/yingxu-chrome-profile`，默认仅监听 `127.0.0.1:9223`；与 Kimi 的 9222 专用浏览器分离。启动只接受 Chrome 官方路径和固定参数，不读取、复制或退出日常 Chrome。
- **已验证**：选题、账号登录和发布预填共用同一 CDP 实例；任务结束不关闭窗口；重复启动复用同一 PID；通过 `Browser.close` 正常退出；带有效期的测试 Cookie 在完整重启后保留，测试后已删除。
- **已验证**：真实隔离页面显示“映序专用 Chrome”和四个平台登录入口；证据 `docs/acceptance/browser-dedicated-setup.png`。前端 43 个文件、109 项测试通过，生产构建通过；后端共 394 项，392 项通过、1 项跳过、1 项既有仓库数据库 I/O 错误，未写成全绿。
- **待确认**：新专用窗口中的真实平台登录、上传读回、客户 Mac 与安装版。此次没有重新构建 DMG 或覆盖 `/Applications`。


## 13. 逐页评审与持续迭代资料夹（2026-11-11）

- 正式迭代资料夹为 `docs/iteration-review/`。双击其中的 `index.html` 即可离线查看，不依赖映序或其他服务端口。
- 当前基线：26 个页面单元、294 条功能说明、25 张真实页面截图。每页包含页面信息、卡片顺序、控件与限制、页面状态、review 清单和技术索引。
- `data/pages.json` 保存结构化功能事实；`data/iterations.json` 保存供 HTML 使用的完整迭代记录，正式评审与迭代历史统一保存在 `docs/iteration-review/index.html` 内，不再每次新建记录文件。`README.md` 规定更新顺序。
- 已实际验证：HTML 逐页导航、全文搜索、展开全部、review 勾选本地持久化和迭代记录。证据 `docs/iteration-review/assets/review-html.png`。
- 后续先更新 `docs/FUNCTION_MATRIX.md`，运行 `scripts/sync-pages.mjs`；再更新截图与迭代记录，运行 `scripts/build.mjs`，最后检查离线 HTML 并更新 `docs/CHECKS.md` 和 `CHANGELOG_AI.md`。
- 此资料夹是评审与迭代基础，不代替功能验收，也不表示安装包已更新。历史迭代记录只追加，不覆盖。


## 14. Kimi CLI 抖音登录与同步验收（2026-11-13）

- 抖音 `hot/favorites/login/details` 统一经过 `topics/kimi_browser.py` 和 `agents/douyin-collection-agent.md`，由 Kimi CLI 通过 `chrome-persistent` 操作固定 Chrome；发布流程继续使用原确定性浏览器连接。
- “连接抖音采集窗口”已登录立即确认；未登录在同一窗口等待本人操作最多 300 秒，超时不关窗、不清会话、不标成功。
- “同步内容”先检查登录再采集。热榜严格为页面顺序前 20 条，收藏夹分别执行；同步记录显示当前阶段、百分比、Kimi CLI、来源数量和错误。部分完成不冒充全部成功。
- 浏览器工具暂时不可用只读恢复重试一次；持续失败记录真实 `browser_unavailable`，不误写为 `LOGIN_REQUIRED`。
- **已验证**：登录 `job_ae371f11026148d3bf32` 成功；全量同步 `job_436bc53a894148a180fb` 为热榜 20、精选 20、竞对 5、高赞 1，错误 0。首轮部分失败记录保留用于对照，重试新增 20、更新 26，没有重复创建相同作品。
- **已验证**：前端 43 个文件、110 项测试通过，生产构建通过；后端 403 项中 401 项通过、1 项跳过、1 项既有仓库数据库 I/O 错误，未宣称全绿。
- **未验证**：真实未登录状态下的完整 5 分钟等待、安装包、其他平台采集和公开发布。此次未重新打包客户端。


## 15. 作品作者与互动数据、功能编号（2026-11-13）

- 抖音作品详情由 `KimiBrowserCollector.collect("details")` 通过 Kimi CLI 打开真实作品页和作者页，读取作者名称、作者链接、作者粉丝数、点赞数和评论数；不从标题或其他作品猜测。
- Kimi 可在顶层或作品条目内返回 `details`，后端统一规范化；只有作者、粉丝、点赞、评论均已读取且封面已缓存时才跳过重复详情请求。
- **已验证**：作者“商科子弹”、粉丝 3.1 万、点赞 27,708、评论 88，已写入 `wb_research_items.metadata` 并在高赞作品卡显示。证据 `docs/acceptance/kimi-douyin-author-engagement.png`。
- 功能编号规则为 `P页码-C卡序号-F功能序号`，例如 `P04-C03-F02`。当前 26 个页面单元、295 个功能均有唯一编号，索引为 `docs/FUNCTION_IDS.md` 和离线 `docs/iteration-review/index.html`。
- 后续更新必须引用功能编号；在对应卡片末尾追加新编号，不因文案修订改变原编号，删除功能时保留历史编号说明。
- 前端 43 个文件、110 项测试通过，生产构建通过；后端 406 项中 404 项通过、1 项跳过、1 项既有仓库数据库 I/O 错误。
- 真实未登录的完整 5 分钟等待仍未现场执行；本次未重新打包客户端。


## 14. 原创文案手写与 AI 双路径（2026-11-15）

- 仅修改 P10-C02／P10-C03：完整手写文案不要求叙事方向；AI 生成或改写必须填写叙事方向，候选采用后才成为正式文案。
- 进入旁白仍需正式文案、至少一个目标平台和有效画幅；后端明确传入生成／改写类型、方向、当前文案、平台和画幅。
- 不新增表、不迁移旧项目，沿用项目 ID、快照、revision 和非空历史版本。
- 已验证：前端相关 14 项、后端相关 7 项和生产构建通过；隔离手写项目 `20261115-002` 与 AI 项目 `20261115-003` 均进入旁白，AI 项目的视频号和横屏参数保存正确。
- 实际模型：Kimi CLI `2.5.1`，`default_unpinned` 当前默认模型；真实返回内容使用了叙事方向，未固定或虚构上游模型名。
- 逐页资料、原创截图和 `iterations/2026-11-15-original-copy-ai.md` 已更新。未重新打包或替换现有 8765/8848 服务，未执行渲染或公开发布。


## 15. 统一开发版本记录目录（2026-11-15）

- 后续开发统一使用 `/Volumes/Samsung_T5/AI/映序开发日志/开发版本记录/`。原 `docs/iteration-review/` 保留为兼容备份，不删除。
- 新目录包含当前产品功能、技术调用、25 张真实截图、独立迭代记录、结构化数据和版本索引。
- 当前文档基线为 v0.10.0：26 个页面单元、302 条功能说明；v0.1.0～v0.9.0 对应 9 次历史迭代，v0.10.0 为本次统一归档。
- 版本号仅用于开发文档，不表示 DMG、安装包或正式发行版本。
- 双击 `index.html` 可离线查看逐页功能、版本记录和迭代记录；维护顺序见 `README.md`，历史记录只追加。
- 已实际验证：26 页、302 条功能、10 个版本、10 次迭代、下载功能、截图、本地链接及无外部依赖检查通过。


## 16. 原创文案线上生成与改写验收（2026-11-15）

- 8765 线上工作区已部署 P10-C02／P10-C03 双路径，不再只是隔离测试可用。
- AI 生成项目 `20261115-003`：只填写叙事方向，真实生成并采用候选，视频号和横屏保存正确并进入旁白。
- AI 改写项目 `20261115-004`：已有正式文案时按钮变为“根据叙事方向改写当前文案”，真实改写并采用，抖音和竖屏保存正确并进入旁白。
- 线上模型连接为 Kimi CLI `2.5.1`、`default_unpinned` 当前默认模型，真实连接测试 HTTP 200。
- 页面证据 `docs/acceptance/original-online-copy-ai.png`；统一开发版本记录已追加线上结果。
- 8848 旧客户端不会自动获得这些改动，需以新构建客户端的实际验收为准，不能用线上结果冒充安装版通过。


## 17. 开发记录先读取再对比合并（2026-11-15）

- 后续每次记录前必须读取 `data/iterations.json`、`data/versions.json` 和相关独立记录，先确认已有结论，再合并新事实，不能直接覆盖。
- 统一入口新增 `scripts/merge-iteration.mjs`：同一迭代 ID 只补充证据、变更和文件并去重；新 ID 才递增文档版本。
- 每次合并前自动备份到 `backups/<时间>/`，保留旧记录、旧版本和旧索引。
- 已在测试目录验证：新记录递增、同 ID 重复合并不新增版本或重复证据、历史保留和备份均通过。测试版本号未写入正式索引。
- 具体使用顺序见统一目录 `README.md`；合并脚本会自动重新生成离线 HTML。
