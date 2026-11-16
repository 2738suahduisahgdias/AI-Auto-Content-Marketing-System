# 映序 Mac 本地分发

这个包直接运行原 app.py、content_workbench 和 React 页面。没有第二套业务系统，也不含用户数据库、平台登录、模型密钥或授权签发私钥。

## 使用

1. 打开 DMG，将「映序工作台.app」复制到 Applications。
2. 首次启动选择一个新的空工作区文件夹，建议放外置硬盘。选择已恢复的工作区目录可继续原项目。
3. 应用准备本地运行目录后，在 APP 自己的 WebKit 窗口打开工作台。原授权页获取申请码并完成离线激活；在接入向导启动映序专用 Chrome，分别完成平台本人登录。
4. 后续打开默认复用上次工作区。切换请到设置 → 本地媒体 → 项目备份与换电脑 → 切换到已有工作区，选择恢复后的完整目录。外置硬盘断开时不自动在系统盘另建工作区。
5. 文本与视觉模型可选择 Kimi CLI、Codex CLI 或模型 API。每个生成型 Agent 都能在设置 → Agent 配置中独立选择服务和模型；本地媒体引擎不伪装成文本模型。

标准运行不需要客户另装 Python、Node、FFmpeg、Whisper、OCR、Demucs、OpenVoice 或 Playwright。随包提供本地 Python、Node、FFmpeg/FFprobe、OpenSSL 3 及其动态库、Remotion、Whisper small/base、RapidOCR、Demucs、OpenVoice 及所需模型缓存。当前源码的选题、平台登录和发布预填改用映序专用 Chrome，因此 Chrome 是外部运行依赖；其他外部依赖为网络、用户选择的模型 CLI/API 和对应账号。构建会拒绝不支持 Ed25519 的 LibreSSL，并检查随包 OpenSSL 能脱离开发机路径启动。

原数据、缓存、专用 Chrome 资料、运行目录、日志和临时文件都写入所选工作区；用户 Library 下仅保存所选路径。专用 Chrome 默认只监听 `127.0.0.1:9223`，不读取、复制或重启日常 Chrome，首次仍需在专用窗口登录平台。模型 CLI 的登录配置继续从用户原目录读取，不打包进 APP。公开发布不在后台自动执行，最终由用户在平台审核并点击。

## 精简版

精简版 APP 名称为「映序工作台·精简版」，bundle id 为 `com.yingxu.workbench.slim`，可与全量版区分。包内只保留启动器、业务后台、界面、OpenSSL 3 和主服务 Playwright 1.60 驱动；启动路径必须优先包含 `resources/bin`，并在 smoke 中核对实际 OpenSSL 解析结果，不能依赖开发机上的其他版本。媒体 Python、Node、FFmpeg、Remotion、Chromium、Whisper、OpenVoice、Transformers、Torch 与 NLTK 数据全部在首次打开后通过页面下载向导获取。未下载完成的能力明确显示未就绪，不伪造连接成功。

下载按九组展示状态，失败会保存原因并可重试，已经存在的资源不会重复下载。资源写入工作区 `cache/`、`tools/` 和 `runtime/`，不写回已签名 APP。Python 与 Node 固定版本并校验 SHA-256，npm 与 Python 包使用锁定版本。下载完成后再次启动会识别现有文件，不需要重新下载。精简版使用 `--slim` 构建，DMG 文件名带 `-Slim`。

## 工作区迁移

设置 → 本地媒体 → 项目备份与换电脑：导出完整工作区到新的文件夹，再把文件夹复制到目标电脑。恢复会校验全部指纹，只写入不存在的新目录，不覆盖现有库。外部引用素材随包携带，恢复后改为受管理的本地副本，原任务和素材 ID 保留。缺失素材会阻止完整导出，需要先重新定位。

恢复后需重新激活、登录平台、配置模型连接。旧未完成作业保留历史但标记取消，需要人工检查后重试。缓存与代理不打包，按需要重建。迁移包只在本地存储，包含业务内容，按普通项目备份自行保管。

设置 → 本地媒体中的环境路径是高级兼容选项，不是标准运行的前置条件。内置环境优先于开发机路径；只补缺失的模型缓存，不覆盖客户已有缓存或配置。

## 构建与验收

构建机需安装 Xcode Command Line Tools，并在目标架构 Mac 的隔离 Python 环境安装 PyInstaller 6、Pillow 和 Playwright；缺少 Playwright 会导致主服务无法执行浏览器检查，不能只用媒体 Python 中的副本代替。客户运行不需要这些构建工具。构建前运行前端测试、TypeScript 和 Vite（输出 `web/react-dist`）。使用 `uv run --with pyinstaller --with pillow --with 'playwright==1.60.0' python desktop/build.py ...` 可建立正确的隔离构建环境；主服务 Playwright 固定为 1.60.0，对应 Chromium 1223，不能改用未锁定最新版。

统一媒体 Python 必须是可迁移的独立 Python，包含 Whisper、OCR、Demucs、OpenVoice、Playwright 及依赖。模型目录包含 Hugging Face、Transformers、Torch 与 NLTK 缓存。浏览器目录必须同时匹配媒体 Python 的 Playwright 1.48（Chromium 1140）和主服务当前 Playwright（Chromium 1223），不能只复制其中一个版本。

```
python desktop/build.py \
  --output /Volumes/EXTERNAL_USB/builds/mac \
  --public-keys /path/public-keys.json \
  --python-runtime /path/client-python \
  --models-root /path/model-bundle \
  --playwright-browsers /path/playwright-browsers \
  --openvoice-root /path/OpenVoice

/path/映序工作台.app/Contents/MacOS/launcher --root /path/new-test-workspace --port 0 --no-browser --smoke-test
```

`--ui-root /path/isolated-workspace` 用于验收原生 APP 窗口而不修改正式工作区指针。冒烟检查页面、授权配置、Agent 注册表、本地 Python 导入、模型文件以及 Chromium 实际启动。完整验收还需分别检查真实图片、WAV、分轨、字幕、OCR 和视频输出，不能以文件被打包代替运行通过。

`--reuse-runtime` 仅在输入 Python、模型和浏览器未变化时复用上一版资源，仍会重新构建主服务、APP 并校验运行时。`--skip-dmg` 只减少调试期间的 DMG 等待，正式交付前仍需生成并校验 DMG。冷启动媒体导入上限为 600 秒，Chromium 启动上限为 300 秒。

启动器和主服务设置 `PYTHONDONTWRITEBYTECODE=1`，主服务同时设置 `sys.dont_write_bytecode`，避免运行后向已签名 APP 写入 `__pycache__`。构建还会从资源与引擎中排除 `._*` AppleDouble 元数据，防止 FAT/exFAT 工作盘的旁文件进入签名包。桌面服务关闭时同时清理复用的 Whisper worker。签名深检必须放在 smoke、真实媒体和原生窗口运行之后；先验签再运行会漏掉运行期新增文件导致的签名失效。

不向包里放签发私钥。公钥通过现有 configure-license.py 验证后使用。构建应分别在 Intel 和 Apple Silicon 上进行；一个架构的本机测试不代表另一个架构已通过。

当前脚本做 ad-hoc 本机签名，不冒充 Developer ID 正式公证版本。正式外部分发还需要经营者的 Apple Developer ID 签名及公证，不能让客户关闭 Gatekeeper 来替代。

依据：[PyInstaller 打包说明](https://pyinstaller.org/en/stable/operating-mode.html)、[Apple Mac 分发签名](https://developer.apple.com/documentation/xcode/creating-distribution-signed-code-for-the-mac/)。

`--assemble-only` 仅供复用已构建 Python 引擎、调整启动器或 Remotion 资源时使用；修改 app.py、entry.py 或 Python 模块后必须执行完整构建。

## 当前发行边界

- 本次词级进度修复版精简 DMG 位于 `/Volumes/EXTERNAL_USB/kimi/storage/YingxuBuilds/mac-slim-transcript-progress/Yingxu-Mac-x86_64-Slim.dmg`，156,335,776 字节，SHA-256 `ff9f5acfbea9ddf1d4cf6dd2f8876069249cf0a55f0f40a335538ba2f49a5c0e`。只读挂载的原生窗口已真实生成 66 个词/片段；主服务和 worker 均退出，运行后签名深检与镜像校验通过。此为 Intel 测试版，未公证。
- 自包含 Intel APP 位于 `/Volumes/EXTERNAL_USB/kimi/storage/YingxuBuilds/mac-self-contained/映序工作台.app`；全量 DMG 位于 `/Volumes/EXTERNAL_USB/kimi/storage/YingxuBuilds/mac-self-contained/Yingxu-Mac-x86_64.dmg`，6,054,309,077 字节（约 6.05 GB），SHA-256 `9c9dc055d8e521f54e368d1c10dd9ea07560e43a51e03d06f21776c9b5669101`。签名深检和镜像校验 VALID；只读挂载后原生授权页与文件选择框通过。
- 精简版 APP 位于 `/Volumes/EXTERNAL_USB/kimi/storage/YingxuBuilds/mac-slim/映序工作台·精简版.app`；精简 DMG 位于 `/Volumes/EXTERNAL_USB/kimi/storage/YingxuBuilds/mac-slim/Yingxu-Mac-x86_64-Slim.dmg`，153,907,000 字节（约 153.9 MB），SHA-256 `15e7c44cf5a833084ea16cfcd4cd7a450f8fb9d2c68ce69891051d7e8c5843de`。包内含 Kimi CLI 2.5.1 但不含账号凭据。首次打开后按页面提示下载全部九组资源。以上为既有安装包信息；当前源码已改为不复用主 Chrome，而是使用映序专用 Chrome 和工作区固定资料，不再要求重启日常浏览器。此修改尚未重新进入上述 DMG。
- 2026-11-09 已验证：全量引擎 smoke 的本地媒体、Chromium 与 26 个 Agent 均通过；精简 APP 在完整九组资源工作区中 smoke 的本地媒体、Chromium 与 26 个 Agent 均通过。两版均完成独立测试签发、原生选文件、激活、重启保留与错绑拒绝；授权相关 28 项检查通过。历史真实媒体与长视频结果保留，但不替代本构建的 cold smoke。
- 当前构建机为 Intel x86_64、macOS 15.8.1。Apple Silicon 构建、安装版覆盖升级、Developer ID 签名公证和干净客户 Mac 仍需分别验收。
- 正式分发步骤：分别在 Intel 和 Apple Silicon 构建；准备 Developer ID Application 证书；对嵌套运行时和 APP 签名；提交 Apple Notary 并 stapler；在干净 Mac 安装 DMG 后重跑授权、冒烟和真实媒体流程。
