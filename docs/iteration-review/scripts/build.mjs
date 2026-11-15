import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const directory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const data = JSON.parse(fs.readFileSync(path.join(directory, 'data/pages.json'), 'utf8'));
const iterations = JSON.parse(fs.readFileSync(path.join(directory, 'data/iterations.json'), 'utf8'));
const featureCount = data.pages.reduce((total, page) => total + page.cards.reduce((count, card) => count + card.rows.length, 0), 0);
const escape = value => String(value ?? '').replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]);
const list = values => `<ul>${values.map(value => `<li>${escape(value)}</li>`).join('')}</ul>`;
const table = (headers, rows) => `<div class="table-wrap"><table><thead><tr>${headers.map(header => `<th>${escape(header)}</th>`).join('')}</tr></thead><tbody>${rows.map(row => `<tr>${row.map(cell => `<td>${escape(cell)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;

const pageHtml = page => `<article class="review-page" id="page-${escape(page.id)}" data-page="${escape(page.id)}" hidden>
  <header class="page-title"><span class="page-number">${String(page.order).padStart(2, '0')}</span><div><p class="eyebrow">PAGE REVIEW</p><h1>${escape(page.title)}</h1><p>${escape(page.purpose)}</p></div></header>
  <a class="screenshot-link" href="${escape(page.screenshot)}" target="_blank" rel="noreferrer"><img src="${escape(page.screenshot)}" alt="${escape(page.title)}实际页面截图" loading="lazy"><span>点击放大实际页面截图</span></a>
  <p class="evidence">${escape(page.evidence)}</p>
  <section><h2>一、页面信息</h2>${table(['项目', '内容'], [
    ['一级页面', page.title], ['页面入口', page.route], ['页面用途', page.purpose], ['外部依赖与边界', page.dependencies], ['截图与功能证据', page.evidence],
  ])}</section>
  <section><h2>二、页面结构与评审顺序</h2>${table(['顺序', '卡片编号', '二级卡片／工作区', '首先核对的功能'], page.overview.map((item, index) => [item.order, page.cards[index]?.id, item.card, item.task]))}</section>
  <section><h2>三、卡片详细说明</h2>${page.cards.map((card, index) => `<details class="card-detail" open><summary><span>${escape(card.id)}</span>${escape(card.title)}<small>${card.rows.length} 项</small></summary>${table(['功能编号与卡片元素', '功能描述与限制', '功能背后调用的技术方案'], card.rows.map(row => [`${row.id} · ${row.element}`, row.description, row.technology]))}</details>`).join('')}</section>
  <section><h2>四、本页状态与异常表现</h2>${table(['页面状态', '应该看到什么', '技术来源与评审要点'], page.states.map(item => [item.state, item.expected, item.technology]))}</section>
  <section><h2>五、本页 review 检查清单</h2><div class="checklist">${page.checklist.map((item, index) => `<label><input type="checkbox" data-review="${escape(page.id)}:${index}"><span>${escape(item)}</span></label>`).join('')}</div></section>
  <section><h2>六、本页技术索引</h2>${table(['层级', '当前实现'], page.technology.map(item => item))}</section>
  <div class="page-break"></div>
</article>`;

const iterationHtml = record => `<article class="iteration-record" id="iteration-${escape(record.id)}"><p class="eyebrow">ITERATION RECORD</p><h2>${escape(record.title)}</h2><p class="record-date">${escape(record.date)} · <a href="#iteration-${escape(record.id)}">查看本次记录</a></p><p>${escape(record.summary)}</p><details open><summary>本次变更</summary>${list(record.changes)}</details><details open><summary>已验证</summary>${list(record.verification)}</details><details open><summary>未验证与边界</summary>${list(record.unverified)}</details><details><summary>相关文件</summary>${list(record.files)}</details></article>`;

const html = `<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${escape(data.title)}</title>
<style>
:root{--bg:#f5f4ef;--surface:#fff;--ink:#252922;--muted:#6f746a;--line:#dedfd6;--accent:#8a3d29;--accent-soft:#f1e5df;--green:#42634d;--sidebar:292px}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.72 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}a{color:var(--accent);text-decoration:none}button,input{font:inherit}button{cursor:pointer}.topbar{position:sticky;top:0;z-index:20;display:flex;align-items:center;gap:16px;padding:14px 24px;background:rgba(245,244,239,.96);border-bottom:1px solid var(--line);backdrop-filter:blur(14px)}.brand{margin-right:auto}.brand strong{display:block;font-size:18px}.brand small{color:var(--muted)}.search{width:min(390px,35vw);padding:10px 14px;border:1px solid var(--line);border-radius:8px;background:var(--surface)}.button{padding:9px 13px;border:1px solid var(--line);border-radius:8px;background:var(--surface);color:var(--ink)}.button:hover,.button.active{border-color:var(--accent);color:var(--accent)}.layout{display:grid;grid-template-columns:var(--sidebar) minmax(0,1fr);max-width:1800px;margin:auto}.sidebar{position:sticky;top:77px;height:calc(100vh - 77px);overflow:auto;padding:22px 14px 40px;border-right:1px solid var(--line)}.sidebar h2{padding:0 10px;font-size:13px;letter-spacing:.12em;color:var(--muted)}.nav-button{display:flex;width:100%;gap:10px;align-items:baseline;padding:8px 10px;border:0;border-radius:7px;background:transparent;text-align:left;color:var(--muted)}.nav-button span{color:#9a9d94;font-variant-numeric:tabular-nums}.nav-button:hover,.nav-button.active{background:var(--accent-soft);color:var(--accent)}main{min-width:0;padding:34px clamp(20px,4vw,64px) 80px}.review-page{max-width:1280px;margin:auto}.page-title{display:flex;gap:20px;align-items:flex-start;margin-bottom:24px}.page-number{display:grid;place-items:center;flex:0 0 54px;height:54px;border:1px solid var(--accent);border-radius:50%;color:var(--accent);font-size:20px}.eyebrow{margin:0 0 4px;color:var(--accent);font-size:11px;letter-spacing:.16em}.page-title h1{margin:0;font-size:34px;line-height:1.25}.page-title p:last-child{margin:7px 0 0;color:var(--muted);font-size:16px}.screenshot-link{display:block;overflow:hidden;border:1px solid var(--line);border-radius:12px;background:var(--surface)}.screenshot-link img{display:block;width:100%;max-height:780px;object-fit:contain;background:#eee}.screenshot-link span{display:block;padding:10px 14px;color:var(--muted);font-size:13px}.evidence{margin:12px 0 28px;color:var(--muted);font-size:13px}section{margin:36px 0}h2{margin:0 0 14px;font-size:23px}h3{font-size:18px}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:10px;background:var(--surface)}table{width:100%;border-collapse:collapse;table-layout:fixed}th,td{padding:12px 14px;border-bottom:1px solid var(--line);vertical-align:top;text-align:left;overflow-wrap:anywhere}th{background:#eeeee7;color:#555c50;font-size:13px;font-weight:600}tr:last-child td{border-bottom:0}td:first-child{font-weight:550}td:last-child{color:#515b50;font-size:13px}.card-detail{margin:14px 0;border:1px solid var(--line);border-radius:10px;background:var(--surface)}.card-detail>summary{display:flex;gap:12px;align-items:center;padding:15px 17px;cursor:pointer;font-size:17px;font-weight:650;list-style:none}.card-detail>summary::-webkit-details-marker{display:none}.card-detail>summary span{color:var(--accent);font-size:12px;font-weight:500}.card-detail>summary small{margin-left:auto;color:var(--muted);font-weight:400}.card-detail .table-wrap{margin:0 14px 14px}.checklist{display:grid;gap:8px}.checklist label{display:flex;gap:12px;padding:12px 14px;border:1px solid var(--line);border-radius:8px;background:var(--surface);cursor:pointer}.checklist input{flex:0 0 auto;margin-top:6px;accent-color:var(--green)}.checklist input:checked+span{color:var(--muted);text-decoration:line-through}.iteration-record{max-width:1000px;margin:0 auto 32px;padding:26px;border:1px solid var(--line);border-radius:12px;background:var(--surface)}.iteration-record h2{margin:4px 0}.record-date{color:var(--muted)}.iteration-record details{margin:18px 0}.iteration-record summary{cursor:pointer;font-weight:650}.empty-search{padding:60px;text-align:center;color:var(--muted)}.page-break{height:20px;border-bottom:1px solid var(--line)}.footer{max-width:1280px;margin:40px auto 0;color:var(--muted);font-size:12px}.mobile-nav{display:none}@media(max-width:900px){.layout{display:block}.sidebar{position:static;height:auto;border-right:0;border-bottom:1px solid var(--line)}.sidebar nav{display:grid;grid-template-columns:repeat(2,1fr)}.topbar{flex-wrap:wrap;padding:10px 14px}.brand{flex:1 0 100%}.search{width:100%;order:3}main{padding:24px 14px 60px}.page-title h1{font-size:28px}th,td{min-width:150px}.screenshot-link img{max-height:520px}}@media print{.topbar,.sidebar,.screenshot-link span,.footer{display:none!important}.layout{display:block}main{padding:0}.review-page[hidden]{display:none!important}.review-page{max-width:none}.page-break{break-after:page}.card-detail{break-inside:auto}.card-detail>summary{display:flex}.table-wrap{overflow:visible}table{font-size:11px}th,td{min-width:0;padding:7px}section{margin:22px 0}body{background:white;font-size:12px}@page{margin:14mm}}
</style>
</head>
<body>
<header class="topbar"><div class="brand"><strong>${escape(data.title)}</strong><small>基线 ${escape(data.baseline)} · ${data.pages.length} 个页面单元 · ${featureCount} 条功能说明</small></div><input class="search" id="search" type="search" placeholder="搜索页面、卡片、按钮、限制或技术" aria-label="搜索全部功能"><button class="button" id="show-all">展开全部</button><button class="button" id="show-iterations">迭代记录</button><button class="button" id="print">打印</button></header>
<div class="layout"><aside class="sidebar"><h2>逐页功能评审</h2><nav id="navigation">${data.pages.map(page => `<button class="nav-button" data-target="${escape(page.id)}"><span>${String(page.order).padStart(2, '0')}</span>${escape(page.title)}</button>`).join('')}</nav></aside><main id="content"><div id="pages">${data.pages.map(pageHtml).join('')}</div><div id="iterations" hidden>${iterations.map(iterationHtml).join('')}</div><div class="empty-search" id="empty-search" hidden>没有匹配的页面或功能。请缩短关键词后重试。</div><p class="footer">${escape(data.scope)} 所有资料均在本机；不上传页面、截图、勾选状态或任何凭据。</p></main></div>
<script>
const pages=[...document.querySelectorAll('.review-page')];
const navButtons=[...document.querySelectorAll('.nav-button')];
const pageContainer=document.getElementById('pages');
const iterationContainer=document.getElementById('iterations');
const search=document.getElementById('search');
const emptySearch=document.getElementById('empty-search');
let currentPage='today';
let allPages=false;
let iterationMode=false;
function showPage(id,updateHash=true){
  iterationMode=false;iterationContainer.hidden=true;pageContainer.hidden=false;allPages=false;
  currentPage=pages.some(page=>page.dataset.page===id)?id:'today';
  for(const page of pages)page.hidden=page.dataset.page!==currentPage;
  for(const button of navButtons)button.classList.toggle('active',button.dataset.target===currentPage);
  document.getElementById('show-all').classList.remove('active');document.getElementById('show-iterations').classList.remove('active');
  emptySearch.hidden=true;search.value='';
  if(updateHash)location.hash='page='+currentPage;
  window.scrollTo({top:0,behavior:'instant'});
}
function showAll(){iterationMode=false;iterationContainer.hidden=true;pageContainer.hidden=false;allPages=true;for(const page of pages)page.hidden=false;for(const button of navButtons)button.classList.remove('active');document.getElementById('show-all').classList.add('active');document.getElementById('show-iterations').classList.remove('active');location.hash='all';window.scrollTo({top:0,behavior:'instant'})}
function showIterations(updateHash=true){iterationMode=true;pageContainer.hidden=true;iterationContainer.hidden=false;for(const record of iterationContainer.querySelectorAll('.iteration-record'))record.hidden=false;emptySearch.hidden=true;search.value='';for(const button of navButtons)button.classList.remove('active');document.getElementById('show-all').classList.remove('active');document.getElementById('show-iterations').classList.add('active');if(updateHash)location.hash='iterations';window.scrollTo({top:0,behavior:'instant'})}
function showIteration(id){showIterations(false);const record=document.getElementById(id);if(!record)return;for(const item of iterationContainer.querySelectorAll('.iteration-record'))item.hidden=item!==record;location.hash=id;window.scrollTo({top:0,behavior:'instant'})}
for(const button of navButtons)button.addEventListener('click',()=>showPage(button.dataset.target));
document.getElementById('show-all').addEventListener('click',showAll);
document.getElementById('show-iterations').addEventListener('click',()=>showIterations());
document.getElementById('print').addEventListener('click',()=>window.print());
search.addEventListener('input',()=>{
  const query=search.value.trim().toLocaleLowerCase();if(!query){if(iterationMode)showIterations();else if(allPages)showAll();else showPage(currentPage,false);return}
  iterationMode=false;iterationContainer.hidden=true;pageContainer.hidden=false;allPages=true;
  let matches=0;for(const page of pages){const matched=page.textContent.toLocaleLowerCase().includes(query);page.hidden=!matched;if(matched)matches++}
  for(const button of navButtons)button.classList.remove('active');emptySearch.hidden=matches>0;
});
for(const checkbox of document.querySelectorAll('[data-review]')){
  const key='yingxu-review:'+checkbox.dataset.review;checkbox.checked=localStorage.getItem(key)==='1';
  checkbox.addEventListener('change',()=>localStorage.setItem(key,checkbox.checked?'1':'0'));
}
function route(){if(location.hash==='#all')showAll();else if(location.hash==='#iterations')showIterations();else if(location.hash.startsWith('#iteration-'))showIteration(location.hash.slice(1));else showPage(location.hash.startsWith('#page=')?location.hash.slice(6):'today',false)}
window.addEventListener('hashchange',route);
route();
</script>
</body></html>`;
fs.writeFileSync(path.join(directory, 'index.html'), html);
console.log(`已生成 ${path.join(directory, 'index.html')}；${data.pages.length} 个页面单元；${iterations.length} 次迭代记录`);
