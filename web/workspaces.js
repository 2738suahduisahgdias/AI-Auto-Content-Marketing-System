Object.assign(state, { accountData: null, articleData: null, knowledgeData: null, articleId: null, knowledgeEntityId: null, workspaceBusy: false, knowledgeQuery: "", knowledgeType: "" });
const workspaceTitles = { industry: "行业热点", douyin: "抖音选题", wechat: "视频号选题", xiaohongshu: "小红书选题", accounts: "账号日报", publish: "发布与复盘", articles: "文章任务", tasks: "视频任务", knowledge: "Ontology 知识库" };
const workspaceJobNames = { "accounts.sync": "同步账号快照", "accounts.recommend": "账号分析Agent", "accounts.daily": "每日账号分析", "accounts.login": "平台登录窗口（5分钟）", "publish.douyin": "抖音发布预览", "article.outline": "文章Agent生成大纲", "article.draft": "文章Agent生成正文", "article.export": "导出文章" };
function workspaceJob(job) {
  const error = job.error && Object.keys(job.error).length ? job.error : null;
  const partialErrors = Object.entries(job.result?.accounts || {}).filter(([key]) => key.endsWith("_error"));
  return `<article class="workspace-job ${error ? "failed" : ""}"><div><strong>${esc(workspaceJobNames[job.kind] || job.kind)}</strong><small>${esc(job.stage || job.status)} · ${esc(job.created_at)}</small></div><span class="badge ${job.status === "succeeded" && !partialErrors.length ? "green" : error ? "red" : "orange"}">${esc(job.status)}</span>${error ? `<p>错误：${esc(error.message || error.code)}<br>怎么改：${esc(error.action || "检查当前输入、登录状态和服务日志后重试")}</p>` : ""}${partialErrors.map(([key,value]) => `<p>部分失败：${esc(key)} · ${esc(value)}<br>怎么改：在专用窗口登录对应平台后重试；其他平台快照仍可使用。</p>`).join("")}</article>`;
}
async function workspaceAction(action, success = "操作已提交") {
  if (state.workspaceBusy) return null;
  state.workspaceBusy = true;
  try { const result = await action(); await refreshWorkspaces(false); renderWorkspaceViews(); notify(success); return result; }
  catch (error) { notify(error, true); return null; }
  finally { state.workspaceBusy = false; }
}
async function refreshWorkspaces(render = true) {
  const requests = [["accountData", "/api/accounts/bootstrap"], ["articleData", "/api/articles/bootstrap"], ["knowledgeData", "/api/knowledge/bootstrap"]];
  await Promise.all(requests.map(async ([key, path]) => {
    try { state[key] = await api(path); }
    catch (error) { state[key] = { load_error: error.message, items: [], accounts: [], recommendations: [], jobs: [], entities: [], relations: [], rules: [] }; }
  }));
  if (state.articleData?.items?.length && !state.articleData.items.some(item => item.id === state.articleId)) state.articleId = state.articleData.items[0].id;
  if (render) renderWorkspaceViews();
}
function selectedArticle() { return state.articleData?.items?.find(item => item.id === state.articleId) || state.articleData?.items?.[0]; }
function activeRevision(item, kind) { return item?.revisions?.find(revision => revision.id === item.active_revisions?.[kind]); }
function itemTags(items) {
  const tags = [...new Set(items.map(item => item.metadata?.tag).filter(Boolean))];
  return tags.length ? `<div class="topic-tabs">${tags.map(tag => `<span class="badge">${esc(tag)}</span>`).join("")}</div>` : "";
}
function renderWechat() {
  const items = state.topicsData?.sources?.wechat_inbox || [];
  $("#wechat").innerHTML = `<div class="workspace-intro"><div><span class="eyebrow">视频号选题Agent</span><h2>把微信里的灵感变成可回溯的选题快照</h2><p>采用“链接 / 文本 + 标签”协议。当前已支持手动入库；OpenClaw 和聊天卡片自动转发尚未接入。</p></div><span class="badge orange">手动入库可用</span></div><div class="workspace-columns"><article class="card"><div class="section-head"><div><h2>微信 ClawBot 接入指引</h2><p>后续可将同一份消息通过机器人送入本地服务</p></div></div><ol class="guide-list"><li>OpenClaw 官方渠道列表目前没有微信，不能当作现成微信接入；需要另做合规的微信机器人或自定义渠道，不使用来源不明的自动登录工具。</li><li>给机器人发送：<code>视频号链接 + 空格 + #精选</code>，也可使用 <code>#竞品</code>、<code>#高赞</code>、<code>#行业</code>。</li><li>机器人需要把原始链接、文本、标签和发送时间保存为快照；不要自动下载或公开转发他人内容。</li><li>当前聊天卡片转发的回调适配待完成。请先用右侧表单，保存后可打开原链接并创建视频任务。</li></ol><div class="button-row"><a class="button small" href="https://channels.weixin.qq.com/login.html" target="_blank" rel="noreferrer">打开视频号助手 ↗</a><a class="button small" href="https://docs.openclaw.ai/" target="_blank" rel="noreferrer">OpenClaw 官方文档 ↗</a></div><p class="muted">视频号助手与微信机器人不是同一登录体系。扫码和验证始终由你本人完成。</p></article><article class="card"><div class="section-head"><div><h2>保存一条微信消息</h2><p>保存的是研究快照，不代表内容已获转载授权</p></div></div><form id="wechat-message-form"><div class="field"><label for="wechat-url">视频号 / 公众号链接（可选）</label><input id="wechat-url" type="url" placeholder="https://"></div><div class="field"><label for="wechat-tag">标签</label><select id="wechat-tag"><option>精选</option><option>竞品</option><option>高赞</option><option>行业</option></select></div><div class="field"><label for="wechat-text">标题或灵感文本</label><textarea id="wechat-text" required maxlength="12000" placeholder="粘贴标题、口播文字或你自己的选题备注"></textarea></div><button class="button primary" type="submit">保存到视频号选题</button></form></article></div><div class="section-head"><div><h2>微信选题快照</h2><p>${items.length} 条 · 先研究原链接，再决定是否下载或创作</p></div></div>${itemTags(items)}<div class="hotspot-grid">${items.map(item => researchCard(item, false)).join("") || `<div class="empty"><strong>还没有微信消息</strong>使用上方表单保存第一条链接或灵感。</div>`}</div>`;
}
function renderXhs() {
  const items = state.topicsData?.sources?.xhs_notes || [];
  const account = state.accountData?.accounts?.find(item => item.platform === "xiaohongshu");
  $("#xiaohongshu").innerHTML = `<div class="workspace-intro"><div><span class="eyebrow">小红书选题Agent</span><h2>从创作者后台读取近期笔记</h2><p>读取自己账号的笔记元数据，不套用抖音收藏夹模型；不会自动下载视频。</p></div><span class="badge ${account ? "green" : "orange"}">${account ? `已同步 ${esc(account.captured_at)}` : "尚未同步"}</span></div><div class="action-panel"><div><strong>连接专用浏览器中的小红书创作者后台</strong><p>同步会同时尝试账号日报所需的抖音快照。需要登录时会明确提示，请在打开的专用窗口完成登录后重试。</p></div><div class="button-row"><button class="button" data-account-login="xiaohongshu">打开小红书登录窗口</button><button class="button primary" data-sync-accounts>同步小红书与账号</button></div></div>${(state.accountData?.jobs || []).slice(0, 3).map(workspaceJob).join("")}<div class="section-head"><div><h2>近期笔记快照</h2><p>${items.length} 条 · 阅读数缺失时保持未读取，不补造指标</p></div></div><div class="hotspot-grid">${items.map(item => researchCard(item, false)).join("") || `<div class="empty"><strong>尚未读取小红书笔记</strong>点击“同步小红书与账号”；页面结构变化时会返回具体错误。</div>`}</div>`;
}
function renderAccountDaily() {
  const data = state.accountData || {};
  const jobs = data.jobs || [];
  $("#accounts").insertAdjacentHTML("beforeend", `<div class="account-automation"><div class="section-head"><div><h2>每日自助分析与选题推荐</h2><p>每天 09:30 调度；先同步真实快照，再由账号分析Agent推荐，缺失指标保持空值</p></div><div class="button-row"><button class="button" data-sync-accounts>立即同步</button><button class="button primary" data-account-recommend ${data.accounts?.length ? "" : "disabled"}>生成账号选题推荐</button></div></div>${jobs.slice(0, 5).map(workspaceJob).join("")}<div class="grid cols-2 account-snapshots">${(data.accounts || []).map(account => `<article class="card"><div class="section-head"><div><h3>${esc(platformNames[account.platform] || account.platform)}</h3><p>${esc(account.captured_at)}</p></div><span class="badge green">真实快照</span></div><p>${esc(account.profile?.account_name || "账号名称未读取")}</p><small class="muted">${Object.entries(account.profile || {}).filter(([key]) => key !== "account_name").map(([key,value]) => `${esc(key)}：${fmt(value)}`).join(" · ") || "账号指标未读取"}</small></article>`).join("") || `<div class="empty">还没有自动同步的账号快照。上方手动录入的历史数据仍保留，不能冒充今日数据。</div>`}</div><div class="section-head"><div><h2>账号分析Agent推荐</h2><p>${data.recommendations?.length || 0} 条 · 事实、推断和实验分开</p></div></div><div class="topic-grid">${(data.recommendations || []).map(item => `<article class="card topic"><span class="badge green">账号分析Agent</span><h3>${esc(item.title)}</h3><p>${esc(item.reason)}</p><div class="evidence"><strong>建议切入</strong><p>${esc(item.angle)}</p>${(item.uncertainties || []).map(value => `<small>待核实：${esc(value)}</small>`).join("")}</div><small>${esc(item.created_at)}</small></article>`).join("") || `<div class="empty">同步后点击“生成账号选题推荐”；未同步时不生成无依据结论。</div>`}</div></div>`);
}
function approvedVideos() {
  return (state.data?.tasks || []).filter(task => task.state === "approved" && task.files.some(file => file.kind === "video"));
}
function renderPublishing() {
  const videos = approvedVideos();
  const previewJobs = (state.accountData?.jobs || []).filter(job => job.kind === "publish.douyin");
  $("#publish").innerHTML = `<div class="workspace-intro"><div><span class="eyebrow">发布Agent · 预览填充</span><h2>从已批准成片到平台发布预览</h2><p>只上传视频并尝试填写标题和简介；不会点击最终发布，不会替你记录不存在的发布链接。</p></div><span class="badge orange">最终由你确认</span></div><article class="card"><form id="publish-preview-form"><div class="field"><label for="publish-task">已人工批准的视频</label><select id="publish-task" required><option value="">请选择任务</option>${videos.map(task => `<option value="${task.content_id}">${esc(task.title)} · ${esc(task.content_id)}</option>`).join("")}</select></div><div class="form-grid publish-text-grid"><div class="field"><label for="publish-preview-title">实际发布标题</label><input id="publish-preview-title" maxlength="300" required placeholder="标题"></div><div class="field"><label for="publish-preview-description">简介</label><textarea id="publish-preview-description" required placeholder="实际发布简介与标签"></textarea></div></div><div class="button-row"><button class="button" type="button" data-account-login="douyin_publish">打开抖音发布后台登录</button><button class="button primary" type="submit" ${videos.length ? "" : "disabled"}>打开抖音发布预览</button></div><p class="muted">需要已登录的专用浏览器。返回“预览就绪”仅表示自动化步骤报告完成，你仍需在窗口中检查上传进度、文案和平台审核提示。</p></form></article>${!videos.length ? `<div class="empty"><strong>没有可发布的已批准成片</strong>请先在视频任务中完成渲染、五项质检和人工最终审核；不会绕过这些步骤。</div>` : ""}<div class="section-head"><div><h2>预览任务与结果</h2><p>公开发布结果请在视频任务中手动记录真实链接</p></div></div>${previewJobs.map(workspaceJob).join("") || `<div class="empty">尚未创建发布预览。</div>`}<details class="card manual-panel"><summary><strong>继续旧版发布与复盘</strong><span class="muted"> 在视频任务中保存各平台状态、真实链接和 2h / 1d / 3d / 7d 数据</span></summary><div class="task-list">${(state.data?.tasks || []).filter(task => ["approved","published","analyzed"].includes(task.state)).map(taskRow).join("") || `<p class="muted">暂无进入发布阶段的视频任务。</p>`}</div></details>`;
}
const articleStateNames = { brief_ready: "需求待完善", outline_draft: "大纲已保存", draft: "正文待审核", needs_review: "待补齐内容", in_review: "人工审核中", approved: "正文已批准", exported: "已导出", published: "已记录发布" };
function articleExport(item) {
  const revision = activeRevision(item, "export");
  const payload = revision?.payload || {};
  return revision ? `<div class="export-panel"><strong>已导出 Markdown + 安全 HTML</strong><div class="button-row"><a class="button small" href="/api/v2/assets/${payload.markdown_asset_id}/content?download=1">下载 Markdown</a><a class="button small" href="/api/v2/assets/${payload.html_asset_id}/content?download=1">下载 HTML</a></div></div>` : "";
}
function renderArticles() {
  if (state.articleData?.load_error) { $("#articles").innerHTML = `<div class="empty"><strong>文章服务读取失败</strong>${esc(state.articleData.load_error)}<br>请刷新页面重新建立本地会话；其他任务不受影响。</div>`; return; }
  const items = state.articleData?.items || [];
  const item = selectedArticle();
  if (item) state.articleId = item.id;
  const outline = activeRevision(item, "outline");
  const draft = activeRevision(item, "draft");
  $("#articles").innerHTML = `<div class="workspace-intro"><div><span class="eyebrow">文章Agent · 独立内容流</span><h2>从真实问题到可发布长文</h2><p>需求 → 大纲 → 正文 → 事实与结构审校 → 人工批准 → 导出 → 手动记录发布。文章不依赖音频、字幕或视频渲染。</p></div><button class="button primary" data-new-article>＋ 新建文章</button></div><div class="article-layout"><aside class="card article-sidebar"><button class="button small" data-sample-article>创建写作规范样例</button>${items.map(value => `<button class="task-select ${value.id === item?.id ? "active" : ""}" data-article-select="${value.id}"><strong>${esc(value.campaign.title)}</strong><small>${esc(articleStateNames[value.state] || value.state)} · v${value.version}</small></button>`).join("") || `<p class="muted">还没有文章任务。</p>`}</aside><section class="article-editor">${item ? `<div class="work-title"><div><span class="eyebrow">公众号文章 · ${esc(articleStateNames[item.state] || item.state)}</span><h2>${esc(item.campaign.title)}</h2><p>${esc(item.id)} · 当前版本 v${item.version}</p></div></div><div class="article-steps"><span>1 真实需求</span><span>2 论证大纲</span><span>3 正文</span><span>4 人工终审</span><span>5 导出发布</span></div><article class="card"><div class="section-head"><div><h3>文章要求</h3><p>文章Agent可在设置中单独配置提示词、模型变体和运行参数</p></div></div><div class="field"><label for="article-brief">补充要求（生成时作为本次输入，不覆盖其他 Agent）</label><textarea id="article-brief" placeholder="目标读者、真实场景、事实证据、不能出现的承诺">${esc(item.campaign.brief?.text || "")}</textarea></div></article><article class="card"><div class="section-head"><div><h3>一、论证大纲</h3><p>结论、场景、方法、边界和行动清单，避免堆砌工具名</p></div><button class="button small" data-article-generate="article.outline">文章Agent生成大纲</button></div><textarea id="article-outline" class="long-editor" placeholder="先形成大纲，或手动粘贴">${esc(outline?.payload?.text || "")}</textarea><button class="button small" data-save-article="outline">保存大纲</button></article><article class="card"><div class="section-head"><div><h3>二、完整正文</h3><p>生成后必须人工核查事实、案例、数字、来源和过度承诺</p></div><button class="button small" data-article-generate="article.draft" ${outline ? "" : "disabled"}>文章Agent生成正文</button></div><textarea id="article-draft" class="article-draft" placeholder="先保存大纲，再生成或编辑正文">${esc(draft?.payload?.text || "")}</textarea><div class="button-row"><button class="button small" data-save-article="draft">保存正文</button>${draft ? `<button class="button small" data-article-review>提交人工审核</button>` : ""}${draft && ["in_review","draft"].includes(item.state) ? `<button class="button primary small" data-article-approve>我已核查并批准当前正文</button>` : ""}${["approved","exported"].includes(item.state) ? `<button class="button primary small" data-article-export>导出当前正文</button>` : ""}</div>${articleExport(item)}</article>${(state.articleData?.jobs || []).filter(job => job.aggregate_id === item.id).slice(0,4).map(workspaceJob).join("")}<article class="card"><div class="section-head"><div><h3>手动记录公众号发布</h3><p>平台自动发布尚未接入；只有你实际发布后才能填写真实链接</p></div></div><form id="article-publish-form"><div class="field"><label for="article-publish-url">已发布文章 URL</label><input id="article-publish-url" type="url" required placeholder="https://mp.weixin.qq.com/..."></div><button class="button small" type="submit" ${item.active_revisions.export ? "" : "disabled"}>记录真实发布</button></form>${(item.publications || []).map(pub => `<p class="publication-link"><a href="${esc(pub.url)}" target="_blank" rel="noreferrer">${esc(pub.url)}</a> · ${esc(pub.published_at)}</p>`).join("")}</article>` : `<div class="empty"><strong>开始第一条独立文章任务</strong>可以新建真实主题，或先创建符合写作规范的样例。</div>`}</section></div>`;
}
function knowledgeEntity(entity) {
  const relations = (state.knowledgeData?.relations || []).filter(rel => (rel.source_id === entity.id || rel.target_id === entity.id));
  const entities = state.knowledgeData?.entities || [];
  const entityName = (type, id) => entities.find(item => item.type === type && item.id === id)?.name || id;
  const evidenceUrl = rel => rel.evidence?.url || (rel.target_type === "Evidence" ? entities.find(item => item.id === rel.target_id)?.summary : "");
  return `<article class="card knowledge-detail"><div class="section-head"><div><span class="badge green">${esc(entity.type)}</span><h2>${esc(entity.name)}</h2></div><button class="button small" data-close-knowledge>关闭</button></div><p>${esc(entity.summary || "暂无摘要")}</p><pre>${esc(JSON.stringify(entity.properties || {}, null, 2))}</pre><h3>关系与证据</h3>${relations.map(rel => `<div class="knowledge-relation"><strong>${esc(entityName(rel.source_type, rel.source_id))} → ${esc(rel.predicate)} → ${esc(entityName(rel.target_type, rel.target_id))}</strong><pre>${esc(JSON.stringify(rel.evidence || {}, null, 2))}</pre>${evidenceUrl(rel) ? `<a href="${esc(evidenceUrl(rel))}" target="_blank" rel="noreferrer">打开来源证据 ↗</a>` : ""}</div>`).join("") || `<p class="muted">该实体尚无关系。</p>`}</article>`;
}
function renderKnowledge() {
  const data = state.knowledgeData || {};
  if (data.load_error) { $("#knowledge").innerHTML = `<div class="empty">知识库读取失败：${esc(data.load_error)}</div>`; return; }
  const selected = data.entities?.find(item => item.id === state.knowledgeEntityId);
  $("#knowledge").innerHTML = `<div class="workspace-intro"><div><span class="eyebrow">账号 Ontology</span><h2>把定位、受众、痛点、证据和内容连成知识网络</h2><p>实体与关系保存在本地 SQLite；每条自动关系保留来源，研究证据可以回跳原链接。</p></div><button class="button primary" data-knowledge-backfill>同步现有数据到知识库</button></div><form id="knowledge-search-form" class="knowledge-toolbar"><input id="knowledge-query" class="inline-input" value="${esc(state.knowledgeQuery)}" placeholder="搜索实体或摘要"><select id="knowledge-type" class="inline-input"><option value="">全部类型</option>${(data.types || []).map(type => `<option value="${esc(type)}" ${state.knowledgeType === type ? "selected" : ""}>${esc(type)}</option>`).join("")}</select><button class="button" type="submit">搜索</button><span class="badge">${data.entities?.length || 0} 实体 · ${data.relations?.length || 0} 关系</span></form><div class="knowledge-layout"><section><div class="entity-grid">${(data.entities || []).map(entity => `<button class="entity-card ${selected?.id === entity.id ? "active" : ""}" data-knowledge-entity="${entity.id}"><span>${esc(entity.type)}</span><strong>${esc(entity.name)}</strong><small>${esc(entity.summary || "暂无摘要")}</small></button>`).join("") || `<div class="empty">没有匹配实体。可清空搜索，或点击同步现有数据。</div>`}</div><article class="card"><div class="section-head"><div><h2>编辑与审批规则</h2><p>由账号策略初始化，供文章、选题和审核共同复用</p></div></div><ul class="knowledge-rules">${(data.rules || []).map(rule => `<li>${esc(rule.name)}</li>`).join("")}</ul></article></section><aside>${selected ? knowledgeEntity(selected) : `<article class="card knowledge-help"><h2>查看实体详情</h2><p>选择左侧实体，查看它与受众、痛点、平台、证据及内容任务的关系。</p><p class="muted">自动回填使用稳定 ID，同一数据重复同步不会重复创建实体或相同证据关系。</p></article>`}</aside></div>`;
}
function renderWorkspaceViews() {
  if (!state.data) return;
  renderWechat(); renderXhs(); renderPublishing(); renderArticles(); renderKnowledge();
  if (state.accountData && typeof legacyRenderAccounts === "function") { legacyRenderAccounts(); renderAccountDaily(); }
}
const legacyRefresh = refresh;
refresh = async function(message) {
  await legacyRefresh();
  await refreshWorkspaces(false);
  renderWorkspaceViews();
  if (message) notify(message);
};
const legacyRenderAll = renderAll;
renderAll = function() { legacyRenderAll(); renderWorkspaceViews(); };
const legacyRenderAccounts = renderAccounts;
renderAccounts = function() { legacyRenderAccounts(); renderAccountDaily(); };
const legacySwitchView = switchView;
switchView = function(view) {
  let actual = view;
  if (["industry","douyin"].includes(view)) {
    state.topicView = view === "douyin" ? "hot" : "industry";
    state.topicDetail = null; view = "topics"; renderTopics();
  }
  legacySwitchView(view);
  if (view === "topics" && !["industry","douyin"].includes(actual)) actual = state.topicView === "industry" ? "industry" : "douyin";
  if (workspaceTitles[actual]) $("#view-title").textContent = workspaceTitles[actual];
  $("#new-task-top").style.visibility = view === "topics" ? "hidden" : "visible";
};
document.addEventListener("click", async event => {
  const button = event.target.closest("button");
  if (!button || button.disabled) return;
  if (button.dataset.articleSelect) { state.articleId = button.dataset.articleSelect; renderArticles(); }
  else if (button.hasAttribute("data-new-article")) {
    const title = window.prompt("文章主题：要为目标用户解决什么具体问题？");
    if (!title?.trim()) return;
    await workspaceAction(() => api("/api/articles", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: title.trim() }) }), "文章任务已创建");
  } else if (button.hasAttribute("data-sample-article")) await workspaceAction(() => api("/api/articles", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ sample: true }) }), "写作规范样例已创建");
  else if (button.dataset.saveArticle) {
    const item = selectedArticle(); const kind = button.dataset.saveArticle;
    const text = $(kind === "outline" ? "#article-outline" : "#article-draft").value;
    await workspaceAction(() => api(`/api/articles/${item.id}/revisions`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ kind, payload: { text, format: "markdown" }, expected_version: item.version }) }), `${kind === "outline" ? "大纲" : "正文"}已保存为新版本`);
  } else if (button.dataset.articleGenerate) {
    const item = selectedArticle();
    await workspaceAction(() => api(`/api/articles/${item.id}/generate`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ operation: button.dataset.articleGenerate, prompt: $("#article-brief").value, expected_version: item.version }) }), "文章Agent已加入后台；完成后刷新查看新版本");
  } else if (button.hasAttribute("data-article-review")) {
    const item = selectedArticle();
    await workspaceAction(() => api(`/api/articles/${item.id}/actions`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "submit_review", expected_version: item.version }) }), "已提交人工审核");
  } else if (button.hasAttribute("data-article-approve")) {
    const item = selectedArticle(); const draft = activeRevision(item, "draft");
    await workspaceAction(() => api(`/api/articles/${item.id}/actions`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "approve", revision_id: draft.id, manifest_hash: item.manifest.hash }) }), "当前正文已人工批准");
  } else if (button.hasAttribute("data-article-export")) {
    const item = selectedArticle(); const draft = activeRevision(item, "draft");
    await workspaceAction(() => api(`/api/articles/${item.id}/export`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ revision_id: draft.id, expected_version: item.version }) }), "文章导出已加入后台");
  } else if (button.hasAttribute("data-sync-accounts")) await workspaceAction(() => api("/api/accounts/sync", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }), "账号同步已加入后台，请在专用窗口处理登录");
  else if (button.dataset.accountLogin) await workspaceAction(() => api("/api/accounts/browser/open", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ platform: button.dataset.accountLogin }) }), "专用登录窗口正在打开，请在 5 分钟内完成扫码，再返回重新同步");
  else if (button.hasAttribute("data-account-recommend")) await workspaceAction(() => api("/api/accounts/recommend", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }), "账号分析Agent已加入后台");
  else if (button.hasAttribute("data-knowledge-backfill")) await workspaceAction(() => api("/api/knowledge/backfill", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }), "知识库已同步；稳定实体与关系不会重复创建");
  else if (button.dataset.knowledgeEntity) { state.knowledgeEntityId = button.dataset.knowledgeEntity; renderKnowledge(); }
  else if (button.hasAttribute("data-close-knowledge")) { state.knowledgeEntityId = null; renderKnowledge(); }
});
document.addEventListener("submit", async event => {
  if (!["wechat-message-form","publish-preview-form","article-publish-form","knowledge-search-form"].includes(event.target.id)) return;
  event.preventDefault();
  if (event.target.id === "wechat-message-form") {
    const ok = await workspaceAction(() => api("/api/topics/wechat/messages", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url: $("#wechat-url").value, tag: $("#wechat-tag").value, text: $("#wechat-text").value }) }), "微信选题快照已保存");
    if (ok) { await refreshTopics(false); renderWechat(); }
  } else if (event.target.id === "publish-preview-form") {
    const task = state.data.tasks.find(item => item.content_id === $("#publish-task").value);
    const video = task?.files.find(file => file.kind === "video");
    if (!video) return notify({ message: "当前任务没有成片", field: "publish-task", action: "重新选择已批准且包含 MP4 的任务" }, true);
    await workspaceAction(() => api("/api/publish/douyin/preview", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ video_path: video.relative_path, title: $("#publish-preview-title").value, description: $("#publish-preview-description").value }) }), "发布预览已提交；不会自动点击最终发布");
  } else if (event.target.id === "article-publish-form") {
    const item = selectedArticle(); const draft = activeRevision(item, "draft");
    await workspaceAction(() => api(`/api/articles/${item.id}/publish`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ revision_id: draft.id, url: $("#article-publish-url").value }) }), "真实发布链接已记录");
  } else {
    state.knowledgeQuery = $("#knowledge-query").value;
    state.knowledgeType = $("#knowledge-type").value;
    await workspaceAction(async () => { state.knowledgeData = await api(`/api/knowledge/bootstrap?q=${encodeURIComponent(state.knowledgeQuery)}&type=${encodeURIComponent(state.knowledgeType)}`); }, "知识库筛选已更新");
  }
});
document.addEventListener("change", async event => {
  if (event.target.id !== "publish-task") return;
  const task = state.data.tasks.find(item => item.content_id === event.target.value);
  const record = task?.publications?.douyin || {};
  $("#publish-preview-title").value = record.title || task?.title || "";
  $("#publish-preview-description").value = record.description || task?.scripts?.douyin?.slice(0, 500) || "";
});
refreshWorkspaces().catch(error => notify(error, true));
setInterval(async () => {
  if (!["accounts","xiaohongshu","publish","articles"].includes(state.view) || state.workspaceBusy || ["INPUT","TEXTAREA"].includes(document.activeElement?.tagName)) return;
  const jobs = [...(state.accountData?.jobs || []), ...(state.articleData?.jobs || [])];
  const active = jobs.some(job => ["queued","leased","running","retry_wait"].includes(job.status));
  if (!active && !state.workspaceWasBusy) return;
  state.workspaceWasBusy = active;
  try {
    await refreshWorkspaces(false);
    if (state.view === "accounts") renderAccounts();
    else if (state.view === "xiaohongshu") renderXhs();
    else if (state.view === "publish") renderPublishing();
    else if (state.view === "articles") renderArticles();
  } catch (_) {}
}, 3000);
