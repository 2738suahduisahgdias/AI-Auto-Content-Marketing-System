# 选题、研究与微信线索

更新：2026-11-13。状态：已验证，除特别注明外。

## 功能与入口

- `/demo/topics/industry`：行业公开资讯。
- `/demo/topics/douyin`：热榜、精选、竞对和高赞快照。
- `/demo/topics/wechat`：微信消息、手动记录、分类与转任务。
- `/demo/topics/xiaohongshu`：小红书收藏分类与同步。
- 首页今日推荐也读取选题证据；推荐或研究条目可创建视频任务。

## 代码与共享组件

- 页面：`webapp/src/pages/Topics.tsx`、`components/TopicCard.tsx`、`WechatInbox.tsx`。
- 接口：`content_workbench/topics/api.py`。
- 数据与去重：`service.py`、`media_analysis.py`、`chrome_collection.py`、`wechat_inbox.py`、`wechat_client.py`。
- 后台执行：`executors.py`、`scheduler.py`；模型调用由共享 provider 决定，不由页面直接指定。

## 数据与依赖

- `wb_source_accounts`、`wb_collections`、`wb_memberships`、`wb_research_items` 保存采集关系。
- `wb_sync_runs`、`wb_analyses`、`wb_evidence`、`wb_topic_candidates` 保存同步、拆解和推荐证据。
- 转任务时，`TopicAPI` 调用旧任务创建函数，并把 `candidate_id` 或 `research_item_id`、原 URL 和快照时间写入 `tasks.source_json`。
- 微信连接状态与研究条目分开；连接成功不等于已采集或已发布。
- OCR 只负责画面文字，不等同口播全文；RapidOCR 路径来自工作区配置并有开发环境回退。

## 修改风险与检查

- 修改 source key、平台标签、收藏映射或去重会影响推荐、旧任务来源和已有深链。
- 修改转任务逻辑必须同时检查候选防重复、原始证据、旧任务 `source_json` 和视频入口。
- 修改浏览器采集需单独现场验收登录、部分失败和空结果；不能把空结果写成同步成功。
- 自动测试：`test_topics.py`、`test_topic_workspace.py`、`test_topic_candidate_api.py`、`test_wechat_*.py`。
- 只读人工检查：四类页面切换、详情弹窗、原链接、历史同步错误；不主动同步或创建任务。

## Kimi CLI 抖音采集流程（2026-11-13）

- 只有抖音采集动作 `hot/favorites/login/details` 强制通过 `topics/kimi_browser.py` 和 `agents/douyin-collection-agent.md` 调用 Kimi CLI，再由 `chrome-persistent` 操作固定 Chrome；发布和其他页面不改为 Kimi 浏览器驱动。
- “连接抖音采集窗口”先核对真实个人页面。已登录立即返回；未登录在同一固定窗口等待本人操作，最多 300 秒。超时不关闭浏览器、不清除会话或旧数据，不把任务标为成功。
- “同步内容”同样先检查登录，再执行热榜前 20 条和各收藏夹。Kimi 不读取或导出 Cookie；Cookie 只作辅助，最终必须核对真实页面。
- 后台 `wb_jobs` 记录阶段和百分比；同步结果保存 `provider=kimi_cli`、来源数量、完成来源数和每个来源的结构化错误。部分成功不写成全部成功，失败来源的旧快照保留。
- 浏览器工具暂时不可用时标记 `browser_reconnecting`，只读操作最多恢复重试一次；持续故障按真实 `browser_unavailable` 记录，不能误报为未登录。首轮全量同步实测三个收藏夹共 26 条成功、热榜失败，正确显示为部分完成。
- 已验证：Kimi CLI 实际读取固定 Chrome 并确认抖音登录；单独收藏夹“低粉高赞文案”返回 1 条真实作品。热榜初次返回包含后续推荐的 51 条，已在 Agent 和后端同时限制为前 20 条。
- 真实未登录状态下的 5 分钟超时本次未现场等待，使用结构化错误回归验证；不得写成已实测超时。
- **全量按钮验收通过**：`job_436bc53a894148a180fb` 最终为 `succeeded`，热榜 20、精选 20、竞对 5、高赞 1，四个来源均 `ok`、错误 0；新增 20、更新 26，没有重复创建相同作品。截图 `docs/acceptance/kimi-douyin-sync-records.png` 和 `kimi-douyin-topics.png`。
- **作品详情验收通过**：Kimi CLI 读取作者“商科子弹”、粉丝 3.1 万、点赞 27,708、评论 88，并写入 `wb_research_items.metadata`；高赞作品卡同步显示。顶层或条目内 `details` 均兼容，缺作者或互动字段时不会因为封面已缓存而跳过详情。证据 `docs/acceptance/kimi-douyin-author-engagement.png`。
- 功能编号：`P页码-C卡序号-F功能序号`，共 295 个功能均有唯一编号，索引 `docs/FUNCTION_IDS.md`。后续按编号迭代，新增功能在卡片末尾追加，不重用或改写原编号。

## 现场同步结果（2026-11-06）

- 已验证：抖音热点榜同步 20/20，形成 17 条真实研究快照；首条快照创建本地项目 `20261106-002`，来源关联保留。
- 小红书首次个人收藏同步为**部分完成**：新增 0、更新 0，未找到“选题”“企业AI落地竞对账号”“低粉高赞文案”三个配置名称。任务状态 succeeded 只表示同步流程结束，不能写成收藏内容同步成功。
- 已在隔离工作区把映射改为实际存在的“精选选题”“竞对账号内容”“高赞选题”，没有创建、改名或删除用户收藏。重试后三个收藏夹各 1 条，共新增 3 条、更新 0、错误 0，同步记录 `sync_7913ea148dfa4b3386be`；热点收藏夹留空，因此热点分类仍为 0。
- 旧版小红书页面数量与新版分类不同，属于来源差异；平台标签错误已在当前源码修复，安装版表现待确认。
