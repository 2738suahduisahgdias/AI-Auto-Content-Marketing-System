# 映序页面、卡片、功能与技术方案矩阵

更新：2026-11-13。功能编号索引见 `docs/FUNCTION_IDS.md`，编号规则为 `P页码-C卡序号-F功能序号`。

## 表格口径

- 一级是页面，二级是页面中的真实卡片或工作区，三级是卡片里的按钮、输入框、选择器、链接或具体功能。
- “功能描述”写用户操作后的真实效果和关键限制；“技术方案”写当前代码中的前端调用、后端服务、数据存储、浏览器／模型／媒体引擎，不把目标设计写成已实现。
- 同类动态卡片合并，例如四个平台卡、逐镜卡和记忆卡；不同技术链路分别列出。完整输入限制另见 `FUNCTION_MAP.md` 的 A～K 控件级说明书。
- 新版入口省略 `/demo`。页面可打开不等于真实生成、账号同步、上传预填或公开发布已再次验收。

## 1. 全局与今天

| 一级：页面 | 二级：卡片／工作区 | 三级：卡片元素和功能 | 功能描述 | 功能背后调用的技术方案 |
|---|---|---|---|---|
| 全局框架 | 侧栏与移动导航 | 页面导航、选题／视频／设置展开按钮、旧版入口 | 切换真实路由；展开只改变菜单；旧版进入 `/legacy` | React Router `BrowserRouter(basename=/demo)`；`App.tsx` 懒加载；`AppShell.tsx` 共享导航 |
| 全局框架 | 全局数据层 | 页面数据刷新、加载与错误提示 | 聚合各模块真实数据，失败显示错误，不以空数据冒充成功 | `AppContext.tsx` 并发请求 core/topics/agents/accounts/articles/knowledge；`api.ts` 处理 CSRF、会话恢复和错误 |
| 全局框架 | 精简资源下载卡 | 下载全部、失败重试、稍后再下载 | 下载九组运行资源；运行中不可关闭提示 | `/api/slim-dependencies`；`desktop/slim_download.py`；资源写入工作区 `tools/cache/runtime`，不写回签名 APP |
| 今天 `/` | 今日推荐卡 | “生成今日推荐” | 后台结合真实来源和增长记忆生成跨平台推荐；活动任务防重复 | POST `/api/topics/recommend {agent:all}` → `wb_jobs` → `TopicExecutors.recommend` → 配置的 Kimi/Codex/API 与 `KnowledgeService` |
| 今天 `/` | 今日推荐卡 | 推荐条目、理由与证据切换 | 切换当前推荐，显示对应证据，不创建任务 | React 本地选择状态；推荐和证据来自 `TopicService.bootstrap` |
| 今天 `/` | 今日推荐卡 | “制作视频／打开视频任务” | 创建或继续视频项目，保留推荐依据 | POST `/api/topics/candidates/:id/create-task`；旧 `tasks` 项目与 `source_json` 来源关联 |
| 今天 `/` | 今日推荐卡 | “写文章／改做视频” | 创建文章或把文章型推荐转为视频 | POST `/api/articles` 或候选 create-task；文章使用 `wb_campaigns/wb_content_items`，视频使用 `tasks` |
| 今天 `/` | 待继续创作·文章 | 文章条目与继续按钮 | 继续编辑、审核或交给发布 Agent | GET `/api/v2/work-overview`；`overview.py` 只读查询 `wb_content_items/wb_campaigns` 并生成原路由 |
| 今天 `/` | 待继续创作·视频 | 视频条目与继续按钮 | 继续制作；交付过期或已送审时提示对应下一步 | 同上，只读查询 `tasks.source_json.yingxu_handoff`；链接到项目或审核批次 |
| 今天 `/` | 待审核卡 | 审核条目 | 查看技术预审和人工审核 | `overview.py` 查询 `review_items`，链接 `review_batches`；不改审核状态 |
| 今天 `/` | 待同步到平台卡 | 发布条目 | 打开发布工作区检查字段与状态 | `overview.py` 联查 `publish_targets/publish_batches`；状态不是公开结果 |
| 今天 `/` | 候选选题卡 | “查看历史／开始创作” | 展开全部候选；从原候选创建视频任务 | React 本地展开；POST `/api/tasks {topic_id}` 写入 `tasks`，保留原候选关联 |
| 今天 `/` | 空状态与错误区 | 去选题中心、失败原因和重试提示 | 无快照时先采集；模型失败保留已有推荐 | `TopicService` 真实快照和 `wb_jobs.error_json`；不生成演示推荐 |

## 2. 选题中心

| 一级：页面 | 二级：卡片／工作区 | 三级：卡片元素和功能 | 功能描述 | 功能背后调用的技术方案 |
|---|---|---|---|---|
| 行业热点 `/topics/industry` | 页头操作区 | “同步内容” | 获取公开行业资讯并形成研究快照 | POST `/api/topics/industry` → `TopicExecutors.industry` → `industry_connector.fetch_industry`；结果写入 TopicService 快照 |
| 行业热点 `/topics/industry` | 行业资讯快照卡 | 原链接、转选题、归档 | 打开真实资讯、保存候选或归档 | `TopicService.upsert_item/save_candidates/archive`；SQLite 研究条目和候选，不用静态示例 |
| 行业热点 `/topics/industry` | 推荐卡 | 写文章、制作视频、改做视频 | 按推荐格式创建对应任务 | `/api/articles` 或 `/api/tasks`；保留 evidence_ids 和推荐依据 |
| 抖音 `/topics/douyin` | 页头操作区 | “同步内容” | 先核对登录；未登录时等待本人操作最多 5 分钟，再同步热点及个人收藏，活动任务复用 | POST `/api/topics/sync` → `wb_jobs` → `TopicExecutors.sync` → `KimiBrowserCollector` → Kimi CLI／`douyin-collection-agent` 通过 `chrome-persistent` 操作固定 Chrome |
| 抖音 `/topics/douyin` | 来源标签卡 | 热点、精选、竞对、高赞 | 切换不同收藏来源，热点显示实际数量 | `TopicService.bootstrap` 读取分类快照；本地 `douyinView` 状态 |
| 抖音 `/topics/douyin` | 采集与自动化抽屉 | 行业范围、三类 Agent 提示词 | 设置检索与推荐补充规则；必填，单项最长 12000 字符 | POST `/api/topics/settings` → `TopicService.save_settings`；SQLite `settings`，裁剪到 12000 并校验非空 |
| 抖音 `/topics/douyin` | 采集与自动化抽屉 | 精选／竞对／高赞收藏夹 | 保存与本人账号一致的收藏夹名称 | 同上；执行时 `KimiBrowserCollector.collect` 通过 Kimi CLI 在真实页面定位收藏夹 |
| 抖音 `/topics/douyin` | 采集与自动化抽屉 | 每日时间、启用每日任务 | 设置 `HH:MM` 定时采集并保存 | `TopicService.save_settings` 校验 00～23 时、00～59 分；`topics/scheduler.configure_schedule` |
| 抖音 `/topics/douyin` | 采集与自动化抽屉 | “连接抖音采集窗口” | 已登录时直接确认；未登录时在同一固定窗口等待本人操作，最长 5 分钟，超时保留页面与旧数据 | POST `/api/topics/browser/open` → `topics.login` → `KimiBrowserCollector.ensure_login(300)`；Kimi CLI 通过 `chrome-persistent` 核对真实页面，不读取或导出 Cookie |
| 小红书 `/topics/xiaohongshu` | 采集与自动化抽屉 | 精选／竞对／高赞收藏夹 | 保存三类个人收藏夹映射；平台热点不读取个人收藏夹 | POST `/api/topics/settings`；`xhs_featured/competitor/high_praise_collection`；`TopicExecutors.xhs_sync` |
| 小红书 `/topics/xiaohongshu` | 采集与自动化抽屉 | “连接个人小红书” | 通过 Kimi CLI 在固定 Chrome 核对真实个人登录；打开窗口不等于登录成功 | POST `/api/topics/xiaohongshu/browser/open` → `topics.xhs_login` → `XHSBrowserCollector`；复用持久化资料，不读取或导出 Cookie |
| 行业／抖音／小红书 | 作品卡 | 原链接 | 打开真实作品来源 | 卡片 `canonical_url`；浏览器新标签，不经过模拟详情页 |
| 行业／抖音／小红书 | 作品卡 | “转为选题／创建任务” | 收藏候选或创建视频任务 | `/api/topics/items/:id` 或 `/create-task`；`TopicService` + `tasks.source_json` |
| 抖音作品卡 | 媒体研究区 | “下载视频／重新下载” | 由 Kimi CLI 下载真实视频并保存本地地址，不执行拆解 | POST `/api/topics/items/:id/analyze` → `research.analyze` → `douyin_download`；真实文件写入本地资产库 |
| 抖音作品卡 | 媒体研究区 | “详情／查看下载” | 查看真实下载文件、大小和本地地址 | GET `/api/topics/items/:id`；`DownloadDetail` 与 `wb_assets` |
| 抖音作品卡 | 媒体研究区 | “重新获取封面” | 重试封面读取和本地缓存 | POST `/api/topics/items/:id/cover/retry`；`TopicExecutors.retry_cover/cache_cover` |
| 行业／抖音／小红书 | 作品卡 | “归档／恢复” | 改变条目归档状态，不删除来源 | POST `/api/topics/items/:id/archive`；SQLite 保留原始快照 |
| 抖音作品卡 | 作者与互动数据区 | 作者名称、作者粉丝数、点赞数、评论数 | 打开真实作品页补齐作者与互动信息；读不到时保留未读取，不猜数字 | `TopicExecutors.enrich` → `KimiBrowserCollector.collect("details")` → Kimi CLI 读取作品页与作者页；规范化顶层或条目内 `details` 后写入 `wb_research_items.metadata` |
| 行业／抖音／小红书 | 同步记录抽屉 | 任务状态、错误详情、重试同步 | 查看部分成功与失败原因，手动重试 | `wb_jobs`、执行日志与对应 sync API；旧有效快照不被空结果覆盖 |
| 行业／抖音／小红书 | 直接创建视频任务弹窗 | 标题、支柱、人群、痛点、收藏夹、内容切入 | 输入选题并直接进入文案；标题必填且最多 200 字 | POST `/api/tasks`；`tasks` 与 `source_json` 保存分类和来源 |
| 行业／抖音／小红书 | 研究详情弹窗 | 刷新详情、导出下载信息 | 读取当前真实条目并导出下载 JSON，不伪造成拆解报告 | GET `/api/topics/items/:id`；本地下载当前详情 |
| 行业／抖音／小红书 | 研究详情弹窗 | 本地素材、完整路径、文件大小和资产索引 | 已下载时显示真实视频或全部图文文件信息，未下载时显示真实状态 | `DownloadDetail`；`metadata.download_status/download_path/download_media_kind` |
| 行业／抖音／小红书 | 研究详情弹窗 | 打开所在文件夹、复制本地地址 | 调用系统文件管理器或剪贴板处理已下载路径 | POST `/download/reveal`、`/download/copy`；没有真实文件时不显示成功状态 |
| 小红书 | 平台热点卡 | 热点选题标签、排名列表 | 显示真实热点顺序、数量和原链接；普通推荐 feed 不作为热点 | `xiaohongshuView=hot`；`TopicService.bootstrap.sources.xhs_hot` |
| 小红书 | 平台热点卡 | 热点同步与快照字段 | 只保存排名、热度、标题和真实链接，不进入作者互动补全 | `TopicExecutors.xhs_sync` → `XHSBrowserCollector` → `xhs_public_hot`；研究快照 `metadata` |
| 小红书 | 精选收藏卡 | 精选标签、数量与列表 | 切换并显示精选个人收藏的真实作品 | `xiaohongshuView=featured`；`sources.xhs_featured` |
| 小红书 | 精选收藏卡 | 作者、粉丝、点赞、评论、封面 | 逐条补全并展示实际读取结果；缺字段不猜测 | `XHSBrowserCollector` 读取作品与作者；`wb_research_items.metadata` |
| 小红书 | 精选收藏卡 | 收藏夹配置与同步状态 | 按配置的精选收藏夹执行，保留部分完成和具体错误 | `xhs_featured_collection`；`favorite_featured_completed`、`xhs_last_sync` |
| 小红书 | 竞对收藏卡 | 竞对标签、数量与列表 | 切换并显示竞对收藏；真实空收藏保持空状态 | `xiaohongshuView=competitor`；`sources.xhs_competitor` |
| 小红书 | 竞对收藏卡 | 作者、粉丝、点赞、评论、封面 | 逐条补全并展示实际读取结果；缺字段不猜测 | `XHSBrowserCollector` 读取作品与作者；`wb_research_items.metadata` |
| 小红书 | 竞对收藏卡 | 收藏夹配置与同步状态 | 按配置的竞对收藏夹执行，不能用其他收藏内容填充 | `xhs_competitor_collection`；`favorite_competitor_completed`、真实错误记录 |
| 小红书 | 高赞收藏卡 | 高赞标签、数量与列表 | 切换并显示高赞个人收藏的真实作品 | `xiaohongshuView=high_praise`；`sources.xhs_high_praise` |
| 小红书 | 高赞收藏卡 | 作者、粉丝、点赞、评论、封面 | 逐条补全并展示实际读取结果；缺字段不猜测 | `XHSBrowserCollector` 读取作品与作者；`wb_research_items.metadata` |
| 小红书 | 高赞收藏卡 | 收藏夹配置与同步状态 | 按配置的高赞收藏夹执行，保留部分完成和具体错误 | `xhs_high_praise_collection`；`favorite_high_praise_completed`、`xhs_last_sync` |
| 小红书 | 素材探测下载弹窗 | 下载素材、真实探测 | 先读取作品类型与可用档位；探测本身不下载文件 | POST `/download/probe` → `research.probe` → `probe_xiaohongshu_media`；Kimi CLI + video-downloader；命令行无公开结果时由固定 Chrome 读取同作品实际媒体，不导出 Cookie |
| 小红书 | 素材探测下载弹窗 | 视频／图文类型与档位 | 视频显示实际尺寸、时长和来源，未知大小或码率留空；图文明确显示图片组，不虚构视频档位 | `research.probe.result.media_kind/formats`；`DownloadProbeModal`；固定 Chrome 当前流标记 `source=fixed_chrome` |
| 小红书 | 素材探测下载弹窗 | 画质优先、速度优先、兼容优先 | 用户选择后才提交对应下载任务；下载后核验真实文件 | POST `/analyze {mode:quality/speed/compat}` → `research.analyze` → `download_xiaohongshu_media`；视频 FFprobe，图文逐文件检查并保存全部实际图片 |
| 小红书 | 素材探测下载弹窗 | 执行中、失败与无素材状态 | 显示真实进度和终态错误；没有素材信息时不创建下载任务 | `TopicService.bootstrap.jobs` 包含 `research.probe`；`wb_jobs.status/stage/error`；`DownloadProbeModal` 终态不再持续显示读取中 |
| 微信 `/topics/wechat` | 分类标签卡 | 待分类、精选、竞对、高赞、行业、归档 | 筛选消息并显示分类数量 | `WechatInboxService` 读取 SQLite 原始消息与后台分类；React 本地筛选 |
| 微信 `/topics/wechat` | 手动记录弹窗 | 原始链接、内容或想法 | 保存一条待分类消息；正文必填最多 12000 字 | POST `/api/topics/wechat/messages`；`WechatInboxService.create`；不自动访问链接 |
| 微信 `/topics/wechat` | 消息卡 | 整理、归档／恢复 | 修改后台标题、备注、分类；原文只读 | POST `/api/topics/wechat/messages/:id`；标题最多 200、备注最多 12000，原始消息不变 |
| 微信 `/topics/wechat` | 消息卡 | 生成快照／重新解析 | 解析链接公开信息，形成研究快照 | POST `/api/topics/wechat/messages/:id/snapshot` → `WechatSnapshotExecutor/link_snapshot` |
| 微信 `/topics/wechat` | 消息卡 | 转为内容任务 | 从研究条目创建视频项目 | `TopicAPI` create-task；`tasks.source_json` 保留研究条目 ID |
| 微信 `/topics/wechat` | 微信 Bot 连接卡 | 生成二维码、打开扫码页 | 获取真实二维码并供本人扫码 | `/api/topics/wechat/client/login`；`wechat_client.py` 官方连接流程，二维码与连接状态分开 |
| 微信 `/topics/wechat` | 微信 Bot 连接卡 | 配对码、检查连接 | 需要时输入官方配对码并轮询连接 | POST `/api/topics/wechat/client/poll {code}`；仅 `need_verifycode` 使用 |
| 微信 `/topics/wechat` | 微信 Bot 连接卡 | 断开并重新连接 | 确认后停止接收新消息，不删除选题 | POST `/api/topics/wechat/client/disconnect`；原始消息和研究数据独立保存 |

## 3. 文章任务

| 一级：页面 | 二级：卡片／工作区 | 三级：卡片元素和功能 | 功能描述 | 功能背后调用的技术方案 |
|---|---|---|---|---|
| 文章列表 `/articles` | 全部文章卡 | 搜索、状态筛选、分页 | 按标题与状态筛选，每页 10 篇 | `ArticlesAPI.bootstrap`；`Workbench` 查询 `wb_campaigns/wb_content_items`；前端本地筛选 |
| 文章列表 `/articles` | 全部文章卡 | 文章条目 | 打开独立文章路由 | `/articles/:id`；按稳定文章 ID 读取，不复制项目 |
| 新建文章弹窗 | 创建表单 | 文章主题、初始要求、创建／取消 | 标题必填最多 200 字；只创建本地文章 | POST `/api/articles` → `Workbench.create`；`wb_campaigns/wb_content_items` |
| 文章编辑器 `/articles/:id` | 顶部导航与版本信息 | 返回、切换文章、版本详情 | 切换文章并显示当前版本；草稿保存失败时提醒 | React Router；`useContentDraft` 本机草稿；正式版本来自 `wb_revisions` |
| 文章编辑器 `/articles/:id` | 工作区标签 | 写文案、配图片、排版交付 | 切换同一文章工作区 | React 本地 `workspace`；共享同一文章和 revision |
| 写文案 | 主要平台与写作目的卡 | 平台、目的、加入写作要求 | 选择公众号／小红书；把目的追加到生成要求，不启动生成 | `ArticleCreativePlan` 本地计划；随正文 revision 保存 `creative_plan` |
| 写文案 | 文章要求卡 | 补充要求 | 设置本次 AI 生成附加要求 | POST `/api/articles/:id/generate` 时传入 prompt；不自动成为正文 |
| 写文案 | 论证大纲卡 | 生成大纲、编辑、确认大纲 | 生成或手写大纲；保存正式版本供正文使用 | POST `/generate {operation:article.outline}`；POST `/revisions`；`Workbench.save_revision + ProviderRegistry + wb_revisions` |
| 写文案 | 完整正文卡 | 生成正文、编辑、保存正式版本 | 依正式大纲生成或手写正文；修改后旧审批失效 | `article.draft` → `ArticleExecutors`；`Workbench.save_revision` 版本与 CAS |
| 写文案 | 人工审核区 | 提交审核、批准、退回 | 审批绑定当前正文 manifest；退回保留草稿 | POST `/api/articles/:id/actions`；`wb_approvals` + manifest hash + active revision |
| 配图片 | 配图计划卡 | 添加／移除位置、用途、获取方式 | 规划搜索、AI 或自有图片的位置，不直接产生图片 | `ArticleCreativePlan.pictures` 随 `creative_plan` 保存到 revision |
| 配图片 | 配图计划卡 | 画面描述、插入段落 | 设置提示词和插入位置；段落最小 0 | 同上；导出按空行分段和 `after_paragraph` 处理 |
| 配图片 | 搜索工具卡 | 搜索图片、下载并采用 | 搜索候选，下载后绑定素材 | `/api/articles/images/search`、`/adopt`；`articles/images.py` 搜索服务 + `wb_assets` |
| 配图片 | AI 插画卡 | 生成图片 | 生成 SVG 插画并本地渲染 PNG，绑定当前位置 | `/api/articles/images/generate`；Kimi CLI → SVG 安全校验 → Remotion 本地 PNG → `wb_assets` |
| 配图片 | 本地图片卡 | 素材选择、图片路径、导入并采用 | 选择已有图片或引用 PNG／JPEG／WebP 原图 | `/api/v2/local-assets`；`Workbench.import_local_asset` 校验路径与 MIME；图片 ID 写入创作计划 |
| 排版交付 | 交付形式卡 | 公众号／小红书格式选择 | 选择正文、分页图或图文包 | `creative_plan.format`；`articles/page_worker.py` + Pillow／中文字体 |
| 排版交付 | 导出卡 | 导出当前正文 | 生成 HTML、Markdown、ZIP 和所选分页 PNG | POST `/api/articles/:id/export`；仅已批准 revision；`Workbench.export_article` + `wb_assets` |
| 排版交付 | 下载区 | HTML／Markdown／ZIP／分页图下载 | 下载实际生成的文件 | 本地导出目录与文件下载接口；ZIP 含正文和原图，Markdown 不内嵌图片 |
| 排版交付 | 继续制作区 | 从已保存正文制作视频 | 以当前正式正文版本创建视频 | POST `/api/tasks {article_id,article_revision_id}`；`tasks.source_json` 保存版本来源 |
| 排版交付 | 发布入口 | 前往发布中心 | 打开当前文章的发布准备 | `/publish?kind=article&id=...`；`PublishingService.source("article")` 校验当前批准版本 |


## 4. 视频项目首页、原创与对标

| 一级：页面 | 二级：卡片／工作区 | 三级：卡片元素和功能 | 功能描述 | 功能背后调用的技术方案 |
|---|---|---|---|---|
| 视频项目 `/projects` | 页头操作区 | 新建原创、新建对标 | 进入对应首屏，不立即创建项目 | React Router；`CreateOriginal/CreateBenchmark` 组件 |
| 视频项目 `/projects` | 项目工具卡 | 搜索、项目类型筛选、新建视频 | 按名称／ID 和类型过滤 | `AppContext.core.tasks` + `projectType(task.source.project_type)`；本地筛选 |
| 视频项目 `/projects` | 项目卡 | 项目类型、ID、交付状态、打开 | 继续原项目，显示继续创作／已关联／需重新交付 | `tasks.source_json.yingxu_handoff`；原项目 ID 与 revision，无示例 ID 写死 |
| 原创 `/projects/original[/:id]` | 阶段导航卡 | 01～05 阶段按钮、帮助“？” | 返回已开放阶段，查看操作说明 | `StageNavigation` + `workflow_stage`；锁定状态来自项目快照 |
| 原创 | 文案创作卡 | 叙事方向、正式文案 | 可手写完整文案，也可只填叙事方向生成；AI 生成时方向必填，进入下一步时正式文案必填 | `CreateOriginal.validate`；POST `/api/tasks`；PUT `/api/tasks/:id/yingxu` 保存 snapshot 和 revision |
| 原创 | 文案创作卡 | 目标平台、画幅、自定义宽高 | 平台至少一项；画幅必选；自定义宽高均大于 0 | 前端校验后写入 `source_json.target_platforms/aspect`；Remotion 使用对应尺寸 |
| 原创 | AI 文案候选区 | 按方向生成／改写、候选编辑、采用或保留当前文案 | 无文案时生成，有文案时改写；候选不自动覆盖，采用时保留非空历史版本 | POST `/yingxu-script-candidate`；明确传递 operation、direction、current_text、target_platforms、aspect；历史存入 `manuscript.versions` |
| 原创 | 文案创作卡 | 确认方案，进入视频生成 | 校验正式文案、平台和画幅后创建／保存并进入旁白；方向不是手写路径必填项 | `/api/tasks` + `/yingxu`；`useVideoProject` 本机草稿和 revision CAS |
| 原创 | 旁白与时长卡 | 上传真人旁白 | 上传真实音频并显示文件和时长 | POST `/yingxu-files?kind=audio`；`stream_upload` 限制非空／500MB；FFprobe 媒体信息 |
| 原创 | 旁白与时长卡 | 生成词级时间码 | 后台对旁白生成逐词文本和起止秒数，显示真实阶段、百分比和已用时间；同模型进程复用；短术语提示改善中文和品牌识别 | POST `/transcript` → `wb_jobs.project_transcript`；GET `/transcript-jobs/:id`；faster-whisper `--serve` 常驻 worker，`beam_size=5` + 200 字符内开头语境与品牌术语 hotwords；词级结果写入 snapshot，仍需人工校对 |
| 原创 | 旁白与时长卡 | 词语、开始、结束 | 只读查看转写与同步时间 | `snapshot.transcript.words`；不允许前端手改 |
| 原创 | 旁白与时长卡 | AI 修改旁白、分段试听 | 两个按钮均明确未接入 | 无后端调用；禁用控件，不计为可用能力 |
| 原创 | 旁白与时长卡 | 确认旁白与时长 | 转写有效后进入音乐 | `voiceFileId + transcript.words + !transcriptStale` 前端门槛；保存 `/yingxu` |
| 原创 | 生产画面卡 | 选择画风、模板预览 | 查看真实模板效果并选择风格 | GET `/api/video-templates`；`media/templates.py` 注册表和本地预览 |
| 原创 | 生产画面卡 | 生成分镜 | 根据文案、画风和真实时间码生成分镜 | POST `/yingxu-director-candidate` → Remotion 编导 Agent + 配置模型；`directorPlan` 保存快照 |
| 原创 | 生产画面卡 | 选择分镜、分别生成 | 为选中镜头生成独立 AI 单镜 | POST `/ai-video` → Remotion 场景代码 Agent → 安全校验 → Node/Remotion 渲染无声 MP4 |
| 原创 | 镜头详情弹窗 | 起止时间、旁白文字 | 修改当前镜头时间线和文本 | `patchShot` 修改 snapshot；保存 `/yingxu`；不会自动重转写整段音频 |
| 原创 | 镜头详情弹窗 | 上传／更换视频 | 添加真实镜头画面版本 | POST `/yingxu-files?kind=video`；本地文件记录与媒体校验；旧版本保留 |
| 原创 | 镜头详情弹窗 | 新画面描述、视觉参考 | 设置 AI 场景的构图、材质和运动约束 | 随 `/ai-video` prompt 进入 Remotion 场景代码 Agent |
| 原创 | 镜头详情弹窗 | AI 生成版本选择 | 在真实 AI 候选间切换 | `aiCandidateFileIds + fileId + source=ai_video`；本地 `files` 记录 |
| 原创 | 镜头详情弹窗 | 保存本镜、确认本镜 | 保存不等于确认；有画面或有效 Remotion 代码后才能确认 | `shot.confirmed` + `shot.fileId/source`；`useVideoProject.save` revision |
| 对标 `/projects/benchmark[/:id]` | 提供参考卡 | 选择参考视频 | 上传真实参考，显示名称与大小 | POST `/yingxu-files?kind=video`；`stream_upload` + FFprobe；不用演示视频 |
| 对标 | 提供参考卡 | 关注重点（可选） | 指导拆解并形成标题候选；不要求使用边界 | POST `/api/tasks {source_type:benchmark}`；`source_json.focus` |
| 对标 | 提供参考卡 | 查看拆解报告 | 创建项目并执行真实场景拆分、转写或画面字幕识别 | POST `/benchmark-analyze` → `app.py analyze_benchmark`；FFmpeg `scene=0.25` 场景检测 + Whisper base 整片转写 + 真实关键帧；无音轨时 RapidOCR 读取画面文字 |
| 对标 | 拆解报告卡 | 原视频、时间码、逐镜说明、画面字幕 | 保留原片时间码、文本和画面对照；旁白与画面字幕分开显示 | `benchmark_report` + `shots.original_start/end_seconds` + `keyframe_file_id` + `subtitle_text/subtitle_status` |
| 对标 | 拆解报告卡 | 用 Kimi 分析关键帧 | 根据实际帧补充视觉分析 | POST `/benchmark-visual-analysis` → 视觉分析 Agent 读取真实图片；不虚构不可见信息 |
| 对标 | 拆解报告卡 | 报告备注、导出报告 | 保存人工备注并导出真实报告 | snapshot `benchmark_notes`；本地下载当前报告 JSON／文档 |
| 对标 | 逐镜替换卡 | 选择分镜、逐镜编辑 | 多镜选择或打开单镜处理 | React `checked/selected`；`shotReady` 统一校验 |
| 对标 | 镜头详情弹窗 | 原视频对照、保留原镜头 | 使用原参考时间区间、时长和自带声音 | `source=reference`、`trim_start=original_start`、`audio_source=original` |
| 对标 | 镜头详情弹窗 | 新旁白、上传本镜旁白 | 编辑文本或上传替换音频；替换旁白必须有真实文件 | `/yingxu-files?kind=audio`；`narrationFileId + audio_source=replace` |
| 对标 | 镜头详情弹窗 | 上传／更换视频、用户版本 | 添加或切换上传画面，重置相关确认 | `uploadedFileIds`；`source=user_upload`；文件 ID 关联 |
| 对标 | 镜头详情弹窗 | 新画面描述、AI 版本 | 生成并选择 Remotion 单镜 | 与原创 `/ai-video` 共用；`aiCandidateFileIds` 与上传版本分开 |
| 对标 | 镜头详情弹窗 | 声音检查 | 选择原声、替换旁白或静音 | `audio_source`；`fileAudioPresent` 只判断音轨存在，构成由人工确认 |
| 对标 | 镜头详情弹窗 | 有效时长、截取起点 | 保持原时长或用新视频时长；设置截取起点 | `duration_choice/trim_start`；`shotAvailableDuration = 文件时长－起点` |
| 对标 | 镜头详情弹窗 | 视频不足补足方式 | 选末帧静止或循环；不足超过 0.05 秒容差时必选 | `fill_method=freeze/loop`；`shotReady`；Remotion 实际截取／循环／末帧处理 |
| 对标 | 镜头详情弹窗 | 保存本镜、确认本镜 | 校验画面、声音、时长和必需音频后确认 | `shotReady` + `shot.confirmed`；保存 `/yingxu` |
| 原创／对标 | 音乐卡 | 上传音乐、选择音乐库文件 | 添加或切换真实配乐 | `/yingxu-files?kind=audio`；`bgmFileId`；本地音频列表 |
| 原创／对标 | 音乐库卡 | 选择／更换本地文件夹 | 批量导入支持的音频到当前项目 | 浏览器 `webkitdirectory`；过滤音频扩展并逐个上传；文件复制到项目 |
| 原创／对标 | 音乐卡 | 音乐方向、AI 生成配乐 | 按时长和方向生成真实 WAV | POST `/music-generate` → Kimi 音符谱 → `media/ai_music.py` 本地合成 WAV |
| 原创／对标 | 音乐卡 | 时长适配方式、AI 适配时长 | 生成淡出、循环或保留无音乐段落的独立版本 | POST `/music-adapt`；FFmpeg 音频处理；`musicAdaptedFileId/adapted_from` |
| 原创／对标 | 音乐卡 | 试听适配后配乐与旁白 | 同步试听，音乐音量 35%，可暂停 | 浏览器双 `<audio>` 播放；不调用云端，不修改音频 |
| 原创／对标 | 音乐卡 | 分离当前音频人声／伴奏 | 生成独立人声和伴奏，原曲不变 | POST `/audio-separate` → Kimi 规划 + 本地 Demucs；新文件记录 |
| 对标 | 音乐冲突卡 | 原声不另加／先处理再换／叠加 | 解决原视频声音与新音乐冲突 | `musicConflict/musicConflictResolved`；`replacementReady` 检查各镜声音选择 |
| 原创／对标 | 音乐卡 | 确认适配效果／不另加音乐、确认音乐 | 记录人工确认，清除旧最终验收 | `musicConfirmed/finalApprovedFileId`；`confirmationReady/conflictResolved` 门槛 |
| 原创／对标 | 样片卡 | 选择分镜、生成样片 | 生成真实单镜或选中镜样片 | POST `/yingxu-render {preview:true}`；Node/Remotion + FFmpeg；`sampleFileIds` |
| 原创／对标 | 样片卡 | 样片通过 | 人工确认每个必需样片 | `sampleApprovedFileIds`；`sampleApproved()` 检查全部必需 ID |
| 原创／对标 | 合成验收卡 | Remotion 时间线按钮 | 未配置，点击无效果 | 禁用按钮，无接口；独立 Studio 未交付 |
| 原创／对标 | 合成验收卡 | 生成完整成片 | 渲染完整 MP4，不用单镜冒充整片 | POST `/yingxu-render {preview:false}`；Remotion 时间线 + 音轨混合 + FFprobe 校验 |
| 原创／对标 | 合成验收卡 | 成片版本、预览、验收通过 | 选择真实成片，人工验收当前版本 | `finalFileId/finalApprovedFileId`；`files.kind=video` 与本地 `<video>` |
| 原创／对标 | 合成验收卡 | 下载成片 | 下载当前已验收完整成片 | 文件 `download_url`；只有验收后显示 |
| 原创／对标 | 合成验收卡 | 推送到发布中心 | 绑定项目、文件、revision 和哈希，建立审核批次并跳转 | POST `/yingxu-handoff` → `ReviewService.receive_delivery`；`review_deliveries/review_batches/items`；不等于公开发布 |

## 5. 旧视频编辑器与兼容页

| 一级：页面 | 二级：卡片／工作区 | 三级：卡片元素和功能 | 功能描述 | 功能背后调用的技术方案 |
|---|---|---|---|---|
| 旧链接 `/tasks`、`/tasks/:id` | 兼容工作区 | 项目首页、原创项目、原编辑器入口 | 保留原项目链接，不强制迁移 | React Router；无 `project_type` 时按原创读取；原 `tasks/files/video_variants` |
| 原编辑器 `/tasks/:id/editor` | 项目操作卡 | 返回最新、刷新、搜索、分页 | 查找并继续真实项目 | GET `/api/tasks`、`/api/tasks/:id`；SQLite 原任务与前端筛选 |
| 原编辑器 `/tasks/:id/editor` | 新建任务弹窗 | 来源与发布约定：选题／文章、标题、原文、平台、方向、受众、审核与发布方式 | 创建兼容项目；标题最多 200 字且必填 | POST `/api/tasks`；`tasks.source_json` 保存来源和约定 |
| 原编辑器 `/tasks/:id/editor` | 文稿卡 | 版本标签、文稿输入 | 编辑母稿或平台口播稿，当前版本独立保存 | PUT `/api/tasks/:id/scripts`；`tasks.source_json` 文稿和 revision |
| 原编辑器 `/tasks/:id/editor` | 文稿卡 | 生成此栏／重写、保存、确认口播 | 生成当前版本或保存人工稿并推进 | POST `/generate-scripts` → 脚本 Agent；`/scripts` 与 `/actions` 状态机 |
| 原编辑器 `/tasks/:id/editor` | 录音字幕卡 | 真人录音上传 | 上传 WAV／MP3／M4A／AAC，最大 500MB | POST `/files?kind=audio`；流式上传 + FFprobe；`files` 本地记录 |
| 原编辑器 `/tasks/:id/editor` | 录音字幕卡 | 音频列表、试听、下载 | 播放或下载真实音频 | `<audio>` + `/api/files/:id/media`；本地文件路径 |
| 原编辑器 `/tasks/:id/editor` | 录音字幕卡 | 源音频、模型、WhisperX 生成 SRT | 本地转写选中音频 | POST `/transcribe`；`workers/whisperx_worker.py` + faster-whisper；生成 `files.kind=subtitle` |
| 原编辑器 `/tasks/:id/editor` | 录音字幕卡 | 上传 SRT、字幕校对 | 上传或编辑有效字幕，保存时重检 | `/files?kind=subtitle`；PUT `/subtitles`；SRT 时间轴解析 |
| 原编辑器 `/tasks/:id/editor` | 录音字幕卡 | 脚本版本、音色、TTS 文本、生成 AI 录音 | 生成系统语音或本人授权克隆 WAV | `/generate-audio`／`generate-clone-audio`；macOS `say` 或 OpenVoice；真实文件校验 |
| 原编辑器 `/tasks/:id/editor` | 录音字幕卡 | 样本档案名、本人样本、授权确认 | 保存本人音色档案，授权必选 | `voice_samples`／本地语音配置；样本上传 500MB 限制与授权字段 |
| 原编辑器 `/tasks/:id/editor` | 录音字幕卡 | 确认录音与字幕、返回修改脚本 | 推进或回退，后续确认按状态失效 | POST `/actions {confirm_audio/revise_script}`；任务状态机与文件存在性检查 |
| 原编辑器 `/tasks/:id/editor` | 素材规划卡 | SRT、允许素材类型、生成建议 | 按字幕、母稿和音频时长生成规划 | POST `/generate-asset-plan` → 素材规划 Agent；只生成文本计划 |
| 原编辑器 `/tasks/:id/editor` | 素材清单卡 | 上传素材与凭证 | 上传图片、视频、音频、PDF／TXT 授权材料 | `/files?kind=asset`；500MB 限制与任务目录存储 |
| 原编辑器 `/tasks/:id/editor` | 素材清单卡 | 添加／移除、名称、来源、关联文件 | 维护逐项分镜和素材关系 | PUT `/assets`；`asset_plan` 写入任务来源，文件 ID 关联 |
| 原编辑器 `/tasks/:id/editor` | 素材清单卡 | 起止秒、素材类型、画面关系 | 设置素材使用方式 | 同上；FFmpeg／Remotion 制作时读取 |
| 原编辑器 `/tasks/:id/editor` | 素材清单卡 | 搜索词、提示词、授权风险、备注、授权复选 | 记录检索、生成和授权边界 | 同上；勾选不代表系统验证版权 |
| 原编辑器 `/tasks/:id/editor` | 素材清单卡 | 保存、跳过未完成、确认全部授权 | 保存计划或推进制作 | PUT `/assets` + `/actions`；未完成项需明确跳过或确认 |
| 原编辑器 `/tasks/:id/editor` | 制作方案卡 | 渲染模式、目标平台、模板 | 选择智能混合、素材混合、全部上传及模板 | `production_preset`；`media/templates.py`；Remotion／FFmpeg 渲染策略 |
| 原编辑器 `/tasks/:id/editor` | 制作方案卡 | 烧录字幕 | 仅全部上传模式设置字幕烧录 | FFmpeg subtitles 滤镜；`burn` 参数 |
| 原编辑器 `/tasks/:id/editor` | 自动生产卡 | 生成成片、取消、重试 | 启动／取消／重排真实生产任务 | `/produce`、`/jobs/:id/cancel或retry`；`wb_jobs` + Remotion worker |
| 原编辑器 `/tasks/:id/editor` | 自动生产卡 | 查看预览、手动上传成片 | 预览文件或上传 MP4／MOV／WebM | 本地文件 URL；`/files?kind=video`；重复上传使旧质检失效 |
| 原编辑器 `/tasks/:id/editor` | 封面卡 | AI 封面、成片抽帧、上传封面 | 生成／抽取／上传真实封面 | `/cover`、封面抽帧逻辑和 `/files`；Kimi／FFmpeg／本地图片校验 |
| 原编辑器 `/tasks/:id/editor` | 结果版本卡 | 下载、质检／审批、重新生成 | 每个风格独立下载、检查和重做 | `video_variants` 关联 template version、file_id 和质量状态 |
| 原编辑器 `/tasks/:id/editor` | 五项质检卡 | 当前版本、五项复选、备注 | 逐项人工检查并保存 | PUT `/quality`；`video_variants.quality_json`；五项齐全才能提交 |
| 原编辑器 `/tasks/:id/editor` | 五项质检卡 | 保存、返修素材、仅重做成片、提交终审 | 保存结果或回退对应阶段 | `/quality` + `/actions`；状态机清除后续审批 |
| 原编辑器 `/tasks/:id/editor` | 人工终审卡 | 当前版本、批准此版本 | 完整观看后批准当前文件 | `/actions {approve_final,variant_id}`；审批绑定具体版本和文件 |
| 原编辑器 `/tasks/:id/editor` | 复盘卡 | 四窗口真实指标 | 输入播放、互动等，空值不自动变 0 | PUT `/metrics`；`tasks.source_json.metrics` 按时间窗口保存 |
| 原编辑器 `/tasks/:id/editor` | 复盘卡 | 复盘结论、保存、完成归档 | 保存经验或完成复盘 | `/metrics` + 状态机；四窗口播放／阅读和结论齐全才能归档 |


## 6. 审核中心

| 一级：页面 | 二级：卡片／工作区 | 三级：卡片元素和功能 | 功能描述 | 功能背后调用的技术方案 |
|---|---|---|---|---|
| 审核 `/review` | 映序成片卡 | 来源信息、返回映序制作 | 查看项目、文件和制作版本，返回原项目；过期时警告 | `review_deliveries` 关联 `tasks/files/revision/SHA-256`；GET `/api/review/yingxu/:content_id` |
| 审核 `/review` | 选择或切换内容来源卡 | 文件夹路径、选择文件夹、读取文件夹 | 扫描当前目录支持的视频，不递归、不改原文件 | POST `/api/review/batches`；`ReviewService.create` + `VIDEO_EXTENSIONS` |
| 审核 `/review` | 选择或切换内容来源卡 | 新建上传批次、文件多选、上传 N 个视频 | 上传 MP4／MOV／WebM／MKV 并形成审核项 | POST `/api/review/uploads`；流式上传 + 文件检查 + `review_batches/items` |
| 审核 `/review` | 机器预审卡 | 目标宽／高、最长时长 | 设置尺寸和时长规则；尺寸正整数，时长正数且大于最短时长 | `review/schemas.validate_rules`；默认 1080×1920、180 秒 |
| 审核 `/review` | 机器预审卡 | 黑帧／静音阈值 | 设置连续异常秒数，必须大于 0 | 同上；FFmpeg `blackdetect/silencedetect` |
| 审核 `/review` | 机器预审卡 | OCR、AI 风险复选 | 分别启用字幕越界和模型风险证据 | RapidOCR 帧分析 + 配置的风险 Agent；均不替代人工合规判断 |
| 审核 `/review` | 机器预审卡 | 开始机器预审 | 生成技术报告、问题时间点和修复建议 | POST `/api/review/batches/:id/start` → `wb_jobs` → `ReviewExecutors` + FFprobe／FFmpeg |
| 审核 `/review` | 批次进度卡 | 总数、待终审、通过、失败统计 | 查看当前批次真实状态 | `ReviewService.bootstrap` 聚合 `review_items.status/decision` |
| 审核 `/review` | 批次进度卡 | 通过全部无阻断项 | 只通过有报告、无 error、未过期且未预审的项目 | POST `/api/review/items/:id/decide`；`ReviewService.decide` 条件校验 |
| 审核 `/review` | 单视频审核卡 | 视频预览、技术检查、问题与风险 | 播放真实文件，查看技术报告和 AI 证据 | `/api/files/:id/media`；`report/ai_risk` JSON；本地文件路径 |
| 审核 `/review` | 单视频审核卡 | 查看检查详情 | 展开只读原始报告 | React 展开状态；不调用修改接口 |
| 审核 `/review` | 单视频审核卡 | 安全转码并复审 | 对 eligible 文件生成安全输出并重新预审 | POST `/api/review/items/:id/repair`；FFmpeg 新输出 + 新哈希，不覆盖原文件 |
| 审核 `/review` | 单视频审核卡 | 驳回、人工通过 | 记录人工终审决定；错误或过期项不能通过 | `/decide`；`review_items.decision/output_path`，与发布来源衔接 |

## 7. 发布中心与定时队列

| 一级：页面 | 二级：卡片／工作区 | 三级：卡片元素和功能 | 功能描述 | 功能背后调用的技术方案 |
|---|---|---|---|---|
| 发布 `/publish` | 类型与记录卡 | 文章发布／视频发布标签 | 切换内容类型和来源 | React 查询参数；`PublishingService.bootstrap(kind,id)` |
| 发布 `/publish` | 发布记录卡 | 状态筛选、搜索、来源复选 | 筛选并选择需要预填的记录 | GET `/api/publishing/queue`；`publish_batches/targets` 本地筛选 |
| 发布 `/publish` | 发布记录卡 | 全选当前筛选、提交选中后台预填 | 批量提交 draft／failed 目标预填 | POST `/api/publishing/batches/:id/prepare`；`wb_jobs` + `PublishingExecutors.prepare` |
| 发布 `/publish` | 审核成果来源卡 | 查看成片、打开对应审核 | 查看真实文件或定位审核批次 | `/api/files/:id/media`；`review_deliveries.review_batch_id` |
| 发布 `/publish` | 审核成果来源卡 | 准备发布字段 | 打开对应审核项的发布编辑区 | `PublishingService.source_for_publish` 校验批准输出、当前路径与 SHA-256 |
| 发布 `/publish` | 文章来源卡 | 文章来源下拉框 | 选择已批准文章，不读取视频替代 | `PublishingService.source("article")`；`wb_content_items/wb_revisions/wb_approvals` |
| 发布 `/publish` | 发布 Agent 字段生成卡 | 补充要求 | 输入文本生成附加规则，最多 2000 字 | POST `/api/publishing/generate-fields` 时传入 prompt；`useContentDraft` 保存本机草稿 |
| 发布 `/publish` | 发布 Agent 字段生成卡 | 生成选中平台字段 | 回填文本并保存本机草稿，需再保存正式批次 | `PublishingExecutors.generate_fields` → 发布 Agent + `publish_knowledge` 字段契约；不自动公开 |
| 发布 `/publish` | 平台卡共用区 | 平台启用复选 | 选择进入批次的平台，锁定状态不能重复提交 | `publish_targets` 状态机；`lockedStatuses` 前端与后端共同校验 |
| 发布 `/publish` | 抖音视频卡 | 标题、描述、话题 | 标题必填 30 字；描述必填并与话题合计 1000 字 | `publishing/contracts.py (douyin,video)`；`validate_generated_fields` 长度和组合校验 |
| 发布 `/publish` | 小红书视频卡 | 标题、正文、话题 | 标题必填 20 字；正文与话题合计 1000 字 | `(xiaohongshu,video)` 契约 + 发布浏览器字段读回 |
| 发布 `/publish` | 小红书文章卡 | 长文标题、正文、发布描述、话题、模板 | 标题 20 字、正文 6000 字；描述与话题 1000 字；模板需验证 | `(xiaohongshu,article)` 契约；`prepare_xhs_article` 检查图片数量、文本和平台状态 |
| 发布 `/publish` | 视频号卡 | 短标题、描述、话题 | 短标题 16 字、描述安全上限 2000 字；当前手动发布 | `(wechat_channels,video)` 契约；`manual_transfer`，不宣称自动上传已验收 |
| 发布 `/publish` | 公众号卡 | 标题、作者、正文、摘要 | 标题 64、作者 8、摘要 120 字；正文以编辑器读回为准 | `(wechat_official_account,article)` 契约；当前手动发布，封面等由平台处理 |
| 发布 `/publish` | 平台卡共用区 | 打开专用浏览器登录 | 在固定窗口打开对应后台并等待本人登录 | `/api/publishing/connections/:platform/login` → `publishing/browser_worker.py` → Playwright CDP 专用 Chrome |
| 发布 `/publish` | 平台卡共用区 | 复制发布内容、手动复制 | 复制当前字段；剪贴板失败时手动选择 | Navigator Clipboard API；失败只显示备用文本域，不伪报成功 |
| 发布 `/publish` | 平台卡共用区 | 手动打开后台 | 用默认浏览器打开平台官网 | 平台外链；与专用 Chrome 登录入口不同 |
| 发布 `/publish` | 平台卡共用区 | 下载视频／文章配图长图 | 下载审核文件或回文章页下载 | 文件下载 URL／文章路由；真实文件与资产 ID |
| 发布 `/publish` | 平台卡共用区 | 重试失败预览 | 按已保存内容重新预填失败目标 | `/api/publishing/targets/:id/retry`；fencing job_id 防止旧任务结果覆盖 |
| 发布 `/publish` | 平台卡共用区 | 已在后台核实为已发布 | 输入人工证据，登记未知远端结果 | `/targets/:id/reconcile`；`unknown_remote → published` 仅在人工证据后 |
| 发布 `/publish` | 批次操作栏 | 保存文章／视频批次 | 保存平台选择和字段，不执行预填 | POST `/api/publishing/batches`；`source_hash` 绑定内容版本 |
| 发布 `/publish` | 批次操作栏 | 一键同步到后台 | 保存后提交可编辑目标预填 | `/batches` + `/prepare`；`publishing/browser_worker.py` 上传／读回；不是公开发布 |
| 发布 `/publish` | 公开确认弹窗 | 返回检查、确认公开 | 二次确认后执行；未知结果禁止直接重试 | `/batches/:id/confirm` → `PublishingExecutors.execute`；仅明确启用环境 + ready + source hash 一致 |
| 发布 `/publish` | 定时队列卡 | 首次发布时间 | 设置第一次执行时间 | `/api/schedule`；`ScheduleService._datetime` 解析 ISO 时间并转 UTC |
| 发布 `/publish` | 定时队列卡 | 全局间隔、每日上限 | 设置正整数分钟数和每日数量 | `ScheduleService._positive`；`publish_schedules` |
| 发布 `/publish` | 定时队列卡 | 创建定时队列 | 为已预览且 source hash 确认的目标排期 | `ScheduleService.create_schedule`；`publish_queue` + 时间槽计算 |
| 发布 `/publish` | 定时队列卡 | 暂停／恢复、应用设置 | 修改队列状态或排期 | `/api/schedule/:id`；`update_schedule`；不重写内容版本 |
| 发布 `/publish` | 定时队列卡 | 取消未开始 | 只取消 queued 项，运行中不变 | `/api/schedule/:id/cancel`；`publish_queue.status` |

## 8. 增长记忆、采集知识与发布知识

| 一级：页面 | 二级：卡片／工作区 | 三级：卡片元素和功能 | 功能描述 | 功能背后调用的技术方案 |
|---|---|---|---|---|
| 增长记忆 `/knowledge` | 知识回填卡 | 同步现有数据到知识库 | 按稳定 ID 回填实体、规则和关系，避免重复 | POST `/api/knowledge/backfill`；`KnowledgeService.backfill` → `kb_entities/kb_rules/kb_relations` |
| 增长记忆 `/knowledge` | 搜索与筛选卡 | 实体关键词、类型、搜索、清空 | 查找或恢复实体列表 | GET `/api/knowledge/bootstrap`；SQLite 查询与前端筛选 |
| 增长记忆 `/knowledge` | 知识网络卡 | 实体条目、属性、关系、来源证据 | 查看真实实体关系和来源 | `kb_entities/kb_relations`；`KnowledgeService` JSON 属性与 evidence |
| 增长记忆 `/knowledge` | 编辑与审批规则卡 | 规则列表 | 查看供文章、选题、审核复用的规则 | `kb_rules`；由账号策略初始化，不是模型临时生成 |
| 增长记忆 `/knowledge` | 记忆统计卡 | 总量、有效、避坑、参与推荐 | 查看真实数量和启用状态 | `growth_memories.payload_json`；前端统计 |
| 增长记忆 `/knowledge` | 记忆编辑卡 | 新增、标题 | 打开编辑并填写名称，标题必填最多 200 字 | POST `/api/knowledge/memories`；`KnowledgeService.save_memory` 非空校验 |
| 增长记忆 `/knowledge` | 记忆编辑卡 | 适用平台、内容类型、判断 | 选择平台、文章／视频／规则、有效／避坑／待验证 | 同接口；枚举校验 `platform/kind/outcome` |
| 增长记忆 `/knowledge` | 记忆编辑卡 | 来源、效果依据 | 有效／避坑必填，各最多 4000 字；待验证可空 | `MEMORY_EVIDENCE_REQUIRED` 与 `MEMORY_TOO_LONG` |
| 增长记忆 `/knowledge` | 记忆编辑卡 | 可复用经验、保存、取消 | 保存经验与适用场景；正文必填最多 4000 字 | `growth_memories` UPSERT；`save_memory` 校验 |
| 增长记忆 `/knowledge` | 记忆列表卡 | 搜索、分类筛选 | 按标题、经验和效果筛选 | 前端读取 `/api/knowledge/memories` 后过滤 |
| 增长记忆 `/knowledge` | 记忆列表卡 | 编辑、暂停／启用推荐 | 更新同一记忆或改变是否参与推荐 | POST `/api/knowledge/memories`；选题 Agent 按平台读取最近 20 条启用记忆 |
| 采集知识 `/knowledge/collection` | 筛选卡 | 平台、类别 | 选择采集契约组合 | `accounts/collection_ontology.py` 静态机器契约；GET `/api/accounts/collection-knowledge` |
| 采集知识 `/knowledge/collection` | 知识实体卡 | 实体选择、验证状态 | 查看采集入口、数据结构和证据状态 | 同上；`verification` 是契约状态，不读取当前 Cookie 判断登录 |
| 采集知识 `/knowledge/collection` | 知识详情卡 | 机器可读 JSON、采集入口 | 查看契约或打开真实平台 | `/api/accounts/collection-knowledge/:platform/:category`；平台 URL |
| 发布知识 `/knowledge/publishing` | 筛选卡 | 平台、内容类型 | 选择发布字段契约，不支持组合显示空状态 | `publishing/contracts.py`；GET `/api/publishing/knowledge/:platform/:kind` |
| 发布知识 `/knowledge/publishing` | 生成规范卡 | 字段、必填、长度、组合限制 | 查看各平台真实生成规则 | `publish_knowledge` + `contract_fields`；生成时由 `validate_generated_fields` 执行 |
| 发布知识 `/knowledge/publishing` | 机器契约区 | 查看规则 JSON | 打开只读平台契约 | `/api/publishing/knowledge/...`；不把保存字段当成已写入平台 |


## 9. 设置：Agent、模型、媒体、模板与隐私

| 一级：页面 | 二级：卡片／工作区 | 三级：卡片元素和功能 | 功能描述 | 功能背后调用的技术方案 |
|---|---|---|---|---|
| Agent 配置 `/settings/agents` | 环境检测与能力状态卡 | 刷新真实状态、重新检查本机、检查详情 | 查看执行器、依赖和阻塞原因 | GET `/api/v2/runtime-readiness`；`readiness.py` 只读检查 Worker、CLI、FFmpeg、Chrome、Playwright 等 |
| Agent 配置 `/settings/agents` | Agent 配置中心 | Agent 列表、启用状态 | 选择 26 个注册 Agent之一；未接入不能启用 | GET `/api/agents/config`；`agents/registry.AGENTS` 注册表与连接状态 |
| Agent 配置 `/settings/agents` | Agent 编辑器 | 执行引擎 | 从当前 Agent 支持的引擎中选择；跟随系统时读取系统默认 | PUT `/api/agents/config/:id`；`save_agent_config` 校验 `definition.engines` |
| Agent 配置 `/settings/agents` | Agent 编辑器 | 模型／变体 | 选择变体或输入模型名，必填 1～100 字符 | 同上；`INVALID_AGENT_MODEL/VARIANT`；SQLite `settings.agent_configs` |
| Agent 配置 `/settings/agents` | Agent 编辑器 | 补充提示词 | 追加当前 Agent 规则，最多 12000 字，不覆盖安全约束 | 同上；`require_agent_enabled` 在执行时读取并传给 Provider |
| Agent 配置 `/settings/agents` | 高级执行参数折叠区 | 超时、尝试次数、并发 | 分别为 30～3600 秒、1～5 次、1～2 并发 | 同上；`INVALID_AGENT_LIMIT` 前后端范围校验 |
| Agent 配置 `/settings/agents` | 写作 Skills 区 | 每行一个 Markdown 路径 | 为脚本／文章 Agent 注入只读技能文件 | `custom.skills`；仅允许 `skills/`、`.agents/skills/` 下 `.md`；`ArticleSkillInjection` |
| Agent 配置 `/settings/agents` | 保存操作区 | 保存该 Agent、恢复默认 | 独立保存或恢复当前 Agent，只影响新任务 | `save_agent_config(reset?)`；`settings.agent_configs`；不改历史媒体 |
| 模型连接 `/settings/models` | 系统默认文本模型卡 | 默认服务 | 选择 Kimi CLI、Codex CLI 或 OpenAI 兼容 API | GET/PUT `/api/agents/system-model`；`providers/system.py`；跟随系统的 Agent 执行时读取 |
| 模型连接 `/settings/models` | 系统默认文本模型卡 | API 基础地址、模型名称 | 配置兼容 API 端点和实际模型 | 同上；`ProviderRegistry` 根据 engine 创建 API Provider；密钥服务与模型分开校验 |
| 模型连接 `/settings/models` | 系统默认文本模型卡 | API Key | 输入密钥；已保存时留空保留，保存后不回显 | `public_settings` 隐藏敏感值；密钥写入本机配置，不进入文档或前端状态回显 |
| 模型连接 `/settings/models` | 保存与测试区 | 保存默认模型 | 保存配置但不调用模型 | PUT `/api/agents/system-model`；下一次跟随系统的执行使用 |
| 模型连接 `/settings/models` | 保存与测试区 | 保存并测试连接 | 保存后执行真实最小调用，失败显示原因 | POST `/api/agents/system-model/test` → 当前 Provider `complete_json`；不伪报连接 |
| 模型连接 `/settings/models` | 文章插画与本地渲染卡 | 刷新模型状态 | 查看插画 Provider 与 Remotion 渲染状态 | GET `/api/articles/image-provider`；`articles/images.py` + 本地 Remotion 环境 |
| 模型连接 `/settings/models` | 模型连接测试卡 | 脚本／素材规划等真实测试 | 使用临时输入检查指定 Agent | 各 Agent 测试接口；`ProviderRegistry` 真实 CLI/API；不创建业务内容 |
| 本地媒体 `/settings/media` | 本地素材卡 | 素材路径、选择文件、复制进素材库 | 导入引用或本地副本，默认不复制 | GET/POST `/api/v2/local-assets`；`Workbench.import_local_asset`；`wb_assets.storage_key` |
| 本地媒体 `/settings/media` | 本地素材卡 | 刷新、素材类型、显示更多 | 重新检查文件可用性并筛选列表 | `/api/v2/local-assets`；`os.path` 存在性、MIME 与引用状态；前端分页展开 |
| 本地媒体 `/settings/media` | 本地素材卡 | 重新定位、验证并重新定位、取消 | 修复失效引用，必须验证内容一致 | POST `/api/v2/local-assets/:id/relink`；`Workbench.relink_asset`；不静默换素材 |
| 本地媒体 `/settings/media` | 本地模型环境位置卡 | Whisper／OCR／Demucs／OpenVoice Python 路径 | 配置真实可执行环境 | GET/POST `/api/media-tools`；`media/tools.py` 写入工作区 `config/media-tools.json` |
| 本地媒体 `/settings/media` | 本地模型环境位置卡 | OpenVoice 模型文件夹 | 选择模型根目录 | 原生目录选择器 + `/api/media-tools`；模型文件留在本机 |
| 本地媒体 `/settings/media` | 本地模型环境位置卡 | 保存环境位置 | 保存路径，但不等于能力通过 | 同上；之后仍需各能力自测 |
| 本地媒体 `/settings/media` | 渲染缓存卡 | 容量输入、保存容量 | 设置 1～1000 的可重建缓存容量 | `/api/yingxu-cache`；`media/render_cache.py` 与文件锁；不涉及业务原文件 |
| 本地媒体 `/settings/media` | 渲染缓存卡 | 清理可重建缓存 | 只删除受控派生输入和 bundle cache | `render_cache.inventory/clear` + `lease` 文件锁；保护项目素材与最终输出 |
| 本地媒体 `/settings/media` | 渲染缓存卡 | 刷新占用 | 查看缓存文件和可清理字节 | `render_cache.stats/bundle_stats`；只读统计 |
| 本地媒体 `/settings/media` | 项目备份与换电脑卡 | 新导出目录、导出完整工作区 | 校验并打包数据库、项目、版本和外部素材 | POST `/api/workspace/export`；`storage/portable.export_workspace`；新目录、清单和 SHA-256 |
| 本地媒体 `/settings/media` | 项目备份与换电脑卡 | 迁移包目录、恢复到新目录 | 校验迁移包并写入不存在的新目录 | POST `/api/workspace/restore`；`restore_workspace` 检查指纹、空间和目标不存在 |
| 本地媒体 `/settings/media` | 项目备份与换电脑卡 | 已有工作区目录、校验并切换 | 切换完整工作区并重启；有任务禁止 | POST `/api/workspace/select`；`workspace_selection.py` + `desktop/entry.py`；原数据保留 |
| 本地媒体 `/settings/media` | 本地媒体能力测试卡 | Remotion 测试 | 临时渲染并校验媒体输出 | 对应媒体测试接口；Node/Remotion/FFmpeg，不加入项目 |
| 本地媒体 `/settings/media` | 本地媒体能力测试卡 | 系统语音测试 | 生成并检查临时 WAV | macOS 系统语音 `say` + FFprobe |
| 本地媒体 `/settings/media` | 本地媒体能力测试卡 | WhisperX 测试 | 本地临时转写检查 | faster-whisper worker 与配置模型缓存 |
| 本地媒体 `/settings/media` | 本地媒体能力测试卡 | OpenVoice 测试 | 本地音色转换并检查 WAV | OpenVoice/MeloTTS 与配置模型路径；原授权音色要求不变 |
| 视频模板 `/settings/templates` | 视频模板库卡 | 模板预览、放大预览 | 查看真实模板图片／视频 | GET `/api/video-templates`；`media/templates.py` 与本地预览文件 |
| 视频模板 `/settings/templates` | 视频模板库卡 | 升级为稳定 | 将模板设为 stable | POST `/api/video-templates/:key/status`；`config/video_templates.json` 注册表状态 |
| 视频模板 `/settings/templates` | 视频模板库卡 | 停用 | 将模板设为 deprecated，保留模板 | 同上；不删除文件或历史版本 |
| 视频模板 `/settings/templates` | 视频模板库卡 | 恢复为草稿 | 将模板设为 draft | 同上；不等于稳定可用 |
| 数据与隐私 `/settings/data` | 数据与隐私卡 | 本地存储与输入边界说明、刷新状态 | 查看 SQLite、回环监听、模型输入和人工审核边界 | `docs` 与当前 `desktop/entry.py`、Provider 输入范围；无删除业务数据接口 |

## 10. 离线授权与新手引导

| 一级：页面 | 二级：卡片／工作区 | 三级：卡片元素和功能 | 功能描述 | 功能背后调用的技术方案 |
|---|---|---|---|---|
| 离线授权 `/activation` | 联系与申请码卡 | 微信二维码 | 打开刘洋微信二维码原图 | 本地 `/demo-wechat.png` 静态资源；不读取微信账号 |
| 离线授权 `/activation` | 联系与申请码卡 | 申请码、复制申请码 | 查看并复制当前安装身份申请码 | GET `/api/v2/license`；`LicenseService.status` + `protocol.request_code(installationId)`；Clipboard API |
| 离线授权 `/activation` | 导入授权码卡 | 授权码文本域 | 粘贴最长 16000 字符的授权内容 | React 本地 token；POST `/api/v2/license/activate` 时提交 |
| 离线授权 `/activation` | 导入授权码卡 | 选择授权文件 | 选择 `.yxlicense/.txt` 并填入 | `desktop/launcher.m` WebKit `runOpenPanelWithParameters`；取消也完成回调 |
| 离线授权 `/activation` | 导入授权码卡 | 验证并激活 | 验签、绑定安装身份，成功后保存；失败不覆盖有效授权 | `LicenseService.activate` → `protocol.verify` → OpenSSL 3 Ed25519；`license/state.json` 原子写入 |
| 离线授权 `/activation` | 只读查看区 | 先查看已有工作与成果 | 进入工作台查看，不绕开执行授权 | `sessionStorage yx-read-only` + `LicenseGate`；`LicenseService.require_active` 仍限制任务 |
| 新手引导 `/welcome` | 步骤卡 | 本地存储、环境、能力、第一条视频 | 切换并显示各步骤完成状态 | `LicenseService.onboarding`；`license/state.json.onboarding.steps` |
| 新手引导 `/welcome` | 本地存储卡 | 使用当前本地目录 | 保存存储步骤，不自动迁移文件 | POST `/api/v2/license/onboarding {step:storage}` |
| 新手引导 `/welcome` | 环境检查卡 | 重新检测 | 检查本机环境 | GET `/api/accounts/setup`；`accounts/setup.py` 依赖检测 |
| 新手引导 `/welcome` | 环境检查卡 | 已了解检测结果，继续 | 标记环境步骤，不代表全部依赖通过 | POST `/api/v2/license/onboarding {step:environment}` |
| 新手引导 `/welcome` | 能力说明卡 | 按需配置，继续 | 标记能力说明已读 | POST `/api/v2/license/onboarding {step:capabilities}` |
| 新手引导 `/welcome` | 第一条视频卡 | 使用示例稿／继续第一条视频 | 创建或继续真实本地项目 | POST `/api/v2/license/first-project`；`tasks`；必需模式下 `require_active` |
| 新手引导 `/welcome` | 文章体验折叠区 | 创建文章规范样例 | 创建本地文章样例 | POST `/api/articles`；`wb_campaigns/wb_content_items`；不公开发布 |
| 新手引导 `/welcome` | 完成区 | 结束入门提示，进入工作台 | 标记引导完成 | POST `/api/v2/license/onboarding {step:complete}`；`AppShell` 保留设置内重入 |

## 11. 接入向导与专用 Chrome

| 一级：页面 | 二级：卡片／工作区 | 三级：卡片元素和功能 | 功能描述 | 功能背后调用的技术方案 |
|---|---|---|---|---|
| 接入向导 `/setup` | 安装后的接入清单卡 | 激活、微信、模型、平台、首次制作链接 | 跳到对应配置或页面锚点 | React Router Link／HTML anchor；不自动执行操作 |
| 接入向导 `/setup` | 映序专用 Chrome 卡 | 启动专用浏览器 | 启动或复用固定 Chrome，使用工作区固定资料 | POST `/api/accounts/browser/connection {action:start}` → `dedicated_browser.ensure_started`；官方 Chrome + 本机 CDP 9223 |
| 接入向导 `/setup` | 映序专用 Chrome 卡 | 重启专用浏览器 | 正常关闭后使用同一 Profile 再启动 | `browser_connection.control` 检查活动任务 → CDP `Browser.close` → `ensure_started` |
| 接入向导 `/setup` | 映序专用 Chrome 卡 | 关闭专用浏览器 | 正常退出专用实例，不关闭日常浏览器 | `stop` → Playwright `new_browser_cdp_session().send(Browser.close)`；主 Python 无驱动时复用 `.venv-topics` |
| 接入向导 `/setup` | 映序专用 Chrome 卡 | 重新检测、状态文本 | 查看安装、运行、Profile 模式和端口占用 | GET `/api/accounts/browser/connection`；`lsof/ps`（macOS）或 Windows 对应检查 + `/json/version` |
| 接入向导 `/setup` | 环境状态卡 | 系统、Python、当前地址、重新检查 | 查看本机环境与当前工作台地址 | GET `/api/accounts/setup`；`accounts/setup.py`；`platform/shutil/importlib` 只读探测 |
| 接入向导 `/setup` | 核心依赖卡 | Python、Node、FFmpeg、Chrome、Playwright 等 | 逐项显示已检测、待安装或可选 | 同上；工具存在不等于账号登录或生成通过 |
| 接入向导 `/setup` | 当前可用范围折叠卡 | 能力与阻塞项 | 查看文案、导出、视频、审核、发布等真实状态 | `readiness.runtime_readiness`；Worker 执行器映射和依赖检查 |
| 接入向导 `/setup` | 开发者安装折叠卡 | macOS／Windows 切换 | 切换源码安装命令说明 | React 本地 OS 状态；`scripts/start.sh/start.ps1` 说明，不执行安装 |
| 接入向导 `/setup` | 微信机器人连接卡 | 二维码、配对码、检查、断开 | 完成微信 Bot 连接，数据独立保存 | `topics/wechat_client.py` 与 `/api/topics/wechat/client/*`；不是专用 Chrome 平台登录 |
| 接入向导 `/setup` | 抖音登录卡 | 打开登录窗口 | 打开抖音创作者后台并等待登录 | `/api/accounts/browser/open` → `accounts.login` → `existing_browser.wait_for_login` → 专用 Chrome |
| 接入向导 `/setup` | 小红书登录卡 | 打开登录窗口 | 打开小红书创作者后台并等待登录 | 同上，`xiaohongshu_login`；登录状态由页面和 URL 证据判断 |
| 接入向导 `/setup` | 视频号登录卡 | 打开登录窗口 | 打开视频号助手并等待扫码 | 同上，`channels_login`；不再用系统默认浏览器新窗口代替 |
| 接入向导 `/setup` | 公众号登录卡 | 打开登录窗口 | 打开公众号后台并等待扫码 | 同上，`official_login`；可结合后台 token／页面证据判断 |
| 接入向导 `/setup` | 登录任务卡 | 状态、错误、处理建议 | 查看登录任务是否确认成功，打开窗口不等于成功 | `wb_jobs` + `accounts.login` 结果；`login_verified` 和结构化错误 |
| 接入向导 `/setup` | 完成接入卡 | 配置 Agent、开始选题 | 进入设置或抖音选题 | React Router Link；不自动保存配置 |

## 12. 旧版 `/legacy`

| 一级：页面 | 二级：卡片／工作区 | 三级：卡片元素和功能 | 功能描述 | 功能背后调用的技术方案 |
|---|---|---|---|---|
| 旧版 `/legacy` | 旧版侧栏 | 今天、选题、账号日报、发布复盘、文章、视频、知识、设置 | 打开旧版各工作区 | `web/index.html` 原生导航 + `web/app.js` 视图切换；不使用 React AppShell |
| 旧版 `/legacy` | 旧版顶部操作区 | ＋新建任务 | 打开原任务创建流程 | `web/app.js` + 原 `/api/tasks`；旧 `tasks` 数据 |
| 旧版 `/legacy` | 旧版内容工作区 | 原任务、账号、发布与设置控件 | 保留旧接口和旧数据视图 | `web/workspaces.js`、`web/publishing.js` 等原生 JS；与新版数据口径需分别核查 |

## 维护规则

1. 新增页面时增加新的一级行；新增卡片时增加二级行；新增按钮、输入框或功能时增加三级行，不能只改页面标题。
2. 技术方案至少写清一层真实接口和一层后端实现；涉及数据时写明表／文件，涉及外部能力时写明 Chrome、模型 CLI/API、FFmpeg、Remotion、Whisper、OCR 等真实引擎。
3. 控件的具体输入限制同步维护 `FUNCTION_MAP.md`；本表负责结构和技术关系，不用“系统处理”“AI 完成”等模糊词替代真实调用。
4. 未接入、禁用、只读、手动转移、预填和公开发布必须分开描述；目标原型和 PRD 不得写成已调用能力。
