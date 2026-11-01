# 自动代理、项目迁移与 Mac 本地包验收

## 继承边界

开发分支 `codex/yingxu-mac-local-workbench`。复用原 app.py、content_workbench、files/wb_assets、文章版本、映序制作快照及审核/发布流程。前端入口继续为原 React 工作台，未重造系统、未修改原生产代码或业务数据库、未合并主分支。仅重启了隔离 demo API 8876 以加载新接口；重启前无执行中作业，待处理 topics.sync 不在该 worker 的允许列表内。

## 本轮实现

- 自动代理：视频播放器及单镜预览使用本地 H.264/AAC 代理，最长边 720 像素。沿用原缓存限额和跨进程锁，指纹去重、重定位复用、坏缓存重建；失败或空间不足回退原片。最终渲染和下载使用原片，代理不会成为交付源。
- 项目迁移：设置 → 本地媒体新增完整工作区导出和恢复。SQLite 一致性快照、外部引用随包复制、SHA256 校验、路径重映射，保留原任务/素材/文章版本 ID。恢复只创建新目录，原工作区不覆盖。迁移包为文件夹，方便大文件分块复制，不在内存中压缩整包。
- Mac 包：原后端与前端随原生启动器分发。内置 Python/Pillow、Node、FFmpeg/FFprobe、OpenSSL、Remotion、Headless Chrome。工作区由客户选择，支持外置盘；依赖只读复用应用内版本，渲染缓存、配置、素材与日志在工作区。离线授权仍必需，公钥随包，私钥/激活状态/客户数据库/模型账户不随包。
- 抽帧复查修复了原映序转接遗漏的媒体镜头类型：有素材的分镜明确传入 `type=media`，避免时长正确却显示代码模板。代理和正式出片均增加实际画面校验。
- 包内首次模板加载在外接盘压力下超过默认 28 秒，已将 selectComposition/renderMedia 的等待上限改为 120 秒；失败仍报错，不注册假成片。

## 已完成验证

| 项目 | 结果 |
|---|---|
| 全后端 | 250 项：249 通过，1 项因历史样本缺失跳过 |
| 全前端 | 35 个文件、64 项通过；使用单 worker 避免外接盘争用导致 worker 启动超时 |
| 静态检查 | TypeScript、Vite 隔离构建、render.mjs 语法及 git diff --check 通过 |
| 代理与迁移专项 | 5 项真实 FFmpeg 测试通过，覆盖音轨/时长、重定位复用、损坏重建、容量回退、原片下载、文章视频版本保留、坏包/越界拒绝 |
| 媒体修复回归 | 代理/迁移 5 项、录音时间线 12 项通过；原流程真实媒体预览出片通过 |
| 源码真实渲染 | 媒体类型修复后，原渲染流程的实拍单镜已真实出片；完整画面验收以下面的最终包内结果为准 |
| 冻结引擎启动 | 新工作区与迁移后工作区启动通过；原页面、离线授权状态及映序静态图片返回正常；4 个内置可执行依赖通过运行验证 |
| 包内真实渲染 | PATH 仅包内 bin + /usr/bin + /bin，代理单镜 2.005 秒、原片成片 4.011 秒；未使用开发目录的 Node/FFmpeg；代理/成片抽帧的测试色块面积分别为 72.52% / 72.55%，确认实拍可见 |
| 包内文章功能 | 打包 Python/Pillow 调用原 page_worker.py，成功生成 4 页 1080×1440 PNG |
| Chrome 交互 | 原设置页迁移包恢复成功，显示“现有工作区未覆盖”；恢复目标为独立合成验收目录，现有业务库未切换 |

第一轮前端并发运行出现 worker 启动超时，已以单 worker 全量重跑通过；第一轮包内模板加载超时已修正并重新真实出片通过。旧失败日志保留，不把它们算作成功。

## 证据位置

外接盘 `/Volumes/EXTERNAL_USB/映序开发/2026-11-01/acceptance/proxy-migration/`：

- `result.json`：早期源码时长与迁移结果，不作为实拍画面正确的证据。
- `installed-result.json`：包内依赖路径、代理和正式成片的时长与来源。
- `installed-proxy.mp4`、`installed-final.mp4`：包内真实产物。
- `portable.yingxu-project/`、`restored/`：测试迁移包与恢复目录。

`acceptance/mac-final-run/article-pages/` 保存 4 页 PNG 和 pages.json；`acceptance/ui-restored-workspace/` 为 Chrome 恢复结果。以上输入均为本地合成夹具，没有客户资料、付费模型调用或公开发布。

## 范围限制

- 这是 Intel Mac 本机验收。没有 Apple Silicon 实机结果，也没有 Developer ID 正式签名/公证；不能把本机测试包称为客户正式发行包。
- 首次冷启动在当前外接盘上明显慢于热启动；安装到客户机器后的首次体验和长时高分辨率大视频压力验收仍需独立验证。
- 代理首次生成同步等待，目前没有后台代理队列进度条。新机器须重新激活、登录平台及配置模型；恢复的未完成作业取消并保留历史，需要手动检查后重试。
- 可选 WhisperX/OpenVoice、模型 CLI 和平台登录仍走原设置页；本轮不证明这些外部能力全部完成。
- 不要求用户关闭 Gatekeeper，不绕过平台或系统安全保护；最终平台发布仍由人审核点击。

最终回归日志保存于外接盘 `acceptance/desktop-evidence/`，包内视频的可见媒体验收记录在 `installed-result.json`。

## 最终桌面入口复验（2026-11-02 凌晨）

- 原生 `.app` 经 `codesign --verify --deep --strict` 验证，通过磁盘完整性和指定要求检查。仍是 ad-hoc 本机签名，不是 Developer ID 公证。
- 最终入口在新工作区启动成功，原页面、映序图片和离线授权接口正常，授权状态为 unactivated；没有放宽授权检查。
- `tests/test_desktop_entry.py` 新增 1 项通过：挂载目录即使存在，只要外置盘并未实际挂载，就在创建目录之前拒绝启动，避免写入系统盘替代位置。
- 本机 `security find-identity -v -p codesigning` 返回 0 个有效身份，尚不具备正式 Developer ID 签名条件。未修改 Gatekeeper 或其他系统安全设置。

## 最终安装包

- 文件：`/Volumes/EXTERNAL_USB/映序开发/2026-11-01/builds/mac-0.1.0/Yingxu-Mac-x86_64.dmg`
- 大小：363638151 字节（约 346.8 MiB）。
- SHA256：`ce3679da3666e95e69e802faefe0a382e4738ed5a690a42106c50d208390618e`。
- 最终版本已通过严格应用签名校验、原生启动和 `hdiutil verify` 镜像校验。离线授权保持启用。
- 配套 `acceptance.json`、`SHA256SUMS.txt` 位于同一构建目录。这个 Intel 本机测试包未做 Developer ID 公证，不作为 Apple Silicon 或所有客户设备已验证的结论。
