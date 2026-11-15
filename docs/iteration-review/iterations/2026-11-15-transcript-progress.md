# 2026-11-15：词级时间码后台进度与模型复用

## 范围

只修改原创项目 P10-C04-F02“生成词级时间码”及必要的本地执行器、后台任务、测试和文档。没有改文案、音乐、分镜、审核、发布的界面和数据关系。

## 实际变更

- 转写改为 `project.transcript` 后台任务；页面轮询任务状态，展示真实阶段、百分比和已用秒数。
- small/base 各由常驻 faster-whisper worker 复用模型，避免每次转写重新初始化。
- 开始识别立即上报真实 8% 起点，之后按实际分段结束时间推进；不模拟匀速百分比。
- 修复后台任务查询错误使用 `self.v2` 的问题，统一读取现有 `V2.jobs`。
- 沿用项目 ID、音频文件和 snapshot；每次生成新的字幕文件，不覆盖旧项目或旧字幕。

## 线上真实验收

- 项目 `20261115-001`，音频为 17.85 秒真人中文语音，文件 ID 15，不是静音或模拟媒体。
- 复用后的任务 `job_eae57fe633a84b7e932a` 从创建到完成 12.450 秒，任务 `job_97b4cd3e8f0b48699626` 为 6.997 秒。
- 修复后加载与转写合计约 12 秒；后台状态依次出现 `model_loading`、`transcribing` 8% 和 `succeeded`。
- 页面实际显示“转写中 · 8% · 已用 4 秒”；两次连续任务使用同一 worker PID 54422。
- 证据：`evidence/transcript-progress.png` 和项目 `docs/acceptance/transcript-progress.png`。

## 自动检查

- Python：转写 worker、项目执行器、进程退出和旧数据兼容共 12 项通过；真实 worker 55503 调用 `stop()` 后返回码 0。
- React：视频项目相关 15 项通过，覆盖真实百分比展示和成功后保存词语。
- 前端生产构建通过；相关 Python 文件 Ruff format/check 和语法检查通过；worker 覆盖率为 91%。
- 完整后端在 Python 3.12 + OpenSSL 3 下 434 项通过、1 项跳过。完整前端并行轮次 124 项通过、1 项高负载超时；单 worker 复验为 44 个文件、125 项全部通过。
- 回归测试先复现短音频缺少起始进度，再验证修复；不是只检查函数能否导入。

## 精简版原生 APP 最终验收

- 从最终只读 DMG 打开原生窗口，项目 `20261115-001` 的真实任务 `job_5011282586ed4cffb913` 成功生成 66 个词/片段；模型就绪后转写约 10 秒。
- 首次媒体环境准备慢，早期复用任务 `job_8b177fa34d9641d88e2b` 的后台耗时为 30.718 秒，不能把首次加载时间当成每次转写时间。
- 主服务 66954 和 worker 67213 均已在退出检查后消失；运行后的签名深检为 `valid on disk`、`satisfies its Designated Requirement`。
- 镜像校验 `VALID`，SHA-256 为 `ff9f5acfbea9ddf1d4cf6dd2f8876069249cf0a55f0f40a335538ba2f49a5c0e`。
- 构建排除 `._*` AppleDouble 元数据，桌面关闭入口同步清理 Whisper worker；相关 27 项测试通过。
- 原生截图：`docs/acceptance/transcript-slim-native.jpg`；任务时间记录：`docs/acceptance/transcript-real-results.json`。

## 未验证与边界

- 长音频、大量并发、其他硬件性能和安装版覆盖升级未验证。
- 进度按实际分段更新；单个长分段期间可能停在同一百分比，不插入虚假平滑进度。
- 词级识别使用本地 faster-whisper，不是 Kimi CLI；转写文本仍需要人工校对。
- 本机测试不证明 Apple Silicon、Windows 或干净客户机器已通过。
