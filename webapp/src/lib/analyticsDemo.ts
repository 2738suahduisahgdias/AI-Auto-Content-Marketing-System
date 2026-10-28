export type PlatformKey = "douyin" | "wechat_channels" | "xiaohongshu" | "wechat_official_account";
export type RangeKey = "today" | "yesterday" | "7d" | "30d";
export type WindowKey = "24h" | "72h" | "7d";

export interface PlatformMetrics {
  originals: number;
  publications: number;
  reach: number | null;
  likes: number | null;
  comments: number | null;
  shares: number | null;
  favorites: number | null;
  avgConsumptionSeconds: number | null;
  completionRate: number | null;
  engagementRate: number | null;
  profileVisits: number | null;
  newFollowers: number | null;
  inquiries: number;
  qualifiedLeads: number;
  highIntentLeads: number;
  deals: number;
}

export interface ContentItem {
  id: string;
  platform: PlatformKey;
  title: string;
  kind: "视频" | "文章";
  pillar: string;
  publishedAt: string;
  duration: string;
  metrics: PlatformMetrics;
  windows: Record<WindowKey, { reach: number; interactions: number }>;
  retention: number[];
  comments: string[];
  insight: string;
  suggestion: string;
}

export interface CompetitorAccount {
  id: string;
  name: string;
  platform: PlatformKey;
  group: "企业AI落地" | "AI教学" | "AI营销获客";
  followers: number;
  followerGrowth: number;
  posts30d: number;
  medianInteractions: number;
  hitRate: number;
  completeness: "完整" | "部分" | "有限";
}

export interface CompetitorContent {
  id: string;
  accountId: string;
  title: string;
  publishedAt: string;
  likes: number;
  comments: number;
  shares: number | null;
  favorites: number | null;
  followersSnapshot: number;
  format: string;
  topic: string;
  completeness: "完整" | "部分" | "有限";
  observationWindow: WindowKey;
  insight: string;
}

export const rangeLabels: Record<RangeKey, string> = { today: "今日", yesterday: "昨日", "7d": "近 7 天", "30d": "近 30 天" };
export const windowLabels: Record<WindowKey, string> = { "24h": "24 小时", "72h": "72 小时", "7d": "7 天" };
export const platformOrder: PlatformKey[] = ["douyin", "wechat_channels", "xiaohongshu", "wechat_official_account"];
export const platformLabels: Record<PlatformKey, string> = { douyin: "抖音", wechat_channels: "视频号", xiaohongshu: "小红书", wechat_official_account: "公众号" };

const bases: Record<PlatformKey, PlatformMetrics> = {
  douyin: { originals: 1, publications: 1, reach: 28640, likes: 1268, comments: 96, shares: 214, favorites: 386, avgConsumptionSeconds: 47, completionRate: .318, engagementRate: .0686, profileVisits: 926, newFollowers: 84, inquiries: 12, qualifiedLeads: 5, highIntentLeads: 2, deals: 0 },
  wechat_channels: { originals: 1, publications: 1, reach: 12860, likes: 482, comments: 43, shares: 198, favorites: null, avgConsumptionSeconds: 52, completionRate: .361, engagementRate: .0562, profileVisits: null, newFollowers: 39, inquiries: 8, qualifiedLeads: 4, highIntentLeads: 2, deals: 1 },
  xiaohongshu: { originals: 2, publications: 2, reach: 9320, likes: 516, comments: 61, shares: 84, favorites: 729, avgConsumptionSeconds: 68, completionRate: .427, engagementRate: .149, profileVisits: 648, newFollowers: 57, inquiries: 17, qualifiedLeads: 8, highIntentLeads: 3, deals: 1 },
  wechat_official_account: { originals: 1, publications: 1, reach: 4260, likes: 89, comments: 12, shares: 136, favorites: 104, avgConsumptionSeconds: 126, completionRate: .386, engagementRate: null, profileVisits: null, newFollowers: 21, inquiries: 6, qualifiedLeads: 3, highIntentLeads: 1, deals: 0 },
};

function scaled(base: PlatformMetrics, factor: number): PlatformMetrics {
  const countKeys = new Set<keyof PlatformMetrics>(["originals", "publications", "reach", "likes", "comments", "shares", "favorites", "profileVisits", "newFollowers", "inquiries", "qualifiedLeads", "highIntentLeads", "deals"]);
  return Object.fromEntries(Object.entries(base).map(([key, value]) => [key, value === null ? null : countKeys.has(key as keyof PlatformMetrics) ? Math.round(value * factor) : value])) as unknown as PlatformMetrics;
}

export const platformMetrics: Record<PlatformKey, Record<RangeKey, PlatformMetrics>> = Object.fromEntries(platformOrder.map(platform => [platform, {
  today: bases[platform],
  yesterday: scaled(bases[platform], .84),
  "7d": scaled(bases[platform], 6.2),
  "30d": scaled(bases[platform], 24.6),
}])) as Record<PlatformKey, Record<RangeKey, PlatformMetrics>>;

const baseContent = bases.douyin;
export const contents: ContentItem[] = [
  { id: "own-1", platform: "douyin", title: "企业AI别先买工具：先画一张业务流程图", kind: "视频", pillar: "企业AI落地", publishedAt: "今天 08:40", duration: "02:18", metrics: { ...baseContent, reach: 16280, likes: 782, comments: 58, shares: 146, favorites: 264, completionRate: .386, engagementRate: .0768, qualifiedLeads: 4 }, windows: { "24h": { reach: 16280, interactions: 1250 }, "72h": { reach: 23140, interactions: 1740 }, "7d": { reach: 28420, interactions: 2160 } }, retention: [100, 82, 71, 65, 58, 47, 39, 31], comments: ["我们是 40 人的制造企业，应该先从质检还是报价流程开始？", "能不能按这张流程图出一期模板？"], insight: "3 秒留存和收藏率高于账号近期中位数，流程图模板是主要价值点。", suggestion: "下一条直接用制造业报价流程做案例，并在前 5 秒展示流程图结果。" },
  { id: "own-2", platform: "douyin", title: "普通人用AI做会议纪要的正确姿势", kind: "视频", pillar: "普通人AI教学", publishedAt: "昨天 18:20", duration: "01:46", metrics: { ...baseContent, reach: 12360, likes: 486, comments: 38, shares: 68, favorites: 122, completionRate: .294, qualifiedLeads: 1 }, windows: { "24h": { reach: 12360, interactions: 714 }, "72h": { reach: 15820, interactions: 902 }, "7d": { reach: 17260, interactions: 1040 } }, retention: [100, 74, 61, 54, 49, 40, 30, 24], comments: ["录音涉及客户隐私怎么处理？", "适合用哪款工具？"], insight: "播放量尚可，但中段流失明显，工具步骤铺垫过长。", suggestion: "把隐私处理放在开头，并将操作步骤压缩为三个动作。" },
  { id: "own-3", platform: "wechat_channels", title: "一个真实企业AI项目是怎么验收的", kind: "视频", pillar: "企业AI落地", publishedAt: "今天 09:15", duration: "03:00", metrics: { ...bases.wechat_channels, reach: 12860 }, windows: { "24h": { reach: 12860, interactions: 723 }, "72h": { reach: 16940, interactions: 960 }, "7d": { reach: 19820, interactions: 1130 } }, retention: [100, 86, 77, 72, 65, 58, 46, 38], comments: ["验收指标可以直接套用吗？", "我们也在找能落地的人。"], insight: "分享率高于其他平台内容，真实验收过程具备社交传播价值。", suggestion: "补充一张验收清单，引导有需要的企业主通过私信领取。" },
  { id: "own-4", platform: "xiaohongshu", title: "企业主AI转型清单：30天从试点到验收", kind: "文章", pillar: "企业AI落地", publishedAt: "今天 10:10", duration: "阅读约 4 分钟", metrics: { ...bases.xiaohongshu, reach: 9320 }, windows: { "24h": { reach: 9320, interactions: 1390 }, "72h": { reach: 12680, interactions: 1880 }, "7d": { reach: 14920, interactions: 2180 } }, retention: [100, 88, 81, 76, 69, 62, 51, 43], comments: ["清单有电子版吗？我们准备下个月做试点。", "FDE 在这个流程里负责哪一段？"], insight: "收藏率和有效咨询表现最好，清单型内容匹配企业主的执行需求。", suggestion: "保留清单结构，增加不同规模的三个试点案例，并承接公众号完整版。" },
  { id: "own-5", platform: "wechat_official_account", title: "AI营销获客不是群发：一套可复用的内容工作流", kind: "文章", pillar: "AI营销获客", publishedAt: "今天 11:30", duration: "阅读约 8 分钟", metrics: { ...bases.wechat_official_account }, windows: { "24h": { reach: 4260, interactions: 341 }, "72h": { reach: 5860, interactions: 478 }, "7d": { reach: 6920, interactions: 590 } }, retention: [100, 90, 83, 78, 71, 61, 48, 36], comments: ["想看具体提示词和审核规则。", "我们团队可以按这个流程试一周。"], insight: "阅读完成度稳定，长文更适合承接方法和建立信任。", suggestion: "增加提示词附件，并将其中三个关键步骤拆成短视频。" },
];

export const syncStatuses = [
  { platform: "douyin" as PlatformKey, status: "成功", time: "今天 09:30", detail: "20 条内容快照 · 指标完整" },
  { platform: "wechat_channels" as PlatformKey, status: "需登录", time: "今天 09:28", detail: "历史数据可用 · 今日增量待验证" },
  { platform: "xiaohongshu" as PlatformKey, status: "部分成功", time: "今天 09:31", detail: "18 条笔记 · 分享字段缺失 3 条" },
  { platform: "wechat_official_account" as PlatformKey, status: "待接入", time: "尚未同步", detail: "演示真实接入后的状态展示" },
];

export const competitorAccounts: CompetitorAccount[] = [
  { id: "c1", name: "AI落地研究所", platform: "douyin", group: "企业AI落地", followers: 186000, followerGrowth: 3200, posts30d: 18, medianInteractions: 1420, hitRate: .28, completeness: "完整" },
  { id: "c2", name: "企业数智笔记", platform: "douyin", group: "企业AI落地", followers: 92000, followerGrowth: 860, posts30d: 12, medianInteractions: 760, hitRate: .17, completeness: "部分" },
  { id: "c3", name: "AI实践派", platform: "wechat_channels", group: "AI教学", followers: 68000, followerGrowth: 1200, posts30d: 20, medianInteractions: 690, hitRate: .25, completeness: "部分" },
  { id: "c4", name: "增长先锋社", platform: "wechat_channels", group: "AI营销获客", followers: 45000, followerGrowth: 530, posts30d: 9, medianInteractions: 480, hitRate: .11, completeness: "有限" },
  { id: "c5", name: "FDE观察室", platform: "xiaohongshu", group: "企业AI落地", followers: 53000, followerGrowth: 1900, posts30d: 22, medianInteractions: 1680, hitRate: .32, completeness: "完整" },
  { id: "c6", name: "普通人的AI课", platform: "xiaohongshu", group: "AI教学", followers: 121000, followerGrowth: 2700, posts30d: 26, medianInteractions: 2140, hitRate: .35, completeness: "部分" },
  { id: "c7", name: "智能商业评论", platform: "wechat_official_account", group: "企业AI落地", followers: 76000, followerGrowth: 740, posts30d: 16, medianInteractions: 510, hitRate: .19, completeness: "有限" },
  { id: "c8", name: "AI获客方法论", platform: "wechat_official_account", group: "AI营销获客", followers: 38000, followerGrowth: 460, posts30d: 14, medianInteractions: 390, hitRate: .14, completeness: "部分" },
];

export const competitorContents: CompetitorContent[] = [
  { id: "cc1", accountId: "c1", title: "别再买AI课了，企业落地先看这4个验收点", publishedAt: "昨天 20:10", likes: 2380, comments: 186, shares: 420, favorites: 630, followersSnapshot: 186000, format: "真人口播", topic: "验收方法", completeness: "完整", observationWindow: "24h", insight: "用反常识开头切入采购焦虑，随后给出可执行验收清单。" },
  { id: "cc2", accountId: "c2", title: "一个50人团队的AI转型路线图", publishedAt: "3 天前", likes: 960, comments: 72, shares: null, favorites: 180, followersSnapshot: 92000, format: "图文口播", topic: "转型路线", completeness: "部分", observationWindow: "72h", insight: "明确团队规模，降低用户对方法适用性的判断成本。" },
  { id: "cc3", accountId: "c3", title: "FDE进企业第一周到底做什么", publishedAt: "2 天前", likes: 1120, comments: 164, shares: 205, favorites: null, followersSnapshot: 68000, format: "访谈切片", topic: "FDE实践", completeness: "部分", observationWindow: "72h", insight: "岗位具体问题和真实经历带来高评论讨论。" },
  { id: "cc4", accountId: "c4", title: "AI获客最重要的不是提示词", publishedAt: "5 天前", likes: 620, comments: 45, shares: null, favorites: null, followersSnapshot: 45000, format: "真人口播", topic: "获客认知", completeness: "有限", observationWindow: "7d", insight: "观点鲜明，但公开字段不足，只用于选题研究。" },
  { id: "cc5", accountId: "c5", title: "企业AI试点复盘：我们砍掉了这3个场景", publishedAt: "昨天 12:30", likes: 1980, comments: 142, shares: 138, favorites: 920, followersSnapshot: 53000, format: "清单图文", topic: "试点复盘", completeness: "完整", observationWindow: "24h", insight: "失败经验和具体删减决策带来高收藏。" },
  { id: "cc6", accountId: "c6", title: "普通人AI学习路线：30天只需练这5件事", publishedAt: "4 天前", likes: 3680, comments: 210, shares: 260, favorites: 1840, followersSnapshot: 121000, format: "清单图文", topic: "学习路线", completeness: "部分", observationWindow: "7d", insight: "低门槛、明确周期和清单结构构成长尾收藏。" },
  { id: "cc7", accountId: "c7", title: "AI项目报价背后：企业到底在为什么付费", publishedAt: "2 天前", likes: 310, comments: 48, shares: 96, favorites: null, followersSnapshot: 76000, format: "深度文章", topic: "商业价值", completeness: "有限", observationWindow: "72h", insight: "从工具价格转向业务价值，适合高意向企业主。" },
  { id: "cc8", accountId: "c8", title: "内容获客复盘：100条内容带来的真实线索", publishedAt: "6 天前", likes: 460, comments: 58, shares: 110, favorites: 150, followersSnapshot: 38000, format: "数据复盘", topic: "获客复盘", completeness: "部分", observationWindow: "7d", insight: "真实数量和业务结果增强可信度，适合差异化跟进。" },
];

export const competitorGroups = ["全部", "企业AI落地", "AI教学", "AI营销获客"] as const;
export const myPublicBenchmark = { medianInteractions: 902, postingFrequency: 4.2, interactionsPer1kFollowers: 20.6, hitRate: .25 };

export function visibleInteractions(item: Pick<CompetitorContent, "likes" | "comments" | "shares" | "favorites">) {
  return item.likes + item.comments + (item.shares ?? 0) + (item.favorites ?? 0);
}

export function totalMetrics(range: RangeKey): PlatformMetrics {
  const keys = Object.keys(bases.douyin) as (keyof PlatformMetrics)[];
  return Object.fromEntries(keys.map(key => {
    if (["completionRate", "engagementRate"].includes(key)) {
      const values = platformOrder.map(platform => platformMetrics[platform][range][key]).filter((value): value is number => typeof value === "number");
      return [key, values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null];
    }
    if (key === "avgConsumptionSeconds") {
      const values = platformOrder.map(platform => platformMetrics[platform][range][key]).filter((value): value is number => typeof value === "number");
      return [key, values.length ? Math.round(values.reduce((sum, value) => sum + value, 0) / values.length) : null];
    }
    const values = platformOrder.map(platform => platformMetrics[platform][range][key]);
    return [key, values.some(value => value === null) ? null : (values as number[]).reduce((sum, value) => sum + value, 0)];
  })) as unknown as PlatformMetrics;
}

export const overviewReachTrend = {
  labels: ["10/15", "10/16", "10/17", "10/18", "10/19", "10/20", "10/21", "10/22", "10/23", "10/24", "10/25", "10/26", "10/27", "10/28"],
  values: [32100, 34800, 29600, 38200, 41500, 39800, 44600, 42100, 46800, 43900, 48200, 51300, 48900, 55080],
};

export const acquisitionTrend = {
  labels: ["第1周", "第2周", "第3周", "第4周", "第5周", "本周"],
  qualified: [9, 12, 11, 16, 15, 20],
  highIntent: [2, 3, 4, 5, 6, 8],
};

export const platformTrends: Record<PlatformKey, { labels: string[]; reach: number[]; engagement: number[] }> = {
  douyin: { labels: ["10/22", "10/23", "10/24", "10/25", "10/26", "10/27", "10/28"], reach: [18200, 21400, 19800, 23600, 25100, 22900, 28640], engagement: [5.4, 5.8, 5.6, 6.1, 6.4, 6.2, 6.86] },
  wechat_channels: { labels: ["10/22", "10/23", "10/24", "10/25", "10/26", "10/27", "10/28"], reach: [8200, 9100, 8900, 10400, 11200, 10600, 12860], engagement: [4.3, 4.6, 4.5, 4.9, 5.2, 5.1, 5.62] },
  xiaohongshu: { labels: ["10/22", "10/23", "10/24", "10/25", "10/26", "10/27", "10/28"], reach: [5600, 6300, 6100, 7200, 7800, 8100, 9320], engagement: [11.2, 12.1, 11.8, 12.9, 13.4, 14.1, 14.9] },
  wechat_official_account: { labels: ["10/22", "10/23", "10/24", "10/25", "10/26", "10/27", "10/28"], reach: [2900, 3200, 3100, 3500, 3700, 3600, 4260], engagement: [6.2, 6.5, 6.4, 6.9, 7.2, 7.1, 8.0] },
};

export const leadSamples = [
  { id: "lead-1", profile: "制造业 · 40 人", platform: "xiaohongshu" as PlatformKey, need: "希望从报价流程开始试点，下个月有实施计划", level: "高意向", content: "企业主AI转型清单" },
  { id: "lead-2", profile: "企业服务商 · 12 人", platform: "wechat_channels" as PlatformKey, need: "正在评估AI项目交付与验收合作", level: "深度沟通", content: "真实企业AI项目验收" },
  { id: "lead-3", profile: "AI 从业者 · FDE", platform: "douyin" as PlatformKey, need: "希望获得业务流程诊断模板", level: "有效线索", content: "先画一张业务流程图" },
];
