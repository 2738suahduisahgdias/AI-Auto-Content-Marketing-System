# 旧版、历史文档与数据兼容

更新：2026-11-05。状态：已验证，除特别注明外。

## 旧版入口与实现

- `/legacy` 使用 `web/index.html`、`app.js`、`workspaces.js`、`publishing.js` 等原生 JavaScript，不经 React Router。
- `ContentWorkflow.app` 是 8765 简易启动壳，不等于完整 Mac 客户端 `映序工作台.app`。
- `SYSTEM_AUDIT.md` 记录旧架构，`product-design/` 同时包含历史评审、PRD、原型和验收材料；使用前先分辨年代与证据类型。

## 数据兼容边界

- 旧 `tasks`、`files`、`video_variants` 与 V2 `wb_*` 表并存，不应简单合并或改写成同一状态。
- 旧视频发布可从旧批准任务进入；映序交付必须从对应审核 approved 项进入，不能绕过 `review_deliveries`。
- 旧版研究卡片按条目实际平台显示来源；新版收藏分类与旧 `xhs_notes` 数量是不同数据集，不应强行要求数量相同。
- `wb_legacy_links` 和迁移 dry-run 用于旧对象映射；正式迁移必须先备份，第二次 dry-run 应 `changed=0`。
- 旧深链：`/demo/tasks/:id`、`/demo/articles/:id` 和 `/legacy` 都是兼容检查范围。

## 修改风险与检查

- 修改旧版 `approvedVideos()` 或发布选择器要同时覆盖旧任务和新审核项，避免重复、绕过或错误来源。
- 修改数据库 schema、状态或文件路径必须检查旧任务、旧发布、审核输出、文章版本和已有链接。
- 自动：`test_legacy_api_security.py`、`test_legacy_ui.py`、`test_yingxu_delivery.py`、迁移与 portable 测试。
- 只读人工：旧版各菜单与新版同内容对照、旧深链刷新、文件存在性；不迁移、不删除旧数据。

## 状态

- 已验证：旧版所有主导航可访问，旧深链和文章/视频新版深链返回 200。
- 已验证：当前源码修复旧版新审核项发布来源与平台标签，安装版是否升级待确认。
- 待确认：历史备份是否存在及完整恢复；`test_a02_real_backup_migration_twice` 因无真实备份跳过。
