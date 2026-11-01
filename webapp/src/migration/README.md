# 映序迁入刘量原系统

运行入口：main.tsx → 原 AppProvider/App → YingxuVideoWorkspace → BoundYingxu（整个视频任务页）。

这里没有独立项目数据模型：文案、分镜与场景保存在原 tasks.source_json.yingxu，文件用原 files，版本用原 stage_revisions，交付用原 source_json.yingxu_handoff。

`yingxu-runtime.js` 来源为映序 v13 原代码，适配作用域、生命周期、文件上传、保存、原后台跳转和发布交付边界。原始文件及校验值在 public/yingxu-original。

`render_yingxu` 是原 Remotion 渲染器的输入输出适配，不是新的视频引擎。它使用原 TalkingHead/场景/字幕组件与 scripts/render.mjs；未接入视频模型的镜头必须先上传真实素材。

旧独立 Demo 已归档到 product-design/archive/rejected-standalone-demo，不可恢复成新入口。
