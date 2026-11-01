# 全自动AI内容营销平台

本机多 Agent 内容营销系统：选题、文章与口播、配音字幕、素材规划、Remotion/FFmpeg 视频、人工审核发布、账号日报、竞对研究和私信线索管理。

## 下载代码

- GitHub：`https://github.com/2738suahduisahgdias/AI-Auto-Content-Marketing-System`
- ZIP：`https://github.com/2738suahduisahgdias/AI-Auto-Content-Marketing-System/archive/refs/heads/main.zip`
- 本地工作台：`http://127.0.0.1:8765/`
- 首次接入向导：`http://127.0.0.1:8765/setup`

代码启动后才能访问本地链接；GitHub 页面不是线上工作台。数据库、Cookie 和账号凭据不会随代码上传。

前端 HTML、CSS、JavaScript 和编译后的静态资源已经一并提交到 `web/react-dist/`。ZIP 下载包包含完整界面，启动 `app.py` 后即可查看，不要求先执行前端构建。

## 安装前准备：网络与账号

1. **准备可访问 GitHub 的网络环境**。如果你所在网络无法直接打开 GitHub，请先准备合规、稳定的访问环境（也常被称为“翻墙环境”），并确认能打开仓库和下载 ZIP。不要在工作台里配置或共享个人代理账号。
2. **准备注册邮箱**。没有邮箱时可先注册 Gmail；Gmail 或其他可接收验证邮件的邮箱都能注册 GitHub，GitHub 不强制要求谷歌邮箱。
3. **注册或登录 GitHub**。打开 `https://github.com/signup` 按提示完成注册；已有账号直接登录。仅下载公开 ZIP 不强制要求 GitHub 账号，克隆代码和后续协作建议使用账号。
4. 完成上述准备后，再按下面的 macOS 或 Windows 步骤安装。

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

## 浏览器桥接服务（平台采集与微信发布必装）

基础文章和本地视频页面可以先启动，但复用已登录 Chrome 的账号采集、视频号和公众号发布还需要 **Kimi WebBridge 本机服务 + Chrome 扩展**。它不包含在项目 ZIP 中，也不会由安装脚本静默安装。

1. 按官方页面安装服务：<https://www.kimi.com/zh-cn/features/webbridge>。
2. 启动服务（已经运行时命令会安全地保持现状）：

   macOS / Linux：
   ```bash
   ~/.kimi-webbridge/bin/kimi-webbridge start
   curl http://127.0.0.1:10086/status
   ```

   Windows PowerShell：
   ```powershell
   & "$env:USERPROFILE\.kimi-webbridge\bin\kimi-webbridge.exe" start
   Invoke-RestMethod http://127.0.0.1:10086/status
   ```

3. 安装并启用 [Chrome Web Store 扩展](https://chromewebstore.google.com/detail/kimi-webbridge/fldmhceldgbpfpkbgopacenieobmligc)。无法访问商店时，可下载[官方扩展 ZIP](https://kimi-web-img.moonshot.cn/webbridge/latest/extension/kimi-webbridge-extension.zip)，解压后在 `chrome://extensions` 开启开发者模式并选择“加载已解压的扩展程序”。
4. 再运行 `bash scripts/setup.sh --check`（Windows：`scripts/setup.ps1 -Check`）。状态中必须同时看到 `running: true` 和 `extension_connected: true`；只启动服务但未连接扩展时，账号功能仍不可用。

服务异常时按官方指引处理。项目脚本不会自动停止、重启或卸载 WebBridge，也不会另开一套浏览器。

## 首次登录平台

1. 打开 `http://127.0.0.1:8765/setup`，先完成依赖检查。
2. 逐个点击抖音、小红书、视频号或公众号的登录入口。
3. 在打开的窗口中由本人完成扫码、短信和二次验证。
4. 返回向导重新检查。窗口打开不等于连接成功，状态以真实账号快照或已核验发布证据为准。
5. 在「设置」中按需配置 Agent；基础工作台不依赖 OpenVoice 等可选模型。

## 四平台每日数据更新

- `accounts.daily` 默认每天 **09:30（Asia/Shanghai）** 执行，先同步账号快照，再运行账号分析 Agent。
- 抖音、小红书、视频号、公众号分别采集；单个平台未登录或页面结构变化，不会覆盖其他平台已取得的快照。
- 未读取到内容时标记为空结果和检查原因，不把空结果写成同步成功；无标签数字只保留原始文本，不猜测指标含义。
- 视频号、公众号需要本人在接入向导完成扫码后，才能进行真实数据采集。

## 技术结构

- Python 3.9 标准库 HTTP 服务 + SQLite
- React + TypeScript + Vite 工作台
- Remotion + FFmpeg 视频生产
- 隔离 Playwright/RapidOCR 采集环境
- 本地社媒数据能力目录与 `/api/social/*` 接口；目录覆盖 167 项，`supported` 与 `adapter_required` 分开标识，不接外部社媒数据 API 或积分计费
- 文本模型 Provider 默认使用本机 Kimi CLI，Codex CLI 作为后续可验收扩展；口播转写使用本地 faster-whisper

这些本地模型、虚拟环境和账号数据不纳入 Git。未配置的能力显示“未配置/未测试”，不会冒充已连接。

## 视频模板工作流

- 项目级 Remotion Skills 位于 `.agents/skills/`；重新安装：`npx skills add remotion-dev/skills --all --yes`。
- `config/video_templates.json` 是模板注册表。`draft` 用于开发和验收，`stable` 才能进入生产，`deprecated` 不再用于新任务；模板以 `id@version` 标识。
- 生产端在视频任务的“成片”步骤选择 1–4 个稳定模板，共享同一音频、SRT 和分镜。模板 Props 受 `allowed_props` 白名单限制，不能通过接口注入 Composition 或代码。
- `render_runs` 保存模板版本、完整 Props、内容输入快照和输出文件。输入 SHA-256 与本地 MP4 均匹配时命中缓存；多模板中单个失败不影响其他成功结果。
- 成片保存在 `renders/<任务ID>/`，文件名包含模板 ID、模式和平台；未传模板的旧请求默认使用 `founder-ip@1.0.0`，上传模式仍由 FFmpeg 处理。

多模板渲染请求示例：

```json
{
  "mode": "remotion",
  "platform": "douyin",
  "template_ids": ["founder-ip@1.0.0", "enterprise-explainer@1.0.0"],
  "template_props": {
    "founder-ip@1.0.0": {
      "appearance": {"accentColor": "#d7f277"}
    }
  }
}
```

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

## 安装协助与联系方式

安装或接入遇到问题，可联系：**刘洋 · `liuyangfjnu`**。请附上操作系统、报错截图和终端错误文本；不要发送账号密码、Cookie、Token 或短信验证码。

## 数据边界

`data/` 中的数据库、媒体、备份、浏览器资料和账号快照默认不上传；`data/seed.example.json` 是不含真实账号内容的初始化示例。旧文件式 YAML 仅作历史参考，运行以 `app.py` 和当前数据库为准。
