# 图文生产与小红书配图交接验收

2026-11-01，开发分支 codex/yingxu-mac-local-workbench。沿用原文章版本、审批、资产和发布任务系统；原生产服务未修改。

## 本次接通

- Wikimedia Commons 搜图、下载并采用；作者、许可、来源随 HTML、Markdown、ZIP 和分页图片保留。
- 本机 Codex CLI 内置 image_gen 生图；不读取 API Key；单次任务不自动重试。真实单图验收完成，后续测试复用该图，不重复计费。
- 本地 Pillow 中文分页，1080×1440 PNG，ZIP 同时含原图和分页图；图片和导出绑定审批版本。
- 小红书图文上传优先使用当前导出的分页图，没有分页则使用正文配图；回读图片数量、加载状态、标题和正文后才标记预览就绪。
- 修复浏览器旧会话引用失效标签页、入口异步加载、文本入口缺少可点击引用和编辑器空段落导致误报的问题。
- 隔离 demo 仅启用小红书预填，不启用公开发布任务。公众号配图未验证时明确阻止漏图预填。

## 实际结果

- 验收文章 item_6edfdbe5fc6c41378aee，已保存、审批、导出 3 页 PNG，并交接发布素材。
- 通过 Chrome 中工作台按钮创建批次 pubbatch_1dd52166926448bf97d9，自动上传 3 张图、填写标题/描述/话题，任务 succeeded，平台进入待人工审核状态。未点击公开发布。
- 生成图和项目资产存放 EXTERNAL_USB 的 migration-preview/assets/v2。
- 后端全量：216 项，215 通过，1 项因历史备份样本缺失跳过。后续连接器修复相关 19 项再次通过。
- 前端：33 文件、57 项通过；TypeScript 与隔离 dist 构建通过。

## 明确限制

- 公众号页面受当前代理浏览器访问限制，未现场验收，不能声称公众号图文自动上传完成。
- 小红书当前账号本次验证上传 3 张；适配器上限按观察到的编辑器 18 张限制。平台改版仍可能需要维护。
- 图片数量与文本自动回读不代替人工核对账号、图片内容与授权。公开发布仍需人工。
- 搜图来源当前仅 Wikimedia Commons；Codex 是否可生图取决于本机登录、工具可用性和账户额度。

## 发布字段与执行能力补充验收

- 发布 Agent 支持并默认选择 Codex CLI，保留原 Kimi 配置兼容；当前隔离 demo 已切换 Codex 并启用 publish.fields worker。
- 真正执行 job_eb2e71e9ac0f46bf8c64：Codex 返回小红书标题、正文、描述、话题，任务 succeeded，auto_saved=false、auto_published=false；未调用公众号。
- bootstrap 返回 execution_enabled；隔离环境为 false。前端禁用公开发布按钮，后端 confirm 在变更批次或入队前返回 PUBLISH_EXECUTOR_DISABLED，避免永远排队。
- 本轮相关后端 29 项通过；前端全量 33 文件、58 项通过；TypeScript 检查通过。
