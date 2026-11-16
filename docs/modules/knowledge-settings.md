# 记忆、知识库与设置

更新：2026-11-05。状态：已验证，除特别注明外。

## 功能与入口

- `/demo/knowledge`：增长记忆、来源与效果依据。
- `/demo/knowledge/collection`：平台采集规则与数据契约。
- `/demo/knowledge/publishing`：发布字段、长度和验证规则。
- `/demo/settings/agents|models|media|templates|data`：Agent、模型、媒体、模板与隐私。
- `/demo/setup|activation|welcome`：接入、授权与新手引导。

## 代码与数据

- 页面：`pages/Knowledge.tsx`、`CollectionKnowledge.tsx`、`PublishKnowledge.tsx`、`Settings.tsx`、`SystemModelSettings.tsx`、`MediaTools.tsx`。
- 知识与记忆：`content_workbench/knowledge/`；增长记忆接口为 `/api/knowledge/memories`。
- Agent：`content_workbench/agents/registry.py`、`content_workbench/providers/system.py`、`content_workbench/providers/local.py`、`content_workbench/providers/text.py`。
- 媒体路径：`content_workbench/media/tools.py` 与工作区 `/Volumes/CodexData/YingxuWorkspace/config/media-tools.json`；模板：`config/video_templates.json`。
- 设置保存在本地数据库或工作区配置，敏感凭据不进入项目地图。

## 依赖与修改风险

- 全局默认文本模型与单 Agent override 共同决定选题、文章、编导和发布文案的模型路径。
- 收藏不自动等于爆款经验；增长记忆需要来源与效果依据，不能虚构指标。
- 修改 Agent 注册表、模型路由或提示词会影响多个业务模块，必须按实际使用方扩大回归。
- 修改模板版本、状态或 Props 会影响渲染缓存、预览和旧成片复现。
- 模型、图像、OCR、OpenVoice 和 Remotion 是独立能力，不得用一个“已连接”代替全部能力验收。

## 检查方法

- 自动：`test_agents.py`、`test_system_text_model.py`、`test_media_tools.py`、`test_video_templates.py`。
- 只读人工：打开记忆与两个知识库、Agent 配置、模型连接、本地媒体、模板预览和隐私页；不修改设置或运行收费测试。
- 现场另测：真实模型生成、OpenVoice、WhisperX、RapidOCR、Remotion 输出及磁盘路径切换。

## 状态

- 已验证：设置页面和模板预览可访问；RapidOCR 配置路径存在。
- 已验证：OpenVoice 独立诊断生成有效 WAV。
- 待确认：其他机器的首次安装、长任务和不同硬件上的模型稳定性；前端全量 ESLint 基线仍未全通过。

## 2026-11-06 隔离依赖与默认模型

- 文本创作、分析和编排默认使用 Kimi CLI；文章图片为 Kimi SVG→Remotion PNG，配乐为 Kimi 音符谱→本地 WAV，AI 单镜为 Kimi 场景代码→Remotion MP4，视觉分析读取真实关键帧，声音分离为 Kimi 规划→Demucs。
- Playwright/OCR、Demucs、OpenVoice、构建工具和缓存均安装在 APFS 的 `/Volumes/EXTERNAL_USB/kimi/storage/YingxuTools/` 隔离目录；正式 8848 配置未改。
- 现有 26 个独立 Agent；16 个生成型 Agent 均支持跟随系统或独立选择 Kimi CLI、Codex CLI、模型 API，并可分别填写模型名称。选择会传入实际 CLI/API 调用，历史明确配置不因默认值调整而重置。
- 新客户端内置可迁移 Python、Whisper、OCR、Demucs、OpenVoice、Playwright 和模型缓存，高级路径覆盖仅作兼容选项。完整 APP 的文件与运行结果分开验收，详见 `desktop/README.md` 和本次交接记录。
