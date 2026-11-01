import {useState} from 'react';
import {Link} from 'react-router-dom';
import {Button,Card} from './ui';
type Picture={id:number;position:string;method:string;description:string};
export type CreativePlan={platform:string;purpose:string;pictures:Picture[];format:string};
export const defaultCreativePlan=():CreativePlan=>({platform:'公众号',purpose:'',pictures:[],format:'可编辑图文正文'});
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
 {pictures.map((row,index)=><section className="article-picture-plan" key={row.id}><div className="article-card-head"><h3>配图 {index+1}</h3><Button onClick={()=>setPictures(rows=>rows.filter(x=>x.id!==row.id))}>移除位置</Button></div><div className="article-plan-grid"><label>对应段落或用途<input className="input" value={row.position} onChange={e=>update(row.id,{position:e.target.value})} placeholder="封面 / 第 2 节：工作流程"/></label><label>获取方式<select value={row.method} onChange={e=>update(row.id,{method:e.target.value})}><option>搜索现成图片</option><option>AI 生成示意图</option><option>使用自己的图片</option></select></label></div><label>画面描述 / 搜索词 / 生图提示词<textarea className="textarea" value={row.description} onChange={e=>update(row.id,{description:e.target.value})} placeholder="描述图片需要说明什么；真实案例优先用截图或真实素材"/></label><p className="article-plan-boundary">{row.method==='搜索现成图片'?'待接图片搜索：展示候选、原始来源和使用信息，由你确认采用。':row.method==='AI 生成示意图'?'待接生图模型：展示提示词、费用和结果，不能用生成图冒充真实案例证据。':'待接本地选图：默认引用原文件，支持预览、替换和外接硬盘重定位。'}</p></section>)}
 <p className="article-plan-boundary">配图计划可随正文保存；实际图片的搜索、生成和正文绑定仍待接入。计划不会被当成已完成的图片。</p></Card>
 <Card className="article-creative-plan" hidden={stage!=='delivery'}><h2>排版与交付</h2><p>当前规划平台：{platform}。先检查阅读效果，再将完整图文版本交给审核与发布 Agent。</p><div className="article-plan-grid"><label>交付形式<select value={format} onChange={e=>setFormat(e.target.value)}>{(platform==='公众号'?['可编辑图文正文','分页长文图片','正文与图片']:['文字笔记','分页图文卡片','文字与图片']).map(x=><option key={x}>{x}</option>)}</select></label></div><div className="article-plan-preview"><strong>{platform} · {format} · 结构示意</strong><p>{platform==='公众号'?'封面 → 标题与摘要 → 导语 → 分节正文与插图 → 行动建议':'封面标题 → 开头吸引点 → 分段正文或分页卡片 → 结尾互动 → 话题'}</p><p>已规划 {pictures.length} 个图片位置，尚无已确认图片。正式预览将支持字号、分页、逐图替换与阅读顺序检查。</p></div><p className="article-plan-boundary">平台专用排版与长图导出待接本地渲染技能；下方仅保留现有 Markdown / HTML 真实交付。图文联合审批待开发，改稿、换图或修改关键排版后应重新确认。</p></Card>
 <p className="article-plan-boundary">文案 Agent 统筹写作，图片搜索、生图、排版由独立技能执行。<Link to="/settings/agents">查看 Agent 配置与接入说明</Link></p>
 </>;
}
