# 2026-11-16：小红书真实视频与图文下载验收

## 版本与范围

- 本次是 v0.11.0 小红书选题功能的后续验收和兼容修复，使用新的独立记录，不改写历史。
- 功能页面：`P06 小红书选题`，重点为 `P06-C05` 下载详情和 `P06-C10` 素材探测下载弹窗。
- 真实验收继续使用独立 8768 工作区，不迁移、清空或删除已有选题；保留原作品 ID、快照和本地资产。

## 本次修复

1. `xiaohongshu_download.py` 使用延迟解析类型标注，解决 Python 3.9 导入时的 `float | None` 运行时错误。
2. `TopicService.bootstrap.jobs` 补入 `research.probe`，弹窗可以收到真实成功或失败终态，不再持续显示“读取中”。
3. 下载 Skill 的 `_probe_format_ytdlp.py` 对 `null` 返回明确错误，不再触发 `AttributeError`。
4. 未登录命令行遇到登录跳转或空结果时，由 Kimi CLI 在同一固定 Chrome 的真实作品页读取实际媒体；不读取或导出 Cookie，不绕过 DRM。
5. 视频只报告当前实际加载流的尺寸、时长和来源；未知码率、文件大小保持为空。图文去重并保存当前作品的全部实际图片，不混入头像或推荐内容。
6. 功能文档的迭代深链接改为只显示目标记录，返回“迭代记录”时恢复全部历史；Obsidian 与仓库 HTML 均已实际操作验证。
7. 收尾自检将封面缓存的异常忽略范围收窄到系统／网络错误，未知错误不再被吞掉；同步整理下载弹窗导入顺序。

## 真实验收

### 精选视频

- 作品：`research_5953b29ab59f10aaabe8`，标题“做个AI 24小时在线搞💰，是什么感觉！！”。
- 探测任务 `job_aadb57857d214cc08756` 成功：1080×1920、约 31.93 秒，来源标记 `fixed_chrome`。
- 用户选择“兼容优先”后，下载任务 `job_a362718caf414e8fb9bf` 成功。
- 文件：`assets/topic-downloads/research_5953b29ab59f10aaabe8/01.mp4`。
- FFprobe 和本地读取确认：31.881066 秒、15,972,890 字节、真实 MP4；页面显示 15.97 MB。
- “复制本地地址”后的系统剪贴板与资产路径完全一致；“打开所在文件夹”调用成功。
- 页面证据：`evidence/xiaohongshu-video-download.png`。

### 高赞图文

- 作品：`research_bd68cf9b7fcb83c13e2b`，标题“🪐从一人开始，到无限可能｜会员计划”。
- 探测正确返回 `image_set`，没有伪造视频档位。
- 用户选择“兼容优先”后，下载任务 `job_ae14e24ebe124597b53e` 成功。
- 共 9 张 WebP，逐张 Pillow 校验通过，均为 1080×1440，合计 1,141,506 字节；首图和末图已人工查看。
- 页面显示“图文素材 · 9 个文件”和整组 1.14 MB，不把首图大小当作整组大小。
- “复制本地地址”和“打开所在文件夹”均完成实际操作核对。
- 页面证据：`evidence/xiaohongshu-image-set-download.png`。

## 自动测试与自检

- Python 3.9 实际运行小红书采集下载测试：7 项通过。
- 项目指定 OpenSSL 环境下完整后端：429 项通过、1 项跳过。
- 新增探测任务入口回归测试；下载弹窗失败终态与兼容模式测试 2 项通过。
- 小红书页面 6 项测试单独通过；生产构建通过；本次相关前端文件 ESLint 通过。
- 前端完整单轮：126/127 项通过，`Tasks.test.tsx` 一项在 5 秒限制超时；该用例单独复测通过，因此不宣称单轮全绿。
- 全量前端 ESLint 仍有 319 errors、18 warnings，分布在大量既有文件；未为了本次功能大范围改写。
- 功能基线保持 26 个页面单元、316 条功能说明，没有覆盖其他并行迭代。
- 收尾自检新增未知封面异常回归测试；相关后端 19 项、下载弹窗前端 2 项及 Ruff、ESLint 通过。

## 未验证与边界

- 只实际验收“兼容优先”；“画质优先”和“速度优先”的真实下载结果未验证。
- 竞对收藏夹真实为空，没有竞对作品可执行下载验收。
- 未重新打包 DMG，未验证安装版、干净客户机器、Windows 或 Apple Silicon 客户端。
- 未执行公开发布；本地下载与发布中心、公开发布是不同环节。
- Git 本地提交为 `34daa58`；推送时本机无法解析 `github.com`，未形成远端同步，不能称为 GitHub 已交付。

## 主要文件

- `agents/xiaohongshu-download-agent.md`
- `content_workbench/topics/xiaohongshu_download.py`
- `content_workbench/topics/service.py`
- `tests/test_topics.py`
- `webapp/src/components/DownloadProbeModal.test.tsx`
- `docs/FUNCTION_MATRIX.md`
- `docs/FUNCTION_MAP.md`
- `docs/CHECKS.md`
- 外部已安装 Skill：`video-downloader/scripts/_probe_format_ytdlp.py`，修改前备份在 `/tmp/yingxu-probe-format-ytdlp.backup-20261116.py`。
