# 视频项目迭代实施与交接

状态：已完成开发与开发环境验收，2026-11-05。安装版 8848 未被覆盖；当前结果属于本仓库源码、开发服务 8765 和旧数据验收副本。

## 交付范围

- 侧栏“视频任务”升级为“视频项目”；主项进入真实首页，子菜单为原创、对标。
- 首页支持搜索、类型筛选、新建和继续原项目，不自动创建空项目。
- 原创：文案 → 旁白与词级时间码 → 音乐适配 → 画风与分镜 → 样片/成片验收。
- 对标：参考视频与使用边界 → 真实拆解报告 → 逐镜替换 → 音乐冲突处理 → 样片/成片验收。
- 两条流程均在现有 AppShell 中原生实现，无 iframe/webview、无第二套全局导航、无原型端口依赖。
- 旧 `/tasks/:id` 继续打开项目，`/tasks/:id/editor` 保留原编辑器；没有数据库表迁移、数据清空或安装包覆盖。

## 修改文件与共享代码影响

### 视频专用页面

- `webapp/src/pages/videoProjects/VideoProjectHome.tsx`：项目首页。
- `OriginalProject.tsx`：原创建建、已有文案、旁白、画风、分镜和流程入口。
- `BenchmarkProject.tsx`：参考上传、拆解报告、逐镜画面/旁白/时长处理。
- `ProjectShared.tsx`：阶段导航、上传、音乐、真实样片/成片和验收共用组件。
- `useVideoProject.ts`：类型、原任务快照、revision、草稿、直接项目恢复。
- `video-projects.css`：专用布局与响应式样式。
- `VideoProjects.test.tsx`：导航、必填、门槛、报告跳转、版本和时长测试。

### 路由与导航共享代码

- `webapp/src/components/AppShell.tsx`：只修改视频项目主项与子菜单，其他页面入口保持。
- `webapp/src/App.tsx`：新增 `/projects*`；保留 `/tasks*` 和旧编辑器。
- `webapp/src/lib/types.ts`：补充原任务已有 `source` 字段类型，不改数据结构。

### 数据、接口与渲染

- `app.py`：保存项目规格；新增真实转写结果、音乐适配、对标拆解；校验新媒体文件引用；让渲染读取对标截取、循环、末帧静止、静音和逐镜旁白；交付签名覆盖新声音/时长字段。
- `workers/whisperx_worker.py`：在 SRT 旁输出真实 `.words.json`。
- `remotion-app/src/VideoComposition.tsx`、`effects.tsx`：读取上述真实媒体参数；原视频不被改写。
- `config/media-tools.json`：仅开发工作区指向项目本地 faster-whisper；不包含凭据。
- `tests/test_video_projects.py`、`tests/test_whisperx_worker.py`：真实媒体与 worker 回归。

共享修改的必要性：新流程必须沿用原任务 ID、文件和 revision，且合成不能只在页面上显示选择而实际忽略。影响范围已通过全量 Python、React、Remotion 和旧项目副本回归。

## 真实验收证据

### 原创 `20261105-001`

- 真实文案保存；真实音频转写成功；真实编导 Agent 返回 2 镜，不是原型示例镜头。
- 真实音乐淡出适配保留原曲。
- 样片 #5；完整成片 #6 `yingxu-final-v18.mp4`，H.264/AAC、1080×1920、5.376 秒。
- 人工验收后进入审核批次 `review_104ad10220b44d14a4b3`，审核页显示文件 #6、制作版本 21。
- “验收后下载”已实际执行，`yingxu-final-v18.mp4` 下载完成，491,565 字节。

### 对标 `20261105-002`

- 本机 4 秒双色参考视频拆为 2 镜，关键帧真实生成，整片转写 1 次；转写文字未伪装成人工校对结果。
- 第一镜保留原镜头和原声；第二镜上传 1 秒绿色画面，用户选择循环到 2 秒并静音；明确叠加 4 秒音乐适配。
- 样片 #13；完整成片 #14 `yingxu-final-v19.mp4`，H.264/AAC、1080×1920、4.011 秒。3 秒抽帧为实际上传的绿色画面。
- 人工验收后进入审核批次 `review_3e11cd41d01a494a80db`，审核页显示文件 #14、制作版本 22。
- 发布中心对两个项目均显示“等待审核，尚未发布”；未执行公开发布。

### 旧项目与其他页面

- `/tasks/20261103-001` 在真实数据库副本中显示原标题、正文和文件 #20 `yingxu-final-v34.mp4`。
- 真实库 handoff 仍为 approved、revision 36、stale=false；`review_deliveries` 仍绑定相同文件和 SHA-256。原片 H.264/AAC、1080×1920、146.837 秒。
- 选题、文章、审核、发布、记忆、设置和 `/legacy` 均已在浏览器回归。旧版文案保持原样，主工作台使用“视频项目”。
- 截图和成片抽帧：`docs/acceptance/video-projects/`。

## 原型二次对齐（用户指出重复创建后）

- 原创新首页就是“文案创作”，删除额外项目名称和前置创建逻辑；确认方案后直接进入旁白，真实新建 `20261105-006` 已验证无第二张文案表单。
- 对标首屏改为“提供参考视频”，保留使用边界和可选关注重点，不增加项目创建表单；关注重点随真实报告保存。
- 两条流程补齐顶部阶段条，未创建项目时不能跳到后续步骤。
- 音乐主操作区与右侧音乐库按原型双栏排列，支持单首和文件夹多首真实导入；增加淡出、循环、保留无音乐段落适配。
- 原创样片移回“生产画面”，最终验收页只保留完整成片和交付；多镜样片逐条真实生成、逐条人工通过。
- 对标弹窗按原片只读、旁白、上传视频、AI 区域顺序重排；最终页不再重复样片。
- 修复原创专用 CSS 未随路由加载的问题，直开和刷新均能显示双栏与原型布局。
- 新证据：`original-direct-narration.png`、`benchmark-start.png`、`original-music-two-columns.png`、`benchmark-shot.png`。

## 新用户全 Kimi CLI 隔离验收（2026-11-05～06）

- 全新工作区 `/Volumes/EXTERNAL_USB/kimi/storage/YingxuNewUserWorkspace`、服务 8766，未修改正式 8848、生产模型配置或账号。文本类 Agent 均使用 Kimi CLI 2.5.1；其他执行器保持独立配置。
- 原创 `20261105-002`：真实词级时间码、5.36 秒音乐适配、Kimi 3 镜编导、3 条逐镜样片与验收完成。成片 #8 `yingxu-final-v22.mp4`，5.376 秒、1080×1920、H.264/AAC，审核批次 `review_b03f795365694afc8633`、revision 25；技术预审通过。
- 对标 `20261105-003`：2 镜、整片转写 1 次；第一镜保留原声，第二镜绿色视频循环到 2 秒并静音，明确叠加 4 秒音乐。成片 #15 `yingxu-final-v16.mp4`，4.011 秒、1080×1920、H.264/AAC，审核批次 `review_d93746072f04439d8bf7`、revision 19；技术预审通过。
- 两条下载文件 SHA-256 均与交付记录一致；发布中心均为“等待审核，尚未发布”，未公开发布。
- 补齐两个 Remotion Agent 的 Kimi frontmatter；第一版场景代码未过安全检查，第二次 Kimi 修正通过后才渲染。
- 修复 Remotion 自测成功后清理临时目录的竞态 500；重跑显示已连接，系统语音和 WhisperX 自测也已连接。
- 隔离进程模型缓存固定在 APFS；small 与 base 模型真实下载/转写成功，未修改全局缓存设置。
- 新证据：`new-user-original-sample-*.png`、`new-user-original-final.png`、`new-user-benchmark-shot-*.png`、`new-user-today.png`。

## 测试结果

- `PATH="/usr/local/opt/openssl@3/bin:$PATH" python3 -m unittest discover -s tests -v`：360 项通过，1 项因无真实备份跳过。
- `cd webapp && npm test -- --maxWorkers=2 && npm run build`：42 个文件、105 项测试通过，生产构建成功。
- `cd remotion-app && npm run lint`：ESLint 和 TypeScript 通过。
- 新增 Python 测试与 worker 的 Ruff format/check 全部通过。旧 `app.py` 全量 Ruff 有 124 项历史风格问题，未做大范围自动改写。
- 既有前端全量 ESLint 基线仍有 314 errors、16 warnings，不宣称全库 lint 全绿。
- 普通并发下旧 `Topics.test.tsx` 曾两次出现 5 秒超时，单独复测通过；最终以较低并发完整通过，未修改旧测试。

## 视频项目初版的能力边界（2026-11-05）

- **真实可用**：项目与版本、文案候选、旁白和词级时间码、音乐适配、真实模板和编导、对标拆解、逐镜上传与版本、声音/时长选择、真实样片/成片、下载、审核交付和发布中心关联。
- **当时未接入**：AI 配乐、AI 视频生成、视觉语义模型、自动声音分离、独立 Remotion Studio。后续补齐结果见下节；独立 Studio 和自定义画风包仍不属于已交付能力。
- **已知风险**：竖屏原片在 1280×800 弹窗中较高，需要滚动查看全部操作；外接磁盘曾出现短暂 SQLite disk I/O error，后续恢复。持续出现时应停止写入并检查磁盘。

## 2026-11-06 能力补齐与最终验收

- AI 配乐为 Kimi 音符谱→本地 WAV，AI 单镜为 Kimi 场景代码→Remotion MP4；视觉理解由 Kimi 读取关键帧，声音分离为 Kimi 规划→Demucs 独立人声/伴奏。均已有真实文件，不再列为未接入。
- OpenVoice、RapidOCR、Playwright 和 Kimi 风险分析均已实测。AI 风险分析只依据技术报告辅助判断，不替代人工确认事实、版权和隐私。
- 抖音热点同步 20/20、17 条快照并转项目 `20261106-002`。抖音、小红书登录及 5.376 秒审核成片预填均成功，字段读回一致、状态 ready；视频号 draft/手动上传，没有公开发布。
- 压力项目 `20261106-004` 的成片 #5 为 12 镜、69.013 秒、1080×1920、H.264/AAC；后段抽帧和音频电平通过。脚本 `build/acceptance/run-long-video.py`。
- 后端 365 项通过、1 项跳过；前端 42 个文件、106 项通过。独立 Intel APP 完整冒烟通过，Kimi 媒体 Agent 和模块已打包。
- **仍未验证**：公开发布、其他机器首次模型准备、真实备份第二次 `changed=0`、安装版覆盖升级、Apple Silicon 构建、Developer ID 签名公证和干净客户 Mac。
- **需要产品决策**：是否在平台后台公开发布、是否准备 Apple 开发者证书与干净测试机、是否将当前源码打包覆盖安装版。未替用户决定。
- 本轮新增证据：`kimi-ai-shot-*.png`、`openvoice-kimi-test.wav`、`douyin-preview-ready.png`、`xiaohongshu-preview-ready.png`、`long-video-004-*.png`。

## 2026-11-15 词级时间码真实进度与模型复用

- P10-C04-F02 使用 `project.transcript` 后台任务；页面轮询真实阶段、百分比和已用秒数。small/base 模型由常驻 worker 复用，开始识别上报 8% 起点，后续按实际分段推进。
- 项目 `20261115-001` 的 17.85 秒真人中文旁白已多次生成真实词语与起止秒数；复用后任务耗时 12.450 秒、6.997 秒。截图 `acceptance/transcript-progress.png`。
- 主服务退出会关闭模型 worker；真实 worker 55503 的 `stop()` 返回码为 0。Python 相关 27 项、React 相关 15 项、生产构建和 worker 91% 覆盖率检查通过。
- 最终精简 DMG 的原生任务 `job_5011282586ed4cffb913` 生成 66 个词/片段；主服务 66954 和 worker 67213 均退出，运行后签名与镜像校验通过。DMG 大小 156,335,776 字节，SHA-256 `ff9f5acfbea9ddf1d4cf6dd2f8876069249cf0a55f0f40a335538ba2f49a5c0e`。
- 构建排除 `._*` AppleDouble 元数据，桌面入口同步清理模型进程。原生证据 `acceptance/transcript-slim-native.jpg`、任务记录 `acceptance/transcript-real-results.json`。
- 长音频、多任务并发、其他硬件性能和安装版覆盖升级仍未验证；百分比不按时间模拟增长。
