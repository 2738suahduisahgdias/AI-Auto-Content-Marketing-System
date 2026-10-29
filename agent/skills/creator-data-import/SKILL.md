---
name: creator-data-import
description: 读取抖音、小红书、视频号和公众号创作者后台的官方 XLSX、XLS、CSV 导出，生成系统统一指标。用于历史数据回填、导出文件校验和日报数据准备；不读取浏览器登录态，不采集在线页面。
version: 1.0.0
---

# 官方创作者数据读取

仅在用户选择或指定本机官方导出文件后运行。优先使用此 Skill，而不是重复打开平台后台。

## 安全边界

- 只读取明确提供的文件，不遍历下载目录，不上传文件或指标。
- 不读取 Cookie、Token、密码，不打开浏览器，不自动重试，不绕过验证码。
- 缺失指标保持 `null`，不得补零或猜测。
- 此命令只解析文件，不代表已经同步或保存到账号日报。保存必须走系统现有同步流程。

## 命令

在项目根目录执行：

```bash
python3 agent/skills/creator-data-import/scripts/read_export.py --platform douyin --files "数据表现_短视频全量指标.xlsx" "数据表现_粉丝全量指标.xlsx"
python3 agent/skills/creator-data-import/scripts/read_export.py --platform xiaohongshu --files "近30日观看数据.xlsx" "近30日互动数据.xlsx" "近30日涨粉数据.xlsx" "近30日发布数据.xlsx"
python3 agent/skills/creator-data-import/scripts/read_export.py --platform wechat_channels --files "视频号逐日数据.csv"
python3 agent/skills/creator-data-import/scripts/read_export.py --platform wechat_official_account --files "公众号内容分析明细.xls"
```

小红书文件顺序固定为观看、互动、涨粉、发布。抖音文件顺序固定为短视频全量指标、粉丝全量指标。

成功时输出 `status=success`、平台、文件名和统一指标的 JSON。失败时查看 `message` 中的具体文件或解析原因，并按 `action` 修正；不要把失败当作空数据。

公众号旧版 XLS 需要项目已有的 `.venv-accounts` 隔离环境。缺少时按 `requirements-accounts.txt` 安装，不修改主 Python 环境。
