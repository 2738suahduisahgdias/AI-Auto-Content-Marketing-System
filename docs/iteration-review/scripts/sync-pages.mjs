import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const source = fs.readFileSync(path.join(root, 'docs/FUNCTION_MATRIX.md'), 'utf8');
const rows = [];
let section = '';
for (const line of source.split('\n')) {
  const heading = line.match(/^## (\d+)\./);
  if (heading) { section = heading[1]; continue; }
  if (!line.startsWith('|') || line.startsWith('|---') || line.includes('一级：页面')) continue;
  const cells = line.slice(1, -1).split('|').map(value => value.trim());
  if (cells.length === 5) rows.push({ section, page: cells[0], card: cells[1], element: cells[2], description: cells[3], technology: cells[4] });
}

const definitions = [
  ['global', '全局导航与数据层', '全部新版页面', '理解整套工作台的导航、数据加载和精简资源准备', '本地服务与授权状态；精简版另需下载资源', 'today.png'],
  ['today', '今天', '/demo/', '生成并选择今日推荐，继续文章、视频、审核和发布准备', '推荐生成需要真实来源和模型；其他区域只读汇总', 'today.png'],
  ['industry', '行业热点', '/demo/topics/industry', '同步公开行业资讯，收藏推荐并转为文章或视频', '网络与公开资讯来源；推荐生成需要模型', 'industry.png'],
  ['douyin', '抖音选题', '/demo/topics/douyin', '同步抖音热点与个人收藏，拆解视频并转成内容任务', '专用 Chrome、本人抖音登录、收藏夹名称；下载与模型按需', 'douyin.png'],
  ['wechat', '微信选题', '/demo/topics/wechat', '保存和整理微信消息，生成研究快照并转内容任务', '微信 Bot 或手动记录；公开链接解析受目标页面限制', 'wechat.png'],
  ['xiaohongshu', '小红书选题', '/demo/topics/xiaohongshu', '同步个人收藏，查看笔记研究并转为内容任务', '专用 Chrome、本人小红书登录、收藏夹名称与网络', 'xiaohongshu.png'],
  ['articles', '文章任务列表', '/demo/articles', '搜索、筛选、新建并打开文章', '本地 SQLite；新建只创建任务，不自动生成', 'articles.png'],
  ['article-editor', '文章编辑器', '/demo/articles/:id', '完成写作要求、大纲、正文、图片、审核和导出', '模型、真实图片、Pillow／Remotion 导出环境；审批绑定版本', 'article-editor.png'],
  ['projects', '视频项目首页', '/demo/projects', '搜索、筛选、新建和继续原创／对标项目', '本地项目记录；旧项目 ID 与交付状态保留', 'projects.png'],
  ['original', '原创项目', '/demo/projects/original[/:id]', '从文案、旁白、音乐、分镜到样片、成片和审核交付', '模型、Whisper、Remotion、FFmpeg；各阶段有前置门槛', 'original.png'],
  ['benchmark', '对标项目', '/demo/projects/benchmark[/:id]', '拆解真实参考视频，逐镜替换、处理音乐并合成审核交付', '真实视频、模型、Whisper、Remotion、FFmpeg 和使用授权', 'benchmark.png'],
  ['legacy-editor', '旧视频编辑器', '/demo/tasks/:id/editor', '继续使用旧六阶段流程和原版本记录', '旧任务、素材、媒体工具和版本状态；不强制迁移', 'legacy-editor.png'],
  ['review', '短视频审核中心', '/demo/review', '读取本地视频，技术预审、AI 风险证据和人工终审', 'FFmpeg／FFprobe；OCR／模型按需；原文件不覆盖', 'review.png'],
  ['publish', '发布中心', '/demo/publish', '接收审核成果，编辑平台字段、预填、排期和结果核对', '审核来源、模型、专用 Chrome；预填不等于公开发布', 'publish.png'],
  ['knowledge', '增长记忆大脑', '/demo/knowledge', '维护有效经验、避坑记录和知识关系，供选题参考', '真实证据与效果数据；待验证不能冒充成功规律', 'knowledge.png'],
  ['collection', '采集知识库', '/demo/knowledge/collection', '查看各平台采集规则、字段和验证边界', '规则契约是说明，不证明当前登录或实时同步', 'collection.png'],
  ['publish-knowledge', '发布知识库', '/demo/knowledge/publishing', '查看平台独立字段、长度和组合限制', '契约驱动字段生成；保存字段不表示已写入平台', 'publish-knowledge.png'],
  ['settings-agents', 'Agent 配置', '/demo/settings/agents', '独立配置 Agent 引擎、模型、提示词和执行参数', '未接入能力不能启用；保存只影响新任务', 'settings-agents.png'],
  ['settings-models', '模型连接', '/demo/settings/models', '配置默认文本模型并执行真实连接测试', 'Kimi／Codex CLI 或模型 API、账号和网络', 'settings-models.png'],
  ['settings-media', '本地媒体', '/demo/settings/media', '管理素材、工具路径、缓存、迁移和本地媒体能力', '本地文件、模型环境、磁盘空间；高风险操作需新目录', 'settings-media.png'],
  ['settings-templates', '视频模板', '/demo/settings/templates', '查看真实模板并管理稳定、草稿和停用状态', '模板注册表与真实预览；状态影响之后制作', 'settings-templates.png'],
  ['settings-data', '数据与隐私', '/demo/settings/data', '查看本地数据、模型输入和人工审核边界', '说明页，不提供清空或删除业务数据操作', 'settings-data.png'],
  ['activation', '离线授权', '/demo/activation', '复制安装申请码、导入授权文件并验证激活', 'OpenSSL 3 Ed25519、安装身份、公钥配置；申请码截图需隐藏', 'activation.png'],
  ['welcome', '新手引导', '/demo/welcome', '检查存储和环境，创建第一条视频或文章样例', '必需授权模式下先激活；示例只创建真实本地任务', 'welcome.png'],
  ['setup', '接入向导', '/demo/setup', '检查环境、启动专用 Chrome、连接微信和平台账号', 'Chrome、Playwright、模型、微信及平台本人登录', 'setup.png'],
  ['legacy', '旧版工作台', '/legacy', '保留旧版导航和原任务、账号、发布、设置入口', '原生 JS 与旧接口；数据口径需与新版分开核查', 'legacy.png'],
];

function assign(row) {
  const page = row.page;
  if (row.section === '1') return page === '全局框架' ? ['global'] : ['today'];
  if (row.section === '2') {
    if (page.startsWith('行业热点')) return ['industry'];
    if (page.startsWith('抖音 ')) return ['douyin'];
    if (page.startsWith('小红书 ')) return ['xiaohongshu'];
    if (page.startsWith('微信 ')) return ['wechat'];
    if (page === '行业／抖音／小红书') return ['industry', 'douyin', 'xiaohongshu'];
    if (page === '抖音作品卡') return ['douyin'];
  }
  if (row.section === '3') return page === '文章列表 `/articles`' || page === '新建文章弹窗' ? ['articles'] : ['article-editor'];
  if (row.section === '4') {
    if (page.startsWith('视频项目')) return ['projects'];
    if (page === '原创／对标') return ['original', 'benchmark'];
    if (page.startsWith('原创')) return ['original'];
    if (page.startsWith('对标')) return ['benchmark'];
  }
  if (row.section === '5') return ['legacy-editor'];
  if (row.section === '6') return ['review'];
  if (row.section === '7') return ['publish'];
  if (row.section === '8') {
    if (page.startsWith('增长记忆')) return ['knowledge'];
    if (page.startsWith('采集知识')) return ['collection'];
    return ['publish-knowledge'];
  }
  if (row.section === '9') {
    if (page.startsWith('Agent 配置')) return ['settings-agents'];
    if (page.startsWith('模型连接')) return ['settings-models'];
    if (page.startsWith('本地媒体')) return ['settings-media'];
    if (page.startsWith('视频模板')) return ['settings-templates'];
    return ['settings-data'];
  }
  if (row.section === '10') return page.startsWith('离线授权') ? ['activation'] : ['welcome'];
  if (row.section === '11') return ['setup'];
  if (row.section === '12') return ['legacy'];
  throw new Error('未分配 ' + JSON.stringify(row));
}

const technologyBySection = {
  '1': [['前端', 'Today.tsx、AppShell.tsx、WorkOverview.tsx'], ['接口', '/api/topics/recommend、/api/v2/work-overview、/api/tasks'], ['数据', 'tasks、wb_content_items、review_items、publish_targets、增长记忆']],
  '2': [['前端', 'Topics.tsx、TopicCard.tsx、WechatInbox.tsx'], ['服务', 'TopicService、TopicExecutors、WechatInboxService、专用 Chrome'], ['数据', '研究快照、候选、tasks.source_json、wb_jobs、本地媒体资产']],
  '3': [['前端', 'Articles.tsx、ArticleCreativePlan.tsx、ArticleImageTools.tsx'], ['服务', 'Workbench、ArticleExecutors、ProviderRegistry、Workbench.export_article'], ['数据', 'wb_campaigns、wb_content_items、wb_revisions、wb_approvals、wb_assets']],
  '4': [['前端', 'videoProjects/*.tsx、useVideoProject.ts'], ['服务', 'app.py 项目接口、专用 Chrome、Kimi/本地媒体引擎'], ['数据', 'tasks、files、source_json.yingxu、review_deliveries、renders']],
  '5': [['前端', 'Tasks.tsx、VideoStages.tsx'], ['服务', 'app.py 原任务状态机、媒体 worker、Remotion/FFmpeg'], ['数据', 'tasks、files、video_variants、source_json、wb_jobs']],
  '6': [['前端', 'Review.tsx'], ['服务', 'ReviewService、ReviewExecutors、review/schemas.py'], ['数据', 'review_batches、review_items、review_deliveries、本地原文件与新输出']],
  '7': [['前端', 'Publish.tsx、PublishingPanel.tsx、ScheduleSettings.tsx'], ['服务', 'PublishingService、PublishingExecutors、ScheduleService、专用 Chrome'], ['数据', 'publish_batches、publish_targets、publish_schedules、publish_queue']],
  '8': [['前端', 'Knowledge.tsx、GrowthMemory.tsx、CollectionKnowledge.tsx、PublishKnowledge.tsx'], ['服务', 'KnowledgeService、collection_ontology、publishing/contracts.py'], ['数据', 'growth_memories、kb_entities、kb_rules、kb_relations、机器契约']],
  '9': [['前端', 'Settings.tsx 及设置共享组件'], ['服务', 'agents/registry、providers、media/tools、storage/portable、render_cache'], ['数据', 'settings.agent_configs、config/*.json、wb_assets、工作区工具与缓存']],
  '10': [['前端', 'Activation.tsx、Welcome.tsx'], ['服务', 'LicenseService、licensing/protocol、Workbench'], ['数据', 'license/state.json、installationId、onboarding、项目记录']],
  '11': [['前端', 'Setup.tsx、WechatConnection.tsx、PublishingPanel.tsx'], ['服务', 'accounts/setup、accounts/dedicated_browser、accounts/local_browser、wechat_client'], ['数据', '工作区固定 Chrome Profile、wb_jobs、平台登录结果']],
  '12': [['前端', 'web/index.html、web/app.js、web/workspaces.js'], ['服务', '原 app.py 与旧版接口'], ['数据', '旧 tasks、账号、发布和设置记录']],
};

const pages = definitions.map(([id, title, route, purpose, dependencies, screenshot], index) => {
  const own = rows.filter(row => assign(row).includes(id));
  const groups = new Map();
  for (const row of own) {
    if (!groups.has(row.card)) groups.set(row.card, []);
    groups.get(row.card).push({ element: row.element, description: row.description, technology: row.technology });
  }
  const cards = [...groups].map(([cardTitle, items], cardIndex) => {
    const cardId = `P${String(index + 1).padStart(2, '0')}-C${String(cardIndex + 1).padStart(2, '0')}`;
    return {
      id: cardId,
      title: cardTitle,
      rows: items.map((row, rowIndex) => ({ ...row, id: `${cardId}-F${String(rowIndex + 1).padStart(2, '0')}` })),
    };
  });
  return {
    id, order: index + 1, title, route, purpose, dependencies,
    screenshot: `assets/screenshots/${screenshot}`,
    evidence: id === 'original' ? '2026-11-15 已在隔离工作区验证手写与 AI 双路径；AI 使用 Kimi CLI 2.5.1、default_unpinned 当前默认模型，真实生成候选并保存视频号与横屏参数。' : '截图为隔离工作区真实页面；动态卡片和有数据状态按当前源码核对，未在本轮重新执行全部生成、同步或发布。',
    overview: cards.map((card, cardIndex) => ({ order: cardIndex + 1, card: card.title, task: card.rows[0]?.description || '查看与操作' })),
    cards,
    states: [
      { state: '首次加载', expected: '显示真实加载状态，不用空白或演示数据冒充完成', technology: 'AppContext / 当前页面 API 并发读取' },
      { state: '空数据或无权限', expected: '保留可用入口并说明下一步；未接入能力保持禁用或明确提示', technology: '空状态来自真实接口；LicenseGate 与执行器状态约束' },
      { state: '操作执行中', expected: '对应按钮显示进行中并防重复提交；离开页面后后台任务按原机制保留', technology: 'busy/active 前端状态 + wb_jobs / 本地执行器' },
      { state: '操作失败或外部不可用', expected: '显示具体错误和处理建议，保留已有内容与文件，不伪报成功', technology: '结构化 DomainError / 任务 error_json / 页面 ErrorBox' },
      { state: '有真实记录', expected: '按卡片显示真实 ID、来源、版本或文件；操作进入原记录', technology: dependencies },
    ],
    checklist: [
      ...cards.map(card => `核对“${card.title}”中的控件效果、输入限制、禁用条件和技术调用是否一致。`),
      '核对空状态、加载中、执行中、失败及有数据状态是否都能区分。',
      '核对本页没有把预填、保存、登录、生成或上传误写成公开发布或真实验收通过。',
    ],
    technology: technologyBySection[own[0]?.section || '1'],
  };
});

const output = {
  title: '映序逐页功能评审与迭代记录',
  baseline: '2026-11-11',
  scope: '当前新版主要路由、旧视频编辑器与旧版入口；未挂载的历史组件不计为当前页面。',
  pages,
};
const directory = path.join(root, 'docs/iteration-review/data');
fs.mkdirSync(directory, { recursive: true });
fs.writeFileSync(path.join(directory, 'pages.json'), JSON.stringify(output, null, 2));
const markdownCell = value => String(value).replaceAll('|', '／');
const indexMarkdown = ['# 映序功能编号索引', '', '编号规则：`P页码-C卡序号-F功能序号`。页面和卡片顺序与离线评审一致；修改内容时保留原编号，新增功能追加新编号。', ...pages.flatMap(page => [
  '',
  `## P${String(page.order).padStart(2, '0')} ${page.title}`,
  '',
  '| 功能编号 | 卡片 | 卡片元素和功能 |',
  '|---|---|---|',
  ...page.cards.flatMap(card => card.rows.map(row => `| ${row.id} | ${markdownCell(card.title)} | ${markdownCell(row.element)} |`)),
])];
fs.writeFileSync(path.join(root, 'docs/FUNCTION_IDS.md'), indexMarkdown.join('\n') + '\n');
console.log(`页面 ${pages.length}；功能行 ${pages.reduce((total, page) => total + page.cards.reduce((count, card) => count + card.rows.length, 0), 0)}`);
