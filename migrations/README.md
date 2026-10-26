# Workbench v2 迁移与恢复

## 边界

`001_workbench_v2.sql` 只创建 `wb_` 前缀表。不要绕过迁移程序直接在正式库执行 SQL。正式迁移前先停止新写入并创建 SQLite online backup。

## 备份

```bash
python3 -m content_workbench.storage.backup --root /Volumes/EXTERNAL_USB/kimi/content-agent
```

备份包含一致性数据库、数据库引用的媒体/样本、SHA-256 manifest 和代码哈希。

## 副本 dry-run

```bash
python3 -m content_workbench.storage.migrate \
  --source /path/to/backup/source.db \
  --target /path/to/copy/dryrun.db \
  --dry-run --report /path/to/copy/dry-run.json
```

连续运行两次；第二次必须 `changed=0`。检查 `integrity_check`、`foreign_key_errors`、对象映射和 `blocked`。缺少来源的旧字幕必须人工确认，不能按最新音频自动绑定。

## 正式切换

只有副本验证和测试通过后才执行：

```bash
python3 -m content_workbench.storage.migrate \
  --source /Volumes/EXTERNAL_USB/kimi/content-agent/data/content-agent.db \
  --target /Volumes/EXTERNAL_USB/kimi/content-agent/data/content-agent.db \
  --apply --report /path/to/backup/migration-applied.json
```

迁移程序使用确定性 legacy ID 和 `wb_legacy_links` 保证幂等。旧审批只保存为历史证据；新内容从 `needs_review` 开始，不伪造各平台审批。

## 回滚

- 切换前失败：弃用 dry-run 副本，原库继续使用。
- 切换后尚无 v2 新写：停服务，用备份恢复数据库及引用文件。
- 切换后已有 v2 新写：不得直接覆盖恢复；先导出新增 revision/assets/publications，再决定向前修复或人工重导。

恢复后用只读连接核对任务、版本、资产 hash、审批和发布记录。敏感凭据不属于迁移内容。
