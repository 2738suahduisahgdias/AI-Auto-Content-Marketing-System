import ArticleImageTools from "./ArticleImageTools";
import ArticleImagePicker from "./ArticleImagePicker";
import {useState} from 'react';
import {Link} from 'react-router-dom';
import {Button,Card} from './ui';
type Picture={id:number;position:string;method:string;description:string;asset_id?:string;after_paragraph?:number};
export type CreativePlan={platform:string;purpose:string;pictures:Picture[];format:string};
export const defaultCreativePlan=():CreativePlan=>({platform:'公众号',purpose:'',pictures:[],format:'可编辑图文正文'});
export const normalizeCreativePlan=(value?:Partial<CreativePlan>):CreativePlan=>({...defaultCreativePlan(),...value,pictures:(value?.pictures||[]).map((row,index)=>Object.assign({id:index+1,position:'正文配图',method:'使用自己的图片',description:''},row))});
export default function ArticleCreativePlan({stage,onApply,disabled,plan,onChange,onSave}:{stage:'write'|'images'|'delivery';onApply:(text:string)=>void;disabled:boolean;plan:CreativePlan;onChange:(plan:CreativePlan)=>void;onSave:()=>void}) {
 const {platform,purpose,pictures,format}=plan;
 const setPlatform=(value:string)=>onChange({...plan,platform:value,format:value==='公众号'?'可编辑图文正文':'文字笔记'});
 const setPurpose=(value:string)=>onChange({...plan,purpose:value});
 const setFormat=(value:string)=>onChange({...plan,format:value});
 const setPictures=(update:(rows:Picture[])=>Picture[])=>onChange({...plan,pictures:update(pictures)});
 const [notice,setNotice]=useState('');
 const update=(id:number,patch:Partial<Picture>)=>setPictures(rows=>rows.map(row=>row.id===id?{...row,...patch}:row));
 return <>
 <Button disabled={disabled} onClick={onSave}>保存正文与配图计划</Button>
 <Card className="article-creative-plan" hidden={stage!=='write'}><h3>主要平台与写作目的</h3><div className="article-plan-grid"><label>主要平台<select value={platform} onChange={e=>{setPlatform(e.target.value)}}><option>公众号</option><option>小红书</option></select></label><label>这篇内容希望达到什么目的？<input className="input" value={purpose} onChange={e=>setPurpose(e.target.value)} placeholder="例如：让门店老板理解 AI 客服能解决什么"/></label></div><Button disabled={disabled} onClick={()=>{onApply(`主要平台：${platform}。写作目的：${purpose||'清楚讲解主题'}。按平台独立组织标题、正文和结尾，不编造事实。`);setNotice('已加入写作要求，尚未启动生成。')}}>加入写作要求</Button><p role="status">{notice}</p><p className="article-plan-boundary">平台、目的、图片计划和交付形式随正文保存为本地版本；修改后原审批失效。另一平台独立版本尚未接通。</p></Card>
 <Card className="article-creative-plan" hidden={stage!=='images'}><div className="article-card-head"><div><h2>按段落配图片</h2><p>每个位置分别选择找图、生图或自己的图片，可以混用；也可以不配图。</p></div><Button onClick={()=>setPictures(rows=>[...rows,{id:Date.now(),position:'',method:'搜索现成图片',description:''}])}>添加配图位置</Button></div>
 {!pictures.length&&<div className="article-plan-preview">还没有配图计划。需要图片时添加位置，纯文字内容可以直接进入排版交付。</div>}
 {pictures.map((row,index)=><section className="article-picture-plan" key={row.id}><div className="article-card-head"><h3>配图 {index+1}</h3><Button onClick={()=>setPictures(rows=>rows.filter(x=>x.id!==row.id))}>移除位置</Button></div><div className="article-plan-grid"><label>对应段落或用途<input className="input" value={row.position} onChange={e=>update(row.id,{position:e.target.value})} placeholder="封面 / 第 2 节：工作流程"/></label><label>获取方式<select value={row.method} onChange={e=>update(row.id,{method:e.target.value})}><option>搜索现成图片</option><option>AI 生成示意图</option><option>使用自己的图片</option></select></label></div><label>画面描述 / 搜索词 / 生图提示词<textarea className="textarea" value={row.description} onChange={e=>update(row.id,{description:e.target.value})} placeholder="描述图片需要说明什么；真实案例优先用截图或真实素材"/></label><label>插入到第几段之后（0 为正文之前，空行分段）<input className="input" type="number" min="0" value={row.after_paragraph||0} onChange={e=>update(row.id,{after_paragraph:Number(e.target.value)})}/></label><ArticleImageTools method={row.method} prompt={row.description} disabled={disabled} onSelect={asset_id=>update(row.id,{asset_id})}/><ArticleImagePicker key={row.asset_id||"empty"} assetId={row.asset_id} disabled={disabled} onSelect={asset_id=>update(row.id,{asset_id})}/><p className="article-plan-boundary">{row.method==='搜索现成图片'?'搜索会显示候选与来源，下载后保存到本地。':row.method==='AI 生成示意图'?'生图复用本机 Codex CLI 登录；这里只发送本位置的提示词。':'本地图片默认引用原文件；采用后保存正文，导出时会验证文件内容。'}</p></section>)}
 <p className="article-plan-boundary">配图计划可随正文保存；已采用的本地图片随正文绑定并参与版本审核；搜图和生图结果保存到原素材库。未采用图片的位置仅是计划，不会写入导出。</p></Card>
 <Card className="article-creative-plan" hidden={stage!=='delivery'}><h2>排版与交付</h2><p>当前规划平台：{platform}。先检查阅读效果，再将完整图文版本交给审核与发布 Agent。</p><div className="article-plan-grid"><label>交付形式<select value={format} onChange={e=>setFormat(e.target.value)}>{(platform==='公众号'?['可编辑图文正文','分页长文图片','正文与图片']:['文字笔记','分页图文卡片','文字与图片']).map(x=><option key={x}>{x}</option>)}</select></label></div><div className="article-plan-preview"><strong>{platform} · {format} · 结构示意</strong><p>{platform==='公众号'?'封面 → 标题与摘要 → 导语 → 分节正文与插图 → 行动建议':'封面标题 → 开头吸引点 → 分段正文或分页卡片 → 结尾互动 → 话题'}</p><p>已规划 {pictures.length} 个图片位置，已采用 {pictures.filter(p=>p.asset_id).length} 张图片。HTML 导出包含图片，图文包包含正文和原图；选择分页格式后，导出会同时生成本地 PNG 页面。</p></div><p className="article-plan-boundary">分页图在本地生成，依赖 Pillow 和中文字体；下方提供自包含 HTML 和图文 ZIP 包；Markdown 单独下载不含图片文件。已绑定图片与正文一起审核，换图或修改位置后保存会使旧审批失效。</p></Card>
 <p className="article-plan-boundary">文案 Agent 统筹写作，图片搜索、生图、排版由独立技能执行。<Link to="/settings/agents">查看 Agent 配置与接入说明</Link></p>
 </>;
}
