# 微信本地可靠入库

此目录是现有 OpenClaw 的扩展，不替换原客户端、微信账号或内容数据库。

原问题：Agent 可以直接回答“已保存到待分类”，不调用入库工具。`before_dispatch` 现在先调用原桥接，再根据真实回执生成答复，不依赖模型决定是否保存。

边界：只处理 `openclaw-weixin`、既有 `CONTENT_AGENT_WECHAT_SENDER_ID` 对应的私聊；其他发送者和群聊不处理。不执行消息内容，不访问消息链接，不公开发布。缺失平台消息 ID、桥接超时、响应格式错误均不得回复保存成功。消息 ID 使用 `openclaw-weixin:<平台原始ID>`，由原后台去重。

通过官方 `openclaw plugins install --link <本目录> --force` 接入，需启用该插件的 `hooks.allowConversationAccess`。原凭据环境变量和工作区指针继续沿用。安装需在实际 Gateway 状态目录执行，保留配置备份；插件热重载失败时通过原监护程序重启，不重复启动实例。

测试：`node --test integrations/openclaw-wechat-inbox/handler.test.mjs`。

2026-11-02：真实第二条验收消息原先仅有模型回复，没有工具调用。已从原会话提取平台原始 ID 与原文，经过本处理器补投两次；新后台只有一个待分类消息及关联内容项。此为恢复与去重验证，不能代替下一条实时微信入站验收。
