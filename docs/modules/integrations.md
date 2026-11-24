# 账号、社媒、微信、授权与后台集成

更新：2026-11-10。状态：已验证，除特别注明外。逐页卡片和按钮见 `docs/FUNCTION_MAP.md`。

## 功能与入口

- 接入向导 `/demo/setup`：检查 Chrome、Playwright、微信 Bot、模型和四平台登录入口。
- “映序专用 Chrome”卡提供重新检测、启动、重启和关闭；抖音、小红书、视频号、公众号都从同一固定窗口打开。
- 选题页的抖音采集登录、小红书登录，以及发布中心四个平台的“打开专用浏览器登录”，使用同一浏览器资料。
- 账号数据由 `/api/accounts/*` 提供；新版 `/accounts/*` 前端路由重定向首页，不写成仍在使用独立新版账号分析页。
- 社媒能力目录由 `/api/social/*` 提供，区分 supported 与 adapter_required。
- 离线授权 `/demo/activation` 与 `content_workbench/licensing/`；Worker 执行前要求有效授权。

## 专用 Chrome 架构与安全边界

- 生命周期：`accounts/dedicated_browser.py`；本机接口：`accounts/browser_connection.py`；Playwright 接入：`topics/browser_worker.py`、`accounts/local_browser.py`。
- 固定资料目录：工作区 `data/yingxu-chrome-profile`。目录含登录状态，不得进入 Git、文档、截图或备份说明中的公开附件。
- 默认调试地址：`http://127.0.0.1:9223`，独立于 Kimi 的 9222 实例。可用环境变量为隔离测试换端口，生产不监听局域网，不添加任意来源参数。
- 启动前检查端口真实进程和 `--user-data-dir`。其他程序或其他 Chrome 占用端口时返回 `BROWSER_PORT_OCCUPIED`，不误连、不强制关闭。
- 不读取、复制或退出日常 Chrome，不使用日常默认 Profile。首次使用映序专用窗口时需要分别登录平台；之后复用，平台会话过期仍需重新登录。
- 任务结束只断开 Playwright，不关闭共享窗口。用户主动关闭时通过 CDP `Browser.close` 正常退出，让持久资料写入磁盘；运行中浏览器任务会阻止重启或关闭。
- 仅监听本机不等于有身份认证。本机程序及获准控制映序的 AI 仍能操作专用浏览器中的账户。

## 主要代码与数据

- 账号：`accounts/api.py`、`executors.py`、`service.py`、`existing_browser.py`。
- 选题浏览器：`topics/chrome_collection.py`、`topics/browser_worker.py`。
- 发布浏览器：`publishing/executors.py`、`publishing/browser_worker.py`。旧 WebBridge worker 只保留非专用模式兼容路径，不是当前客户端标准依赖。
- 社媒：`social/api.py`、`executors.py`、`catalog.py`。
- 微信：`topics/wechat_client.py`、`wechat_inbox.py`、`wechat_inbox_bridge.py`。
- 后台：`jobs/store.py`、`jobs/worker.py`、`schedule/`、`topics/scheduler.py`、`accounts/scheduler.py`。
- 授权：`licensing/`、`operator_tools/`；公开验签公钥可以打包，私钥和客户记录不得进入文档或构建说明。
- 原生文件选择：`desktop/launcher.m` 实现 WebKit `runOpenPanelWithParameters`，取消也必须完成回调。
- 验签运行时：`desktop/runtime_bundle.py` 只接受 OpenSSL 3，并携带 `libcrypto`/`libssl`；macOS 自带 LibreSSL 不支持当前 Ed25519 验签。
- 申请码由工作区固定 `installationId` 生成；重装 APP 但沿用工作区时相同是预期。换用其他安装身份的授权返回 `LICENSE_DEVICE`，不能覆盖已有有效授权。

## 真实依赖与风险

- Chrome 已连接只证明浏览器可用，不证明平台已登录、同步成功、字段已上传或公开发布。
- 微信 Bot 连接与原始消息分开保存；断开连接不能删除研究数据。
- 账号自动分析调度默认关闭；不要根据历史文档写成每日分析正在运行。
- Worker、调度和恢复共享 `wb_jobs`；修改执行器映射、浏览器资源锁或授权门禁可能导致任务排队但不能执行。
- 发布预填、人工审核与公开发布是不同状态。不得因为页面在专用 Chrome 中打开就标记发布成功。

## 检查方法

- 自动：`test_dedicated_browser.py`、`test_browser_connection.py`、`test_account_collection.py`、`test_reliability_repairs.py`、`test_publishing.py`、`test_social_capabilities.py`、`test_wechat_*.py`、`test_offline_license.py`、`test_schedule.py`。
- 真实隔离验收：使用独立工作区和测试端口；验证同一 PID 复用、任务结束不关窗、正常关闭、带有效期测试 Cookie 重启保留、端口冲突拒绝。不要读取真实 Cookie 或账号凭据。
- 页面：接入向导检查专用浏览器卡片和四个平台入口；选题与发布中心检查登录按钮是否进入同一窗口。
- 现场另测：本人扫码、二次验证、真实账号快照、上传字段读回、失效恢复和平台同步。

## 本次状态与待确认

- 已验证：固定目录、仅本机监听、同进程复用、任务结束不关窗、正常关闭、持久测试 Cookie 重启保留；测试 Cookie 已删除。
- 已验证：前端 43 个文件、109 项测试和生产构建通过；22 个主要路由在隔离工作区完成渲染盘点。
- 已验证：后端共 394 项，392 项通过、1 项跳过；`test_codex_missing_binary_is_unavailable` 仍因仓库旧数据库 disk I/O error 失败，未修改旧库，不宣称全绿。
- 待确认：新专用窗口的真实平台登录、上传读回、安装版覆盖升级及干净客户 Mac。当前源码修改尚未重新打包或覆盖安装版。


## 2026-11-24 · 预览登录 worker 与共享 Chrome 修复

- 8847/8876 预览启动缺少 `YINGXU_DEDICATED_CHROME=1`，登录流程可能退回临时 Playwright 或旧 WebBridge；临时路径结束会关闭 context。预览后端现在强制启用共享专用 Chrome，正式 8848 配置不变。
- 预览 worker 复用现有执行器，注册并允许 `accounts.login`、`topics.login`、`topics.xhs_login`，不再让平台登录任务永久停在 `queued`。
- 真实页面启动专用 Chrome 后，Playwright 断开仍保留 `127.0.0.1:9223`；依次打开小红书、抖音、视频号和公众号并执行登录判断后，仍为同一个 Chrome PID 76123。未通过登录判断的页面也没有触发关窗。
- 旧 `topics.login` 已被 worker 接管并进入 `running`；其后的 `accounts.login` 仍按浏览器资源锁排队。浏览器可用不等于四个账号已登录，本人扫码、二次验证、字段和上传读回仍需分别验收。
- 回归：`test_reliability_repairs` 14 项、`test_dedicated_browser` 与 `test_browser_connection` 11 项、账号采集与 Kimi 浏览器相关 37 项，共 62 项 unittest 通过。未执行 pytest/Ruff，原因同环境工具缺失记录。


## 2026-11-24 · 登录运行时补充修复与真实任务结果

- 预览后端改用现有 `playwright_python()` 选择解释器，避免系统 Python 缺少 Playwright；`existing_browser` 的同步本地浏览器调用移到独立新线程，避开 worker 线程中的事件循环。
- 抖音 `topics.login` 改用 `browser_worker` 确定性检查，小红书 `topics.xhs_login` 改用共享 `existing_browser`。热点、收藏和详情采集仍保留 Kimi 路径，本次没有宣称这些采集已恢复。
- `browser_worker` 改为从项目根目录通过 `python -m content_workbench.topics.browser_worker` 调用，避免直接文件执行时找不到项目包。
- 真实小红书任务 `job_089d1d79789f4d299e79` 为 `succeeded`，返回 `login_verified=true`。真实抖音任务 `job_4b944e82fa844d6b922b` 为 `running/waiting_for_user_login`，不再出现 Kimi 空响应、模块导入或 Sync API 错误；本人登录尚待完成。
- 直接执行 1 秒抖音登录检查返回 `login_required` 后，9223 仍由同一 Chrome PID 76123 监听。窗口保留不等于账号已登录。
- 最终相关 83 项 unittest 在 Python 3.12 下通过；`datetime.UTC` 测试不使用系统 3.9 运行。pytest/Ruff 仍不可用。
