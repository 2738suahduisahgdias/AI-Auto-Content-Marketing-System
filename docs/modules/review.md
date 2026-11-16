# 视频审核与交付

更新：2026-11-05。状态：已验证，除特别注明外。

## 功能与入口

`/demo/review` 读取映序交付、上传文件或本地文件夹。机器预审提供媒体证据，人工决定 approved/rejected；原文件不因预审而改变。

## 代码与数据

- 页面：`webapp/src/pages/Review.tsx`。
- 服务：`content_workbench/review/service.py`、`executors.py`、`media_review.py`。
- 交付绑定：`delivery.py` 的 `receive_delivery`、`assert_delivery`、`record_delivery_decision`。
- `review_batches`、`review_items` 保存批次、状态、决定、报告和输出路径。
- `review_deliveries` 保存 `content_id + file_id + revision + source_sha256` 与审核项的对应关系，审批后还记录 `output_sha256`。

## 真实依赖与风险

- `receive_delivery` 要求当前映序 handoff 未过期且源文件哈希一致。
- `source_for_publish` 只接受人工 approved 且有输出文件的审核项，并再次检查交付和输出哈希。
- 制作修改、文件替换或重新交付可能使旧审核失效；不得只修改页面状态绕过这些检查。
- OCR、黑帧、静音、尺寸和编码检查都有边界，机器通过也不等于人工质检或品牌审核完成。

## 检查方法

- 自动：`test_review.py`、`test_yingxu_delivery.py`、`test_media_review.py`。
- 只读人工：打开审核页，核对任务标题、文件编号、制作 revision、人工决定、实际输出路径和 ffprobe。
- 跨模块：从审核项追踪到发布 `source_id`；不能从旧 `tasks.state` 推断新审核状态。
- 数据保护：不运行预审、转码或批准操作，仅查询现有记录和文件。

## 真实案例

`reviewitem_1db92b2b48ed43669083` 关联 `20261103-001`、文件 #20、制作 revision 36，决定和状态均为 approved，输出为实际 MP4。发布仍需独立检查平台字段和证据，详见 `../CASES.md`。

## 2026-11-06 工具补验

- Playwright 1.48.0 已启动真实 Chromium，RapidOCR 1.4.4 已识别文章图片中文；真实视频技术预审的 OCR 字幕边界检查通过。
- Kimi 风险分析已返回结果，但只依据技术报告辅助判断，不能证明事实、版权和隐私全部安全；人工通过与驳回仍是独立步骤。
- OpenVoice 独立输出 `../acceptance/video-projects/openvoice-kimi-test.wav`：5.270930 秒、PCM s16le、22050Hz 单声道、232,492 字节，应用内自测为“已连接”。
