# 刘量内容营销工作台

本机多 Agent 内容生产系统：选题、文章与口播、配音字幕、素材规划、Remotion/FFmpeg 视频、人工发布记录与数据复盘。

## 技术结构

- Python 3.9 标准库 HTTP 服务 + SQLite
- 原生 HTML/CSS/JavaScript
- Remotion + React + TypeScript
- Kimi CLI、macOS say、OpenVoice、faster-whisper、FFmpeg/FFprobe
- `product-design/` 中的产品 PRD 与独立交互 Demo

## 本地启动

```bash
cp -n data/seed.example.json data/seed.json
python3 app.py --port 8765
```

或双击 `ContentWorkflow.app`。打开 `http://127.0.0.1:8765/`。

```bash
cd remotion-app
npm ci
npx remotion studio --no-open --port=3000
```

## 本地能力依赖

- Kimi CLI：脚本与分镜生成，使用本机已登录 CLI，不复制凭据。
- FFmpeg/FFprobe：媒体探测与合成。
- `.venv-faster-whisper/`：本地字幕与字幕图片环境。
- `vendor/OpenVoice/` 与 `vendor/openvoice-venv/`：本人授权音色克隆。
- macOS `say`：系统语音。

这些本地模型、虚拟环境和账号数据不纳入 Git。未配置的能力应显示“未配置/未测试”，不能当作已连接。

## 测试

```bash
python3 -m unittest discover -s tests -v
node --check web/v2.js
cd remotion-app && npm run lint
```

测试会使用临时数据库和短视频。真实平台发布、长期指标与供应商付费验收需单独进行。

## 数据边界

`data/` 中的数据库、媒体、备份和账号快照默认不上传；`data/seed.example.json` 是不含真实账号内容的初始化示例。旧文件式 YAML 仅作历史参考，运行以 `app.py` 和当前数据库为准。
