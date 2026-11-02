# 映序 Mac 本地分发

这个包直接运行原 app.py、content_workbench 和已迁移映序的 React 页面。没有第二套业务系统，也不含用户数据库、平台登录、模型密钥或授权签发私钥。

## 使用

1. 打开 DMG，将「映序工作台.app」复制到 Applications。
2. 首次启动选择一个新的空工作区文件夹，建议放外置硬盘。选择已恢复的工作区目录可继续原项目。
3. 应用准备本地 Remotion 运行目录后打开 localhost 页面；在原授权页获取申请码并完成离线激活。
4. 后续打开默认复用上次工作区。切换请到设置 → 本地媒体 → 项目备份与换电脑 → 切换到已有工作区，选择恢复后的完整目录。外置硬盘断开时不自动在系统盘另建工作区。
5. 模型 CLI 登录、平台登录和可选 WhisperX/OpenVoice 环境继续通过原设置页配置。安装包自带 Python/Pillow、Node、FFmpeg、FFprobe、OpenSSL 和 Remotion/Headless Chrome；不包含模型账户。

原数据、缓存、运行目录、日志、临时文件都写入所选工作区；用户 Library 下仅保存所选路径。公开发布不在后台自动执行，最终由用户在平台审核并点击。

## 工作区迁移

设置 → 本地媒体 → 项目备份与换电脑：导出完整工作区到新的文件夹，再把文件夹复制到目标电脑。恢复会校验全部指纹，只写入不存在的新目录，不覆盖现有库。外部引用素材随包携带，恢复后改为受管理的本地副本，原任务和素材 ID 保留。缺失素材会阻止完整导出，需要先重新定位。

恢复后需重新激活、登录平台、配置模型连接。旧未完成作业保留历史但标记取消，需要人工检查后重试，避免换电脑自动重复调用。缓存与代理不打包，按需要重建。迁移包只在本地存储，包含业务内容，按普通项目备份自行保管。

## 构建与验收

构建机需安装 Xcode Command Line Tools（用于编译原生启动器），并在目标架构 Mac 的隔离 Python 环境安装 PyInstaller 6 和 Pillow；客户运行不需要安装这些构建工具。构建前运行前端测试、TypeScript 和 Vite（输出 webapp/dist）。

```
python desktop/build.py --output /Volumes/EXTERNAL_USB/builds/mac --public-keys /path/public-keys.json
/path/映序工作台.app/Contents/MacOS/launcher --root /path/new-test-workspace --port 0 --no-browser --smoke-test
```

不向包里放签发私钥。公钥通过现有 configure-license.py 验证后使用。构建应分别在 Intel 和 Apple Silicon 上进行；一个架构的本机测试不代表另一个架构已通过。

当前脚本做 ad-hoc 本机签名，不冒充 Developer ID 正式公证版本。正式外部分发还需要经营者的 Apple Developer ID 签名及公证，不能让客户关闭 Gatekeeper 来替代。

依据：[PyInstaller 打包说明](https://pyinstaller.org/en/stable/operating-mode.html)、[Apple Mac 分发签名](https://developer.apple.com/documentation/xcode/creating-distribution-signed-code-for-the-mac/)。

`--assemble-only` 仅供复用已构建 Python 引擎、调整启动器或 Remotion 资源时使用；修改 app.py、entry.py 或 Python 模块后必须执行完整构建。

## 客户本地模型环境

设置 → 本地媒体 → 本地模型环境位置，可选择字幕 Python、音色 Python 和 OpenVoice 模型目录。路径保存在客户工作区 config/media-tools.json。默认路径为 tools/whisper/bin/python、tools/openvoice/bin/python、tools/OpenVoice。保存位置只检查文件路径，不代表生成能力通过；必须运行对应真实测试。当前没有一键安装全部模型的能力，未安装时使用上传录音、上传 SRT 和系统音色。新电脑需要重新选择本机环境，不能直接继承另一台电脑的绝对路径。

当前 0.1.3 为 Intel Mac 本地测试包，未经过 Developer ID 签名公证；不得当作已完成干净客户机器验收的发行包。
