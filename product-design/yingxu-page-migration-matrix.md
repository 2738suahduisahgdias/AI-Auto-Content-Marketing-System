# 映序逐页改造对照表

版本：1.0 · 2026-11-01 · 状态：开发规格，尚未完成实现验收。

## 1 改造原则与优先级

以现有 AI-Auto-Content-Marketing-System 为代码和数据底座，在开发分支 `codex/yingxu-mac-local-workbench` 内改造。**从文案编辑到视频生成，采用映序的产品流程；与原系统冲突时，映序优先。** 现有接口、存储、任务执行和历史记录尽量复用；不能为了保留旧页面，继续保留已被取消的操作门槛。

这不是重建另一套系统。`product-design/prototypes/mac-studio/` 只作为视觉参考，停止作为独立产品扩展；其中的演示数据、localStorage 和假生成结果不得成为正式业务实现。原系统其他业务能力继续保留。对照表中的“保留”指能力和数据，不要求保留旧布局、旧入口或旧组件边界。

依据：当前开发分支源码、`product-design/video-workflow-prd-v2.md` 与用户最新决定。下表文件路径均相对仓库根目录；已有文件是改造入口，标注“拟新增”的名称是设计建议，不表示已存在。验收栏均为待执行要求，不是已通过的测试报告。

## 2 统一工作流与冲突裁决

目标流程：灵感／选题（可选）→ 项目简报与场景 → 文案（AI、手写或导入，可编辑保存）→ 分镜与素材 → 预览与生成 → 成片版本 → 发布与复盘。允许已有文案直接进入；已完成视频直接入库进入发布；各步骤共享同一项目标识和来源关系。

| 冲突点 | 明确采用的行为 | 保留的底层约束 |
|---|---|---|
| 原阶段驱动与映序编辑流程 | 按项目组织，可回到文案和分镜修改；改动形成新版本 | 保留任务状态与历史，建立新旧状态映射；旧产物不覆盖 |
| 文稿平台字段与通用视频文案 | 一个有效文案即可制作；选择当前文案版本，不固定绑定抖音或母稿 | 保留原多平台字段、来源、版本和 AI 候选保护；当前源码已支持非全部必填，不重复重做 |
| 必须录音／必须 SRT | 旁白、原声、纯音乐、无声均可；只在选用字幕或语音能力时要求对应输入 | 有语音时保留真实转写、字幕修订和同步能力 |
| 场景与输出页重复选择路线 | 场景推荐一次：知识、科技、数据等默认 Remotion；广告、短剧默认视频模型；镜头可覆盖 | 输出页保留比例、分辨率、帧率、格式等规格；高级设置显示实际引擎 |
| 统一按口播／分镜时长 | 已上传成品按探测到的真实时长；裁切需显式操作；其他镜头按旁白、音乐或手动时长安排 | 保留媒体探测与时间轴合法性检查，不静默截短或拉伸 |
| 10 秒预览与强制审核步骤 | 保留快速预览；普通导出不要求重复勾选质量清单。生成动作锁定当前输入快照；修改后提示预览过期 | 保留指纹、确定性参数、文件哈希；若旧接口要求批准预览，前后端一起改，不能只隐藏按钮 |
| 原质量／发布审核 | 机器检查显示结果，人工检查提供可选清单；明确的硬错误阻止无效任务，组织启用的发布审核继续生效 | 发布操作仍针对选定文件版本；不把“不要强制勾选”解释为自动公开发布 |
| 上传声音与配乐库重复 | 分成旁白、音色样本、背景音乐和音效；音乐统一从库选择或导入 | 样本不自动当配乐，原声与背景音乐分别混音；必要授权记录不反复逐任务索取 |
| 独立 demo 与原系统 | 在现有 React 页面和 Python 服务内渐进改造；桌面壳承载同一套应用 | 一套本地数据库和任务系统；不另造持久化或队列孤岛 |

## 3 原系统全页面改造对照

| 原页面／组件 | 已有功能 | 必须保留什么 | 映序补充什么 | 修改哪些文件 | 怎样验证没有退化 |
|---|---|---|---|---|---|
| 应用框架与全局导航 | React 路由、共享状态和页面容器 | 全部业务入口、旧链接可达、真实错误反馈 | 项目工作台整体布局；视频页专业制作台；项目列表可切看板；合并重复入口 | `webapp/src/App.tsx`、`webapp/src/components/AppShell.tsx`、`webapp/src/AppContext.tsx`、`webapp/src/styles.css` | 逐条访问下列旧路由；刷新和返回不丢选择；导航重组后旧链接仍定位对应记录 |
| 今日工作 `/` | 今日任务概览与业务入口 | 真实任务状态和待办来源 | 最近项目、继续创作、首次视频引导；不另建模拟统计 | `webapp/src/pages/Today.tsx`、`webapp/src/lib/api.ts` | 同一任务在首页、列表、详情状态一致；空库、失败任务均有可用入口 |
| 选题 `/topics/:source` | 多来源选题、采集与内容处理 | 来源记录、采集结果、微信收件箱、已有选题 | 选题进入项目简报，携带来源；灵感采集、拆解结果关联选题 | `webapp/src/pages/Topics.tsx`、`webapp/src/components/WechatInbox.tsx`、`content_workbench/topics/api.py`、`content_workbench/topics/service.py`、`content_workbench/topics/media_analysis.py` | 历史选题可查；原微信入口可用；从选题建项目保留来源，重复点击不重复创建 |
| 文章 `/articles/:id?` | 文章编辑与内容管理 | 文章 ID、内容、历史与原文章业务 | “用于视频”引用选定版本；视频文案变体独立保存，原文不被改写覆盖 | `webapp/src/pages/Articles.tsx`、`content_workbench/articles/api.py`、`webapp/src/lib/types.ts` | 旧文章读写正常；转视频后编辑视频稿不覆盖文章；可追溯来源版本 |
| 任务／项目 `/tasks/:id?` | 创建任务、分组阶段、事件与历史 | content_id、文件、事件、任务状态、取消重试入口 | 成为内容项目入口；每项目简报、场景、编辑视图和运营看板共享记录 | `webapp/src/pages/Tasks.tsx`、`webapp/src/pages/tasks.css`、`webapp/src/lib/names.ts`、`webapp/src/lib/types.ts`、`app.py`、`content_workbench/domain/workflow_registry.py` | 旧任务逐状态迁移；新旧记录能打开；改文案产生新版本，旧成片仍可下载；看板和编辑视图一致 |
| 账号 `/accounts/:view?` | 账号数据、分析和采集入口 | 账号身份、平台关联、统计与真实采集 | 账号管理与分析可分导航但共用记录；项目发布选择已有账号 | `webapp/src/pages/AccountAnalytics.tsx`、`webapp/src/pages/RealAccountAnalytics.tsx`、`content_workbench/accounts/api.py`、`content_workbench/accounts/service.py` | 原账号与指标数量不变；登录状态失效可恢复；分析页与发布页选中同一账号 |
| 竞品 `/competitors` | 竞品分析入口与真实数据页面 | 竞品跟踪、历史采集 | 优质作品关联灵感，不混成项目素材副本 | `webapp/src/pages/Competitors.tsx`、`webapp/src/pages/RealCompetitors.tsx`、`content_workbench/accounts/service.py` | 历史竞品可查；进入灵感保留来源；不改变采集对象 |
| 社媒数据 `/social` | 社媒查询、数据服务执行 | 已有服务配置、查询结果与线索能力 | 与内嵌浏览器、选题研究衔接；查询数据与媒体下载状态分别展示 | `webapp/src/pages/SocialData.tsx`、`content_workbench/social/api.py`、`content_workbench/social/service.py`、`content_workbench/social/executors.py` | 原查询仍执行；无凭证明确报错；不能把查询成功显示成下载成功 |
| 复盘 `/retrospective` | 内容复盘与数据展示 | 原内容、账号、发布结果关联 | 按项目和成片版本复盘，经验可沉淀为模板建议 | `webapp/src/pages/Retrospective.tsx`、`content_workbench/accounts/analytics.py` | 原历史指标口径不变；不同成片版本不混记；无数据不显示模拟成功 |
| 审核 `/review` | 集中审核、媒体与业务审核 | 审核记录、明确启用的审核规则 | 与视频页共享版本；普通创作无需新增重复检查页 | `webapp/src/pages/Review.tsx`、`content_workbench/review/api.py`、`content_workbench/review/service.py`、`content_workbench/review/media_review.py` | 对旧文件的审核不会授权新文件；未启用审核的本地导出不被空清单卡住 |
| 发布 `/publish` 与发布面板 | 发布记录、平台执行、排期 | 平台账号、封面、排期、失败反馈与去重语义 | 项目内确认成片后进入既有发布能力；支持仅导出和发布前检查 | `webapp/src/pages/Publish.tsx`、`webapp/src/components/PublishingPanel.tsx`、`content_workbench/publishing/api.py`、`content_workbench/publishing/service.py`、`content_workbench/schedule/api.py` | 先用测试适配器验证请求与文件哈希；超时未知不重复发布；排期时区正确；真实公开发布单独确认 |
| 知识库 `/knowledge` | 知识管理与检索服务 | 文档、引用、索引与现有知识能力 | 文案生成引用本地知识，显示来源；不能拿模板库覆盖知识库 | `webapp/src/pages/Knowledge.tsx`、`content_workbench/knowledge/api.py`、`content_workbench/knowledge/service.py` | 原文档可查；生成文案能追溯引用；删除项目不删除知识源 |
| 采集知识 `/knowledge/collection` | 采集规则与知识管理 | 原平台采集配置和规则 | 归入管理中心，供采集工具复用 | `webapp/src/pages/CollectionKnowledge.tsx`、`content_workbench/accounts/collection_knowledge.py` | 原规则可编辑保存，实际采集读取同一规则；导航移动不改变配置 |
| 发布知识 `/knowledge/publishing` | 发布规则与知识管理 | 平台发布知识、规则与执行关联 | 归入管理中心，与发布检查衔接 | `webapp/src/pages/PublishKnowledge.tsx`、`content_workbench/publishing/knowledge.py` | 原规则仍参与发布；错误规则可定位，不变成纯展示文字 |
| 设置 `/settings` | Agent 参数、模型／语音／渲染连接自测 | 提示词、超时、重试、并发、真实连接测试与错误 | 分能力配置文字、图片、视频、语音、字幕；模板管理；存储与缓存；默认项目参数 | `webapp/src/pages/Settings.tsx`、`content_workbench/agents/api.py`、`content_workbench/agents/registry.py`、`content_workbench/providers/text.py`、`content_workbench/providers/local.py` | 保存后重启仍生效；执行读取新配置；视频模型未配置不阻塞 Remotion；密钥不进入日志或项目包 |
| 初始化 `/setup` | 原初始化与设置入口 | 可复用的环境检测和配置结果 | 离线激活后按首用状态引导；基础配置→模板→首条视频；可中断继续 | `webapp/src/pages/Setup.tsx`、`webapp/src/App.tsx`、`content_workbench/accounts/setup.py`；授权与引导服务拟新增 | 首用、再用、中断、升级四种启动验证；跳过非必要项可继续；重跑引导不清空数据 |

## 4 文案到视频：逐组件改造对照

本节组件均来自 `webapp/src/components/VideoStages.tsx`；拆分组件时先保留行为测试，再移入新的专业制作台。不得把整个文件直接替换成独立 demo。

| 原页面／组件 | 已有功能 | 必须保留什么 | 映序补充什么 | 修改哪些文件 | 怎样验证没有退化 |
|---|---|---|---|---|---|
| ScriptsStage | 手填保存、按字段 AI 生成、平台稿、候选版本防覆盖 | 手工内容优先、版本号、并发生成保护 | 文案导入与在线修改；当前视频稿选择；选题关联；项目简报上下文；一稿即可制作 | `webapp/src/components/VideoStages.tsx`、`content_workbench/agents/writing.py`、`app.py`、`content_workbench/media/contracts.py` | AI 请求期间改稿，返回仅作候选；保存后重开一致；仅一稿可继续；坏文件导入不覆盖旧稿 |
| ContentStage／任务简报 | 内容驱动生产入口 | 已有内容与任务关联 | 项目唯一简报，场景驱动默认路由和风格；展示可编辑的受影响字段 | `webapp/src/components/VideoStages.tsx`、`webapp/src/pages/Tasks.tsx`、`content_workbench/media/contracts.py` | 切换场景更新建议、不清空手填；输出规格页无第二次必选路由；历史项目可补默认值 |
| AudioStage：旁白与字幕 | 音频上传、系统音色、克隆、WhisperX、SRT 编辑 | 真音频、音色配置、可编辑字幕和错误反馈 | 旁白可选，选当前文案；原视频声轨识别；字幕开关；音色样本独立管理 | `webapp/src/components/VideoStages.tsx`、`app.py`、`content_workbench/media/probe.py` | AI 配音、上传旁白、原声、无声各跑通；字幕修改参与新版本；不开字幕不要求 SRT |
| AssetsStage | 素材类型和分镜资产录入 | 素材来源、文件关联和已有素材可用性 | “上传已完成实拍”和“人物／物品图生视频”分开；参考图与动作要求；素材引用默认不复制 | `webapp/src/components/VideoStages.tsx`、`content_workbench/media/storyboard.py`、`content_workbench/media/probe.py`；视频供应商适配器拟新增 | 上传 47 秒视频不会按 30 秒规划截短；图生视频提交实际参考图与提示词；失败可重试、不误报完成 |
| TemplatePlan／分镜 | 内容规划、语义场景、模板布局 | 结构化分镜、场景类型、可确定重现的参数 | 文案段落关联镜头；每镜头 Remotion／AI／上传素材可覆盖；拖动排序与时长规则 | `webapp/src/components/VideoStages.tsx`、`content_workbench/media/storyboard.py`、`content_workbench/media/contracts.py`、`remotion-app/src/VideoComposition.tsx` | 修改文案标记受影响镜头；排序、混合路线、实际时长在预览与成片一致 |
| 模板与效果 | 模板注册、风格场景和效果实现 | 现有可用模板及渲染参数 | 模板库、可播放真实样片、效果提示词、适用场景；项目保存模板版本快照 | `content_workbench/media/templates.py`、`remotion-app/src/templates.tsx`、`remotion-app/src/style-scenes.tsx`、`remotion-app/src/effects.tsx`；模板库 React 页拟新增 | 样片与模板 ID／版本对应；修改模板不改变旧项目；缺失模板可读报错；提示词确实进入规划输入 |
| useVisualPreview／ProduceStage | 动态预览、生产任务、轮询 | 真实产物、输入指纹、任务状态、取消失败信息 | 专业制作台预览与生成；按需预览；生成锁定输入快照；支持只重做受影响部分 | `webapp/src/components/VideoStages.tsx`、`content_workbench/media/visual_previews.py`、`content_workbench/media/render.py`、`content_workbench/media/versioning.py`、`app.py` | 改稿后旧预览明确失效；预览与全片同一快照；取消后不报告成功；同任务不重复占用渲染 |
| ResultStage／VideoPreview／CoverSection | 成片预览、下载和封面入口 | 历史视频文件、媒体信息、下载能力 | 成片版本比较、导出位置、生成来源和封面编辑统一 | `webapp/src/components/VideoStages.tsx`、`content_workbench/media/versioning.py` | 老文件仍可下载；预览、导出、封面对应选定版本；路径含中文和空格可用 |
| QualityStage／ReviewStage | 质量清单和审核入口 | 真正失败检查、审核历史和文件绑定 | 机器检查优先，普通本地导出取消重复强制勾选；明确区分建议与阻断原因 | `webapp/src/components/VideoStages.tsx`、`content_workbench/review/media_review.py`、`content_workbench/domain/services.py` | 不勾清单也能导出有效视频；文件损坏明确阻止；新文件不继承旧审核结论 |
| PublicationsStage／RetroStage | 项目发布与复盘 | 发布状态、版本关联、反馈 | 与全局发布／复盘共用服务，避免重复列表模型 | `webapp/src/components/VideoStages.tsx`、`content_workbench/publishing/service.py`、`content_workbench/accounts/analytics.py` | 全局与项目内状态一致；发布未知状态不自动再次提交；复盘可追溯成片 |

## 5 必须接入原系统的新增桌面能力

以下功能没有完整的现成页面，不能标记为“改完 UI 即完成”。新模块名称先作为候选；实施时按仓库结构确定，接入现有数据库和任务服务。

| 原页面／组件 | 已有功能 | 必须保留什么 | 映序补充什么 | 修改哪些文件 | 怎样验证没有退化 |
|---|---|---|---|---|---|
| Topics 采集入口 → 桌面研究浏览器 | 采集、下载与分析服务代码 | 平台来源、原下载器、原选题接口 | Electron WebContentsView 打开平台顶层页，自有工具栏下载／拆解；不是 iframe 绕过；转写结合关键帧时间码 | `content_workbench/topics/browser_worker.py`、`content_workbench/topics/douyin_download.py`、`content_workbench/topics/media_analysis.py`；桌面主进程浏览器模块和 IPC 拟新增 | 真实页面登录隔离；跨站网页拿不到本地文件与密钥；下载失败支持本地导入；随机时间码对照音画核实拆解 |
| AudioStage → 配乐库 | 已有旁白上传，不等于完整音乐库 | 音频文件和来源 | 本地目录扫描、网络来源导入、试听；自动分析时长、BPM、节拍、段落与响度，置信度及人工修正；剪辑对齐 | `webapp/src/components/VideoStages.tsx`、`content_workbench/media/probe.py`；`content_workbench/media/music_analysis.py` 与配乐库组件拟新增 | 真样本核对节拍和时长；低置信度明确提示；重复扫描去重；无网络可用本地库；配乐不变成旁白 |
| 文件上传 → 本地素材管理 | 现有任务文件与媒体探测 | 文件 ID、产物引用、原媒体不被删除 | 默认引用原文件，可选复制；外置盘标识、断开检测与重新定位 | `app.py`、`content_workbench/media/probe.py`、`content_workbench/storage/db.py`、`content_workbench/storage/migrate.py`；媒体定位服务拟新增 | 对比导入前后磁盘占用；拔盘显示离线；换挂载路径重新定位；同名错误素材需指纹校验 |
| 预览与生产 → 代理、缓存、恢复 | 渲染、预览与任务存储 | 既有 JobStore、取消／失败状态 | 代理预览、缓存上限、只清理可再生数据；渲染前空间估算；分阶段恢复 | `content_workbench/media/render.py`、`content_workbench/media/visual_previews.py`、`content_workbench/jobs/store.py`、`content_workbench/jobs/worker.py`；缓存服务拟新增 | 清缓存后原素材哈希不变；磁盘不足提前提示；中断只复用校验合格阶段，不承诺任意帧恢复；盘断开不损坏已有产物 |
| 数据备份 → 项目迁移 | 已有数据库备份模块 | 现有备份与恢复能力 | 轻量项目包和含素材完整包；清单、校验和、相对路径；缺失素材清单 | `content_workbench/storage/backup.py`、`content_workbench/storage/migrate.py`；项目包导入导出服务拟新增 | 另一目录恢复可打开、渲染；轻量包明确需重定位；包内不含账号密钥；旧数据库恢复可回滚 |
| Setup → 激活与首用 | 初始化页与独立演示 | 原环境配置、已有用户数据 | 微信二维码、申请码、离线签名授权、首次引导状态；经营者独立发码工具 | `webapp/src/pages/Setup.tsx`；授权校验、桌面安全存储、经营者工具拟新增 | 篡改／错设备授权拒绝但不删项目；再次启动不重复引导；客户端无签名私钥；离线不能假报客户已加微信或已激活 |

## 6 合并、替换和暂不删除的清单

- 合并重复的全局创作简报入口：项目保留唯一简报，旧数据迁移后再移除重复 UI。
- 替换文案到视频的旧交互顺序，取消重复路线选择、无声视频的录音与字幕门槛、普通导出的强制勾选；同步修改后端约束和测试。
- 旁白、样本、音乐和音效分别归位；不能删除旧音频文件或直接重标所有 audio 文件为配乐。
- 演示页保留为视觉参考，不作为正式首页，不搬入它的模拟结果和独立状态存储。
- `webapp/src/pages/Accounts.tsx` 与实际路由使用的 `webapp/src/pages/AccountAnalytics.tsx` 属于重复候选，先查引用和功能差异；本轮不凭文件名删代码。
- 不直接删除 `app.py`、旧 `/api/tasks`、现有 worker、知识管理、Agent 配置、账号采集、社媒查询、获客线索、审核、排期或历史版本。先证明调用方迁移完毕，再单独提交清理。
- 不再建设客户云端内容库、手机号注册与短信后台；既定方向为本地存储、微信联系和离线授权。外部 AI 调用配置与本地存储独立。

## 7 开发顺序与回归门槛

1. **固定基线**：备份脱敏测试数据，记录原页面、旧任务各阶段、文件哈希、账号与发布记录；先执行现有测试，记录基线失败，不把原有失败算成改造通过。
2. **先接通主链路**：在 Tasks 和 VideoStages 内实现项目简报→单稿→分镜→预览／生成；继承接口与执行服务。用“AI 客服如何落地”实际输出可播放 MP4，不用固定模拟分镜代替真实结果。
3. **再扩展路线与资产**：接入已完成实拍、图生视频、音乐分析及大文件管理；独立验证失败与恢复。
4. **再统一外观与导航**：项目工作台＋视频专业制作台＋运营看板；保留所有原业务入口；套用选定视觉规范，避免外观原型反过来决定业务结构。
5. **桌面验收**：授权、引导、浏览器隔离、外置盘、重启、升级和项目迁移；完成后邀请用户体验开发版。分支验收通过后再合并原系统，未通过不改主分支。

已有回归入口：`webapp/src/pages/Tasks.test.tsx`、`webapp/src/components/VideoStages.test.tsx`、`webapp/src/pages/Articles.test.tsx`、`webapp/src/pages/Topics.test.tsx`、`webapp/src/pages/Publish.test.tsx`、`webapp/src/components/PublishingPanel.test.tsx`、`tests/test_video_templates.py`、`tests/test_publishing.py`。先检查各测试断言与新规格是否冲突：取消的强制步骤应更新断言，数据保护、版本绑定、错误处理和发布去重不得以“流程变化”为由删掉。

验收至少覆盖：旧项目打开与下载、单稿手动流程、AI 并发改稿保护、无旁白 Remotion、上传实拍真实时长、图生视频错误与重试、音乐分析、预览过期、低磁盘空间、拔盘恢复、缓存清理、备份换目录恢复、发布未知结果、首次／再次启动。每项记录输入、预期、实际结果、截图或产物、日志和对应提交；外部模型费用与真实公开发布另按实际授权执行。

**本次交付只补齐改造依据与文件映射，不代表上述新增能力已经开发。** “没有退化”是保住原有业务数据和有效能力，同时兑现明确变更的新流程，而不是让旧强制流程原样存在。


## 2026-11-01 用户纠正：原选题页面直接复用

选题完整流程不重做、不简化。demo 的灵感与选题直接挂载原 Topics.tsx 和 AppProvider，保留 TopicCard、WechatInbox、收藏分类、配置、同步、推荐、下载拆解、归档与创建任务接口。外层只加来源导航。创建任务后进入原任务路由。删除自建 TopicLibrary，不在选题页插入新的 Agent 操作面板。

原选题区是真实工作区，操作会按原逻辑写入后台；其他 Agent 面板是演示任务，不执行模型、下载或发布。原服务需有效登录；未登录时显示原错误反馈，不用示例填充。

其他工作区增加总控任务汇总、文章配图需求、品牌规则质检和发布字段准备。实际执行器仍待接入。发布填写成功后必须交给人工审核，本 demo 不伪造已填写或已发布状态。原视频制作台继续保留。

### 内容项目复核补充

映序视频流程优先，不沿用旧 PRD 必须录音的 UI 顺序。本次修正 demo 新建入口（空白、已有文案、拆解主题、已有成片）、项目续编位置与场景默认路线；未完成的示例不标待发布。既有编辑镜头不随场景更换而覆盖。项目仍是演示记录，尚未与原 content_id、选题创建任务、产物版本建立真实联动；不得标记为已经完整继承。原选题创建任务目前仍进入原任务工作区，该衔接是后续真实接入项。

### 纠正：功能迁移，不是整页嵌入

撤销工作台 iframe 接入。刘量页面以 OriginalWorkspace 直接挂载既有 React 业务组件与 AppProvider，统一使用 demo 外层导航。映序以 YingxuStudio 和 yingxu-runtime 迁入同页 DOM：保留原页面生成函数、状态及业务事件，适配 DOM 查询范围、事件作用域、静态资源路径、定时器清理和发布交付。样式限定在组件范围，防止污染其他页面；暖白琥珀为已授权主题覆盖。原平台浏览功能内的平台 iframe 是原有功能，不等于工作台嵌入。

已验证原规格与节奏页面能够原地切换，包含场景、简报、效果模板、输出规格、声音及配乐入口。当前验证不代表每个功能和像素均已验收；真实后台仍需有效登录，未宣称完整迁移验收。

## 2026-11-01 复核结论：迁移验收不通过

本节纠正前文可能造成“完整迁移已完成”印象的表述。此次只读核对入口、数据写入目标、原组件复用情况和测试范围，未把源码未修改等同于功能接通。

| 承诺 | 当前事实 | 验收结论 |
|---|---|---|
| 刘量系统为底座 | main.tsx 的 /demo 分支仍独立挂载 DemoWorkbench；原 App 只在非 demo 路由运行 | 未完成 |
| 原模块原样复用 | 选题及账号、竞品、社媒、知识、设置等导入原组件，但另包 MemoryRouter / AppProvider；跨区路由和认证未验收 | 部分完成 |
| 只替换视频生产 | 原映序运行逻辑已同页挂载，无工作台 iframe；仍以 yingxu-demo-v1 单草稿存储，不使用原 content_id | UI 迁入，业务未迁入 |
| 一套项目数据 | DemoWorkbench 仍保存 yingxu:preview-only:v1 和 initialProjects，映序另存 yingxu-demo-v1；原后台另有数据库 | 不通过 |
| 选题进入映序 | OriginalTopics 非选题路由执行 location.assign，创建任务后进入旧 /tasks | 未接通 |
| 文章转视频 | 文章页仍为演示 textarea，复制操作写 setProjects；映序不读取此记录 | 确认断链 |
| 模板、素材、音乐复用 | 外层模板 patch 旧 project；素材与音乐写 config，不写映序 state | 确认断链 |
| 文件版本交付 | 交付只含标题，按标题去重；缺失 content_id、asset_id、版本和审核关联 | 未接通，存在同名覆盖风险 |
| 今日实际进度 | 当前只读映序本地草稿和演示 Agent 请求，不读原任务队列 | 未完成 |
| 完整功能与像素验收 | demo 测试 mock 原工作区与选题组件；局部按钮测试不能证明跨模块业务或像素一致 | 未完成 |

确认保留：git 与基线 fd724d7 对比，webapp/src/pages、webapp/src/components、content_workbench 和 app.py 无差异。只能证明原文件未被改坏，不能证明 demo 已经使用全部原功能。

后续修正顺序：原任务/数据链路为底座 → 删除重复数据写入 → 文章与选题交接 → 资产及成片版本 → 发布交付 → 总控进度 → 样式和逐页验收。此次核对不擅自扩大改动，不以修饰页面代替修复链路。

## 2026-11-01 修复验收：原系统底座已接通（取代上节失败状态）

本节描述当前实际运行代码；上节“不通过”是修复前审计，不是当前入口。

| 原页面／组件 | 保留功能 | 映序迁移／适配 | 修改文件 | 验证 |
|---|---|---|---|---|
| App / AppProvider / AppShell | 原导航、路由、会话、数据刷新 | `/demo` 使用同一 App，视频页启用迁移编辑器；没有 iframe 或第二套项目表 | `webapp/src/main.tsx`, `App.tsx`, `vite.config.ts` | 浏览器读取原数据库副本；原 AppShell/AppContext 源码未变 |
| Today | 原任务进度、队列与工作入口 | 读取原任务中保存的实际状态 | 无业务改动 | 与基线逐文件字节比对一致 |
| Topics / 微信收藏组件 | 平台采集、收藏、后台数据、下载与选题转任务 | 选题创建的原 content_id 直接进入迁移编辑器 | 无业务改动 | 原页面回归；真实选题 create-task 来源关联验收 |
| Articles | 原正文编辑、保存、版本、配图、文章发布 | 新增“从已保存正文制作视频”，携带文章及已保存版本 ID | `pages/Articles.tsx`, `app.py:create_task` | HTTP 创建文章版本→视频，原文章版本未被覆盖；未保存正文不能转换 |
| Tasks / VideoStages | 原任务列表、筛选、创建、ID、记录；非 demo 仍用原 VideoStages | 编辑区挂载映序原流程：文案、场景简报、声音、分镜、样片、合成、交付 | `pages/Tasks.tsx`, `migration/BoundYingxu.tsx`, `migration/yingxu-runtime.js` | 浏览器场景更新、文案同步分镜、保存后跳转与重开回显 |
| 原 files / stage_revisions / source_json | 原文件归属、媒体探测、版本及事件 | 快照保存在同一任务，乐曲、旁白、实拍文件使用原 files.id；并发版本冲突拒绝 | `app.py:save_yingxu/upload_file` | 错误归属、409 冲突、真实 MP4 探测、稿件保存测试 |
| 原 Remotion 引擎 | 原 TalkingHead、场景组件、字幕组件与 render.mjs | 将映序分镜适配成原 props；真实 10 秒样片／全片；可选旁白和背景音乐；横竖规格 | `app.py:yingxu_render_props/render_yingxu`, `remotion-app/src/Root.tsx`, `VideoComposition.tsx`, `narration.tsx` | 真正生成 10 秒和 12 秒 MP4，ffprobe 校验；页面按钮真实发起并回填成片 |
| Publish / Review | 原人工审核、平台字段、账号、预览、定时及公开发布确认 | 视频页只交付文件 ID、制作版本、文件哈希；发布页增加待审核收件区 | `pages/Publish.tsx`, `app.py:handoff_yingxu` | 真实文件交付、重复提交去重、修改后过期；没有公开发布 |
| Settings / Knowledge / Accounts / 其他原页面 | 原 Agent 配置、账号、品牌、模板、选题服务 | 迁移编辑器跳转原页面，不再维护重复设置副本 | 原页面无业务改动；统一 `migration/theme.css` | 源码逐文件比对及页面加载 |
| 旧独立 DemoWorkbench | 仅留历史追溯 | 已移出 src，归档且不参与路由、编译及运行 | `product-design/archive/rejected-standalone-demo/` | 主入口无 DemoWorkbench；无旧演示项目数据写入 |

### 验收证据和边界

- 原基线 `fd724d7992a322bb08fe091386627746e382e02b`。核对原 pages、components、content_workbench、app.py、remotion-app/src 及 render.mjs 共 167 文件：159 个完全一致，8 个为上表列明的必要适配。详见同目录 `yingxu-migration-source-verification.json`。
- 映序 v13 原始 7 文件 SHA-256 全部一致；保存在 `webapp/public/yingxu-original/`，运行版本为带本地数据适配的 `migration/yingxu-runtime.js`。
- 后端迁移、选题和视频模板测试 21 项通过；原任务、选题、微信收藏、文章、发布的前端测试及迁移编辑器测试共 12 项通过；TypeScript 检查通过。
- 隔离副本在外接盘 `runtime/migration-preview`，API 8876，前端 8847；正式 8765 与正式数据库未改，主分支未合并。
- 真实验收任务：`20261101-004`，“AI 客服如何落地”。生成过 10 秒样片与 12 秒全片；无旁白验收不要求音频流。页面可查看真实视频。
- 尚未宣称已接通：大模型写代码、视频大模型生成、真实自动拆解、视觉提示词自动编译、完整内容质检。原映序相应规划功能保留，并显示依赖说明；不伪造成功状态。
- 桌面文件引用／外置盘重定位／代理缓存／大文件断点恢复仍属于桌面版后续任务，本次浏览器上传沿用文件接口限额，不冒充已完成桌面实现。
- 本预览禁用后台 worker 与定时调度，避免复制的历史队列重新执行。原发布流程保留，但本次未用真实账号公开发布。
- 已检查生成画面与关键页面，未宣称全站逐像素一致；统一配色属于已授权修改。保留原功能与布局的依据包括源码对照、原测试及真实链路验收。
- 原映序内联事件目前通过迁移绑定层保持行为，构建会提示 eval 警告；正式发行前需改成显式事件映射并验证 CSP。不能据此把 demo 称为生产发行版。

### 最终补充验收

- 文案页不再显示另一套选题管理表单，直接回原 Topics；AI 起草复用原脚本 Agent、Skills 与连接配置，返回候选而不覆盖原稿。自动化测试验证此边界；本次未调用付费模型，配置依赖保留说明。
- 新增素材在已缓存 Remotion bundle 中可读取。实际上传 1 秒实拍并将规划时长设为 99 秒，合成结果仍为 1 秒；上传测试配乐后成片包含音频流。
- 成片记录保存制作版本和渲染输入指纹；文案变化后旧成片交付返回 409。单纯步骤切换不会误判为画面内容变化。
- 重启入口：`python3 scripts/start-migration-demo.py`。只使用外接盘的隔离数据库，后台调度不启动。

## 用户最新确认：整个视频任务页采用映序（2026-11-01）

此决定替代上文“只在原 Tasks 编辑区域挂载”的布局。底层依旧使用原数据，视频页 UI 整页替换：

- `/demo/tasks/:id?` 直接渲染 `YingxuVideoWorkspace` → `BoundYingxu`，不挂载原 Tasks 页面。
- 去掉旧视频任务列表侧栏、状态筛选标签、旧页标题、旧步骤条和创建表单。
- 映序标题下拉切换真实项目，映序新建弹窗调用原 `/api/tasks`。保存、文案、简报、声音、分镜、制作、交付均在映序页面中。
- 原 `Tasks.tsx` 恢复为基线文件，用于非预览旧入口回退；未改正式服务。全局刘量导航和其他模块保持。
- 项目名称下拉与新建新增必要的数据适配入口，沿用映序现有按钮、面板和表单样式，没有建立第二套项目模型。
- 已有原任务第一次进入时继承母稿／平台稿、录音、已关联素材计划；已有映序快照优先，避免覆盖编辑结果。
- 修复移除配乐后仍残留文件 ID、切换素材来源后引用旧文件等迁移细节。
- 最新核对范围 167 个原文件：160 个字节一致，7 个必要适配；入口 App/main 和新增迁移文件另列。前端 8 组 12 项测试通过，包含整页无旧布局、项目切换、新建进入文案、原稿与素材继承；后端 21 项通过。

### 整页替换后的浏览器闭环验收

任务 `20261101-008`：点击映序“新建视频” → 输入三段知识讲解稿 → 保存版本 → 选择知识卡片 → 同步为三个 5 秒分镜 → 页面生成 10 秒样片（文件 105） → 页面生成 15 秒全片（文件 106） → 提交发布 Agent → 发布中心显示同一 content_id、文件 106、制作版本 4、待审核且未发布。返回分镜步骤保存版本 5 后，已交付记录未被错误标记过期。截图保存在隔离预览目录 `yingxu-full-video-workspace.jpg`。
