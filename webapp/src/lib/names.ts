export const platformNames: Record<string, string> = { douyin: "抖音", wechat_channels: "视频号", xiaohongshu: "小红书", wechat_official_account: "公众号" };
export const pillarNames: Record<string, string> = { enterprise_ai: "企业 AI", ai_learning: "AI 学习", ai_marketing: "AI 获客", personal_thinking: "个人思考" };
export const audienceNames: Record<string, string> = { business_owners: "企业主", practitioners: "AI 从业者", fde: "FDE" };
export const stateNames: Record<string, string> = { idea: "待确认选题", topic_approved: "编辑脚本", script_drafted: "脚本待确认", script_approved: "上传录音字幕", waiting_audio: "确认录音字幕", transcribed: "规划素材", assets_planned: "素材授权待确认", assets_approved: "上传成片", rendered: "成片待质检", quality_checked: "质检完成", review_required: "等待人工审核", approved: "等待发布", published: "等待复盘", analyzed: "已复盘" };
export const articleStateNames: Record<string, string> = { brief_ready: "需求待完善", outline_draft: "大纲已保存", draft: "正文待审核", needs_review: "待补齐内容", in_review: "人工审核中", approved: "正文已批准", exported: "已导出", published: "已记录发布" };
export const publishStatusNames: Record<string, string> = { draft: "待预览", preparing: "预览执行中", ready: "待确认", publishing: "发布执行中", published: "已发布", failed: "失败", unknown_remote: "待人工核对" };
export const jobStatusNames: Record<string, string> = { queued: "排队中", leased: "已领取", running: "执行中", retry_wait: "等待重试", succeeded: "已完成", failed: "失败", cancelled: "已取消", unknown_remote: "待人工核对" };
export const metricLabels: Record<string, string> = { followers: "粉丝", following: "正在关注", total_likes: "累计获赞", works_count: "作品数", views: "播放 / 观看", likes: "点赞", comments: "评论", shares: "分享", favorites: "收藏", new_followers: "新增关注", readers: "阅读", profile_visits: "主页访问" };
export const scriptNames: Record<string, string> = { master: "母稿", douyin: "抖音版", wechat_channels: "视频号版", xiaohongshu: "小红书版", wechat_official_account: "公众号文章版" };
export function stageFor(task: { state: string }) {
  return ({ topic_approved: 1, script_drafted: 1, script_approved: 2, waiting_audio: 2, transcribed: 3, assets_planned: 3, assets_approved: 4, rendered: 5, quality_checked: 5, review_required: 6, approved: 7, published: 8, analyzed: 8 } as Record<string, number>)[task.state] ?? 0;
}

export const videoGroups = ["文本", "录音", "成片"];
export const videoGroupOwners = ["选题Agent · 脚本Agent", "用户 · 字幕自动生成", "素材 · 视频构建 · 质检发布"];
const stageToGroup = [0, 0, 1, 2, 2, 2, 2, 2, 2];
export const groupStages: number[][] = [[0, 1], [2], [3, 4, 5, 6, 7, 8]];
export function groupFor(task: { state: string }) {
  return stageToGroup[stageFor(task)] ?? 0;
}

export function nextStepFor(task: { state: string; content_id: string }, jobs: { aggregate_id: string; status: string; progress?: number; stage?: string }[]) {
  const active = jobs.find(job => job.aggregate_id === task.content_id && ["queued", "leased", "running", "retry_wait", "cancel_requested"].includes(job.status));
  if (active) return `自动生产中 · ${active.stage || "处理中"} ${Math.round((active.progress || 0) * 100)}%`;
  const failed = jobs.find(job => job.aggregate_id === task.content_id && ["failed", "cancelled"].includes(job.status));
  if (failed && ["assets_approved", "rendered"].includes(task.state)) return "生产失败 · 查看原因并重试";
  return stateNames[task.state] || task.state;
}

export function taskAttention(task: { state: string; content_id: string }, jobs: { aggregate_id: string; status: string }[]) {
  const failed = jobs.some(job => job.aggregate_id === task.content_id && job.status === "failed");
  if (failed) return 0;
  return ({ review_required: 1, quality_checked: 2, rendered: 2, waiting_audio: 3, script_drafted: 3, assets_planned: 3, approved: 4, published: 5, analyzed: 6 } as Record<string, number>)[task.state] ?? 3;
}
