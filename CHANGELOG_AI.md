# AI 迭代记录

## 2026-11-16 · 小红书真实视频与图文下载验收

- 修复 Python 3.9 导入小红书下载模块时的类型标注错误；真实 3.9 环境下 7 项采集下载测试通过。
- `TopicService.bootstrap.jobs` 补入 `research.probe`，下载弹窗能收到成功和失败终态；新增后端入口和前端终态回归测试。
- 下载 Skill 对空探测结果返回明确错误；命令行遇到登录跳转时，由 Kimi CLI 在同一固定 Chrome 作品页读取实际媒体，不导出 Cookie，不绕过 DRM。
- 精选视频 `job_a362718caf414e8fb9bf` 下载成功：31.881066 秒、1080×1920、15,972,890 字节，FFprobe 与本地读取通过。
- 高赞图文 `job_ae14e24ebe124597b53e` 下载成功：9 张 1080×1440 WebP，合计 1,141,506 字节，逐张 Pillow 校验通过。
- 两种素材的完整路径、复制地址和打开文件夹均实际操作；证据 `docs/iteration-review/evidence/xiaohongshu-video-download.png`、`xiaohongshu-image-set-download.png`。
- 指定 OpenSSL 环境下后端 429 项通过、1 项跳过；前端生产构建和相关检查通过。全量前端单轮 126/127，Tasks 超时项单独复测通过，不宣称单轮全绿。
- 统一开发版本记录新增 v0.13.0，保留 26 个页面单元、316 条功能说明及全部历史。仅真实验收兼容优先；未打包 DMG，未执行公开发布。

## 2026-11-15 · 词级时间码后台进度与模型复用

- P10-C04-F02 改为后台 `project.transcript` 任务；页面每秒读取真实阶段、百分比和已用秒数，不再同步等待整段转写。
- small/base 按模型复用常驻 faster-whisper worker；开始识别立即上报真实起点，后续按分段结束时间推进，不模拟匀速进度。
- 8765 项目 `20261115-001` 使用 17.85 秒真人中文语音：复用后两次后台任务分别耗时 12.450 秒和 6.997 秒；页面实测显示“转写中 · 8% · 已用 4 秒”，截图 `docs/acceptance/transcript-progress.png`。
- 修复 `V2.jobs` 调用错误和短音频中间状态被页面轮询跳过的问题；回归先复现漏报，再通过自动测试。
- Python 相关 12 项、React 相关 15 项和生产构建通过；本次 Python 文件 Ruff format/check 通过。真实 worker 55503 调用 `stop()` 后返回码 0，主服务退出会关闭复用进程。旧 `app.py` 的历史风格问题未扩大修改。
- 完整后端在 Python 3.12 + OpenSSL 3 下 434 项通过、1 项跳过；完整前端并行轮次 124 项通过、1 项高负载超时，单 worker 复验为 44 个文件、125 项全部通过。转写 worker 覆盖率统计为 91%。
- 最终精简 DMG 的原生窗口完成任务 `job_5011282586ed4cffb913`，生成 66 个词/片段；模型就绪后约 10 秒。主服务 66954 与 worker 67213 均退出，运行后签名有效；镜像 `VALID`，SHA-256 `ff9f5acfbea9ddf1d4cf6dd2f8876069249cf0a55f0f40a335538ba2f49a5c0e`。
- 构建排除 `._*` AppleDouble 元数据，桌面入口同步清理 Whisper worker；相关 27 项测试通过。原生证据 `docs/acceptance/transcript-slim-native.jpg` 和 `transcript-real-results.json`。
- 长音频、多任务并发和其他硬件性能未验证；词级时间码使用本地 faster-whisper，不冒充 Kimi CLI 转写。

## 2026-11-15 · 升级版 APP 内 AI 生成与改写通过

- 升级版 APP 冷启动与运行时检查通过：26 个 Agent、本地媒体和浏览器可用；使用独立测试签发身份激活隔离工作区，未使用经营者私钥或正式授权。
- APP 内 AI 生成项目 `20261115-001`：真实生成并采用候选，视频号和横屏保存正确并进入旁白。
- APP 内 AI 改写项目 `20261115-002`：真实改写并采用，抖音和竖屏保存正确并进入旁白。
- APP 内模型连接为 Kimi CLI `2.5.1`、`default_unpinned` 当前默认模型，连接测试 HTTP 200；证据 `docs/acceptance/original-app-copy-ai.png`。
- 本次构建位于 `/Volumes/EXTERNAL_USB/kimi/storage/YingxuBuilds/mac-original-ai`，DMG 签名和完整性以最终校验为准；未覆盖 `/Applications` 中旧客户端。

## 2026-11-15 · 开发记录改为先读取再对比合并

- 后续每次记录前必须读取现有 `data/iterations.json`、`data/versions.json` 和相关独立记录，先对比已有结论，再合并新事实，不能直接覆盖。
- 统一入口新增 `scripts/merge-iteration.mjs`：同一迭代 ID 只补充证据、变更和文件并去重，新 ID 才递增文档版本。
- 每次写入前自动备份到 `backups/<时间>/`，保存旧记录、旧版本和旧索引；合并后自动重建离线 HTML。
- 已在测试目录连续执行两次合并，验证新记录递增、同 ID 不重复、历史保留和备份均通过；测试版本号未写入正式索引。
- 具体使用顺序已写入统一目录 `README.md` 和 `iterations/2026-11-15-version-archive.md`。

## 2026-11-15 · 原创 AI 生成与改写在 8765 线上版本通过

- 8765 线上工作区已部署 P10-C02／P10-C03 双路径，不再只是隔离工作区测试可用。
- 线上 AI 生成项目 `20261115-003`：只填写叙事方向，真实生成并采用候选，视频号和横屏保存正确并进入旁白。
- 线上 AI 改写项目 `20261115-004`：已有正式文案时按钮变为“根据叙事方向改写当前文案”，真实改写并采用，抖音和竖屏保存正确并进入旁白。
- 实际模型连接为 Kimi CLI `2.5.1`、`default_unpinned` 当前默认模型，真实连接测试 HTTP 200。线上证据 `docs/acceptance/original-online-copy-ai.png`。
- 统一开发版本记录已追加线上生成与改写结果，不把隔离结果当作线上结果。
- 8848 旧安装包仍是旧界面，客户端必须重新构建并单独验收；不以线上通过冒充安装版通过。

## 2026-11-15 · 统一开发版本记录与产品功能归档

- 在 `/Volumes/Samsung_T5/AI/映序开发日志/开发版本记录/` 建立统一开发资料夹，后续以此作为功能与迭代维护入口，原 `docs/iteration-review/` 保留为兼容备份。
- 汇总当前 26 个页面单元、302 条功能说明、25 张真实截图、9 次历史迭代及独立参考文件，包含热点卡、收藏作者互动和本地下载等当前功能。
- 新增 `VERSION_INDEX.md`、`data/versions.json` 和 HTML 版本记录视图：v0.1.0～v0.9.0 对应历史迭代，v0.10.0 为本次统一归档。版本号只用于开发文档，不冒充安装包版本。
- 新增 `iterations/2026-11-15-version-archive.md` 和归档验证记录；`README.md` 规定后续功能事实、截图、独立记录、版本和 HTML 的更新顺序。
- 已实际通过离线打开、26 页、302 条功能、10 个版本、10 次迭代、下载功能、截图和本地链接检查，无外部资源依赖。证据 `开发版本记录/assets/review-html.png`。
- 本次为文档归档，未修改业务功能或数据，不表示重新验收安装包、真实平台或公开发布。

## 2026-11-15 · 原创 P10-C02／P10-C03 手写与 AI 文案双路径

- 只修改原创文案创作卡和 AI 候选区：完整手写文案不再强制叙事方向；AI 生成／改写需要叙事方向，正式文案、目标平台和画幅仍是下一步门槛。
- AI 按钮按当前文案区分“生成候选”与“改写当前文案”；候选可编辑，只有采用才替换，采用时保留非空历史版本，也可放弃候选。
- 后端明确传递 operation、direction、current_text、target_platforms、aspect；旧项目沿用 ID、快照和 revision，无数据迁移。
- 前端相关 14 项、后端相关 7 项和生产构建通过。
- 隔离手写项目 `20261115-002` 无方向仍进入旁白；AI 项目 `20261115-003` 真实生成并采用候选，视频号和横屏参数保存正确。
- 实际调用 Kimi CLI `2.5.1`，模型配置 `default_unpinned` 当前默认模型；真实返回使用收件箱、重复整理和人工核验等方向内容，不是静态演示。
- 更新 `docs/iteration-review/` 的原创页、真实截图、结构化数据和 `iterations/2026-11-15-original-copy-ai.md`；同步项目地图、功能地图和检查清单。
- 未修改其他业务区，未重新打包或替换 8765/8848，未执行视频渲染、平台上传或公开发布。

## 2026-11-13 · 抖音作者与互动数据、全功能编号

- Kimi CLI 打开真实作品页和作者页，读取作者名称、链接、粉丝数、点赞数和评论数，不从标题或其他作品猜测。
- `KimiBrowserCollector` 兼容顶层和作品条目内 `details`；`TopicExecutors.enrich` 只有作者与互动数据及封面都完整时才跳过详情，缺字段继续补读。
- 热点和收藏作品卡均显示作者、粉丝、点赞和评论，缺失时明确未读取。
- 真实作品验证：作者“商科子弹”、粉丝 3.1 万、点赞 27,708、评论 88，已写入隔离选题库并在高赞作品卡显示。证据 `docs/acceptance/kimi-douyin-author-engagement.png`。
- 全部功能新增 `P页码-C卡序号-F功能序号` 编号，26 个页面单元、295 个功能均唯一；索引 `docs/FUNCTION_IDS.md`，离线 HTML 同步显示。新增功能在卡片末尾追加，不重排旧编号。
- 前端 43 个文件、110 项测试和生产构建通过；后端 406 项中 404 项通过、1 项跳过、1 项既有数据库 I/O 错误。
- 迭代记录 `docs/iteration-review/iterations/2026-11-13-douyin-author-engagement-ids.md`。真实未登录完整等待和安装包未验证，未重新打包客户端。

## 2026-11-13 · Kimi CLI 抖音登录与全量同步

- 抖音 `hot/favorites/login/details` 统一由 `KimiBrowserCollector` 和 `douyin-collection-agent` 通过 `chrome-persistent` 操作固定 Chrome；发布等其他流程不改。
- 登录已验证立即返回；未登录最多等待 300 秒，超时不关窗、不清会话、不标成功。同步前再次核对登录并自动继续。
- 热榜严格取页面顺序前 20 条，收藏夹逐个同步；已有封面优先缓存，避免每条作品重复启动浏览器调用。
- 同步记录显示当前阶段、百分比、Kimi CLI、完成来源数、各来源数量和错误。部分完成不冒充全部成功。
- 浏览器工具暂时不可用只读恢复重试一次，持续错误记录真实 `browser_unavailable`，不误写为未登录。
- 登录 `job_ae371f11026148d3bf32` 成功；全量 `job_436bc53a894148a180fb` 为热榜 20、精选 20、竞对 5、高赞 1，错误 0，新增 20、更新 26。首轮部分失败结果保留对照。
- 前端 43 个文件、110 项测试通过，生产构建通过；后端 403 项中 401 项通过、1 项跳过、1 项既有数据库 I/O 错误。
- 证据：`docs/acceptance/kimi-douyin-sync-records.png`、`docs/acceptance/kimi-douyin-topics.png`；本记录统一维护在 `CHANGELOG_AI.md`。
- 真实未登录的完整 5 分钟等待未现场执行；未重新打包客户端，其他平台采集和公开发布未验证。

## 2026-11-11 · 全功能逐页离线评审与持续迭代资料夹

- 按用户确认的单页样板建立 `docs/iteration-review/`，交付可双击打开的 `index.html`、结构化功能数据、真实截图、迭代记录和更新工具。
- 共 26 个页面单元、294 条功能说明、25 张页面截图。每页独立包含页面信息、卡片顺序、控件与限制、状态、review 清单和技术索引，不再要求跨页面跳转才能看完一个功能。
- 新增 `data/pages.json` 和 `data/iterations.json`。历史迭代统一追加到 `CHANGELOG_AI.md`，后续按 `README.md` 同步功能矩阵、截图、主迭代记录和 HTML，不再每次新建记录文件。
- 离线 HTML 支持逐页导航、全文搜索、卡片折叠、展开全部、review 勾选本地保存、迭代记录和打印。
- 已实际通过 `file://` 打开及上述交互检查，证据 `docs/iteration-review/assets/review-html.png`；所有引用截图和记录文件存在。
- 文章和原创截图使用 APFS 隔离工作区创建的真实测试内容；授权申请码隐藏。早期隔离盘 I/O 错误未修改正式库，按既有兼容方案改用 APFS 后采集成功。
- 此资料夹是后续迭代基础，不表示全部业务功能重新验收或安装包已更新；真实平台、公开结果和其他硬件仍按原边界标注。

## 2026-11-10 · 页面、卡片、功能与技术方案五列矩阵

- 新增 `docs/FUNCTION_MATRIX.md`，把原先混合在“设计”列中的层级拆为一级页面、二级卡片、三级卡片元素和功能，另列功能描述及技术方案。
- 共 268 条功能行，覆盖新版主要路由、原创／对标、旧编辑器、审核、发布、知识、设置、授权、新手、接入向导与旧版入口。
- 技术列逐项补充真实 API、后端服务、SQLite 表／本地文件和专用 Chrome、Kimi／Codex／API、Remotion、FFmpeg、Whisper、OCR、OpenVoice 等实现关系。
- 校验时修正为实际存在的 `Workbench.save_revision/export_article/import_local_asset` 和 `app.py analyze_benchmark`，避免使用不存在的抽象服务名；补齐旧编辑器每行的一级页面列。
- 五列 Markdown 结构和主要路由覆盖检查通过；本次只改文档与索引，未修改业务代码或数据。

## 2026-11-10 · 控件级功能地图补全

- 根据“按钮要写实际效果、输入框要写内容与限制”的反馈，扩充 `docs/FUNCTION_MAP.md`，不再停留在卡片级功能说明。
- 使用 TypeScript AST 提取当前页面及真实引用组件的按钮、输入框、选择器和链接节点；补交自闭合 JSX 输入控件后共复核 534 个节点。相同动态控件的规则合并，未把重复卡片数量当成不同功能。
- 文末新增 A～K 控件级说明书：每个操作写明提交、保存、下载、打开、切换或禁用的真实效果；每个输入写明内容、必填、长度、数值范围、格式、文件类型、只读和禁用条件。
- 逐项核对业务校验，包括选题提示词 12000 字符、Agent 参数范围、发布字段独立限制、原创必填、对标声音／时长联动、音乐冲突、样片门槛、审核规则、迁移新目录和专用浏览器安全行为。
- 反向检查发现并补上微信 `need_verifycode` 状态的配对码输入，以及本地图片“导入并采用”的 PNG／JPEG／WebP 限制。此次只改文档与索引，未修改页面功能或业务数据。

## 2026-11-10 · 映序专用 Chrome 与详细功能地图

### 专用浏览器

- 移除当前源码中“重启日常 Chrome 并复用其个人资料”的路径，改为映序自己的固定 Chrome。资料目录为工作区 `data/yingxu-chrome-profile`，默认只监听 `127.0.0.1:9223`，与 Kimi 的 9222 实例分离；不读取、复制或退出日常 Chrome。
- 选题采集、抖音／小红书／视频号／公众号登录和发布预填统一复用同一 CDP 实例。端口被其他程序或其他 Profile 占用时明确拒绝，不启动第二实例、不关闭占用者。
- 任务结束只断开驱动，不关闭共享窗口；用户主动关闭通过 CDP `Browser.close` 正常退出。接入向导新增启动、重启、关闭和状态检测，发布中心四个平台统一使用专用浏览器登录。
- 相关文档不再把 WebBridge 扩展写成客户端标准依赖；当前源码的 Chrome 是外部运行依赖，安装包尚未更新。

### 功能地图与文档

- 新增 `docs/FUNCTION_MAP.md`，按“设计、功能详情、备注”整理 22 个新版主要路由、卡片、按钮、弹窗、条件状态和旧版兼容入口。
- 同步更新 `PROJECT_MAP.md`、`docs/CHECKS.md`、`docs/modules/framework.md`、`docs/modules/integrations.md` 和 `desktop/README.md`。后续修改路由、共享组件或平台流程时同步维护。

### 真实检查与边界

- 隔离工作区和测试端口实测：重复启动复用同一 PID；任务结束窗口仍在；正常关闭成功；带有效期的测试 Cookie 在完整重启后保留并已删除。未读取真实 Cookie 或平台凭据。
- 22 个主要路由通过应用内导航完成渲染盘点；专用接入页截图 `docs/acceptance/browser-dedicated-setup.png`。
- 前端 43 个文件、109 项测试通过，生产构建通过；本次 Python 文件 Ruff format/check 通过。
- 后端共 394 项：392 项通过、1 项跳过、1 项失败。既有 `test_codex_missing_binary_is_unavailable` 读取仓库旧数据库时出现 disk I/O error，未修改旧库，不宣称全量全绿。
- 未重新构建 DMG、未覆盖 `/Applications`；新专用窗口的真实平台登录、上传读回、客户 Mac 和安装版升级仍未验证。

## 2026-11-10 · 主流程可用性修复：MP4、二维码、Kimi 与主浏览器

### 真实问题与修复

- 原生文件选择器不再把全部上传限制为 `.yxlicense` 和 `.txt`，避免误伤视频、音频和图片。已在“对标”页面实际选择 H.264 `upload-test.mp4`，文件名正常显示。
- `target="_blank"` 链接通过 `NSWorkspace` 打开默认浏览器。微信二维码 `demo-wechat.png` 已在主 Chrome 中实际打开并显示图片。
- 包内新增 Kimi CLI 2.5.1，不包含任何用户登录凭据。`YINGXU_KIMI_CLI` 优先指向包内程序，15 个生成型 Agent 默认均为 `kimi_cli`；通过 `KimiCLIProvider.complete_json` 实际返回 `{'ok': True}`，不再依赖新 Mac 另装 CLI。
- 主浏览器通过 CDP 复用当前 Chrome 会话与 Cookie，不再每次创建独立空白档案。首次连接需要用户明确允许重启一次 Chrome，之后直接复用。已通过真实浏览器写入并读取 `yx-main-session` Cookie；不解密或导出用户 Cookie 文件。
- 原生授权状态仍为 `valid`；精简版 `PATH` 继续优先使用包内 OpenSSL 3。

### 验证与交付

- 原生文件选择、主浏览器、Kimi 配置、Agent 注册及发布相关 25 项检查通过；Ruff 涉及文件检查通过。
- 最终精简 DMG：`/Volumes/EXTERNAL_USB/kimi/storage/YingxuBuilds/mac-slim/Yingxu-Mac-x86_64-Slim.dmg`，153,907,000 字节（约 153.9 MB），SHA-256 `15e7c44cf5a833084ea16cfcd4cd7a450f8fb9d2c68ce69891051d7e8c5843de`。
- APP 深度签名和 DMG 完整性均为 VALID。本交付仅重新构建精简版；全量版未包含本轮 MP4、Kimi CLI 和主浏览器修复。
- 新 Mac 仍需用户自己的 Kimi 账号完成一次登录，平台账号也由用户本人登录；不会把开发机凭据带入客户端。

## 2026-11-09 · 发码、原生上传与双版本运行环境修复

### 授权问题与真实验收

- 原生授权页补实现 WebKit `runOpenPanelWithParameters`：文件框可以实际打开，选择 `.yxlicense`/`.txt` 后填入授权码，取消也正确完成回调。
- 查明“授权签名无效”的根因是旧 APP 打入 macOS 自带 LibreSSL，并非客户授权码错误。构建现在只接受 OpenSSL 3，同时携带 `libcrypto`、`libssl` 并改为随包相对路径；重复构建会替换只读生成文件。
- 后续真实客户环境又定位到精简版 `PATH` 漏掉 `resources/bin`：即使包内有 OpenSSL 3，后台也会调用系统 LibreSSL。开发机上的另一份 OpenSSL 4 曾掩盖此问题。现已固定优先使用包内 OpenSSL，并在 cold smoke 强制校验实际解析路径；35 项相关检查通过，用户提供的正式授权文件在精简后台及最终只读 DMG 中均返回 `valid`。
- 使用完全隔离的测试签发身份和两份独立安装身份，未读取经营者私钥或真实客户记录。全量与精简均实际完成：后台保存已发码记录、原生选择授权文件、点击激活、重启后仍显示“授权已生效”、双向错绑返回 `LICENSE_DEVICE` 且不覆盖有效授权。
- 同一工作区重装 APP 后申请码相同是固定 `installationId` 的预期行为，不是流程卡住。授权与启动器相关 28 项检查通过。

### 浏览器与构建依赖

- 主服务 Playwright 固定为 1.60.0，对应 Chromium 1223；媒体 Python 保留 Playwright 1.48 与 Chromium 1140，禁止未锁定最新版混入构建。
- 精简版主服务也携带 Playwright 驱动；下载资源仍保存到工作区。发布预填在精简模式下选择包含驱动的主服务 Python，不再误指向全量版路径。浏览器、发布与精简专项 32 项检查通过。
- 全量引擎 cold smoke：页面、本地媒体、Chromium 和 26 个 Agent 全部通过，`local_media: true`、`browser: true`。
- 精简 APP 在完整九组资源工作区 cold smoke：本地媒体、Chromium 和 26 个 Agent 全部通过；全新工作区启动也单独通过。
- 精简 DMG：`/Volumes/EXTERNAL_USB/kimi/storage/YingxuBuilds/mac-slim/Yingxu-Mac-x86_64-Slim.dmg`，90,375,303 字节（约 90.4 MB），SHA-256 `3f3922d436b24f600a5048825b7e51d60f33781863cb888059887c636eb3028c`。签名深检和镜像校验 VALID；只读 DMG 启动后正式授权状态为 `valid`。
- 全量 DMG：`/Volumes/EXTERNAL_USB/kimi/storage/YingxuBuilds/mac-self-contained/Yingxu-Mac-x86_64.dmg`，6,054,309,077 字节（约 6.05 GB），SHA-256 `9c9dc055d8e521f54e368d1c10dd9ea07560e43a51e03d06f21776c9b5669101`。签名深检和镜像校验 VALID；只读挂载后原生窗口显示“授权已生效”，文件选择框实际打开，取消后正常返回，随后已卸载。

### 回归与边界

- 后端全量回归 382 项中 381 项通过、1 项跳过；`test_codex_missing_binary_is_unavailable` 读取仓库旧 `data/content-agent.db` 时重复出现 `sqlite3: disk I/O error`。只读完整性检查同样报错，未修改该旧库，不将全量回归写成全绿。
- 当前包为 Intel x86_64 ad-hoc 测试包。Apple Silicon、Windows、Developer ID 公证、干净客户 Mac、安装版覆盖升级和公开发布仍未验证；经营者真实私钥未被用于本次测试。

## 2026-11-09 · 真正精简版客户端与签发身份轮换

### 精简包与首次下载

- 新增独立「映序工作台·精简版」及 `com.yingxu.workbench.slim`。APP 约 175 MB，最终 DMG 为 `/Volumes/EXTERNAL_USB/kimi/storage/YingxuBuilds/mac-slim/Yingxu-Mac-x86_64-Slim.dmg`，78,318,341 字节（约 78.3 MB）；全量离线版保留不变。
- 包内只保留启动器、业务后台、React 页面和 OpenSSL。媒体 Python、Node、FFmpeg/FFprobe、Remotion、Chromium、Whisper、OpenVoice、Transformers、Torch 与 NLTK 全部改为首次安装后下载，共九组，资源写入工作区，不写回已签名 APP。
- 下载页显示每组状态、大小和失败原因，支持重试及已完成检测；全新工作区实测显示下载向导，截图 `client-slim-download-guide.png`。Python/Node 固定版本并校验 SHA-256，Playwright 使用官方镜像，Silero 使用固定哈希包。
- 实际修复 UniDic、`pkg_resources`、`whisper-timestamped`、DTW/NumPy/Numba 版本冲突及打包映射。最终 Python 3.11 媒体环境完整导入，Node 22.22.0 和 FFprobe 6 实测通过。

### 验收与授权

- 后端 379 项通过、1 项跳过；前端 108 项通过并生产构建；下载与兼容性专项 16 项通过。旧开发数据库读取异常未修改，最终回归在隔离工作区完成。
- 最终 APP 完整 smoke 通过：26 个 Agent、本地媒体和 Chromium 均正常。Whisper、OCR、Demucs、OpenVoice 和真实 Kimi CLI 通过；OpenVoice 真实 WAV 为 2.647075 秒。
- 下载版 Node 冷缓存渲染通过；十二镜长视频真实生成，69.013 秒、1080×1920、含音轨，尾帧证据 `client-slim-long-video-tail.png`。
- APP 运行后签名深检为 `valid on disk`、`satisfies its Designated Requirement`。DMG 校验 VALID，从只读挂载的 APP 再次完整启动通过，随后已卸载。
- 经营者新签发身份已建立，客户端打包公钥同时保留旧公钥和新公钥；当前工作区也已追加新公钥。旧授权继续有效，未读取或使用私钥密码。
- Apple Silicon、Windows、Developer ID 公证、干净客户 Mac、安装版覆盖升级和公开发布仍未验证；本包为 Intel x86_64 ad-hoc 测试包。

## 2026-11-06 · 佐藤式 UI、全 Agent 模型配置与自包含客户端

### UI 与 Agent

- 全局按克制、编辑式布局重整：扩大页边距和模块间距，减少装饰边框，统一标题、正文和辅助文字层级。首页、选题、文章、视频项目和 Agent 配置已在 1280×800 浏览器检查，证据为 `docs/acceptance/video-projects/ui-sato-*.png`。
- 注册表现有 26 个独立 Agent。新增文章插画、配乐作曲、视觉分析、声音分离规划、Remotion 编导、Remotion 场景代码和社媒数据整理配置；16 个生成型 Agent 均可独立选择 Kimi CLI、Codex CLI、模型 API 并填写模型名。
- 模型参数已进入实际 CLI/API 调用，生成记录使用真实 Provider 和模型，不再由部分函数写死 Kimi。新配置默认 Kimi CLI，既有明确保存的引擎和模型不重置。
- 后端 372 项通过、1 项跳过；前端 42 个文件、106 项通过，生产构建通过。

### 客户端自包含改造

- 主工作台改为 APP 自己的 WebKit 窗口；采集、账号和发布预填复用随包 Chromium 与工作区持久化配置，不再以 Chrome/WebBridge 为标准运行依赖。
- 统一可迁移 Python 包含 Whisper、RapidOCR、Demucs、OpenVoice、Playwright 及本地依赖；Whisper small/base、多语言 Transformers、Torch 和 NLTK 缓存随包提供。只补缺失缓存，不覆盖客户已有文件。
- Kimi/Codex 登录配置仍从用户原目录读取，不打包密钥；模型 CLI/API 和网络是保留的外部依赖。正式 8848 和原业务数据未改。
- 已验证：统一 Python 迁移导入、真实 Demucs 分轨、OpenVoice WAV、内置 Chromium 启动；`client-runtime-openvoice.wav` 为 2.948934 秒、PCM s16le、22050Hz 单声道。
- 真实 Kimi CLI 连接测试返回 `{"ok": true}`，文章插画 Agent 使用 `kimi_cli + default_unpinned`。
- 最终包冷启动媒体导入实测 337.42 秒成功，旧 180 秒冒烟超时据此调整为 600 秒；Chromium 上限为 300 秒。`--reuse-runtime` 只在输入未变化时复用资源，主服务与 APP 仍完整重建。
- 构建修复：Chromium 与独立 Python 不再交给 PyInstaller 改写，避免嵌套 APP 签名破坏；重复构建只替换生成的只读浏览器副本，模型缓存只补缺失文件。`librosa` 仍保留其必需的 `sklearn.decomposition`，`libomp` 单独签名通过。
- 冒烟曾发现主服务需要 `chromium_headless_shell-1223` 而包内只有 1140，已下载并同步 Chromium/Headless Shell 1223，同时保留媒体 Python 1.48 的 1140。最终 APP 重新签名后 smoke 通过：页面、授权配置、本地媒体导入、Chromium 实际启动和 26 个 Agent 均正常，结果为 `client-smoke.json`。
- 最终 APP 已在原生 WebKit 窗口实际打开；未激活工作区显示离线授权页，选择“先查看已有工作与成果”可进入“今天”。截图 `client-native-webkit.jpg`、`client-native-today.jpg`；未修改正式工作区指针。
- 真实媒体验收首次发现脚本把测试图命名为 `long-video-*.png`，而 OCR worker 只读取 `frame-*.png`；已修正验收脚本命名。随后 Kimi CLI 的 PATH 也已补齐，Whisper、OCR、Demucs、OpenVoice 和真实 Kimi CLI 完整通过，OCR 置信度 95.47%，结果为 `client-media.json`。
- 运行后的签名深检发现 Python 在 APP 内新增 `__pycache__`，导致密封资源失效。启动器、主服务和媒体验收现均禁止写入字节码；新增回归先失败后通过，相关 15 项测试与 Ruff 通过。修复版重新执行 smoke、完整媒体和原生窗口后，签名深检为 `valid on disk`、`satisfies its Designated Requirement`。
- 最终 DMG：`/Volumes/EXTERNAL_USB/kimi/storage/YingxuBuilds/mac-self-contained/Yingxu-Mac-x86_64.dmg`，6,037,654,436 字节（约 6.04 GB）。`hdiutil verify` 为 VALID；实际只读挂载后，从 DMG 内 APP 冷启动通过，26 个 Agent、本地媒体和浏览器均正常，随后已卸载。
- Apple Silicon、Developer ID 公证、干净客户 Mac、安装版覆盖升级和公开发布仍未验证。

## 2026-11-06 · Kimi 创作能力、媒体工具、平台预填与压力验收

### Kimi 与本地引擎的职责

- 文章生图不再使用独立 Codex 图片服务：Kimi CLI 生成 SVG 矢量插画，Remotion 在本地渲染 PNG；对应 Agent 已打入测试客户端。真实文章素材为 `asset_ea04d50b0fa240d99bce`，1200×1200，已抽图检查中文与布局。
- AI 配乐由 Kimi 输出可校验的音符谱，本地合成 WAV。项目 `20261106-001` 的文件 #18 `Kimi原创配乐.wav` 为 5.36 秒，与旁白一致。
- AI 单镜由 Kimi 编写 Remotion 场景，本地渲染 MP4；不是把 CLI 冒充成通用视频生成模型。文件 #21、#22、#23 分别为 1.833、2、1.567 秒，均 1080×1920、无音轨，抽帧见 `kimi-ai-shot-*.png`。
- 视觉理解由 Kimi 直接读取真实关键帧；对标项目 `20261105-003` 的第一镜纯红、第二镜纯蓝识别正确。
- 自动声音分离由 Kimi 规划，本地 Demucs 执行。文件 #19 人声、#20 伴奏均为 5.36 秒，原曲 #18 未覆盖，三个文件哈希不同。
- 新增 `article-image-agent.md`、`music-composer-agent.md`、`visual-analysis-agent.md`、`audio-separation-agent.md`；保留各引擎独立配置和失败提示。

### 本地工具安装与实测

- Playwright 1.48.0 已真实启动 Chromium；RapidOCR 1.4.4 已识别文章图片中文，视频技术预审的字幕边界检查通过。
- OpenVoice 已安装并真实转换：`docs/acceptance/video-projects/openvoice-kimi-test.wav`，5.270930 秒、PCM s16le、22050Hz 单声道、232,492 字节；应用内自测显示“已连接”。
- Kimi 风险分析已返回结果，但只能依据技术报告辅助判断，不能证明事实、版权和隐私全部安全，人工终审仍保留。
- 隔离依赖位于 APFS 的 `YingxuTools/`；未修改正式 8848 的媒体路径、账号和业务数据。

### 平台登录、选题与发布预填

- 抖音热点榜真实同步 20/20，形成 17 条研究快照；由首条快照创建项目 `20261106-002`，保留来源关联。
- 小红书个人收藏首次同步为部分完成：新增 0、更新 0，三个配置名称不匹配。核对真实收藏夹后，仅在隔离工作区改为“精选选题”“竞对账号内容”“高赞选题”；重试各读取 1 条，共新增 3 条、错误 0，记录 `sync_7913ea148dfa4b3386be`。未创建、改名或删除用户收藏。
- 发布批次 `pubbatch_b0f33c630e7b4f10a138` 使用审核项 `reviewitem_74f429936d954ebb88ab`，Kimi 生成的抖音、小红书、视频号字段均已保存。
- 抖音和小红书均已登录并上传同一条 5.376 秒审核成片，标题、正文和话题读回一致，状态为 ready/待确认，外部链接为空。视频号保持 draft/手动上传，未执行公开发布。
- 后台标签最初未加载视频元数据，导致抖音首次预填报“未回读时长”；在原上传页启用浏览器渲染并重新加载元数据后读回 5.376 秒，重试成功，没有放宽视频一致性校验，也没有重复公开发布。
- 证据：`docs/acceptance/video-projects/douyin-preview-ready.png`、`xiaohongshu-preview-ready.png`。

### 长视频与大量镜头

- 隔离压力项目 `20261106-004`、成片 #5：12 镜、69.013 秒、1080×1920、H.264 + AAC 双声道、11,460,604 字节；旁白驱动使总时长超过初始 60 秒镜头预算。
- 第 65 秒抽帧仍显示第 12/12 镜；音轨 volumedetect 平均 −18.5 dB、最大 −3.8 dB，不是空音轨。
- 第一轮压力脚本漏写 `rhythm: 旁白驱动`，只影响该测试脚本；已修正并重跑，不据此宣称生产代码曾丢音轨。
- 可重复脚本：`build/acceptance/run-long-video.py`；抽帧：`long-video-004-shot-12.png`、`long-video-004-tail.png`。

### 客户端、回归与未完成外部条件

- 后端全量 365 项通过、1 项跳过；前端 42 个文件、106 项通过。新增相关文件 Ruff 检查通过；旧 `app.py` 的历史风格问题未做大范围改写。
- 测试客户端 `/Volumes/EXTERNAL_USB/kimi/storage/YingxuBuilds/mac-kimi/映序工作台.app` 完整冒烟通过，文章图片、配乐、视觉分析、声音分离 Agent 与媒体模块均已确认打包。
- 当前构建机是 Intel x86_64、macOS 15.8.1，Xcode CLT 可用，但没有 Developer ID 证书，也没有第二台干净 Mac。正式签名公证、Apple Silicon 构建、安装版覆盖升级和干净客户 Mac 验收仍未完成，不得把 ad-hoc 签名和本机冒烟当成正式外部分发通过。
- 正式公开发布需要用户在平台后台检查封面、声明、可见范围等字段后自行决定；本次未点击最终发布。

## 2026-11-05～06 · 新用户全流程与全 Kimi CLI 隔离验收

### 验收边界与模型

- 使用全新隔离工作区 `/Volumes/EXTERNAL_USB/kimi/storage/YingxuNewUserWorkspace` 和服务 8766，从 `/welcome` 开始实测；未修改正式 8848、正式客户端、既有生产模型设置或账号。
- 系统默认文本模型及行业/抖音/小红书选题、脚本、素材规划、发布、账号分析、文章、视频审核 Agent 均显式使用 Kimi CLI 2.5.1。配音、字幕、Remotion、生图等独立执行器未强行替换。
- Kimi 最小调用、文章大纲与正文、原创编导、场景代码、脚本模型五字段自测、素材规划 JSON 自测均真实成功。
- 补齐 `agents/remotion-director-agent.md` 与 `agents/remotion-code-agent.md` 的 Kimi CLI frontmatter，保留原规则；新增全 Agent 文件声明头回归检查。

### 真实内容结果

- 文章 `item_3b099d42a4004a3da85f`：Kimi 大纲任务 `job_c9f232d181514ed28e57`、正文任务 `job_55af6c0fa7ac41658fc9` 成功；人工批准、导入真实图片并重新批准后，导出任务 `job_d3c3cc11109048979f5c` 成功。HTML 与含正文、图片、图片 credits 的 ZIP 均已实际下载。
- 原创 `20261105-002`：真实旁白词级时间码、8 秒原曲与 5.36 秒独立适配版、Kimi 3 镜编导、3 条逐镜样片及逐条验收完成。成片 #8 `yingxu-final-v22.mp4`，5.376 秒、1080×1920、H.264/AAC，892,543 字节；下载 SHA-256 为 `fb1d61d748caa0e06e32bee4998e32759c103c4704cae4a42677b12e942bfd76`。
- 原创审核批次 `review_b03f795365694afc8633`，制作 revision 25，技术预审通过、0 个阻断问题，保持待人工终审。
- 对标 `20261105-003`：4 秒参考视频拆成 2 镜、整片转写 1 次、真实关键帧与时间跳转有效。第一镜保留原镜头和原声；第二镜用 1 秒绿色上传视频循环到 2 秒并静音；8 秒原曲生成 4 秒独立适配版，明确保留并叠加声音。
- 对标成片 #15 `yingxu-final-v16.mp4`，4.011 秒、1080×1920、H.264/AAC，471,926 字节；前后抽帧确认红色保留镜头与绿色替换镜头。下载 SHA-256 为 `4e8432e01cc55932c556cb77dd127fa3a2e71482475b100f75b79d756b845702`。
- 对标审核批次 `review_d93746072f04439d8bf7`，制作 revision 19，技术预审通过、0 个阻断问题，保持待人工终审。
- 发布中心两条均显示“等待审核，尚未发布”，可发布队列为空；未登录平台、未同步或公开发布。
- 新增一条“待验证”增长记忆，来源明确为上述两个项目，注明无播放或转化数据；采集与发布知识库入口正常。

### 环境修复与自测

- 隔离环境继承的 `HF_HOME`、`TORCH_HOME` 曾指向失效的 `/Volumes/CodexData`；仅为 8766 进程改到 APFS 工作区缓存后，原创 small 与对标 base 模型均真实下载/转写成功。
- 原创第一版场景代码未通过安全校验，系统真实触发第二次 Kimi 修正；第二版通过后才渲染，未使用演示场景替代。
- 修复 Remotion 自测在 MP4 已成功校验后，临时目录清理竞态导致 500 的问题。仅捕获目录已不存在的 `FileNotFoundError`，保留其他错误；重跑页面自测显示“已连接”。系统语音、WhisperX、Remotion 自测均已连接。

### 回归与证据

- Python 全量：360 项通过，1 项跳过。新增测试 Ruff format/check 通过；`app.py` 仅格式化本次区域，仍有 121 项既有风格问题，未大范围改写。
- 既有前端 42 个文件、105 项测试、生产构建及 Remotion lint 沿用本次迭代此前通过结果；本轮未修改前端源码，未重复宣称新跑。
- 证据位于 `docs/acceptance/video-projects/`：`new-user-original-sample-*.png`、`new-user-original-final.png`、`new-user-benchmark-shot-*.png`、`new-user-today.png`。

### 未接入、未验证与风险

- AI 配乐、AI 视频、视觉语义模型、自动声音分离、OpenVoice、OCR 与 AI 风险审核未接入或未验证；Playwright 隔离环境待安装。
- 平台账号登录、真实平台选题同步、发布字段实际上传和公开发布未验证；未读取或配置用户凭据。
- 长视频、大量镜头、安装版升级、打包签名公证及干净客户 Mac 未验证。
- 接入向导中的环境文案仍显示开发默认地址 `127.0.0.1:8765/demo/`，在 8766 隔离验收中不是当前访问地址；未影响本次根路由实际操作。

## 2026-11-05 · 视频任务升级为视频项目

### 页面与功能

- 主侧栏改为“视频项目”，新增项目首页与“原创”“对标”子菜单；原编辑器保留。
- 原创实现文案、真人旁白和词级时间码、音乐适配、真实模板与编导分镜、样片、完整成片、验收和审核交付。
- 对标实现真实参考视频拆解、关键帧与一次整片转写、报告时间跳转与导出、逐镜上传/旁白/音轨/时长处理、音乐冲突处理、样片、完整成片、验收和审核交付。
- 全部页面原生位于现有 AppShell，没有 iframe、webview、第二套导航或原型服务依赖。
- 上传素材、AI 候选、样片与完整成片分开；未验收不能下载最终版或推送审核。推送发布中心不等于公开发布。

### 数据与兼容

- 沿用原任务、项目 ID、文件、revision/CAS、草稿、审核和发布关系；未新增表、未迁移或清空数据。
- 旧任务无 `project_type` 时按原创读取；`/tasks/:id` 和 `/tasks/:id/editor` 均保留。
- 新增词级时间码文件、音乐独立适配版本、对标报告与关键帧，源文件不覆盖。
- Remotion 支持对标的真实截取、循环、末帧静止、静音与逐镜旁白；混合音轨不声称自动分离。
- 项目列表刷新失败时直接读取原项目接口，修复新建后或旧深链误报“项目不存在”。

### 真实验收

- 原创 `20261105-001`：成片 #6 `yingxu-final-v18.mp4`，5.376 秒、1080×1920、H.264/AAC；审核批次 `review_104ad10220b44d14a4b3`；验收后下载已完成，491,565 字节。
- 对标 `20261105-002`：2 镜、整片转写 1 次；成片 #14 `yingxu-final-v19.mp4`，4.011 秒、1080×1920、H.264/AAC；审核批次 `review_3e11cd41d01a494a80db`。
- `/tasks/20261103-001` 在数据库副本中保留标题、正文和文件 #20；真实库 approved handoff、revision 36 和 SHA-256 未变。
- 发布中心显示两条新成片“等待审核，尚未发布”；未执行公开发布。
- 选题、文章、审核、发布、记忆、设置和旧版入口回归正常。

### 测试

- Python：358 项通过，1 项跳过。
- React：42 个文件、105 项测试通过；生产构建通过。
- Remotion：ESLint 和 TypeScript 通过。
- 新增 Python 测试及 worker：Ruff format/check 通过。旧 `app.py` 有 124 项历史风格问题，未大范围改写。
- 既有前端全量 ESLint 基线 314 errors、16 warnings，未宣称全绿。
- 证据：`docs/acceptance/video-projects/`、`docs/VIDEO_PROJECT_ITERATION.md`。

### 未接入、未验证与风险

- AI 配乐、AI 视频、视觉语义模型、自动声音分离和独立 Remotion Studio 未接入；自定义画风包待确认。
- 长视频性能、首次模型下载、真实平台公开发布、真实备份第二次迁移和安装版升级后行为未验证。
- 竖屏弹窗在 1280×800 下需滚动；外接磁盘曾短暂出现 SQLite disk I/O error，后续恢复。
- 未覆盖 `/Applications/映序工作台.app`，未提交或推送 Git。

## 2026-11-05 · 原型逐项对齐与去重复

- 删除原创“创建开始写稿”和“文案创作”的重复步骤：首屏直接写文案，确认后直接进入旁白；对标同样直接进入提供参考，不增加项目创建层。
- 对齐原创/对标标题、说明、标语、上传区域、按钮、阶段条、音乐库双栏、逐镜弹窗与最终验收结构。
- 原创样片移回生产画面，支持多镜逐条真实生成和逐条人工通过；最终页不再重复样片。
- 音乐库支持文件夹多首真实导入，新增保留无音乐段落适配；报告保存可选关注重点。
- 修复原创专用 CSS 未加载导致直开/刷新布局失效的问题。
- 真实新建 `20261105-006` 验证确认方案后直接上传旁白；双栏、对标弹窗和阶段条均有浏览器截图。
- 后端完整回归 358 项通过、1 项跳过；新增多镜样片测试证明两次真实渲染和全部确认门槛。

## 2026-11-05 · 开发数据库迁移到 APFS

- 使用 SQLite 在线备份，将开发库迁移到 `/Volumes/EXTERNAL_USB/kimi/storage/YingxuDevWorkspace/data/content-agent.db`，不覆盖原库。
- 回滚备份保留为 `data/backups/content-agent-pre-apfs-20261105-215607.db`；原开发库仍保留。
- CodexData 因容器超级块无效无法挂载，未修复、未格式化；8848 配置与数据库未修改。
- `scripts/start.sh` 在 APFS 新库存在且未显式配置时默认使用新库，显式 `CONTENT_AGENT_DB` 仍可回滚。
- 切换前原库、新库、回滚备份均为 6 个项目、14 个文件、2 条审核交付，完整性均为 `ok`。
- 新建 `20261105-007` 验证真实写入成功，APFS 新库为 7 个，原库和回滚备份仍为 6 个。
- 审核、发布、选题、文章、设置和记忆页面正常；运行日志未发现新的磁盘错误或 500/503/409。
- 迁移与回滚命令、校验和限制详见 `docs/APFS_MIGRATION.md`。
