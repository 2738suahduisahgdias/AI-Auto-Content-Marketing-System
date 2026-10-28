# 全自动AI内容营销平台

本机多 Agent 内容营销系统：选题、文章与口播、配音字幕、素材规划、Remotion/FFmpeg 视频、人工审核发布、账号日报、竞对研究和私信线索管理。

## 下载代码

- GitHub：`https://github.com/2738suahduisahgdias/AI-Auto-Content-Marketing-System`
- ZIP：`https://github.com/2738suahduisahgdias/AI-Auto-Content-Marketing-System/archive/refs/heads/main.zip`
- 本地工作台：`http://127.0.0.1:8765/`
- 首次接入向导：`http://127.0.0.1:8765/setup`

代码启动后才能访问本地链接；GitHub 页面不是线上工作台。数据库、Cookie 和账号凭据不会随代码上传。

## 核心依赖

- Python 3.9+
- Node.js 与 npm（建议 Node.js 20 LTS 或兼容版本）
- FFmpeg / FFprobe，并加入 PATH
- Google Chrome：真实采集、扫码和发布使用本机浏览器
- Git（仅克隆代码需要）

Kimi CLI、WhisperX、OpenVoice 是可选 AI 能力，不会在安装脚本中静默下载大型模型或复制账号凭据。

## macOS 快速启动

```bash
git clone https://github.com/2738suahduisahgdias/AI-Auto-Content-Marketing-System.git
cd AI-Auto-Content-Marketing-System
bash scripts/setup.sh
bash scripts/start.sh
```

只做核心命令检查：

```bash
bash scripts/setup.sh --check
```

## Windows 快速启动

使用 PowerShell：

```powershell
git clone https://github.com/2738suahduisahgdias/AI-Auto-Content-Marketing-System.git
cd AI-Auto-Content-Marketing-System
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
powershell -ExecutionPolicy Bypass -File scripts/start.ps1
```

只做核心命令检查：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1 -Check
```

安装脚本会创建 `.venv-topics` 隔离采集环境、安装 `requirements-topics.txt`、执行两个前端项目的 `npm ci`、构建工作台并初始化脱敏 seed。启动脚本会打开接入向导。

## 首次登录平台

1. 打开 `http://127.0.0.1:8765/setup`，先完成依赖检查。
2. 逐个点击抖音、小红书、视频号或公众号的登录入口。
3. 在打开的窗口中由本人完成扫码、短信和二次验证。
4. 返回向导重新检查。窗口打开不等于连接成功，状态以真实账号快照或已核验发布证据为准。
5. 在「设置」中按需配置 Agent；基础工作台不依赖 OpenVoice 等可选模型。

## 技术结构

- Python 3.9 标准库 HTTP 服务 + SQLite
- React + TypeScript + Vite 工作台
- Remotion + FFmpeg 视频生产
- 隔离 Playwright/RapidOCR 采集环境
- 可选 Kimi CLI、macOS say、OpenVoice、faster-whisper

这些本地模型、虚拟环境和账号数据不纳入 Git。未配置的能力显示“未配置/未测试”，不会冒充已连接。

## 测试

```bash
python3 -m unittest discover -s tests -v
cd webapp && npm test && npm run build && npm run lint
cd ../remotion-app && npm run lint
bash scripts/setup.sh --check
```

Windows 使用 `scripts/setup.ps1 -Check`。测试使用临时数据库和短视频；真实平台发布、长期指标和供应商付费能力需要另外验收。

## 常见问题

- **提示找不到 Python/Node/FFmpeg**：安装后重新打开终端，确认命令已加入 PATH，再运行检查脚本。
- **找不到 Chrome**：安装 Google Chrome；平台登录和采集不能仅靠下载代码完成。
- **页面没有最新功能**：在 `webapp` 执行 `npm run build`，再重启 `app.py`。
- **8765 端口被占用**：停止旧服务，或执行 `python3 app.py --port 8766` 并访问对应端口。
- **登录窗口已完成扫码但状态未更新**：回到接入向导重新检查；仍需以真实同步或发布核验为准。

## 数据边界

`data/` 中的数据库、媒体、备份、浏览器资料和账号快照默认不上传；`data/seed.example.json` 是不含真实账号内容的初始化示例。旧文件式 YAML 仅作历史参考，运行以 `app.py` 和当前数据库为准。
