import {useEffect, useState} from 'react';
import {Link, useNavigate} from 'react-router-dom';
import {useApp} from '@/AppContext';
import {Button, Card, Empty, ErrorBox, PageHeader} from '@/components/ui';
import WorkOverview from '@/components/WorkOverview';
import {Recommendations} from './Topics';
import {api, errorText, jsonOptions} from '@/lib/api';
import type {Json, TopicItem} from '@/lib/types';
import './Topics.css';

export default function Today(){
 const {resources,refresh,notify}=useApp();const navigate=useNavigate();
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[selected,setSelected]=useState(''),[history,setHistory]=useState(false);
 const topics:Json=resources?.topics||{};
 const recommendations:Json[]=topics.recommendations?.all||[];
 const sources=Object.values(topics.sources||{}).flat() as TopicItem[];
 const active=(topics.jobs||[]).find((j:Json)=>j.kind==='topics.recommend'&&j.aggregate_id==='all'&&['queued','leased','running','retry_wait'].includes(j.status));
 const latest=(topics.jobs||[]).find((j:Json)=>j.kind==='topics.recommend'&&j.aggregate_id==='all');
 useEffect(()=>{if(!active)return;const timer=setInterval(()=>void refresh(),3000);return()=>clearInterval(timer)},[active?.id,refresh]);
 useEffect(()=>{const visible=()=>{if(!document.hidden)void refresh()};document.addEventListener('visibilitychange',visible);return()=>document.removeEventListener('visibilitychange',visible)},[refresh]);
 const current=recommendations.find(r=>r.id===selected)||recommendations[0];
 const candidates:Json[]=resources?.core.topics||[];
 async function perform(action:()=>Promise<Json>,message:string){if(busy)return;setBusy(true);setError('');try{const result=await action();await refresh();notify(message);return result}catch(e){setError(errorText(e))}finally{setBusy(false)}}
 async function convert(item:Json){if(item.status==='converted'&&item.task_id){navigate(`/tasks/${item.task_id}`);return;}const task=await perform(()=>api(`/api/topics/candidates/${encodeURIComponent(item.id)}/create-task`,jsonOptions('POST')),'已保留推荐依据并创建视频任务');if(task)navigate(`/tasks/${task.content_id}`)}
 async function article(item:Json){const result=await perform(()=>api('/api/articles',jsonOptions('POST',{title:item.title,brief:{text:`选题：${item.title}\n推荐依据：${item.reason}\n切入：${item.angle}\n来源：${sources.filter(s=>(item.evidence_ids||[]).includes(s.id)).map(s=>s.url).join('\n')}`}})),'已将选题与来源带入文章');if(result)navigate(`/articles/${result.id}`)}
 return <><PageHeader eyebrow="TODAY / CONTENT WORKSPACE" title="今天" description="选择值得做的选题，继续制作，处理审核与发布。"/>
 <div className="section-heading"><div><h2>今日推荐</h2><p>综合抖音、小红书、微信 / 视频号与行业来源，参考品牌规则及增长记忆。</p></div><Button variant="primary" disabled={busy||!!active} onClick={()=>void perform(()=>api('/api/topics/recommend',jsonOptions('POST',{agent:'all'})),'已开始综合推荐，完成后自动更新')}>{active?'正在生成今日推荐…':'生成今日推荐'}</Button></div>
 {error&&<ErrorBox>{error}</ErrorBox>}{!active&&latest?.status==='failed'&&<ErrorBox>{latest.error?.message||'今日推荐生成失败'}<p>{latest.error?.action||'检查模型连接后点击生成今日推荐重试；已有推荐保留。'}</p></ErrorBox>}
 {recommendations.length?<div className="today-selection"><div className="today-selection-list">{recommendations.map(item=><button key={item.id} aria-pressed={current?.id===item.id} onClick={()=>setSelected(item.id)}>{item.title}<small>{item.content_format==='article'?'建议文章':'建议视频'} · {item.memory_basis||'查看推荐依据'}</small></button>)}</div><div>{current&&<><Recommendations items={[current]} agent="all" sources={sources} busy={busy} onConvert={item=>void convert(item)} onArticle={item=>void article(item)}/></>}</div></div>:<Empty title="生成一份跨平台今日推荐" description="先在选题中心同步内容。这里会结合真实来源与记忆给出推荐，不用在每个平台重复生成。" action={<Link className="button" to="/topics/douyin">去选题中心</Link>}/>}
 <WorkOverview contentOnly/>
 <div className="section-heading"><div><h2>候选选题</h2><p>保留原系统候选，开始创作时沿用原有任务流程。</p></div>{candidates.length>5&&<Button size="small" onClick={()=>setHistory(!history)}>{history?'收起历史':'查看历史'}</Button>}</div>
 <div className="today-candidates">{(history?candidates:candidates.slice(0,5)).map(item=><Card className="today-candidate" key={item.id}><div><h3>{item.title}</h3><p>{item.script_angle}</p></div><Button disabled={busy} onClick={()=>void perform(()=>api('/api/tasks',jsonOptions('POST',{topic_id:Number(item.id)})),'已从原候选创建任务').then(task=>{if(task)navigate(`/tasks/${task.content_id}`)})}>开始创作</Button></Card>)}</div>{!candidates.length&&<Empty title="还没有历史候选选题" description="可从推荐或已采集内容开始。"/>}
 </>;
}
