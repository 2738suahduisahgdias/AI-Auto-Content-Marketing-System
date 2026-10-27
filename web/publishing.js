Object.assign(state, { publishing: { articleBatch: null, videoBatch: null, articleSource: null, videoSource: null, videoId: null, busy: false, coverUploading: false } });
const publishingStatusNames = { draft: "待预览", preparing: "预览执行中", ready: "待确认", publishing: "发布执行中", published: "已发布", failed: "失败", unknown_remote: "待人工核对" };
function publishingSource(kind) {
  if (kind === "article") {
    const item = selectedArticle();
    if (!item || !["approved", "exported"].includes(item.state)) return null;
    const draft = activeRevision(item, "draft");
    return { id: item.id, title: item.campaign.title, body: draft?.payload?.text || "", hash: item.manifest.hash };
  }
  const task = approvedVideos().find(item => item.content_id === state.publishing.videoId) || approvedVideos()[0];
  if (!task) return null;
  state.publishing.videoId = task.content_id;
  return { id: task.content_id, title: task.title, body: task.publications?.douyin?.description || task.scripts?.douyin || task.scripts?.master || task.title, hash: task.updated_at };
}
async function loadPublishingBatch(kind, render = true) {
  const source = publishingSource(kind);
  const sourceKey = kind + "Source";
  if (!source) { state.publishing[sourceKey] = null; state.publishing[kind + "Batch"] = null; if (render) renderPublishingViews(kind); return; }
  if (state.publishing[sourceKey] === source.id && state.publishing[kind + "Batch"]) return;
  state.publishing[sourceKey] = source.id;
  try {
    const data = await api(`/api/publishing/bootstrap?kind=${kind}&source_id=${encodeURIComponent(source.id)}`);
    state.publishing[kind + "Batch"] = data.batch;
  } catch (error) {
    state.publishing[kind + "Batch"] = { load_error: error.message };
  }
  if (render) renderPublishingViews(kind);
}
function renderPublishingViews(kind) {
  if (kind === "video") renderPublishing();
  else renderArticlePublishing();
}
function targetPayload(batch, platform) {
  return batch?.targets?.find(target => target.platform === platform)?.payload || {};
}
function targetStatus(batch, platform) {
  return batch?.targets?.find(target => target.platform === platform);
}
function publishingTarget(kind, platform, source) {
  const batch = state.publishing[kind + "Batch"];
  const existing = targetStatus(batch, platform);
  const payload = targetPayload(batch, platform);
  const supported = kind === "article" || platform !== "wechat_channels";
  const title = payload.title || source.title || "";
  const body = payload[kind === "article" ? "body" : "description"] || source.body || "";
  const status = existing?.status || "draft";
  return `<article class="publishing-target ${existing ? "has-batch" : ""}" data-platform="${platform}" data-kind="${kind}"><div class="publishing-target-head"><label class="check"><input type="checkbox" class="publish-target-enabled" ${status === "published" || !supported ? "disabled" : "checked"}><strong>${platformNames[platform]}${kind === "article" && platform === "xiaohongshu" ? "长文" : "视频"}</strong></label><span class="badge ${status === "published" ? "green" : status === "ready" ? "orange" : status === "failed" || status === "unknown_remote" ? "red" : ""}">${publishingStatusNames[status] || status}</span></div>${!supported ? `<p class="muted">视频号字段待登录验证，当前不能加入发布批次。</p>` : ""}<button class="button small" type="button" data-publishing-login="${platform}">打开专用登录窗口</button><div class="field"><label>发布标题</label><input data-field="title" maxlength="${platform === "wechat_official_account" ? 64 : 300}" value="${esc(title)}"></div>${kind === "article" && platform === "wechat_official_account" ? `<div class="form-grid publishing-author-grid"><div class="field"><label>作者（最多 8 字）</label><input data-field="author" maxlength="8" value="${esc(payload.author || "刘量")}"></div><div class="field"><label>摘要（最多 120 字，可留空）</label><textarea data-field="summary" maxlength="120">${esc(payload.summary || body.slice(0, 120))}</textarea></div></div><div class="field"><label>封面（必传，仅保存为本地资产）</label><input type="file" accept=".png,.jpg,.jpeg,.webp" data-publishing-cover="${kind}"><input type="hidden" data-field="cover_asset_id" value="${esc(payload.cover_asset_id || "")}"><span class="hint" data-cover-label>${payload.cover_asset_id ? "已关联封面资产" : "尚未上传封面"}</span></div>` : ""}<div class="field"><label>${kind === "article" ? "正文" : "简介"}</label><textarea class="publishing-body" data-field="${kind === "article" ? "body" : "description"}">${esc(body)}</textarea></div>${kind === "video" ? `<div class="field"><label>标签</label><input data-field="tags" value="${esc(payload.tags || "#企业AI #AI应用")}"></div>` : ""}${existing?.error ? `<div class="settings-error"><strong>${esc(existing.error.code || "发布失败")}</strong><p>${esc(existing.error.message)}</p><p>怎么改：${esc(existing.error.action || "检查平台登录与字段后重试")}</p></div>` : ""}${existing?.preview?.screenshot ? `<p class="muted">预览证据：${esc(existing.preview.screenshot)}</p>` : ""}${existing?.external_url ? `<a class="button small" href="${esc(existing.external_url)}" target="_blank" rel="noreferrer">查看已发布内容 ↗</a>` : ""}${status === "failed" ? `<button class="button small" type="button" data-publishing-retry="${existing.id}">重新生成预览</button>` : ""}</article>`;
}
function publishingBatchActions(kind, batch) {
  if (!batch || batch.load_error) return "";
  const ready = batch.targets?.filter(target => target.status === "ready") || [];
  return `<div class="publishing-actions"><button class="button" type="button" data-publishing-prepare="${kind}">生成选中平台预览</button><button class="button primary" type="button" data-publishing-confirm="${kind}" ${ready.length ? "" : "disabled"}>确认发布选中平台（公开）</button><span class="muted">批次 ${esc(batch.id)} · ${ready.length} 个平台待确认</span></div>`;
}
function renderPublishing() {
  const source = publishingSource("video");
  const batch = state.publishing.videoBatch;
  $("#publish").innerHTML = `<div class="workspace-intro"><div><span class="eyebrow">视频发布Agent · 独立视频任务</span><h2>一次确认，多平台发布视频</h2><p>只使用人工批准的 MP4。先上传并核验预览，再由你确认公开；每个平台独立记录结果。</p></div><span class="badge orange">预览不等于已发布</span></div><article class="card publishing-source"><div class="field"><label for="publishing-video-task">已批准的视频任务</label><select id="publishing-video-task"><option value="">请选择</option>${approvedVideos().map(task => `<option value="${task.content_id}" ${task.content_id === state.publishing.videoId ? "selected" : ""}>${esc(task.title)} · ${esc(task.content_id)}</option>`).join("")}</select></div>${source ? `<p class="muted">${esc(source.title)} · 不会使用文章正文、音频或 SRT 代替成片</p>` : `<div class="empty">没有已批准的视频。先在视频任务完成成片、质检与人工最终审核。</div>`}</article>${source ? `<form id="video-publish-batch-form"><div class="publishing-targets">${["douyin", "xiaohongshu", "wechat_channels"].map(platform => publishingTarget("video", platform, source)).join("")}</div><button class="button primary" type="submit">保存视频发布批次</button></form>${publishingBatchActions("video", batch)}` : ""}${batch?.load_error ? `<div class="settings-error">${esc(batch.load_error)}</div>` : ""}<details class="card manual-panel"><summary><strong>旧版手动发布与复盘</strong><span class="muted"> 保留真实链接和分时段数据记录</span></summary><div class="task-list">${(state.data?.tasks || []).filter(task => ["approved", "published", "analyzed"].includes(task.state)).map(taskRow).join("") || `<p class="muted">暂无进入发布阶段的视频任务。</p>`}</div></details>`;
}
function renderArticlePublishing() {
  const container = $(".article-editor");
  if (!container) return;
  container.querySelector(".article-publishing")?.remove();
  const source = publishingSource("article");
  if (!source) return;
  if (state.publishing.articleSource !== source.id) {
    state.publishing.articleSource = source.id;
    state.publishing.articleBatch = null;
    loadPublishingBatch("article");
    return;
  }
  const batch = state.publishing.articleBatch;
  container.insertAdjacentHTML("beforeend", `<section class="article-publishing"><div class="section-head"><div><h2>文章发布：公众号与小红书长文</h2><p>只使用当前已审批正文，与视频任务完全分开。预览完成后，由你一次确认公开。</p></div><span class="badge orange">文章专用</span></div><form id="article-publish-batch-form"><div class="publishing-targets">${["wechat_official_account", "xiaohongshu"].map(platform => publishingTarget("article", platform, source)).join("")}</div><button class="button primary" type="submit">保存文章发布批次</button></form>${publishingBatchActions("article", batch)}${batch?.load_error ? `<div class="settings-error">${esc(batch.load_error)}</div>` : ""}</section>`);
}
function collectPublishingTargets(form, kind) {
  return $$(".publishing-target", form).filter(card => $(".publish-target-enabled", card).checked && !$(".publish-target-enabled", card).disabled).map(card => {
    const payload = {};
    $$('[data-field]', card).forEach(input => payload[input.dataset.field] = input.value);
    return { platform: card.dataset.platform, payload };
  });
}
async function publishingRequest(path, method, payload) {
  return api(path, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload || {}) });
}
async function publishingAction(kind, action, success) {
  if (state.publishing.busy) return;
  state.publishing.busy = true;
  try {
    const result = await action();
    const data = await api(`/api/publishing/bootstrap?kind=${kind}&source_id=${encodeURIComponent(publishingSource(kind).id)}`);
    state.publishing[kind + "Batch"] = data.batch;
    renderPublishingViews(kind);
    if (success) notify(success);
    return result;
  } catch (error) { notify(error, true); return null; }
  finally { state.publishing.busy = false; }
}
const baseRenderArticlesForPublishing = renderArticles;
renderArticles = function() { baseRenderArticlesForPublishing(); renderArticlePublishing(); };
const baseRefreshWorkspacesForPublishing = refreshWorkspaces;
refreshWorkspaces = async function(render = true) {
  await baseRefreshWorkspacesForPublishing(render);
  await Promise.all([loadPublishingBatch("article", false), loadPublishingBatch("video", false)]);
  if (render) { renderPublishing(); renderArticlePublishing(); }
};
document.addEventListener("change", async event => {
  if (event.target.id === "publishing-video-task") {
    state.publishing.videoId = event.target.value;
    state.publishing.videoSource = null; state.publishing.videoBatch = null;
    await loadPublishingBatch("video");
  }
  if (event.target.matches("[data-publishing-cover]")) {
    const input = event.target;
    const file = input.files[0];
    if (!file) return;
    const card = input.closest(".publishing-target");
    const kind = input.dataset.publishingCover;
    state.publishing.coverUploading = true;
    const label = $("[data-cover-label]", card);
    label.textContent = "正在上传并保存封面…";
    try {
      const asset = await api(`/api/v2/assets?filename=${encodeURIComponent(file.name)}&purpose=publish_cover&rights=owned`, { method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: file });
      $("[data-field='cover_asset_id']", card).value = asset.id;
      label.textContent = `已保存封面：${file.name}`;
      notify("封面已保存为本地资产，创建批次时会再次校验");
    } catch (error) { label.textContent = "封面上传失败：" + (error.action || error.message); notify(error, true); }
    finally { state.publishing.coverUploading = false; }
  }
});
document.addEventListener("click", async event => {
  const button = event.target.closest("button");
  if (!button || button.disabled) return;
  if (button.dataset.publishingLogin) {
    try { await publishingRequest(`/api/publishing/connections/${button.dataset.publishingLogin}/login`, "POST"); notify("专用登录窗口正在打开，5 分钟内完成登录后返回重新预览"); }
    catch (error) { notify(error, true); }
  } else if (button.dataset.publishingPrepare) {
    const kind = button.dataset.publishingPrepare;
    const batch = state.publishing[kind + "Batch"];
    await publishingAction(kind, () => publishingRequest(`/api/publishing/batches/${batch.id}/prepare`, "POST", {}), "平台预览已加入队列，不会公开发布");
  } else if (button.dataset.publishingConfirm) {
    const kind = button.dataset.publishingConfirm;
    const batch = state.publishing[kind + "Batch"];
    const platforms = batch.targets.filter(target => target.status === "ready").map(target => target.platform);
    if (!window.confirm(`即将公开发布到 ${platforms.map(platform => platformNames[platform]).join("、")}。请确认你已检查预览、文案、封面和账号。此操作会对外公开，是否继续？`)) return;
    await publishingAction(kind, () => publishingRequest(`/api/publishing/batches/${batch.id}/confirm`, "POST", { source_hash: batch.source_hash, platforms }), "一键发布已确认，正在逐平台执行");
  } else if (button.dataset.publishingRetry) {
    const kind = button.closest(".publishing-target").dataset.kind;
    await publishingAction(kind, () => publishingRequest(`/api/publishing/targets/${button.dataset.publishingRetry}/retry`, "POST"), "已重新加入预览队列");
  }
});
document.addEventListener("submit", async event => {
  if (!["video-publish-batch-form", "article-publish-batch-form"].includes(event.target.id)) return;
  event.preventDefault();
  const kind = event.target.id.startsWith("video") ? "video" : "article";
  const source = publishingSource(kind);
  const targets = collectPublishingTargets(event.target, kind);
  if (!targets.length) return notify("至少选择一个已支持的发布平台", true);
  await publishingAction(kind, () => publishingRequest("/api/publishing/batches", "POST", { content_kind: kind, source_id: source.id, targets }), "发布批次已保存，下一步生成平台预览");
});
setInterval(async () => {
  for (const kind of ["article", "video"]) {
    const batch = state.publishing[kind + "Batch"];
    if (!batch || state.publishing.busy || ["INPUT", "TEXTAREA"].includes(document.activeElement?.tagName)) continue;
    const active = batch.targets?.some(target => ["preparing", "publishing"].includes(target.status));
    const wasActive = state.publishing[kind + "WasActive"];
    if (!active && !wasActive) continue;
    state.publishing[kind + "WasActive"] = active;
    try {
      const data = await api(`/api/publishing/bootstrap?kind=${kind}&source_id=${encodeURIComponent(publishingSource(kind)?.id || "")}`);
      state.publishing[kind + "Batch"] = data.batch;
      if (state.view === "publish" && kind === "video") renderPublishing();
      if (state.view === "articles" && kind === "article") renderArticlePublishing();
    } catch (_) {}
  }
}, 3000);
loadPublishingBatch("article");
loadPublishingBatch("video");
