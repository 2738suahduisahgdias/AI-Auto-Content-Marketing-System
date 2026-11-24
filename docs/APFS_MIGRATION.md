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


## 2026-11-24 · 8847 隔离预览迁移与模型 I/O 修复

本次只处理 `http://127.0.0.1:8847/demo/` 及其 `8876` API，不修改正式 8848 工作区。旧日志在模型保存后的测试阶段出现 `sqlite3.OperationalError: disk I/O error`；当时预览库位于 exFAT 的 Samsung_T5，完整性只读检查为 `ok`，因此没有把故障写成数据库损坏或硬盘物理损坏。

### 当前路径与回滚

- 当前预览工作区（APFS）：`/Volumes/EXTERNAL_USB/kimi/storage/YingxuPreviewWorkspace/migration-preview`
- 当前日志：`/Volumes/EXTERNAL_USB/kimi/storage/YingxuPreviewWorkspace/migration-preview/server.log`
- 原预览工作区（保留）：`/Volumes/Samsung_T5/kimicode/AI-Auto-Content-Marketing-System/runtime/migration-preview`
- 正式 8848 与既有 `YingxuDevWorkspace` 未修改。

`scripts/start-migration-demo.py` 现在优先使用显式 `YINGXU_PREVIEW_ROOT`；未设置时，如果上述 APFS 数据库存在则默认使用 APFS，否则沿用原路径。正常启动：

```bash
python3 scripts/start-migration-demo.py
```

停止当前预览 API 后，可显式启动到旧目录：

```bash
YINGXU_PREVIEW_ROOT="/Volumes/Samsung_T5/kimicode/AI-Auto-Content-Marketing-System/runtime/migration-preview" \
python3 scripts/start-migration-demo.py
```

旧目录只代表迁移时点，不包含迁移后的新写入。回滚前如需保留新数据，应先另行在线备份当前 APFS 库；不要删除 WAL/SHM 或直接覆盖数据库。

### 迁移与真实验证

- 正常停止旧 `8876` 进程后，使用 SQLite `Connection.backup()` 在线备份，不复制运行中的 WAL/SHM。
- 新旧库 67 张业务表行数全部一致；目标库 `integrity_check = ok`、`foreign_key_check` 错误 0，授权 `license/state.json` 保留。
- 页面“保存并测试连接”实际调用成功，显示 `连接测试通过 · kimi_cli`；`POST /api/agents/system-model/test` 为 200。
- 页面“测试本地连接”实际调用成功，显示脚本生成能力已验证；`POST /api/ai/test` 为 200。
- 使用不带环境变量的默认命令再次真实重启，随后系统默认模型测试再次通过；新请求只写入 APFS 日志。
- 路径选择覆盖环境变量优先、APFS 存在和旧路径回退；`tests.test_reliability_repairs` 共 12 项通过。

本次未验证长期高并发稳定性、安装版、其他电脑或物理硬盘健康。本机及现有虚拟环境没有 pytest/Ruff，离线缓存也无 Ruff，未声称运行这两项检查。
