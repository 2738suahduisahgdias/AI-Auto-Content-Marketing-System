const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const state = { data: null, topicsData: null, agentData: null, agentEditorId: "industry_topic_agent", topicView: "industry", topicBusy: false, topicDetail: null, view: "today", taskId: null, account: "douyin", testing: false, generating: false, ttsTesting: false, ttsGenerating: false, transcribing: false, whisperxTesting: false, cloneTesting: false, assetGenerating: false, assetTesting: false, rendering: false, renderTesting: false };
const platformNames = { douyin: "抖音", wechat_channels: "视频号", xiaohongshu: "小红书", wechat_official_account: "公众号" };
const pillarNames = { enterprise_ai: "企业 AI", ai_learning: "AI 学习", ai_marketing: "AI 获客", personal_thinking: "个人思考" };
const audienceNames = { business_owners: "企业主", practitioners: "AI 从业者", fde: "FDE" };
const stateNames = { idea: "待确认选题", topic_approved: "编辑脚本", script_drafted: "脚本待确认", script_approved: "上传录音字幕", waiting_audio: "确认录音字幕", transcribed: "规划素材", assets_planned: "素材授权待确认", assets_approved: "上传成片", rendered: "成片待质检", quality_checked: "质检已完成", review_required: "等待人工审核", approved: "等待发布", published: "等待数据复盘", analyzed: "已复盘" };
const stages = ["选题", "脚本", "录音字幕", "素材授权", "成片", "质检", "人工审核", "发布", "复盘"];
const stageAgents = ["选题Agent", "脚本Agent", "用户", "素材规划Agent", "视频构建Agent", "质检Agent", "用户", "发布复盘Agent", "数据分析Agent"];
const scriptNames = { master: "母稿", douyin: "抖音版", wechat_channels: "视频号版", xiaohongshu: "小红书版", wechat_official_account: "公众号文章版" };
const qualityNames = { subtitles: ["字幕准确", "文字、时间轴与口播一致"], audio: ["声音清晰", "音量正常，无异常噪声或断音"], visual: ["画面完整", "无黑帧、错字、裁切或异常画面"], copyright: ["版权合规", "来源和授权均已复核"], platform: ["平台规格", "画幅、时长、格式满足发布要求"] };
const stageFor = task => ({ topic_approved: 1, script_drafted: 1, script_approved: 2, waiting_audio: 2, transcribed: 3, assets_planned: 3, assets_approved: 4, rendered: 5, quality_checked: 5, review_required: 6, approved: 7, published: 8, analyzed: 8 }[task.state] ?? 0);
const nextNames = { topic_approved: "编辑并保存五个脚本版本", script_drafted: "人工确认脚本", script_approved: "上传录音和 SRT 字幕", waiting_audio: "确认录音与字幕", transcribed: "填写素材清单、来源与授权", assets_planned: "确认素材与授权", assets_approved: "上传真实成片", rendered: "完成五项质检", quality_checked: "提交人工审核", review_required: "观看成片并最终审核", approved: "记录平台发布结果", published: "录入 2h / 1d / 3d / 7d 数据", analyzed: "复盘已完成" };
const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
const fmt = value => value === null || value === undefined || value === "" ? "未读取" : typeof value === "number" ? new Intl.NumberFormat("zh-CN").format(value) : esc(value);
const shortDate = value => value ? esc(String(value).slice(0, 10)) : "未读取";
const selectedTask = () => state.data.tasks.find(task => task.content_id === state.taskId);

async function api(path, options = {}) {
  const method = options.method || "GET";
  if (method !== "GET" && state.topicsData?.csrf_token) {
    options.headers = { "X-CSRF-Token": state.topicsData.csrf_token, "Idempotency-Key": crypto.randomUUID(), ...(options.headers || {}) };
  }
  const response = await fetch(path, options);
  let result;
  try { result = await response.json(); } catch { result = {}; }
  if (!response.ok) {
    const details = typeof result.error === "object" ? result.error : {};
    const error = new Error(details.message || result.error || `请求未完成（HTTP ${response.status}），请检查当前页面后重试`);
    error.code = details.code;
    error.field = details.field || result.field || "workflow";
    error.action = details.action || result.action || "核对当前步骤和输入后重试";
    error.item = details.item || result.item;
    error.status = response.status;
    throw error;
  }
  return result;
}
function notify(message, error = false) {
  const box = $("#notice");
  if (error && message && message.message) {
    const lines = [`错误：${message.message}`];
    if (message.field) lines.push(`位置：${message.field}`);
    if (message.action) lines.push(`怎么改：${message.action}`);
    box.textContent = lines.join("\n");
  } else {
    box.textContent = message;
  }
  box.className = `notice show${error ? " error" : ""}`;
  clearTimeout(notify.timer);
  notify.timer = setTimeout(() => box.className = "notice", error ? 12000 : 3500);
}
async function refreshTopics(render = true) {
  state.topicsData = await api("/api/topics/bootstrap");
  if (render) renderTopics();
  return state.topicsData;
}
async function refreshAgentConfigs(render = true) {
  state.agentData = await api("/api/agents/config");
  if (render) renderSettings();
  return state.agentData;
}
async function refresh(message) {
  state.data = await api("/api/bootstrap");
  try { await refreshTopics(false); } catch (error) { state.topicsData = { load_error: error.message, settings: {}, sources: {}, recommendations: {}, jobs: [] }; }
  try { await refreshAgentConfigs(false); } catch (error) { state.agentData = { agents: {}, configs: {}, load_error: error.message }; }
  if (!state.taskId || !selectedTask()) state.taskId = state.data.tasks[0]?.content_id || null;
  renderAll();
  if (message) notify(message);
}
function renderAll() {
  $("#capabilities").innerHTML = state.data.capabilities.map(item => `<div class="capability"><span>${esc(item.name)}</span><b>${esc(item.status)}</b></div>`).join("");
  renderToday(); renderTopics(); renderTasks(); renderAccounts(); renderSettings();
}
function switchView(view) {
  state.view = view;
  $$(".view").forEach(el => el.classList.toggle("active", el.id === view));
  $$(".nav-item").forEach(el => el.classList.toggle("active", el.dataset.view === view));
  $("#view-title").textContent = { today: "今天", topics: "选题库", tasks: "任务工作台", accounts: "账号数据", settings: "设置" }[view];
  $("#new-task-top").style.visibility = view === "topics" ? "hidden" : "visible";
}
function openTask(id) {
  state.taskId = id;
  switchView("tasks");
  renderTasks();
}

function renderToday() {
  const tasks = state.data.tasks;
  const active = tasks.filter(task => task.state !== "analyzed");
  const current = active[0];
  const monday = new Date(); const day = monday.getDay() || 7;
  monday.setHours(0, 0, 0, 0); monday.setDate(monday.getDate() - day + 1);
  const published = tasks.filter(task => task.published_at && new Date(task.published_at) >= monday).length;
  const stats = [
    ["本周发布", `${published} / 3–5`, "目标 4 条，不用低质量凑更"],
    ["进行中", active.length, "从脚本到复盘的真实任务"],
    ["待人工审核", tasks.filter(t => t.state === "review_required").length, "最终审核不能由质检替代"],
    ["待复盘", tasks.filter(t => t.state === "published").length, "回收 2h / 1d / 3d / 7d 数据"],
  ];
  $("#today").innerHTML = `
    <div class="grid cols-4">${stats.map(([label, value, hint]) => `<div class="card stat"><span class="label">${label}</span><strong>${value}</strong><small>${hint}</small></div>`).join("")}</div>
    ${current ? `<div class="card hero"><div><span class="eyebrow">今天的唯一下一步</span><h2>${esc(nextNames[current.state])}</h2><p>${esc(current.title)} · ${esc(current.content_id)}</p></div><button class="button" data-open-task="${current.content_id}">继续这条内容 →</button></div>` : `<div class="card hero"><div><span class="eyebrow">今天的唯一下一步</span><h2>从选题库创建今天的第一条内容</h2><p>已导入 5 个有数据依据的候选，也可以手动创建。</p></div><button class="button" data-go-topics>去选择选题 →</button></div>`}
    <div class="section-head"><h2>进行中的任务</h2><p>${active.length} 条 · 每条只推进当前允许的步骤</p></div>
    <div class="task-list">${active.length ? active.map(taskRow).join("") : `<div class="empty"><strong>还没有进行中的任务</strong>选题确认后，任务和目录会自动创建。</div>`}</div>
    ${tasks.some(t => t.state === "analyzed") ? `<div class="section-head"><h2>已完成复盘</h2></div><div class="task-list">${tasks.filter(t => t.state === "analyzed").map(taskRow).join("")}</div>` : ""}`;
}
function taskRow(task) {
  return `<article class="card task-row"><div><h3>${esc(task.title)}</h3><small>${esc(task.content_id)} · ${esc(pillarNames[task.pillar])} / ${esc(audienceNames[task.audience])}</small></div><span class="badge ${task.state === "analyzed" ? "green" : task.state === "review_required" ? "orange" : ""}">${esc(stateNames[task.state])}</span><span class="next-label">${esc(nextNames[task.state])}</span><button class="button small" data-open-task="${task.content_id}">打开任务</button></article>`;
}

const topicViewNames = { industry: "行业热点", hot: "热点选题", featured: "精选选题", competitor: "竞品选题", high_praise: "高赞选题" };
function topicRecommendations(agent) {
  const items = state.topicsData?.recommendations?.[agent] || [];
  if (!items.length) return `<div class="empty"><strong>还没有${agent === "industry" ? "行业" : "抖音"}今日推荐</strong>先同步真实快照，再运行对应选题Agent。</div>`;
  return `<div class="topic-grid">${items.map(item => `<article class="card topic"><div class="topic-meta"><span class="badge green">${esc(pillarNames[item.pillar] || "企业 AI")}</span><span class="badge">${esc(audienceNames[item.audience] || "企业主")}</span></div><h3>${esc(item.title)}</h3><p>${esc(item.reason)}</p><div class="evidence"><p><strong>差异化切入：</strong>${esc(item.angle)}</p>${(item.uncertainties || []).map(value => `<small>待核实：${esc(value)}</small>`).join("")}</div><small>${esc(item.created_at || "")}</small></article>`).join("")}</div>`;
}
function researchCard(item, allowAnalyze = true) {
  const meta = item.metadata || {};
  return `<article class="card hotspot"><div class="hotspot-top">${meta.rank ? `<span class="hotspot-rank">#${meta.rank}</span>` : ""}<strong>${esc(meta.heat || meta.source_name || "快照")}</strong><span class="badge ${item.analysis_status === "succeeded" ? "green" : ""}">${esc(item.analysis_status === "succeeded" ? "已拆解" : "仅快照")}</span></div><h3>${esc(item.title)}</h3><p>${esc(meta.author || meta.published_at || item.collections?.join(" / ") || "页面可见元数据")}</p><small>采集于 ${esc(item.last_seen_at || "未读取")} · 同步不下载视频</small><div class="topic-footer"><a class="button small" href="${esc(item.url)}" target="_blank" rel="noreferrer">原链接观看 ↗</a><button class="button small" data-create-research="${item.id}">创建任务</button>${allowAnalyze ? `<button class="button small" data-analyze-item="${item.id}">下载并拆解</button>` : ""}<button class="button small" data-detail-item="${item.id}">${item.analysis_status === "succeeded" ? "查看拆解" : "详情"}</button></div></article>`;
}
function syncSummary(last) {
  let stats = {}; try { stats = JSON.parse(last.stats_json || "{}"); } catch (_) {}
  const errors = (stats.errors || []).map(item => item.code === "LOGIN_REQUIRED" ? "收藏需要登录" : item.code).filter(Boolean);
  return `热榜 ${stats.hot ?? 0}/20 · 精选 ${stats.featured ?? 0} · 竞品 ${stats.competitor ?? 0} · 高赞 ${stats.high_praise ?? 0} · 未下载媒体${errors.length ? ` · ${[...new Set(errors)].join("、")}` : ""}`;
}
function topicJobBanner() {
  const data = state.topicsData || {};
  const jobs = data.jobs || [];
  const active = jobs.find(job => ["queued", "leased", "running"].includes(job.status));
  const latest = jobs[0];
  const failed = !active && latest && ["failed", "unknown_remote"].includes(latest.status) ? latest : null;
  const last = data.last_sync;
  return `${active ? `<div class="info-banner">后台执行中：${esc(active.kind)} · ${esc(active.stage || active.status)}。你可以离开本页，任务会持久保存。</div>` : ""}${failed ? `<div class="info-banner error-banner">最近任务失败：${esc(failed.error?.code || failed.status)} · ${esc(failed.error?.message || "请检查采集窗口和设置")}</div>` : ""}${last ? `<div class="info-banner">最近快照：${esc(last.status)} · ${esc(last.started_at)} · ${syncSummary(last)}</div>` : `<div class="info-banner">尚未运行新采集。旧热榜只有 5 条历史快照，不能当作今日 Top20。</div>`}`;
}
function researchDetailModal() {
  const item = state.topicDetail;
  if (!item) return "";
  const analyses = item.analyses || [];
  const report = analyses[0]?.report || {};
  return `<div class="research-modal" role="dialog" aria-modal="true"><div class="research-dialog"><div class="section-head"><div><h2>${esc(item.title)}</h2><p><a href="${esc(item.url)}" target="_blank" rel="noreferrer">打开原链接 ↗</a> · 研究与生产授权分开</p></div><button class="button small" data-close-research>关闭</button></div>${!analyses.length ? `<div class="empty"><strong>尚未拆解</strong>点击“下载并拆解”后才读取视频和抽帧，不会在同步时批量下载。</div>` : `<div class="info-banner">${esc(report.ocr_engine || "OCR")} · ${report.frame_count || 0} 帧 · ${report.frames_with_text || 0} 帧有文字。OCR 不等同于口播全文。</div><div class="frame-timeline">${(report.timeline || []).map(frame => `<article class="frame-row"><a href="/api/v2/assets/${frame.asset_id}/content" target="_blank" rel="noreferrer"><img src="/api/v2/assets/${frame.asset_id}/content" alt="视频帧 ${frame.start_ms}"></a><div><strong>${(frame.start_ms / 1000).toFixed(1)}s <span class="badge">置信度 ${esc(frame.confidence)}</span></strong><p>${esc(frame.text || "未识别到清晰文字")}</p></div></article>`).join("")}</div><div class="issues"><strong>拆解边界</strong><ul>${(report.limitations || []).map(value => `<li>${esc(value)}</li>`).join("")}</ul></div>`}</div></div>`;
}
function renderTopics() {
  const data = state.topicsData;
  const { topics, strategy, favorites } = state.data;
  if (!data) { $("#topics").innerHTML = `<div class="empty">正在读取选题研究快照…</div>`; return; }
  if (data.load_error) { $("#topics").innerHTML = `<div class="empty"><strong>选题服务暂不可用</strong>${esc(data.load_error)}<br>其他工作流不受影响。</div>`; return; }
  const settings = data.settings;
  const view = state.topicView;
  const sourceItems = data.sources?.[view] || [];
  const sourceBody = view === "industry" ? `
    <div class="topic-layout"><section><div class="section-head"><div><h2>行业今日推荐</h2><p>独立行业选题Agent · 只分析真实公开资讯</p></div><button class="button primary small" data-topic-recommend="industry">生成今日推荐</button></div>${topicRecommendations("industry")}<div class="section-head"><h2>行业资讯快照</h2><p>${sourceItems.length} 条 · 仅元数据</p></div><div class="hotspot-grid">${sourceItems.slice(0,20).map(item => researchCard(item,false)).join("") || `<div class="empty">尚未同步行业资讯，点击右上方“同步行业热点”。</div>`}</div></section><aside class="card topic-settings"><div class="section-head"><div><h2>行业范围与每日任务</h2><p>保存后按本地时间自动执行，无需终端</p></div></div><div class="field"><label>行业范围 / 搜索关键词</label><input id="industry-scope" value="${esc(settings.industry_scope || "")}"></div><div class="field"><label>行业选题Agent提示词</label><textarea id="industry-prompt" rows="6">${esc(settings.industry_prompt || "")}</textarea></div><div class="field"><label>抖音选题Agent提示词</label><textarea id="douyin-prompt" rows="6">${esc(settings.douyin_prompt || "")}</textarea></div><div class="form-grid"><div class="field"><label>每日时间</label><input id="daily-time" type="time" value="${esc(settings.daily_time || "09:00")}"></div><label class="check"><input id="daily-enabled" type="checkbox" ${settings.daily_enabled ? "checked" : ""}>启用每日任务</label></div><div class="field"><label>精选收藏夹</label><input id="featured-collection" value="${esc(settings.featured_collection || "选题")}"></div><div class="field"><label>竞品收藏夹</label><input id="competitor-collection" value="${esc(settings.competitor_collection || "企业AI落地竞对账号")}"></div><div class="field"><label>高赞收藏夹</label><input id="high-praise-collection" value="${esc(settings.high_praise_collection || "低粉高赞文案")}"></div><button class="button primary" data-save-topic-settings>保存设置与每日任务</button><hr><button class="button" data-sync-industry>同步行业热点</button><button class="button" data-sync-topics>同步抖音快照</button><button class="button" data-topic-login>连接采集窗口</button><p class="muted">专用浏览器首次需要登录。扫码、验证码和二次验证由你完成。</p></aside></div>` : `
    <div class="section-head"><div><h2>${topicViewNames[view]} ${view === "hot" ? `<span class="badge ${data.hot_complete ? "green" : "orange"}">实际 ${data.hot_count} / 20</span>` : `<span class="badge">${sourceItems.length} 条快照</span>`}</h2><p>${view === "hot" ? "公开热榜，抓不全时明确标记，不补造榜单" : `收藏夹「${esc(data.collection_mapping?.[view] || "")}」 · 先看原链接，选择后才下载`}</p></div><div class="button-row">${view === "hot" ? `<button class="button primary small" data-topic-recommend="douyin">抖音今日推荐</button>` : ""}<button class="button small" data-sync-topics>同步快照</button></div></div>${view === "hot" ? `<div class="section-head"><h2>抖音今日推荐</h2><p>独立抖音选题Agent · 热榜 + 三类收藏</p></div>${topicRecommendations("douyin")}` : ""}<div class="hotspot-grid">${sourceItems.map(item => researchCard(item)).join("") || `<div class="empty"><strong>当前来源还没有作品快照</strong>请检查收藏夹名称并同步；不会用收藏数量冒充已抓取作品。</div>`}</div>`;
  $("#topics").innerHTML = `<div class="topic-tabs">${Object.entries(topicViewNames).map(([key,name]) => `<button class="filter-chip ${view === key ? "active" : ""}" data-topic-view="${key}">${name}</button>`).join("")}<span class="filter-spacer"></span><span class="badge ${data.connection?.connection_status === "ready" ? "green" : "orange"}">${esc(data.connection?.connection_status || "未配置")}</span></div><div id="topic-job-banner">${topicJobBanner()}</div>${sourceBody}<details class="card manual-panel"><summary><strong>手动创建选题</strong><span class="muted"> 保留旧版创建方式</span></summary><form id="manual-form"><div class="form-grid"><div class="field"><label for="manual-title">选题标题</label><input id="manual-title" name="title" maxlength="200" required placeholder="这条内容要解决什么真实问题？"></div><div class="field"><label for="manual-pillar">内容支柱</label><select id="manual-pillar" name="pillar">${Object.entries(pillarNames).map(([k,v]) => `<option value="${k}">${v}</option>`).join("")}</select></div><div class="field"><label for="manual-audience">主要人群</label><select id="manual-audience" name="audience">${Object.entries(audienceNames).map(([k,v]) => `<option value="${k}">${v}</option>`).join("")}</select></div></div><div class="form-grid"><div class="field"><label for="manual-pain">核心痛点（可选）</label><input id="manual-pain" name="pain_point" placeholder="用户当前卡在哪里"></div><div class="field" style="grid-column:span 2"><label for="manual-angle">内容切入（可选）</label><input id="manual-angle" name="angle" placeholder="用什么真实场景、证据或步骤来讲"></div></div><div class="field"><label for="manual-collection">来源收藏夹（可选）</label><select id="manual-collection" name="favorite_collection"><option value="">不使用收藏夹分类</option>${favorites.items.filter(item => item.enabled).map(item => `<option value="${esc(item.name)}">${esc(item.name)} · ${esc(item.role)}</option>`).join("")}</select></div><button class="button primary" type="submit">创建任务并进入脚本</button></form></details><details class="card manual-panel"><summary><strong>保留：账号候选选题</strong><span class="muted"> ${topics.length} 个历史候选</span></summary><div class="topic-grid">${topics.map(topic => `<article class="card topic"><div class="topic-meta"><span class="badge green">${esc(pillarNames[topic.pillar])}</span><span class="badge">${esc(audienceNames[topic.audience])}</span></div><h3>${esc(topic.title)}</h3><div class="evidence">${topic.evidence.map(e => `<p>${esc(e.content)}</p><small>来源：${esc(e.source)}</small>`).join("")}</div><p><strong>切入：</strong>${esc(topic.script_angle)}</p><button class="button primary small" data-create-topic="${topic.id}">选此题并创建任务</button></article>`).join("")}</div></details>${researchDetailModal()}`;
}
async function topicAction(path, payload, message) {
  if (state.topicBusy) return;
  state.topicBusy = true;
  try { await api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload || {}) }); notify(message || "任务已加入后台队列"); await refreshTopics(); }
  catch (error) { notify(error, true); }
  finally { state.topicBusy = false; }
}
async function saveTopicSettings() {
  const payload = { industry_scope: $("#industry-scope").value, industry_prompt: $("#industry-prompt").value, douyin_prompt: $("#douyin-prompt").value,
    daily_time: $("#daily-time").value, daily_enabled: $("#daily-enabled").checked,
    featured_collection: $("#featured-collection").value, competitor_collection: $("#competitor-collection").value, high_praise_collection: $("#high-praise-collection").value };
  await topicAction("/api/topics/settings", payload, "行业范围、提示词和每日任务已保存");
}
async function createResearchTask(itemId) {
  try { const task = await api(`/api/topics/items/${itemId}/create-task`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }); state.taskId = task.content_id; await refresh(`已创建 ${task.content_id}，来源快照已保留`); switchView("tasks"); }
  catch (error) { notify(error, true); }
}
async function showResearchItem(itemId) {
  try { state.topicDetail = await api(`/api/topics/items/${itemId}`); renderTopics(); }
  catch (error) { notify(error, true); }
}

function renderTasks() {
  const tasks = state.data.tasks;
  if (!tasks.length) {
    $("#tasks").innerHTML = `<div class="empty"><strong>任务工作台还是空的</strong><button class="button primary" data-go-topics>去选题库创建任务</button></div>`; return;
  }
  const task = selectedTask();
  $("#tasks").innerHTML = `<div class="workspace"><aside class="card task-sidebar"><div class="head"><strong>全部任务</strong><small class="muted"> · ${tasks.length}</small></div>${tasks.map(item => `<button class="task-select ${item.content_id === task.content_id ? "active" : ""}" data-select-task="${item.content_id}"><strong>${esc(item.title)}</strong><small>${esc(item.content_id)} · ${esc(stateNames[item.state])}</small></button>`).join("")}</aside><section class="workbench"><div class="work-title"><div><span class="eyebrow">${esc(pillarNames[task.pillar])} · ${esc(audienceNames[task.audience])}</span><h2>${esc(task.title)}</h2><p>${esc(task.content_id)}${task.angle ? ` · ${esc(task.angle)}` : ""}</p>${task.source?.type === "douyin_hotspot" ? `<p class="source-note">来源：抖音热点 #${task.source.rank}「${esc(task.source.title)}」 · 热度 ${esc(task.source.heat)} · ${esc(task.source.captured_at)} 快照</p>` : ""}${task.source?.type === "douyin_favorite_collection" ? `<p class="source-note">来源：抖音收藏夹「${esc(task.source.name)}」 · ${esc(task.source.usage)}</p>` : ""}</div><span class="badge green">${esc(stateNames[task.state])}</span></div>${renderSteps(task)}<div class="card stage-card">${renderStage(task)}${renderHistory(task)}</div></section></div>`;
  if (stageFor(task) === 2) setTimeout(loadSubtitle, 0);
}
function renderSteps(task) {
  const current = stageFor(task);
  return `<div class="steps">${stages.map((name, index) => `<div class="step ${index < current || task.state === "analyzed" ? "done" : index === current ? "current" : ""}">${index + 1}. ${name}<small>${index === 8 && task.state === "analyzed" ? "发布复盘Agent" : stageAgents[index]}</small></div>`).join("")}</div>`;
}
function stageHead(title, description) {
  const task = selectedTask();
  const agent = task.state === "analyzed" ? "发布复盘Agent" : stageAgents[stageFor(task)];
  const status = agent === "用户" ? "人工确认" : agent === "脚本Agent" && state.data.ai.ready ? "已连接" : agent === "素材规划Agent" && state.data.asset_ai.ready ? "已连接" : agent === "视频构建Agent" && state.data.render_ai.ready ? "已连接" : ["脚本Agent", "素材规划Agent", "视频构建Agent"].includes(agent) ? "未测试" : "未接入";
  return `<div class="stage-head"><div><h3>${title}</h3><p>${description}</p></div><span class="badge ${agent === "用户" ? "orange" : ""}">${agent} · ${status}</span></div>`;
}
function actionBar(hint, buttons) { return `<div class="action-bar"><span class="next-label">${hint}</span><div class="actions">${buttons}</div></div>`; }
function renderStage(task) {
  switch (stageFor(task)) {
    case 1: return renderScripts(task);
    case 2: return renderAudio(task);
    case 3: return renderAssets(task);
    case 4: return renderVideo(task);
    case 5: return renderQuality(task);
    case 6: return renderReview(task);
    case 7: return renderPublish(task);
    case 8: return renderRetro(task);
    default: return "";
  }
}
function renderScripts(task) {
  const ai = state.data.ai;
  return `${stageHead("脚本与平台改编", "编辑母稿、三个短视频版本和公众号文章；生成或保存后仍需人工确认。")}
    ${Object.entries(scriptNames).map(([key, name]) => `<div class="script-editor"><label for="script-${key}">${name}<span>${key === "master" ? "90–180 秒母稿" : key === "wechat_official_account" ? "完整方法，不是逐字转录" : "独立成立的平台版本"}</span></label><textarea id="script-${key}" data-script="${key}" placeholder="在这里粘贴或编辑${name}…" ${state.generating ? "disabled" : ""}>${esc(task.scripts[key])}</textarea></div>`).join("")}
    <div class="info-banner">脚本Agent：<strong>${ai.ready ? "已连接" : "尚未通过真实测试"}</strong>。使用本地 CLI 当前默认模型和共享会员额度；生成成功会覆盖五版草稿，失败保留原稿，均需人工确认。${!ai.ready && ai.last_error ? `<br>最近错误：${esc(ai.last_error)}` : ""}</div>
    ${actionBar("生成可能需要一些时间；五个版本齐全后才能人工确认", `<button class="button" data-generate-scripts ${!ai.ready || state.generating ? "disabled" : ""}>${state.generating ? "脚本Agent正在生成…" : "脚本Agent生成五版草稿"}</button><button class="button" data-save-scripts ${state.generating ? "disabled" : ""}>保存脚本</button>${task.state === "script_drafted" ? `<button class="button primary" data-task-action="approve_script" ${state.generating ? "disabled" : ""}>我已核对，确认脚本</button>` : ""}`)}`;
}
function fileList(task, kind) {
  const files = task.files.filter(file => file.kind === kind);
  return files.length ? `<ul class="file-list">${files.map(file => `<li><span>${esc(file.original_name)}</span><small>${(file.size / 1024).toFixed(1)} KB${file.media_info.duration_seconds ? ` · ${file.media_info.duration_seconds}s` : ""}</small></li>`).join("")}</ul>` : `<p class="muted">尚未上传</p>`;
}
const formatSize = bytes => bytes >= 1048576 ? `${(bytes / 1048576).toFixed(2)} MB` : `${(bytes / 1024).toFixed(1)} KB`;
function audioMediaList(task) {
  const files = task.files.filter(file => file.kind === "audio");
  return files.length ? `<div class="audio-file-list">${files.map(file => `<article class="audio-file"><div class="audio-file-head"><strong>${esc(file.original_name)}</strong><a class="button small" href="${file.download_url}" download>下载</a></div><code>${esc(file.relative_path)}</code><p>${formatSize(file.size)} · 时长 ${file.media_info.duration_seconds ?? "未读取"} 秒</p><audio controls preload="metadata" src="${file.url}">浏览器不支持音频试听</audio></article>`).join("")}</div>` : `<p class="muted">尚未上传或生成录音</p>`;
}
function srtMediaList(task) {
  const files = task.files.filter(file => file.kind === "srt");
  return files.length ? `<div class="srt-file-list">${files.map(file => `<div class="srt-file"><div><strong>${esc(file.original_name)}</strong><code>${esc(file.relative_path)}</code><small>${formatSize(file.size)}</small></div><a class="button small" href="${file.download_url}" download>下载 SRT</a></div>`).join("")}</div>` : "";
}
function subtitleEditor(task) {
  const file = task.files.find(item => item.kind === "srt");
  if (!file) return "";
  return `<section class="subtitle-editor"><div class="section-head"><div><h2>字幕查看与人工校对</h2><p>${esc(file.original_name)} · 仅等待录音字幕确认时可编辑</p></div><button class="button small" data-save-subtitle ${task.state !== "waiting_audio" ? "disabled" : ""}>保存校对</button></div><textarea id="subtitle-text" data-file-id="${file.id}" ${task.state !== "waiting_audio" ? "disabled" : ""}>正在读取字幕…</textarea></section>`;
}
async function loadSubtitle() {
  const task = selectedTask();
  const file = task?.files.find(item => item.kind === "srt");
  const editor = $("#subtitle-text");
  if (!file || !editor) return;
  try {
    const response = await fetch(file.url);
    if (!response.ok) throw new Error("字幕读取失败");
    const text = await response.text();
    if (selectedTask()?.content_id === task.content_id && $("#subtitle-text")) $("#subtitle-text").value = text;
  } catch (error) { if ($("#subtitle-text")) $("#subtitle-text").value = error.message; }
}
function renderAudio(task) {
  const voiceData = state.data.voices;
  const mediaAI = state.data.media_ai;
  const allVoices = [...voiceData.system_voices, ...voiceData.clone_profiles].sort((a,b) => Number(b.id === voiceData.last_used_id) - Number(a.id === voiceData.last_used_id));
  const lastUsed = allVoices.find(voice => voice.id === voiceData.last_used_id);
  const selectedVoice = allVoices[0];
  const selectedReady = selectedVoice?.kind === "clone" ? voiceData.capabilities.clone_ready : voiceData.capabilities.system_ready;
  const hasSrt = task.files.some(file => file.kind === "srt");
  const audioFiles = task.files.filter(file => file.kind === "audio");
  return `${stageHead("录音与字幕", "真人、系统语音或本人克隆；音频与 SRT 分开完成，均可试听、下载和人工校对。")}
    <div class="audio-mode-grid"><section class="upload-box"><span class="eyebrow">方式一</span><h4>真人上传录音</h4><p>WAV / MP3 / M4A / AAC，最大 500MB；通过 FFprobe 检查。</p><input type="file" id="audio-file" accept=".wav,.mp3,.m4a,.aac"><button class="button small" data-upload="audio" data-input="audio-file">上传真人录音</button></section><section class="upload-box"><span class="eyebrow">单独完成</span><h4>上传 SRT 字幕</h4><p>${hasSrt ? "已有字幕文件，可下载、查看或继续校对。" : "当前缺少字幕；可上传或后续使用 WhisperX 生成。"}</p><input type="file" id="srt-file" accept=".srt"><button class="button small" data-upload="srt" data-input="srt-file">上传并检查 SRT</button>${srtMediaList(task)}</section></div>
    <section class="voice-panel"><div class="section-head"><div><h2>WhisperX 自动 SRT</h2><p>本地 CPU 转写当前任务音频；首次可能需要下载模型</p></div><span class="badge ${mediaAI.whisperx.ready ? "green" : "orange"}">${esc(mediaAI.whisperx.status)}</span></div><div class="voice-form-grid"><div class="field"><label for="whisperx-file">源音频</label><select id="whisperx-file">${audioFiles.map(file => `<option value="${file.id}">${esc(file.original_name)}</option>`).join("")}</select></div><div class="field"><label for="whisperx-model">模型</label><select id="whisperx-model"><option value="small">small（默认）</option><option value="base">base</option></select></div></div><button class="button small" data-transcribe ${!mediaAI.whisperx.ready || state.transcribing || !audioFiles.length ? "disabled" : ""}>${state.transcribing ? "正在本地转写…" : "使用 WhisperX 生成 SRT"}</button>${!mediaAI.whisperx.ready ? `<p class="muted">${esc(mediaAI.whisperx.last_error || "安装完成后请先在设置中做真实转写测试")}</p>` : ""}</section>
    <section class="voice-panel"><div class="section-head"><div><h2>方式二：AI 生成录音</h2><p>macOS 系统语音或 OpenVoice 本人克隆，成功后都可试听与下载</p></div><div><span class="badge ${voiceData.capabilities.system_ready ? "green" : "orange"}">系统 ${esc(voiceData.capabilities.system_status)}</span> <span class="badge ${voiceData.capabilities.clone_ready ? "green" : "orange"}">克隆 ${esc(voiceData.capabilities.clone_status)}</span></div></div><div class="voice-form-grid"><div class="field"><label for="tts-script">脚本版本</label><select id="tts-script">${Object.entries(scriptNames).map(([key,name]) => `<option value="${key}">${name}${key === "master" ? "（默认）" : ""}</option>`).join("")}</select></div><div class="field"><label for="tts-voice">系统音色 / 本人克隆</label><select id="tts-voice">${allVoices.map(voice => `<option value="${voice.id}" data-kind="${voice.kind}" ${voice.id === voiceData.last_used_id ? "selected" : ""}>${voice.kind === "clone" ? "本人克隆" : "系统"} · ${esc(voice.name)}</option>`).join("")}</select></div></div><p class="muted">${lastUsed ? `上次使用：${esc(lastUsed.name)} · ${esc(lastUsed.last_used_at)} · 已使用 ${lastUsed.use_count} 次，已优先推荐` : "还没有使用记录；系统和本人克隆共用最近使用推荐"}</p><div class="field"><label for="tts-text">用于 TTS 的文本（可编辑）</label><textarea id="tts-text" class="tts-text">${esc(task.scripts.master || "")}</textarea></div><button class="button primary" id="generate-audio-button" data-generate-audio ${!selectedReady || state.ttsGenerating ? "disabled" : ""}>${state.ttsGenerating ? "正在生成并验证 WAV…" : "生成 AI 录音"}</button></section>
    <section class="voice-panel"><div class="section-head"><div><h2>本人音色记忆库</h2><p>样本独立保存；只有授权样本且 OpenVoice 真实测试成功才可生成</p></div><span class="badge ${voiceData.capabilities.clone_ready ? "green" : "orange"}">${esc(voiceData.capabilities.clone_status)}</span></div><div class="voice-form-grid"><div class="field"><label for="voice-profile-name">档案名</label><input id="voice-profile-name" maxlength="100" placeholder="例如：本人安静环境样本"></div><div class="field"><label for="voice-sample-file">本人语音样本</label><input type="file" id="voice-sample-file" accept=".wav,.mp3,.m4a,.aac"><span class="hint">WAV / MP3 / M4A / AAC，建议 10 秒到 5 分钟</span></div></div><label class="check"><input type="checkbox" id="voice-sample-authorized">我确认这是本人声音，并授权用于音色克隆</label><button class="button small" data-save-voice-sample>保存本人样本</button><div class="clone-list">${voiceData.clone_profiles.length ? voiceData.clone_profiles.map(profile => `<article class="clone-profile"><strong>${esc(profile.name)}</strong><span>${esc(profile.duration_seconds)} 秒 · ${esc(profile.created_at)}</span><small>${esc(profile.clone_status)}</small></article>`).join("") : `<p class="muted">尚未保存本人样本。保存样本不代表克隆已可用。</p>`}</div></section>
    <section><div class="section-head"><h2>任务音频：位置、试听与下载</h2><p>真人和 AI 文件均在此列出</p></div>${audioMediaList(task)}</section>
    ${subtitleEditor(task)}
    <div class="info-banner">自动转写或 AI 录音都不等于字幕人工确认。进入素材规划前，录音和有效 SRT 必须同时存在。</div>
    ${actionBar("校对并保存字幕后，再确认录音与字幕", `<button class="button danger" data-task-action="revise_script">返回修改脚本</button><button class="button primary" data-task-action="confirm_audio">确认录音与字幕</button>`)}`;
}
function renderAssets(task) {
  const plan = task.asset_plan.length ? task.asset_plan : [{ id: "", name: "", source: "", licensed: false, file_id: null, note: "", asset_type: "own" }];
  const files = task.files.filter(file => file.kind === "asset");
  const srtFiles = task.files.filter(file => file.kind === "srt");
  const assetAI = state.data.asset_ai;
  const typeNames = { own: "自有素材", screen_record: "屏幕录制", stock: "合法素材库", ai_image: "AI 图像", ai_video: "AI 视频" };
  return `${stageHead("素材清单、来源与授权", "AI 只生成分镜建议；每一项仍须实际上传、填写来源并由你确认授权。")}
    <section class="asset-ai-panel"><div class="section-head"><div><h2>素材规划Agent分镜建议</h2><p>${esc(assetAI.status)} · 使用当前任务 SRT、母稿和音频时长，不下载或生成媒体</p></div><span class="badge ${assetAI.ready ? "green" : "orange"}">${esc(assetAI.status)}</span></div><div class="asset-ai-controls"><div class="field"><label for="asset-srt-file">用于分镜的 SRT</label><select id="asset-srt-file">${srtFiles.map(file => `<option value="${file.id}">${esc(file.original_name)}</option>`).join("")}</select></div><fieldset><legend>允许的素材类型</legend><div class="asset-type-options">${Object.entries(typeNames).map(([key,name]) => `<label><input type="checkbox" class="asset-allowed" value="${key}" ${["own","screen_record","stock"].includes(key) ? "checked" : ""}>${name}</label>`).join("")}</div></fieldset></div><button class="button primary" data-generate-asset-plan ${!srtFiles.length || !state.data.ai.ready || state.assetGenerating ? "disabled" : ""}>${state.assetGenerating ? "素材规划Agent正在生成…" : "素材规划Agent生成分镜建议"}</button><p class="muted">AI 建议不等于素材已下载、已生成或已授权。生成失败保留原计划。${assetAI.last_error ? ` 最近错误：${esc(assetAI.last_error)}` : ""}</p></section>
    <div class="upload-box"><h4>上传真实素材与授权凭证</h4><p>图片、视频、音频或授权凭证；文件仅保存到此任务的素材目录</p><input type="file" id="asset-file" accept=".png,.jpg,.jpeg,.webp,.gif,.mp4,.mov,.mp3,.wav,.m4a,.pdf,.txt"><button class="button small" data-upload="asset" data-input="asset-file">上传素材</button>${fileList(task,"asset")}</div>
    <div class="section-head"><h2>分镜与素材清单</h2><button class="button small" data-add-asset>＋ 添加一项</button></div>
    <div id="asset-plan">${plan.map((item,index) => `<div class="asset-row" data-asset-id="${esc(item.id)}"><div class="row"><div class="field"><label>素材名称 / 用途</label><input class="asset-name" value="${esc(item.name)}" placeholder="例如：片头实拍"></div><div class="field"><label>来源</label><input class="asset-source" value="${esc(item.source)}" placeholder="自己拍摄 / 已购素材库及订单"></div><div class="field"><label>关联上传文件</label><select class="asset-file"><option value="">请选择文件</option>${files.map(file => `<option value="${file.id}" ${file.id === item.file_id ? "selected" : ""}>${esc(file.original_name)}</option>`).join("")}</select></div></div><div class="asset-time-row"><div class="field"><label>开始秒</label><input type="number" min="0" step="0.1" class="asset-start" value="${item.start_seconds ?? ""}"></div><div class="field"><label>结束秒</label><input type="number" min="0" step="0.1" class="asset-end" value="${item.end_seconds ?? ""}"></div><div class="field"><label>素材类型</label><select class="asset-type">${Object.entries(typeNames).map(([key,name]) => `<option value="${key}" ${item.asset_type === key ? "selected" : ""}>${name}</option>`).join("")}</select></div></div><div class="field"><label>画面与口播关系</label><textarea class="asset-description">${esc(item.description)}</textarea></div><div class="row"><div class="field"><label>搜索词</label><input class="asset-search" value="${esc(item.search_query)}" placeholder="素材库检索或录屏规划"></div><div class="field"><label>授权风险</label><input class="asset-risk" value="${esc(item.license_risk)}" placeholder="授权、隐私、商标或客户数据风险"></div></div><div class="field"><label>AI 生成提示词</label><textarea class="asset-prompt">${esc(item.generation_prompt)}</textarea></div><div class="field"><label>授权或备注</label><input class="asset-note" value="${esc(item.note)}" placeholder="授权范围、凭证位置或使用限制"></div><label class="check"><input type="checkbox" class="asset-licensed" ${item.licensed ? "checked" : ""}>我确认此素材来源明确且已取得所需授权</label><button class="button small danger" data-remove-asset="${index}">移除</button></div>`).join("")}</div>
    ${actionBar("可只跳过未完成分镜；全部跳过后使用全部 Remotion", `<button class="button" data-save-assets>保存分镜与素材清单</button>${task.state === "assets_planned" ? `<button class="button" data-task-action="skip_incomplete_assets">跳过未完成项并继续</button><button class="button primary" data-task-action="approve_assets">确认全部素材与授权</button>` : ""}`)}`;
}
function latestFile(task, kind) { return task.files.find(file => file.kind === kind); }
function videoPreview(task) {
  const file = latestFile(task, "video");
  return file ? `<video class="video-preview" controls preload="metadata" src="${file.url}"></video><div class="video-download"><div><strong>${esc(file.original_name)}</strong><code>${esc(file.relative_path)}</code><p class="muted">${file.media_info.duration_seconds || "未读取"} 秒${file.media_info.mode ? ` · ${esc(file.media_info.mode)} / ${esc(file.media_info.platform)}` : ""}</p></div><a class="button small" href="${file.download_url}" download>下载 MP4</a></div>` : "";
}
function renderVideo(task) {
  const renderAI = state.data.render_ai;
  return `${stageHead("视频构建与成片", "三种真实渲染方式；成功并验证 MP4 后才进入质检，失败保留旧成片。")}
    <section class="render-panel"><div class="section-head"><div><h2>视频构建Agent自动渲染</h2><p>${esc(renderAI.status)} · 1080×1920 / 30fps · 音频与 SRT 同步</p></div><span class="badge ${renderAI.ready ? "green" : "orange"}">${esc(renderAI.status)}</span></div><div class="voice-form-grid"><div class="field"><label for="render-mode">渲染模式</label><select id="render-mode"><option value="remotion">全部 Remotion：文字卡、字幕、背景与音频，无素材也可</option><option value="mixed">混合：上传场景 + Remotion 标题、字幕与画幅</option><option value="upload">全部上传：关联视频/图片 + 音频，FFmpeg 合成</option></select></div><div class="field"><label for="render-platform">目标平台</label><select id="render-platform">${Object.entries(platformNames).map(([key,name]) => `<option value="${key}">${name}</option>`).join("")}</select></div></div><label class="check"><input type="checkbox" id="burn-subtitles" checked>上传模式烧入 SRT 字幕</label><button class="button primary" data-render-task ${state.rendering ? "disabled" : ""}>${state.rendering ? "正在真实渲染…" : "开始渲染 MP4"}</button><p class="muted">上传/混合至少需要 1 个已关联且授权的视频或图片场景。${renderAI.last_error ? ` 最近错误：${esc(renderAI.last_error)}` : ""}</p></section>
    <div class="upload-box"><h4>也可以手动上传成片</h4><p>MP4 / MOV / WebM，最大 500MB。重复上传会清除旧质检结果。</p><input type="file" id="video-file" accept=".mp4,.mov,.webm"><button class="button small" data-upload="video" data-input="video-file">上传并检查成片</button></div>${videoPreview(task)}
    ${actionBar("渲染成功后可预览、下载并进入五项质检", `<button class="button danger" data-task-action="revise_assets">返回修改素材</button>`)}`;
}
function renderQuality(task) {
  const checks = task.quality.checks || {};
  return `${stageHead("成片五项质检", "逐项实际观看和检查；保存未通过结果后必须返修，不能提交人工审核。")}${videoPreview(task)}
    <div class="quality-grid">${Object.entries(qualityNames).map(([key,[name,hint]]) => `<label class="quality-item"><input type="checkbox" data-quality="${key}" ${checks[key] ? "checked" : ""}><span><strong>${name}</strong><small>${hint}</small></span></label>`).join("")}</div>
    <div class="field" style="margin-top:15px"><label for="quality-note">质检备注 / 返修原因</label><textarea id="quality-note" placeholder="记录发现的问题、时间点或平台规格说明">${esc(task.quality.note)}</textarea></div>
    ${task.quality.checked_at ? `<div class="info-banner">上次结果：<strong>${task.quality.passed ? "通过" : "未通过"}</strong> · ${esc(task.quality.checked_at)}</div>` : ""}
    ${actionBar("自动检查不等于人工最终审核", `<button class="button" data-save-quality>保存质检结果</button>${task.state === "quality_checked" ? `<button class="button danger" data-task-action="revise_assets">返回素材返修</button><button class="button danger" data-task-action="revise_render">仅重做成片</button>${task.quality.passed ? `<button class="button primary" data-task-action="submit_review">提交人工审核</button>` : ""}` : ""}`)}`;
}
function renderReview(task) {
  return `${stageHead("人工最终审核", "请完整观看最终成片。此确认与之后的发布确认是两个独立检查点。")}${videoPreview(task)}
    <div class="info-banner">当前五项质检已通过，但仍需你本人确认最终内容、表达与发布风险。</div>
    ${actionBar("审核要求修改时，可返回脚本或素材，后续审批会清除", `<button class="button danger" data-task-action="revise_script">返回脚本返修</button><button class="button danger" data-task-action="revise_assets">返回素材返修</button><button class="button primary" data-task-action="approve_final">我已看成片，批准最终版本</button>`)}`;
}
function renderPublish(task) {
  const records = task.publications || {};
  return `${stageHead("人工发布记录", "编辑各平台标题、简介、标签与链接；保存不等于发布，发布确认仍需单独操作。")}
    ${Object.entries(platformNames).map(([key,name]) => { const record = records[key] || {}; return `<section class="publish-row" data-platform="${key}"><div class="publish-head"><strong>${name}</strong><select class="publish-status"><option value="unpublished" ${(!record.status || record.status === "unpublished") ? "selected" : ""}>未发布</option><option value="published" ${record.status === "published" ? "selected" : ""}>已发布</option><option value="skipped" ${record.status === "skipped" ? "selected" : ""}>本次不发</option></select></div><div class="publish-fields"><div class="field"><label>发布标题</label><input class="publish-title" maxlength="300" value="${esc(record.title)}" placeholder="该平台实际使用的标题"></div><div class="field"><label>发布链接</label><input class="publish-url" value="${esc(record.url)}" placeholder="已发布必填 https:// 真实链接"></div></div><div class="field"><label>简介 / 正文摘要</label><textarea class="publish-description" placeholder="记录该平台实际使用的简介或正文摘要">${esc(record.description)}</textarea></div><div class="field"><label>标签</label><input class="publish-tags" maxlength="1000" value="${esc(record.tags)}" placeholder="例如：#企业AI #AI营销"></div></section>`; }).join("")}
    <div class="info-banner">发布复盘Agent：<strong>未接入</strong>。平台自动发布未接入；扫码、短信、滑块及二次验证始终由你本人完成。</div>
    ${actionBar("至少一个平台记录为已发布并附链接", `<button class="button" data-save-publications>保存发布信息</button>${task.state === "approved" ? `<button class="button primary" data-task-action="confirm_publish">我确认已完成上述发布</button>` : ""}`)}`;
}
function renderRetro(task) {
  const fields = [["views","播放 / 阅读"],["likes","点赞"],["comments","评论"],["shares","分享"],["followers","新增关注"],["leads","有效咨询"]];
  const names = { "2h":"2 小时", "1d":"1 天", "3d":"3 天", "7d":"7 天" };
  return `${stageHead(task.state === "analyzed" ? "复盘已完成" : "数据回收与复盘", "分四个时间点录入真实数据；暂时没读到的单项可留空，不会自动变成 0。")}
    <table class="metric-table"><thead><tr><th>时间点</th>${fields.map(([,name]) => `<th>${name}</th>`).join("")}</tr></thead><tbody>${Object.entries(names).map(([period,label]) => `<tr data-period="${period}"><td>${label}</td>${fields.map(([key]) => `<td><input type="number" min="0" step="1" data-metric="${key}" value="${task.metrics[period]?.[key] ?? ""}" placeholder="未读取"></td>`).join("")}</tr>`).join("")}</tbody></table>
    <div class="field"><label for="retrospective">复盘结论</label><textarea id="retrospective" placeholder="哪些信号值得复测？下次保留、修改或停止什么？不要只看播放量。">${esc(task.retrospective)}</textarea></div>
    ${task.state === "analyzed" ? `<div class="info-banner">这条内容已于 ${esc(task.completed_at)} 完成复盘。仍可补充更正数据。</div>` : ""}
    ${actionBar("完成需四个时间点的播放/阅读数据和复盘结论", `<button class="button" data-save-metrics>保存复盘数据</button>${task.state === "published" ? `<button class="button primary" data-task-action="complete_retro">完成复盘并归档</button>` : ""}`)}`;
}
function renderHistory(task) {
  return `<div class="history"><details><summary>操作记录（${task.events.length}）</summary><ul>${task.events.map(event => `<li>${esc(event.created_at)} · <strong>${esc(event.event)}</strong> ${esc(event.detail)}</li>`).join("")}</ul></details></div>`;
}

const metricLabels = { followers: "关注", following: "正在关注", total_likes: "累计获赞", works_count: "作品数", content_manager_total: "内容管理总数", total_likes_and_favorites: "获赞与收藏", published_notes_count: "已发布笔记", videos_count: "视频数", original_content_count: "原创内容", total_publications: "总发表", views: "播放 / 观看", exposures: "曝光", likes: "点赞", heart_reactions: "心形反应", thumb_reactions: "拇指反应", comments: "评论", shares: "分享", favorites: "收藏", new_followers: "新增关注", net_new_followers: "净增关注", new_heart_reactions: "新增心形反应", new_comments: "新增评论", readers: "阅读", profile_visits: "主页访问", new_views: "新增观看" };
function renderAccounts() {
  const account = state.data.accounts.find(item => item.platform === state.account) || state.data.accounts[0];
  state.account = account.platform;
  const summary = { ...account.profile, ...(account.weekly_summary || {}), ...(account.daily_summary || {}) };
  const ignored = new Set(["biography", "biography_is_truncated", "period_start", "period_end", "date"]);
  const metrics = Object.entries(summary).filter(([key]) => !ignored.has(key) && !key.includes("change") && !key.includes("rate"));
  const metricKeys = account.platform === "wechat_official_account" ? ["readers","likes","comments","shares"] : account.platform === "wechat_channels" ? ["views","heart_reactions","comments","shares"] : ["views","likes","comments","shares"];
  $("#accounts").innerHTML = `<div class="account-tabs">${state.data.accounts.map(item => `<button class="button small ${item.platform === account.platform ? "active" : ""}" data-account="${item.platform}">${platformNames[item.platform]}</button>`).join("")}</div>
    <article class="card"><div class="account-profile"><div><span class="eyebrow">数据分析Agent · 未接入自动分析 · 只读快照已导入</span><span class="badge">${platformNames[account.platform]}</span><h2>${esc(account.account_name)}</h2><p>账号 ID：${fmt(account.account_id)} · 采集于 ${esc(account.captured_at)}</p></div>${account.backend_url ? `<a class="button small" href="${esc(account.backend_url)}" target="_blank" rel="noreferrer">打开官方创作者后台 ↗</a>` : ""}</div><div class="account-metrics">${metrics.slice(0,8).map(([key,value]) => `<div class="metric"><span>${metricLabels[key] || esc(key)}</span><strong>${fmt(value)}</strong></div>`).join("")}</div><p class="muted">${fmt(account.profile?.biography)}</p></article>
    <div class="section-head"><h2>最近公开内容</h2><p>私密、仅自己可见或未通过内容不进入对比</p></div><article class="card table-wrap"><table class="data-table"><thead><tr><th>内容</th><th>发布时间</th>${metricKeys.map(key => `<th>${metricLabels[key] || key}</th>`).join("")}<th>链接</th></tr></thead><tbody>${account.content_items.map(item => `<tr><td>${esc(item.title)}</td><td>${shortDate(item.published_at)}</td>${metricKeys.map(key => `<td>${fmt(item.metrics?.[key])}</td>`).join("")}<td>${item.url ? `<a href="${esc(item.url)}" target="_blank" rel="noreferrer">查看原文</a>` : "未读取"}</td></tr>`).join("")}</tbody></table></article>
    <div class="issues"><strong>数据边界</strong><ul>${(account.collection_issues || []).map(issue => `<li>${esc(issue)}</li>`).join("")}<li>未读取字段：${(account.missing_fields || []).map(esc).join("、") || "无"}</li></ul></div>`;
}

function renderAgentSettings() {
  const data = state.agentData;
  if (!data || data.load_error) return `<article class="card settings-error">Agent 配置读取失败：${esc(data?.load_error || "尚未加载")}</article>`;
  const entries = Object.entries(data.agents);
  const id = state.agentEditorId in data.agents ? state.agentEditorId : entries[0][0];
  state.agentEditorId = id;
  const definition = data.agents[id];
  const config = data.configs[id];
  return `<article class="card agent-config"><div class="section-head"><div><h2>Agent 配置中心</h2><p>每个独立 Agent 单独配置；只影响之后的新任务，历史产物和运行中任务不变</p></div><span class="badge ${config.enabled ? "green" : "orange"}">${config.enabled ? "已启用" : definition.connected ? "已停用" : "未接入"}</span></div><div class="agent-config-layout"><aside class="agent-list">${entries.map(([agentId,item]) => `<button class="agent-list-item ${agentId === id ? "active" : ""}" data-agent-edit="${agentId}"><strong>${esc(item.name)}</strong><small>${esc(item.description)}</small><span>${esc(data.configs[agentId].engine)} · ${data.configs[agentId].enabled ? "启用" : item.connected ? "停用" : "未接入"}</span></button>`).join("")}</aside><section class="agent-editor"><div class="section-head"><div><h3>${esc(definition.name)}</h3><p>${esc(definition.description)}</p></div></div><label class="check"><input id="agent-enabled" type="checkbox" ${config.enabled ? "checked" : ""} ${definition.connected ? "" : "disabled"}>允许该 Agent 接收新任务</label><div class="form-grid"><div class="field"><label>执行引擎</label><select id="agent-engine">${definition.engines.map(engine => `<option value="${engine}" ${config.engine === engine ? "selected" : ""}>${engine}</option>`).join("")}</select></div><div class="field"><label>模型 / 变体</label>${definition.variants ? `<select id="agent-model">${definition.variants.map(model => `<option value="${model}" ${config.model === model ? "selected" : ""}>${model}</option>`).join("")}</select>` : `<input id="agent-model" value="${esc(config.model)}"></div>`}</div><div class="form-grid"><div class="field"><label>超时（秒）</label><input id="agent-timeout" type="number" min="30" max="3600" value="${config.timeout_seconds}"></div><div class="field"><label>最多尝试次数</label><input id="agent-attempts" type="number" min="1" max="5" value="${config.max_attempts}"></div><div class="field"><label>并发上限</label><input id="agent-concurrency" type="number" min="1" max="2" value="${config.concurrency}"></div></div>${definition.prompt ? `<div class="field"><label>补充提示词</label><textarea id="agent-prompt" rows="5">${esc(config.prompt)}</textarea><span class="hint">只追加到该 Agent，不覆盖原有安全约束，不影响其他 Agent</span></div>` : `<p class="muted">该 Agent 是确定性工具或调度器，没有可编辑提示词。</p>`}<div class="button-row"><button class="button primary" data-agent-save="${id}">保存 ${esc(definition.name)}</button><button class="button" data-agent-reset="${id}">恢复该 Agent 默认</button></div><p class="muted">禁用只阻止新任务；未接入 Agent 不能启用。模型自定义仅限已验证的引擎与变体。</p></section></div></article>`;
}
async function saveAgentConfig(agentId) {
  const payload = { enabled: $("#agent-enabled").checked, engine: $("#agent-engine").value, model: $("#agent-model").value,
    prompt: $("#agent-prompt")?.value || "", timeout_seconds: Number($("#agent-timeout").value),
    max_attempts: Number($("#agent-attempts").value), concurrency: Number($("#agent-concurrency").value) };
  try { await api(`/api/agents/config/${agentId}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }); await refreshAgentConfigs(); notify("Agent 配置已保存，之后的新任务生效"); }
  catch (error) { notify(error, true); }
}
async function resetAgentConfig(agentId) {
  try { await api(`/api/agents/config/${agentId}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ reset: true }) }); await refreshAgentConfigs(); notify("已恢复该 Agent 默认配置，其他 Agent 未改变"); }
  catch (error) { notify(error, true); }
}
function renderSettings() {
  const ai = state.data.ai;
  const voices = state.data.voices;
  const mediaAI = state.data.media_ai;
  const assetAI = state.data.asset_ai;
  const renderAI = state.data.render_ai;
  $("#settings").innerHTML = renderAgentSettings() + `<div class="settings-layout"><article class="card"><div class="section-head"><div><h2>本地 Kimi 脚本生成</h2><p>脚本Agent · 使用 agents/script-agent.md，禁止工具调用</p></div><span class="badge ${ai.ready ? "green" : "orange"}">${ai.ready ? "已连接" : "未连接"}</span></div><div class="account-metrics"><div class="metric"><span>CLI 安装</span><strong>${ai.installed ? "已安装" : "未找到"}</strong></div><div class="metric"><span>版本</span><strong>${esc(ai.version || "未读取")}</strong></div><div class="metric"><span>OAuth / 连接状态</span><strong>${esc(ai.oauth_status)}</strong></div><div class="metric"><span>最近真实成功</span><strong class="setting-time">${esc(ai.last_success || "尚未验证")}</strong></div></div><div class="info-banner"><strong>本地 CLI 调用，云端模型，共享会员额度，草稿需人工确认。</strong><br>${esc(ai.model)}。网站不会读取凭据文件，也不会固定或伪造模型 ID。</div>${ai.last_error ? `<div class="settings-error"><strong>最近错误</strong><p>${esc(ai.last_error)}</p></div>` : ""}<button class="button primary" data-test-ai ${state.testing || !ai.installed ? "disabled" : ""}>${state.testing ? "正在进行真实连接测试…" : "测试本地连接"}</button><p class="muted">测试会实际调用一次 Kimi，并验证五个 JSON 字符串；仅检测文件存在不会标记为已连接。</p></article><article class="card"><h2>数据与自动化边界</h2><ul class="settings-list"><li>任务、设置和审批保存在本机 SQLite，服务只监听 127.0.0.1。</li><li>生成输入仅包含当前任务、候选/热点证据和必要账号策略，不发送全库历史文章。</li><li>脚本生成成功不会自动人工批准，也不会自动发布。</li><li>质检Agent、发布复盘Agent仍未接入。</li></ul><div class="model-setting"><h2>视频构建Agent</h2><p><span class="badge ${renderAI.ready ? "green" : "orange"}">${esc(renderAI.status)}</span></p><p class="muted">真实 Remotion/FFmpeg MP4；成功验证后才标记已连接。最近成功：${esc(renderAI.last_success || "尚未验证")}</p>${renderAI.last_error ? `<div class="settings-error">${esc(renderAI.last_error)}</div>` : ""}<button class="button small" data-test-render ${state.renderTesting ? "disabled" : ""}>${state.renderTesting ? "正在真实渲染测试…" : "测试视频构建Agent"}</button></div><div class="model-setting"><h2>素材规划Agent</h2><p><span class="badge ${assetAI.ready ? "green" : "orange"}">${esc(assetAI.status)}</span></p><p class="muted">真实 Kimi 分镜 JSON 测试；不下载素材、不生成媒体、不代表授权。最近成功：${esc(assetAI.last_success || "尚未验证")}</p>${assetAI.last_error ? `<div class="settings-error">${esc(assetAI.last_error)}</div>` : ""}<button class="button small" data-test-assets ${state.assetTesting ? "disabled" : ""}>${state.assetTesting ? "正在真实生成分镜…" : "测试素材规划Agent"}</button></div><div class="voice-settings"><h2>语音能力</h2><div class="model-setting"><p><span class="badge ${voices.capabilities.system_ready ? "green" : "orange"}">系统语音 ${esc(voices.capabilities.system_status)}</span></p><p class="muted">macOS say + FFmpeg + FFprobe。最近成功：${esc(voices.last_success || "尚未验证")}</p>${voices.last_error ? `<div class="settings-error">${esc(voices.last_error)}</div>` : ""}<button class="button small" data-test-tts ${state.ttsTesting ? "disabled" : ""}>${state.ttsTesting ? "正在生成测试音频…" : "测试系统语音"}</button></div><div class="model-setting"><p><span class="badge ${mediaAI.whisperx.ready ? "green" : "orange"}">WhisperX ${esc(mediaAI.whisperx.status)}</span></p><p class="muted">本地 CPU 转写，默认 small；首次需要下载模型。最近成功：${esc(mediaAI.whisperx.last_success || "尚未验证")}</p>${mediaAI.whisperx.last_error ? `<div class="settings-error">${esc(mediaAI.whisperx.last_error)}</div>` : ""}<button class="button small" data-test-whisperx ${state.whisperxTesting ? "disabled" : ""}>${state.whisperxTesting ? "正在真实转写…" : "测试 WhisperX"}</button></div><div class="model-setting"><p><span class="badge ${mediaAI.openvoice.ready ? "green" : "orange"}">OpenVoice ${esc(mediaAI.openvoice.status)}</span></p><p class="muted">官方 MIT OpenVoice V2，本地 CPU；需要 checkpoints_v2 和本人授权样本。最近成功：${esc(mediaAI.openvoice.last_success || "尚未验证")}</p>${mediaAI.openvoice.last_error ? `<div class="settings-error">${esc(mediaAI.openvoice.last_error)}</div>` : ""}<button class="button small" data-test-clone ${state.cloneTesting ? "disabled" : ""}>${state.cloneTesting ? "正在真实克隆测试…" : "测试 OpenVoice"}</button></div><p class="muted">模型自测文件仅用于验证并自动清理，不会加入任务或音色库。</p></div></article></div>`;
}

async function doAction(action) {
  if (!selectedTask()) return;
  try { await api(`/api/tasks/${state.taskId}/actions`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action }) }); await refresh("操作已保存"); }
  catch (error) { notify(error, true); }
}
async function save(path, payload, message) {
  try { await api(`/api/tasks/${state.taskId}/${path}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }); await refresh(message); return true; }
  catch (error) { notify(error, true); return false; }
}
function collectAssetPlan() {
  return $$(".asset-row").map(row => ({ id: row.dataset.assetId, name: $(".asset-name",row).value, source: $(".asset-source",row).value, file_id: Number($(".asset-file",row).value) || null, note: $(".asset-note",row).value, licensed: $(".asset-licensed",row).checked, start_seconds: $(".asset-start",row).value === "" ? null : Number($(".asset-start",row).value), end_seconds: $(".asset-end",row).value === "" ? null : Number($(".asset-end",row).value), asset_type: $(".asset-type",row).value, description: $(".asset-description",row).value, search_query: $(".asset-search",row).value, generation_prompt: $(".asset-prompt",row).value, license_risk: $(".asset-risk",row).value }));
}
async function approveAssetsWithSave() {
  const saved = await save("assets", { asset_plan: collectAssetPlan() }, "分镜关联已保存，正在检查授权");
  if (saved) await doAction("approve_assets");
}
async function createTask(payload) {
  try { const task = await api("/api/tasks", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }); state.taskId = task.content_id; await refresh(`已创建 ${task.content_id} 及任务目录`); switchView("tasks"); }
  catch (error) { notify(error, true); }
}
async function testAI() {
  state.testing = true; renderSettings();
  try {
    await api("/api/ai/test", { method: "POST" }); state.testing = false;
    await refresh("Kimi 真实连接测试成功，脚本Agent已连接");
  } catch (error) {
    state.testing = false; await refresh(); notify(error, true);
  }
}
async function generateScripts() {
  if (state.generating) return;
  state.generating = true; renderTasks();
  try {
    await api(`/api/tasks/${state.taskId}/generate-scripts`, { method: "POST" }); state.generating = false;
    await refresh("脚本Agent已生成五版草稿，请逐版核对后人工确认");
  } catch (error) {
    state.generating = false; await refresh(); notify(error, true);
  }
}
async function testTTS() {
  state.ttsTesting = true; renderSettings();
  try {
    await api("/api/voices/test", { method: "POST" }); state.ttsTesting = false;
    await refresh("系统语音真实生成、WAV 转换和检查均已通过");
  } catch (error) {
    state.ttsTesting = false; await refresh(); notify(error, true);
  }
}
async function testMedia(kind) {
  const key = kind === "whisperx" ? "whisperxTesting" : "cloneTesting";
  state[key] = true; renderSettings();
  try {
    await api(kind === "whisperx" ? "/api/whisperx/test" : "/api/voices/clone/test", { method: "POST" });
    state[key] = false; await refresh(`${kind === "whisperx" ? "WhisperX" : "OpenVoice"} 真实测试成功`);
  } catch (error) {
    state[key] = false; await refresh(); notify(error, true);
  }
}
async function testAssetAgent() {
  state.assetTesting = true; renderSettings();
  try {
    await api("/api/assets/test", { method: "POST" }); state.assetTesting = false;
    await refresh("素材规划Agent真实分镜测试成功");
  } catch (error) {
    state.assetTesting = false; await refresh(); notify(error, true);
  }
}
async function generateAssetPlan() {
  if (state.assetGenerating) return;
  const payload = { file_id: Number($("#asset-srt-file").value), allowed_types: $$(".asset-allowed:checked").map(input => input.value) };
  state.assetGenerating = true; renderTasks();
  try {
    await api(`/api/tasks/${state.taskId}/generate-asset-plan`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    state.assetGenerating = false; await refresh("分镜建议已保存；请上传真实素材并逐项确认授权");
  } catch (error) {
    state.assetGenerating = false; await refresh(); notify(error, true);
  }
}
async function renderTask() {
  if (state.rendering) return;
  const payload = { mode: $("#render-mode").value, platform: $("#render-platform").value, burn_subtitles: $("#burn-subtitles").checked };
  state.rendering = true; renderTasks();
  try {
    await api(`/api/tasks/${state.taskId}/render`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    state.rendering = false; await refresh("真实 MP4 渲染完成，可预览、下载并进入质检");
  } catch (error) {
    state.rendering = false; await refresh(); notify(error, true);
  }
}
async function testRenderAgent() {
  state.renderTesting = true; renderSettings();
  try {
    await api("/api/render/test", { method: "POST" }); state.renderTesting = false;
    await refresh("视频构建Agent真实 MP4 自测成功");
  } catch (error) {
    state.renderTesting = false; await refresh(); notify(error, true);
  }
}
function updateGenerateAudioButton() {
  const button = $("#generate-audio-button");
  const select = $("#tts-voice");
  if (!button || !select) return;
  const kind = select.selectedOptions[0]?.dataset.kind;
  const capabilities = state.data.voices.capabilities;
  button.disabled = state.ttsGenerating || !(kind === "clone" ? capabilities.clone_ready : capabilities.system_ready);
}
async function generateAudio() {
  if (state.ttsGenerating) return;
  const payload = { script_key: $("#tts-script").value, voice_id: $("#tts-voice").value, text: $("#tts-text").value };
  const endpoint = $("#tts-voice").selectedOptions[0]?.dataset.kind === "clone" ? "generate-clone-audio" : "generate-audio";
  state.ttsGenerating = true; renderTasks();
  try {
    await api(`/api/tasks/${state.taskId}/${endpoint}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    state.ttsGenerating = false; await refresh("AI 录音已生成并保存，可试听下载；仍需 SRT 字幕");
  } catch (error) {
    state.ttsGenerating = false; await refresh(); notify(error, true);
  }
}
async function transcribeAudio() {
  if (state.transcribing) return;
  const payload = { file_id: Number($("#whisperx-file").value), model: $("#whisperx-model").value };
  state.transcribing = true; renderTasks();
  try {
    await api(`/api/tasks/${state.taskId}/transcribe`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    state.transcribing = false; await refresh("WhisperX 已生成 SRT，请人工校对后确认");
  } catch (error) {
    state.transcribing = false; await refresh(); notify(error, true);
  }
}
async function saveVoiceSample(button) {
  const file = $("#voice-sample-file").files[0];
  const name = $("#voice-profile-name").value;
  const authorized = $("#voice-sample-authorized").checked;
  if (!file) return notify("请选择本人语音样本", true);
  button.disabled = true; button.textContent = "正在检查并保存样本…";
  try {
    await api(`/api/voices/samples?name=${encodeURIComponent(name)}&authorized=${authorized}&filename=${encodeURIComponent(file.name)}`, { method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: file });
    await refresh("本人样本已保存；生成能力以 OpenVoice 真实测试状态为准");
  } catch (error) {
    await refresh(); notify(error, true);
  }
}

document.addEventListener("click", async event => {
  const button = event.target.closest("button,[data-go-topics],[data-open-task]");
  if (!button || button.disabled) return;
  if (button.dataset.view) switchView(button.dataset.view);
  else if (button.id === "new-task-top") { switchView("topics"); const form = $("#manual-form"); if (form) form.closest("details").open = true; setTimeout(() => $("#manual-title")?.focus(), 0); }
  else if (button.hasAttribute("data-go-topics")) switchView("topics");
  else if (button.dataset.openTask) openTask(button.dataset.openTask);
  else if (button.dataset.selectTask) { state.taskId = button.dataset.selectTask; renderTasks(); }
  else if (button.dataset.topicView) { state.topicView = button.dataset.topicView; state.topicDetail = null; renderTopics(); }
  else if (button.hasAttribute("data-save-topic-settings")) await saveTopicSettings();
  else if (button.hasAttribute("data-sync-topics")) await topicAction("/api/topics/sync", {}, "抖音快照同步已开始；此阶段不下载视频");
  else if (button.hasAttribute("data-sync-industry")) await topicAction("/api/topics/industry", { agent: "industry" }, "行业热点与推荐已开始");
  else if (button.hasAttribute("data-topic-login")) await topicAction("/api/topics/browser/open", {}, "专用采集窗口即将打开，请在窗口内完成登录");
  else if (button.dataset.topicRecommend) await topicAction("/api/topics/recommend", { agent: button.dataset.topicRecommend }, "选题Agent已开始分析真实快照");
  else if (button.dataset.analyzeItem) await topicAction(`/api/topics/items/${button.dataset.analyzeItem}/analyze`, {}, "已选择该视频，开始按需下载、抽帧和OCR");
  else if (button.dataset.detailItem) await showResearchItem(button.dataset.detailItem);
  else if (button.dataset.createResearch) await createResearchTask(button.dataset.createResearch);
  else if (button.hasAttribute("data-close-research")) { state.topicDetail = null; renderTopics(); }
  else if (button.dataset.createTopic) await createTask({ topic_id: Number(button.dataset.createTopic) });
  else if (button.dataset.createHotspot) await createTask({ hotspot_rank: Number(button.dataset.createHotspot) });
  else if (button.dataset.agentEdit) { state.agentEditorId = button.dataset.agentEdit; renderSettings(); }
  else if (button.dataset.agentSave) await saveAgentConfig(button.dataset.agentSave);
  else if (button.dataset.agentReset) await resetAgentConfig(button.dataset.agentReset);
  else if (button.dataset.useCollection) {
    $("#manual-collection").value = button.dataset.useCollection;
    $("#manual-pillar").value = button.dataset.pillar;
    $("#manual-audience").value = button.dataset.audience;
    $("#manual-create").scrollIntoView({ behavior: "smooth", block: "start" });
    $("#manual-title").focus();
  }
  else if (button.dataset.account) { state.account = button.dataset.account; renderAccounts(); }
  else if (button.hasAttribute("data-test-ai")) await testAI();
  else if (button.hasAttribute("data-test-tts")) await testTTS();
  else if (button.hasAttribute("data-test-whisperx")) await testMedia("whisperx");
  else if (button.hasAttribute("data-test-clone")) await testMedia("clone");
  else if (button.hasAttribute("data-test-assets")) await testAssetAgent();
  else if (button.hasAttribute("data-test-render")) await testRenderAgent();
  else if (button.hasAttribute("data-render-task")) await renderTask();
  else if (button.hasAttribute("data-generate-scripts")) await generateScripts();
  else if (button.hasAttribute("data-generate-audio")) await generateAudio();
  else if (button.hasAttribute("data-transcribe")) await transcribeAudio();
  else if (button.hasAttribute("data-generate-asset-plan")) await generateAssetPlan();
  else if (button.hasAttribute("data-save-voice-sample")) await saveVoiceSample(button);
  else if (button.hasAttribute("data-save-subtitle")) await save("subtitles", { file_id: Number($("#subtitle-text").dataset.fileId), text: $("#subtitle-text").value }, "字幕校对已保存");
  else if (button.dataset.taskAction === "approve_assets") await approveAssetsWithSave();
  else if (button.dataset.taskAction) await doAction(button.dataset.taskAction);
  else if (button.hasAttribute("data-save-scripts")) {
    const scripts = {}; $$("[data-script]").forEach(el => scripts[el.dataset.script] = el.value);
    await save("scripts", { scripts }, "五个脚本版本已保存");
  } else if (button.dataset.upload) {
    const input = $("#" + button.dataset.input); const file = input.files[0];
    if (!file) return notify("请先选择文件", true);
    button.disabled = true; button.textContent = "正在上传并检查…";
    try {
      await api(`/api/tasks/${state.taskId}/files?kind=${button.dataset.upload}&filename=${encodeURIComponent(file.name)}`, { method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: file });
      await refresh(`${file.name} 已上传并通过检查`);
    } catch (error) { notify(error, true); await refresh(); }
  } else if (button.hasAttribute("data-add-asset")) {
    const task = selectedTask(); task.asset_plan.push({ id: "", name: "", source: "", licensed: false, file_id: null, note: "" }); renderTasks();
  } else if (button.dataset.removeAsset !== undefined) {
    selectedTask().asset_plan.splice(Number(button.dataset.removeAsset), 1); renderTasks();
  } else if (button.hasAttribute("data-save-assets")) {
    await save("assets", { asset_plan: collectAssetPlan() }, "分镜、素材来源与授权已保存");
  } else if (button.hasAttribute("data-save-quality")) {
    const checks = {}; $$("[data-quality]").forEach(el => checks[el.dataset.quality] = el.checked);
    await save("quality", { checks, note: $("#quality-note").value }, "质检结果已保存");
  } else if (button.hasAttribute("data-save-publications")) {
    const publications = {}; $$(".publish-row").forEach(row => publications[row.dataset.platform] = { status: $(".publish-status",row).value, url: $(".publish-url",row).value, title: $(".publish-title",row).value, description: $(".publish-description",row).value, tags: $(".publish-tags",row).value, recorded_at: selectedTask().publications[row.dataset.platform]?.recorded_at });
    await save("publications", { publications }, "平台标题、简介、标签和发布记录已保存");
  } else if (button.hasAttribute("data-save-metrics")) {
    const metrics = {}; $$("[data-period]").forEach(row => { metrics[row.dataset.period] = {}; $$("[data-metric]",row).forEach(input => metrics[row.dataset.period][input.dataset.metric] = input.value === "" ? null : Number(input.value)); });
    await save("metrics", { metrics, retrospective: $("#retrospective").value }, "复盘数据已保存");
  }
});
document.addEventListener("change", event => {
  if (event.target.id === "tts-script") {
    $("#tts-text").value = selectedTask()?.scripts[event.target.value] || "";
  } else if (event.target.id === "tts-voice") updateGenerateAudioButton();
});
document.addEventListener("submit", async event => {
  if (event.target.id !== "manual-form") return;
  event.preventDefault(); const form = new FormData(event.target);
  await createTask(Object.fromEntries(form.entries()));
});
$("#date-label").textContent = new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", weekday: "long" }).format(new Date());
setInterval(async () => {
  if (state.view !== "topics" || state.topicBusy || !state.topicsData || ["INPUT", "TEXTAREA"].includes(document.activeElement?.tagName)) return;
  const active = (state.topicsData.jobs || []).some(job => ["queued", "leased", "running"].includes(job.status));
  if (active) {
    try { await refreshTopics(false); $("#topic-job-banner").innerHTML = topicJobBanner(); } catch (_) {}
  } else if (state.topicWasBusy) {
    try { await refreshTopics(); } catch (_) {}
  }
  state.topicWasBusy = active;
}, 3000);
refresh().catch(error => { $("#loading").innerHTML = `无法连接本地服务：${esc(error.message)}`; });
const loadingObserver = new MutationObserver(() => { if (state.data) { $("#loading").style.display = "none"; loadingObserver.disconnect(); } });
loadingObserver.observe($("#today"), { childList: true });
