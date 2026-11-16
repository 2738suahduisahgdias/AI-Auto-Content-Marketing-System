# 真实关联验证案例

更新：2026-11-05。两个案例均只读检查代码、SQLite 和文件，没有调用创建、生成、审核、同步或发布写操作。

## 案例一：视频任务 → 审核交付 → 实际成片 → 发布目标

### 入口

- 视频：`/demo/tasks/20261103-001`
- 审核：`/demo/review`
- 发布：`/demo/publish?kind=video&id=reviewitem_1db92b2b48ed43669083`

### 真实关联

1. `tasks.content_id = 20261103-001`，标题为“有些慢，是能力正在换轨”，旧状态为 rendered。
2. `source_json.yingxu_handoff` 指向 `reviewitem_1db92b2b48ed43669083`、文件 #20、制作 revision 36，状态 approved，`stale=0`。
3. `review_deliveries` 将同一任务、文件和 revision 绑定到该审核项；`review_items.decision/status` 均为 approved。
4. 审核输出为 `renders/20261103-001/cf6a15082af5-yingxu-final-v34.mp4`。文件实际存在，ffprobe 显示 H.264/AAC、1080×1920、146.837 秒、10,577,682 字节。
5. 发布批次 `pubbatch_6317f0866ce442a6b9ba` 的 `source_id` 是该审核项，而非仅使用旧任务 ID。抖音和小红书目标为 failed，视频号为 draft。

### 代码依据

- `app.py` 的 handoff 记录。
- `content_workbench/review/delivery.py`：交付绑定与审批输出。
- `content_workbench/review/service.py:196`：发布前重新检查 approved、输出文件和 SHA-256。
- `content_workbench/publishing/service.py:245`：发布队列纳入新审核交付。

### 可重复只读检查

```bash
sqlite3 -readonly -header -column "/Volumes/CodexData/YingxuWorkspace/data/content-agent.db" \
  "SELECT content_id,title,state,json_extract(source_json,'$.yingxu_handoff.review_item_id'),json_extract(source_json,'$.yingxu_handoff.file_id'),json_extract(source_json,'$.yingxu_handoff.revision'),json_extract(source_json,'$.yingxu_handoff.status'),json_extract(source_json,'$.yingxu_handoff.stale') FROM tasks WHERE content_id='20261103-001';"

sqlite3 -readonly -header -column "/Volumes/CodexData/YingxuWorkspace/data/content-agent.db" \
  "SELECT d.item_id,d.content_id,d.file_id,d.revision,i.decision,i.status,i.output_path FROM review_deliveries d JOIN review_items i ON i.id=d.item_id WHERE d.content_id='20261103-001';"

ffprobe -v error -show_entries format=duration,size \
  -show_entries stream=codec_name,width,height -of json \
  "/Volumes/CodexData/YingxuWorkspace/renders/20261103-001/cf6a15082af5-yingxu-final-v34.mp4"
```

再只读查询 `publish_batches`、`publish_targets`，确认来源 ID、状态和平台，不打开同步或最终发布。

### 结果与未确认部分

- **已验证**：任务、审核、成片和发布来源可以完整追溯；深链和发布页可访问，实际视频有效。
- **待确认**：平台预览是否仍可生成、当前登录是否有效、失败能否恢复。本次未重试，不把失败或成功写成当前实时结果。
- **注意**：文件 #20、文件版本 v34、handoff revision 36 是不同编号，不可混用。

## 案例二：文章活动版本 → 审批与导出 → 实际文件 → 发布批次

### 入口

- 文章：`/demo/articles/item_bd6ad93f58e84fc9acea`
- 发布：`/demo/publish?kind=article&id=item_bd6ad93f58e84fc9acea%3A0`

### 真实关联

1. `wb_content_items` 中文章“端到端验收｜AI客服如何落地｜1102”为 exported，内容类型 article，版本 8。
2. `wb_revisions` 包含 brief、outline、3 个 draft 和 1 个 export。
3. `rev_a26dc53a423140aaae42` 的 `source_revision_id` 是 `rev_63e2aaef745d4a629c62`，导出不是脱离正文版本的独立文件。
4. 导出记录包含 Markdown 资产 `asset_d9712d564a8a49349de6` 和 HTML 资产 `asset_cef5418979ee4e32a8bb`，两个内容寻址文件均存在。
5. 发布批次 `pubbatch_b5da26242f62402b9e71` 的 `source_id` 是该文章，状态 ready；小红书目标为 ready。该状态不代表已公开发布。

### 代码依据

- `Workbench.get_item/save_revision/approve`：活动版本、manifest 和审批。
- `ArticleAPI`：文章生成、导出与发布记录入口。
- `PublishingService.source("article")`：只接受 approved/exported 的当前正文。

### 可重复只读检查

```bash
sqlite3 -readonly -header -column "/Volumes/CodexData/YingxuWorkspace/data/content-agent.db" \
  "SELECT i.id,c.title,i.state,i.platform,i.content_type,i.version FROM wb_content_items i JOIN wb_campaigns c ON c.id=i.campaign_id WHERE i.id='item_bd6ad93f58e84fc9acea';"

sqlite3 -readonly -header -column "/Volumes/CodexData/YingxuWorkspace/data/content-agent.db" \
  "SELECT id,kind,revision_no,validity,payload_hash,created_by FROM wb_revisions WHERE item_id='item_bd6ad93f58e84fc9acea' ORDER BY kind,revision_no;"

sqlite3 -readonly -header -column "/Volumes/CodexData/YingxuWorkspace/data/content-agent.db" \
  "SELECT json_extract(payload_json,'$.markdown_asset_id'),json_extract(payload_json,'$.html_asset_id'),json_extract(payload_json,'$.source_revision_id') FROM wb_revisions WHERE id='rev_a26dc53a423140aaae42';"
```

用返回的资产 ID 查询 `wb_assets.storage_key`，再用 `test -f` 检查文件，不下载或替换文件。

### 结果与未确认部分

- **已验证**：文章、版本、导出资产和发布批次可追溯；深链可访问，导出文件存在。
- **待确认**：当前正文是否仍与发布页显示一致、平台预览是否仍有效。本次只读取当前数据库和已有证据，没有生成新预览或发布。
- **注意**：`source_file_id` 为空不妨碍文章来源关系；文章来源由 `content_kind + source_id + source_hash` 确定。

## 案例三：原创/对标项目 → 真实成片 → 审核与发布中心

本次使用明确标注的开发验收数据，不在真实工作区新建项目。

### 原创

- 项目 `20261105-001` 经文案、旁白转写、音乐适配、真实编导 2 镜、样片 #5，生成完整成片 #6。
- 成片为 `renders/20261105-001/a69d43ffda28-yingxu-final-v18.mp4`，H.264/AAC、1080×1920、5.376 秒。
- 审核批次 `review_104ad10220b44d14a4b3` 显示相同项目、文件 #6 和制作版本 21。

### 对标

- 项目 `20261105-002` 将本机 4 秒参考视频拆成 2 镜，整片转写 1 次并保存真实关键帧。
- 第一镜保留原声和原时间码；第二镜使用独立上传的 1 秒画面，用户选择循环至 2 秒和静音；明确叠加 4 秒音乐适配。
- 样片 #13 后生成完整成片 #14 `renders/20261105-002/ee3aaf7b4f95-yingxu-final-v19.mp4`，H.264/AAC、1080×1920、4.011 秒。
- 审核批次 `review_3e11cd41d01a494a80db` 显示相同项目、文件 #14 和制作版本 22。3 秒抽帧为上传的绿色画面。

### 结果

- **已验证**：两条流程都从真实项目走到文件、审核和发布中心；发布中心均显示“等待审核，尚未发布”。
- **未执行**：人工技术预审、平台同步和公开发布。
- **证据**：`docs/acceptance/video-projects/` 中的首页、拆解报告、逐镜弹窗与成片抽帧。
