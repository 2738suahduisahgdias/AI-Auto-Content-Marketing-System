# 2026-11-24：登录运行时与真实抖音／小红书任务修复

## 范围

- 接续预览共享浏览器与 worker 修复，处理真实任务暴露的解释器、事件循环、Kimi 空响应和模块调用问题。
- 只改登录路径，不替换热点、收藏和详情采集，不修改正式 8848 或账号凭据。

## 实际变更

1. 预览后端通过现有 `playwright_python()` 选择隔离解释器，避免系统 Python 缺少 Playwright。
2. 本地同步浏览器调用移到独立新线程，避开 worker 线程事件循环。
3. 抖音 `topics.login` 使用 `browser_worker`，小红书 `topics.xhs_login` 使用共享 `existing_browser`，不再依赖 Kimi 完成确定性登录检查。
4. `browser_worker` 从项目根目录以 `python -m` 调用，修复模块导入路径。

## 真实验证

- 小红书任务 `job_089d1d79789f4d299e79` 为 `succeeded`，返回 `login_verified=true`。
- 抖音任务 `job_4b944e82fa844d6b922b` 为 `running/waiting_for_user_login`，不再发生 Kimi 空响应、模块导入或 Sync API 错误。
- 直接 1 秒抖音检查返回 `login_required` 后，9223 仍由同一 Chrome PID 76123 监听。
- 相关 83 项 unittest 在 Python 3.12 下全部通过。

## 未验证与边界

- 抖音本人扫码和登录成功尚未完成；当前只是任务正确等待，不写成已登录。
- 热点、收藏和详情仍走 Kimi，本次未验证这些采集，也未处理其动态工具加载问题。
- 小红书全量同步、四个账号全部登录、上传读回、安装版和其他电脑未验证；pytest/Ruff 不可用。

## 回滚

恢复登录执行器、浏览器线程与预览启动脚本并重启 8876。历史失败任务保留，不作为当前成功证据；不需要回滚数据库或浏览器登录资料。
