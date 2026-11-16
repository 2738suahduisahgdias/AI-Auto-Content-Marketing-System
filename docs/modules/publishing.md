# 发布、平台字段与预览

更新：2026-11-05。状态：已验证，除特别注明外。

## 功能与入口

`/demo/publish` 分为文章发布和视频发布，展示交付来源、发布目标、字段编辑、保存、预览和手动发布入口。预览、预填、保存和公开发布是不同状态。

## 代码与数据

- 页面：`webapp/src/pages/Publish.tsx`、`components/PublishingPanel.tsx`。
- 服务：`content_workbench/publishing/service.py`、`api.py`、`executors.py`。
- 平台契约：`knowledge.py`、`schemas.py`、`coverage.py`；WebBridge worker：`webbridge_worker.py`。
- `publish_batches` 保存内容类型、来源 ID、来源哈希、确认信息；`publish_targets` 保存平台、payload、预览、错误和外部 URL。
- `publication_queue()` 同时读取旧批准视频与 `ReviewService.approved_sources()` 的新审核交付。

## 真实依赖与风险

- 文章来源必须是 approved/exported，视频来源可以是旧批准版本或新审核 approved 项。
- `assert_current` 再次计算来源哈希，内容改变会阻止旧批次继续。
- 客户端设置 `publishing_execution_enabled=False` 且 Worker 排除 `publish.execute`，所以客户端只做草稿预填，最终发布由用户在平台完成。
- 当前源码将四平台登录统一到 WebBridge；抖音、小红书发布最近失败是否恢复仍需现场验收。
- 旧版发布选择器需要同时读取 `/api/publishing/queue`，不能只读旧 `tasks.state`。

## 检查方法

- 自动：`test_publishing.py`、`test_publish_*.py`、`test_webbridge_*.py`。
- 只读人工：切换文章/视频、检查来源、平台字段、失败状态、手动下载入口；不执行同步或最终发布。
- 跨模块：视频审核项、文章活动版本、发布批次来源哈希、实际成片或导出文件必须一致。
- 现场另测：本人登录、平台页面变化、上传读回和人工确认；不能用 mock 结果替代。

## 当前错误证据

真实视频发布批次 `pubbatch_6317f0866ce442a6b9ba` 当前为 failed：抖音和小红书失败，视频号为 draft。该状态只说明历史结果，不能写成当前已发布或当前一定仍失败。

## 2026-11-06 现场预填结果

- 隔离工作区批次 `pubbatch_b0f33c630e7b4f10a138` 关联审核项 `reviewitem_74f429936d954ebb88ab` 和项目 `20261105-002` 的文件 #8；Kimi 生成的三平台字段已保存。
- 抖音与小红书均登录本人账号，实际上传同一条 5.376 秒成片，标题、正文和话题读回一致，目标状态 ready，外部 URL 为空。视频号为 draft/手动上传。
- 后台标签视频元数据未加载曾使抖音首次预填失败；在原页面恢复渲染并读回正确时长后重试成功，没有放宽来源一致性校验。
- 截图：`../acceptance/video-projects/douyin-preview-ready.png`、`xiaohongshu-preview-ready.png`。
- 已验证的是预填，不是公开发布。最终封面、声明、可见范围和发布按钮仍需用户在平台后台检查决定。
