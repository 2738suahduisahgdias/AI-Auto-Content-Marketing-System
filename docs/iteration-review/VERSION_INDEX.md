# 映序开发版本索引

当前文档版本：v0.14.0。功能基线：26 个页面单元、316 条功能说明。

版本号仅用于开发文档和功能迭代，不代表安装包、DMG 或正式发行版本。每次先读取并对比现有记录，再合并新事实，不覆盖历史。

| 文档版本 | 日期 | 功能与迭代 | 记录 |
|---|---|---|---|
| v0.1.0 | 2026-11-11 | 全功能逐页评审基线与专用 Chrome | [查看记录](#iteration-2026-11-11-baseline) |
| v0.2.0 | 2026-11-13 | Kimi CLI 抖音登录与全量同步 | [查看记录](#iteration-2026-11-13-kimi-douyin-collection) |
| v0.3.0 | 2026-11-13 | 抖音作品作者与互动数据、全功能编号 | [查看记录](#iteration-2026-11-13-douyin-author-engagement-ids) |
| v0.4.0 | 2026-11-13 | 抖音全部作品卡逐条补全与真实协议修复 | [查看记录](#iteration-2026-11-13-douyin-batch-author-backfill) |
| v0.5.0 | 2026-11-13 | 热点作品卡与收藏作品卡拆分 | [查看记录](#iteration-2026-11-13-douyin-hot-collection-card-split) |
| v0.6.0 | 2026-11-14 | 证据链七步拆解法与指定视频真实验收 | [查看记录](#iteration-2026-11-14-evidence-chain-video-analysis) |
| v0.7.0 | 2026-11-14 | 移除拆解功能，改为下载与本地地址 | [查看记录](#iteration-2026-11-14-download-only-local-files) |
| v0.8.0 | 2026-11-15 | 原创文案手写与 AI 生成双路径 | [查看记录](iterations/2026-11-15-original-copy-ai.md) |
| v0.9.0 | 2026-11-15 | 收藏作品卡合并与作者互动全量补全 | [查看记录](#iteration-2026-11-15-collection-author-engagement-completion) |
| v0.10.0 | 2026-11-15 | 统一开发版本记录与产品功能归档 | [查看记录](#iteration-2026-11-15-version-archive) |
| v0.11.0 | 2026-11-15 | 小红书四类选题策略与真实素材下载 | [查看记录](#iteration-2026-11-15-xiaohongshu-topic-strategies) |
| v0.12.0 | 2026-11-15 | 词级时间码后台进度与模型复用 | [查看记录](iterations/2026-11-15-transcript-progress.md) |
| v0.13.0 | 2026-11-16 | 小红书真实视频与图文下载验收 | [查看记录](iterations/2026-11-16-xiaohongshu-download-acceptance.md) |
| v0.14.0（当前） | 2026-11-16 | 原创转写修复与对标画面字幕 | [查看记录](iterations/2026-11-16-transcript-and-benchmark-subtitles.md) |

## 后续维护

1. 新功能先在 `index.html` 找到对应页面和卡片，核对现状与技术调用。
2. 更新功能数据、实际截图和独立 Markdown 记录，不要只改说明。
3. 准备新的记录 JSON，执行 `node scripts/merge-iteration.mjs /path/new-record.json`。
4. 脚本先备份并读取现有记录；同一 ID 合并证据，新 ID 才递增文档版本。
5. 打开本地 HTML，验证导航、版本记录、迭代记录、图片和链接。
6. 历史只追加；替代旧结论时在新记录中说明原因，不删除旧记录。
