# 开发数据库迁移到 APFS 的记录与回滚

日期：2026-11-05。方式：SQLite 在线备份，不使用运行中文件复制，不删除或覆盖原库。

## 路径

- 原开发库（保留）：`/Volumes/Samsung_T5/kimicode/AI-Auto-Content-Marketing-System/data/content-agent.db`
- 回滚备份（保留）：`/Volumes/Samsung_T5/kimicode/AI-Auto-Content-Marketing-System/data/backups/content-agent-pre-apfs-20261105-215607.db`
- 当前开发库（APFS）：`/Volumes/EXTERNAL_USB/kimi/storage/YingxuDevWorkspace/data/content-agent.db`
- 客户端 8848 数据库未修改，仍按其原工作区配置运行。

CodexData 原计划目标不可用：该卷当时无法挂载，`verifyVolume` 报告容器超级块无效。没有执行修复、格式化或覆盖。因此改用另一块可写 APFS 磁盘 `EXTERNAL_USB`，没有修改 8848 的配置或数据。

## 启动配置

`scripts/start.sh` 在上述 APFS 数据库存在且未显式设置 `CONTENT_AGENT_DB` 时，默认使用新库。显式设置 `CONTENT_AGENT_DB` 仍可覆盖，因此可以回滚。

正常启动：

```bash
PATH="/usr/local/opt/openssl@3/bin:$PATH" bash scripts/start.sh
```

停止当前开发服务后，用回滚备份启动：

```bash
CONTENT_AGENT_DB="/Volumes/Samsung_T5/kimicode/AI-Auto-Content-Marketing-System/data/backups/content-agent-pre-apfs-20261105-215607.db" \
PATH="/usr/local/opt/openssl@3/bin:$PATH" \
bash scripts/start.sh
```

回滚是启动到备份时间点，不会把后续新写数据反向覆盖到旧库。若需要保留迁移后的新数据，先另行备份当前 APFS 数据库。

## 备份校验

原库、APFS 新库和回滚备份在切换前均为：

- `integrity_check = ok`、`quick_check = ok`、`journal_mode = wal`
- 项目 6 个、文件 14 个、审核交付 2 条、发布批次 0 个
- 项目 ID 均为 `20261105-001` 至 `20261105-006`

此开发库原本不含 `20261103-001`；该旧项目属于另一工作区，不能用本次迁移声称它已被复制。此前旧链接验证使用独立数据库副本。

## 启动与真实写入验证

- 新库启动时各启动接口均为 HTTP 200，没有启动调度错误。
- 项目首页显示原 6 个项目。
- 新建 `20261105-007`（标题为 APFS迁移写入验收-可删除），保存 revision 1 成功。
- 写入后 APFS 新库为 7 个项目；原库和回滚备份仍各为 6 个，未被修改。
- 审核 `review_104ad10220b44d14a4b3` 仍显示原项目文件 #6 和制作版本 21。
- 发布中心仍显示原创文件 #6、对标文件 #14 均等待审核，未公开发布。
- 选题、文章、设置和记忆页面均可读取。
- 最终运行日志未发现新的 `v2 error`、`Traceback`、`disk I/O error` 或 500/503/409。

## 后续检查与限制

- 本验证覆盖启动、读取和一次项目创建，不等于长时间高并发稳定性证明。
- 继续观察 `data/server.log`（若后续配置持久日志）或服务输出，重点检查 `disk I/O error`。
- 不为掩盖错误而重复写、清空 WAL 或删除旧库。
- 如果再次出现持续错误，停止写入并保留当前 APFS 库与回滚备份，再排查磁盘和进程。
