# 文章、版本与导出

更新：2026-11-05。状态：已验证，除特别注明外。

## 功能与入口

- `/demo/articles`：搜索、筛选和新建文章。
- `/demo/articles/:id`：写文案、配图片、排版交付。
- 文章支持 brief、outline、draft、export 等版本；不是视频脚本节点强制附带的一篇文章。

## 代码与数据

- 页面：`webapp/src/pages/Articles.tsx`、`components/ArticleImageTools.tsx`、`PublishingPanel.tsx`。
- 接口：`content_workbench/articles/api.py`；版本与审批：`domain/services.py`。
- `wb_campaigns` 保存主题与 brief；`wb_content_items` 保存文章状态、版本和当前活动版本。
- `wb_revisions` 保存历史版本及 payload hash；`wb_approvals` 保存人工决定；`wb_assets` 保存正文导出与图片等内容寻址文件。
- `PublishingService.source("article")` 只接受 `approved` 或 `exported` 文章，并读取当前活动正文，不使用任意旧稿。

## 真实依赖

- `save_revision` 使用预期版本做 CAS，活动版本变化会使相关下游审批失效。
- `approve` 要求当前 revision 和 manifest hash 一致，防止审批期间内容被替换。
- 导出从当前已审批正文生成 Markdown/HTML；发布批次按 `source_id + source_hash` 关联，不使用“最新文件”替代版本关系。
- 图片、分页长图和导出资产仍须验证实际文件及来源，不是只有界面按钮。

## 修改风险与检查

- 修改 active revision、状态重算或审批逻辑可能让旧发布指向错误正文。
- 修改图片和导出会影响发布预览、素材路径、内容哈希及平台字段。
- 自动测试：`test_writing.py`、`test_article_images.py`、`test_article_image_services.py`、`test_local_runtime_export.py`、`test_publishing.py`。
- 只读人工检查：搜索、打开文章、三个编辑阶段、刷新恢复、导出文件存在性；不点击生成、保存或发布。

## 真实案例

`item_bd6ad93f58e84fc9acea` 当前为 exported，含 brief、outline、3 个 draft 和 1 个 export。`rev_a26dc53a423140aaae42` 指向 `rev_63e2aaef745d4a629c62` 正文；Markdown 和 HTML 文件均已确认存在。详见 `../CASES.md`。

## Kimi 图片能力（2026-11-06）

- 图片服务已从独立 Codex 能力改为 Kimi CLI：Kimi 生成 SVG 矢量插画，本地 Remotion 渲染 PNG；Agent 配置与媒体模块已打入测试客户端。
- 已验证：1200×1200 素材 `asset_ea04d50b0fa240d99bce`，画面包含“选题、制作、审核、发布”和人工终审，中文可读；不是仅验证接口返回。
- Kimi CLI 不直接输出位图，文档和界面不得把它写成通用文生图模型。SVG 安全检查、Remotion 失败或中文布局不合格都应阻止交付。
- 自动回归：`test_article_image_services.py`；相关页面为 `ImageProviderSettings.tsx`、`ArticleImageTools.tsx`、`ArticleCreativePlan.tsx`。
