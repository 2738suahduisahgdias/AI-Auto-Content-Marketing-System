# 2026-11-15：小红书四类选题策略与真实素材下载

## 版本与范围

- 读取版本索引时已有并行版本 v0.12.0；本次使用后续文档版本，不覆盖历史。
- 功能页面：`P06 小红书选题`。
- 保留现有选题、作品 ID、原链接和本地素材；不迁移或清空业务数据。
- 版本号属于开发文档，不代表 DMG 或正式发行版本。

## 实际变更

1. 登录改用 `XHSBrowserCollector + Kimi CLI`，不再走缺少 Playwright 的旧直连路径。
2. 登录必须核对真实个人入口；任务提交不再错误提示“页面已打开”。
3. 平台热点与个人收藏分开：热点保存排名、热度和原链接，不读取作者互动。
4. 精选、竞对、高赞逐类读取、逐类保存；三类作品补齐封面、作者、粉丝、点赞、评论和媒体类型。
5. 下载先探测，用户选择 quality/speed/compat 后才执行；视频与图文分别保存真实文件。
6. 同一作品更换 `xsec_token` 时按平台与真实作品 ID 复用旧记录，避免唯一约束冲突。
7. 新增四类策略、共享操作和素材下载弹窗的 HTML 功能说明。

## 真实验证记录

- 登录后的固定 Chrome 存在真实“我”个人入口，无扫码登录提示。
- 直接调用 Kimi CLI 登录检查返回 `login_verified=true`、`provider=kimi_cli`。
- 平台热点实际入库 10 条话题，包含参与人数、浏览量和真实原链接。
- 精选真实视频：变好AI、4.2 万粉丝、734 点赞、93 评论，媒体类型为 video。
- 高赞真实图文：Pitch. 创业社区、2.6 万粉丝、3430 点赞、25 评论，媒体类型为 image_set。
- 竞对收藏夹真实显示没有收藏笔记，保留空状态和具体错误，不伪造作品。
- 旧链接更换参数后复用同一作品 ID 的回归测试通过。

## 验收中发现并修复的问题

- 当前运行 Python 缺少 Playwright，导致点击登录无浏览器窗口。
- 前端曾把任务入队误写成“登录页已打开”。
- 收藏夹旧配置与真实名称不一致，已通过设置页改为“精选选题”“竞对账号内容”“高赞选题”。
- 热点话题页曾被错误送入作者互动补全，已限制为三类收藏。
- 多收藏夹单次长任务改为逐类执行，避免一个分类拖住全部结果。
- 作品链接参数变化导致唯一约束冲突，已按真实作品 ID 兼容旧数据。
- 专用 Chrome 启动脚本的 `lsof` 检查阻塞，已备份并改为带超时的本机端口与进程检查；重复启动复用正常。
- 多个客户端曾造成 8765 工作区不明确，最终验收使用明确连接目标数据的独立 8768 入口。

## 自动测试

- 后端全量：426 项通过、1 项跳过、44 个子测试通过。
- 小红书采集、下载、API、旧数据兼容和 Agent 配置均有新增或更新测试。
- 前端相关测试与生产构建通过。
- 完整前端高负载轮次存在 5 秒超时，已单独记录，不写成单轮全绿。

## 尚未完成

- 视频和图文的最终真实下载结果待写入。
- GitHub 提交与推送待实际验证；当前 gh 密钥环令牌已失效。
- 未重新打包 DMG，未验证干净客户机器或公开发布。

## 主要文件

- `agents/xiaohongshu-collection-agent.md`
- `agents/xiaohongshu-download-agent.md`
- `content_workbench/topics/xiaohongshu_browser.py`
- `content_workbench/topics/xiaohongshu_download.py`
- `content_workbench/topics/kimi_browser.py`
- `content_workbench/topics/executors.py`
- `content_workbench/topics/service.py`
- `content_workbench/topics/api.py`
- `webapp/src/components/TopicCard.tsx`
- `webapp/src/components/DownloadDetail.tsx`
- `webapp/src/components/DownloadProbeModal.tsx`
- `webapp/src/pages/Topics.tsx`
- `webapp/src/pages/Topics.css`
- `tests/test_xiaohongshu_collection.py`
- `tests/test_topics.py`
- `tests/test_topic_candidate_api.py`
- `tests/test_video_projects.py`

专用 Chrome 启动脚本备份保存在原任务目录：

`outputs/chrome-browser.py.backup-20261115`
