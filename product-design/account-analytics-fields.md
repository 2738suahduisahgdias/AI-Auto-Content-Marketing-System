# 账号日报与竞对分析字段定义

## 1. 数据原则

- 统计时区固定为账号设置的本地时区，默认 `Asia/Shanghai`；“今日”指本地自然日 00:00 至当前时间。
- 今日新增必须来自同一指标前后快照差值；首次采集只有累计值时，不伪造新增量。
- `null` 表示未读取、未接入或不适用，绝不等于 0。汇总时显示实际数据覆盖范围。
- 同一原创内容分发到多个平台，原创内容数只计 1，发布条次按实际已核验的平台发布记录计数。
- 阅读/播放总量是各平台内容消费次数之和，不是跨平台去重人数。
- 自身后台指标与竞对公开指标分层保存。跨账号比较只使用双方同平台、同口径、同观察窗口的数据。

## 2. 通用元数据

| 字段 | 类型 | 含义 |
|---|---|---|
| `platform` | enum | `douyin / wechat_channels / xiaohongshu / wechat_official_account` |
| `account_id` | string | 平台账号标识 |
| `content_id` | string | 系统原创内容标识 |
| `platform_content_id` | string | 平台作品标识 |
| `metric_key` | string | 指标名称 |
| `value` | number/null | 指标值；缺失时为 null |
| `value_kind` | enum | `delta / cumulative / public_snapshot / calculated` |
| `scope` | enum | `account / content / publication` |
| `period_start/end` | datetime | 统计区间 |
| `captured_at` | datetime | 实际采集时间 |
| `observation_window` | enum | `24h / 72h / 7d / lifetime` |
| `source_type` | enum | `platform_raw / system_calculated / ai_inferred / manual_verified / demo` |
| `missing_reason` | string/null | 未读取、无权限、平台未提供、同步失败等 |
| `evidence_url` | string/null | 原始后台或公开内容证据 |

## 3. 生产与传播指标

| 字段 | 公式/定义 |
|---|---|
| `original_content_count` | 周期内去重原创内容数 |
| `publication_count` | 周期内已核验发布条次 |
| `article_count / video_count` | 按内容形式统计的原创内容数 |
| `reach` | 公众号阅读、视频号播放、抖音播放、小红书阅读或观看之和 |
| `likes / comments / shares / favorites` | 各平台原生互动数；平台别名保留在明细层 |
| `profile_visits` | 主页访问次数或人数，按平台原始口径保存 |
| `new_followers / unfollows / net_new_followers` | 新增、取关与净增关注 |

## 4. 内容质量指标

| 字段 | 公式/定义 |
|---|---|
| `avg_watch_seconds` | 总观看时长 ÷ 播放次数 |
| `avg_read_seconds` | 平台提供的平均阅读时长 |
| `avg_completion_rate` | 平均观看时长 ÷ 视频时长 |
| `completion_rate` | 完播人数/次数 ÷ 播放人数/次数，保留平台分子分母口径 |
| `read_completion_rate` | 读完人数 ÷ 阅读人数 |
| `retention_3s / retention_5s` | 观看到 3 秒/5 秒的人数 ÷ 开始播放人数 |
| `retention_curve` | 时间点和对应留存率序列 |
| `replay_rate` | 重复播放次数 ÷ 播放人数 |
| `like_rate` | 点赞 ÷ 阅读/播放 |
| `comment_rate` | 评论 ÷ 阅读/播放 |
| `share_rate` | 分享 ÷ 阅读/播放 |
| `favorite_rate` | 收藏 ÷ 阅读/播放 |
| `engagement_rate` | 点赞、评论、分享、收藏之和 ÷ 阅读/播放 |
| `meaningful_comment_count` | AI 分类出的具体问题、经验或观点评论数，保留原评论证据 |
| `meaningful_comment_rate` | 有效评论 ÷ 总评论 |

不同长度、内容类型和观察窗口不直接比较完播率。平台未提供分母时不计算比率。

## 5. 获客与生产效率

| 字段 | 公式/定义 |
|---|---|
| `inquiries` | 主动私信或表单咨询数 |
| `qualified_leads` | 人工确认符合目标画像且有明确需求的咨询数 |
| `high_intent_leads` | 询问合作、报价、实施周期的高意向线索数 |
| `meetings / deals / revenue` | 深度沟通、成交与成交金额，人工确认 |
| `inquiry_conversion_rate` | 有效咨询 ÷ 阅读/播放，仅用于自身数据 |
| `follow_conversion_rate` | 内容新增关注 ÷ 主页访问量；无内容级归因时只用于账号级 |
| `production_minutes` | 选题到交付的人工与机器耗时 |
| `revision_count` | 人工修改轮次 |
| `cost_per_qualified_lead` | 内容制作投入 ÷ 有效线索数 |

## 6. 竞对公开指标

| 字段 | 公式/边界 |
|---|---|
| `followers_snapshot` | 采集时公开粉丝数 |
| `follower_growth` | 同账号两次公开快照差值 |
| `posting_frequency` | 周期发布数 ÷ 周期天数 |
| `visible_interactions` | 实际可见的点赞、评论、分享、收藏之和；缺项不按 0 补齐 |
| `median_interactions_per_post` | 同组内容可见互动中位数 |
| `interactions_per_1k_followers` | 单篇可见互动 ÷ 当前粉丝快照 × 1000，仅作辅助 |
| `hit_rate` | 超过竞对组同窗口互动 P75 的内容占比 |
| `data_completeness` | `full / partial / limited`，同时展示样本数和缺失字段 |

竞对无公开播放、完播、留存、咨询和成交数据时保持 null，不做推测。跨账号排名优先使用中位数，并按平台、内容类型和 24h/72h/7d 观察窗口分组。

## 7. 同步状态与洞察

同步状态统一为 `succeeded / partial / failed / login_required / not_connected / stale`，记录开始结束时间、内容条数、成功字段、缺失字段、错误动作和最近成功时间。

Agent 输出分 `fact / inference / recommendation`。事实必须引用平台原始或系统计算字段；推断附带样本量和限制；建议应能转化为标题、开头、封面、时长或复测任务。样本不足时输出“不足以形成稳定结论”。

## 8. 正式页面当前映射

- 默认 `/accounts` 与 `/competitors` 只读取 `/api/accounts/bootstrap` 的真实聚合结果；`?demo=1` 才进入独立前端演示数据。
- 原创内容和发布条次来自 `publish_targets.status='published'` 的已核验记录，预览、失败和待核对记录不进入统计。
- 账号及公开作品指标来自 `account_daily_snapshots`，当前按累计快照展示；没有同指标前后值时不生成今日新增或传播趋势。
- 发布趋势只代表生产数量，不命名为播放趋势。
- 竞对内容来自 `wb_research_items` 的 `competitor / high_praise` 来源；公开可见字段为空时保持 null。
- 私信详情、有效/高意向/深度沟通/成交状态与成交金额来自本地 `account_leads` 人工记录；原文默认收起，阶段更新使用 `expected_updated_at` 防止覆盖，不回写外部平台。
- 完播和留存尚无真实数据源，因此正式页面只显示接入状态，不使用演示数值。
