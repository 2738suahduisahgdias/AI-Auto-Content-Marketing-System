import {useEffect,useRef,useState} from 'react';
import {Link,useLocation,useNavigate,useParams} from 'react-router-dom';
import {useApp} from '../AppContext';
import {api,jsonOptions} from '../lib/api';
import type {Task} from '../lib/types';
import BoundYingxu from './BoundYingxu';
import './yingxu-native.css';
import './workspace.css';
export default function YingxuVideoWorkspace(){
 const {resources,refresh}=useApp();const {id}=useParams();const navigate=useNavigate();const location=useLocation();
 const [panel,setPanel]=useState<'projects'|'create'|null>(null);const [title,setTitle]=useState('');const [search,setSearch]=useState('');const [error,setError]=useState('');const [busy,setBusy]=useState(false);
 const saveCurrent=useRef<null|(()=>Promise<unknown>)>(null);
 const tasks=[...((resources?.core.tasks||[]) as Task[])].sort((a,b)=>b.updated_at.localeCompare(a.updated_at));
 const selected=tasks.find(task=>task.content_id===id);
 useEffect(()=>{if(!id&&tasks[0])navigate('/tasks/'+tasks[0].content_id,{replace:true})},[id,tasks[0]?.content_id,navigate]);
 useEffect(()=>setPanel(null),[location.key]);
 async function create(){setBusy(true);setError('');try{if(selected)await saveCurrent.current?.();const task=await api<Task>('/api/tasks',jsonOptions('POST',{title:title.trim(),content:'',source_type:'topic'}));await refresh();setPanel(null);setTitle('');navigate('/tasks/'+task.content_id)}catch(cause){setError(cause instanceof Error?cause.message:'创建失败')}finally{setBusy(false)}}
 if(!resources)return null;
 return <div className="yingxu-video-page">
 {selected?<BoundYingxu key={selected.content_id} task={selected} onOpenProjects={()=>setPanel('projects')} onNewProject={()=>setPanel('create')} onSaveReady={save=>{saveCurrent.current=save}}/>:<div className="yx-native"><section className="panel pad"><div className="eyebrow">映序 · 视频创作</div><h1>{id?'未找到这个视频':'开始你的第一条视频'}</h1><p>从一份文案开始，把想法变成可制作的分镜。</p><div className="actions"><button className="btn primary" onClick={()=>setPanel('create')}>新建视频</button><button className="btn" onClick={()=>setPanel('projects')}>打开已有视频</button><Link className="btn" to="/topics/douyin">从原选题开始</Link></div></section></div>}
 {panel&&<div className="yx-native"><div className="video-modal-backdrop" role="dialog" aria-modal="true" aria-label={panel==='projects'?'切换视频项目':'新建视频'}><section className="video-modal panel pad"><div className="section-head"><h2>{panel==='projects'?'我的视频':'新建视频'}</h2><button className="btn" disabled={busy} onClick={()=>setPanel(null)}>关闭</button></div>
 {panel==='projects'?<><input className="field" aria-label="搜索视频项目" placeholder="搜索视频名称或编号" value={search} onChange={e=>setSearch(e.target.value)}/><div className="video-project-list">{tasks.filter(task=>(task.title+task.content_id).toLowerCase().includes(search.toLowerCase())).map(task=><Link className="video-project-item" key={task.content_id} to={'/tasks/'+task.content_id} onClick={()=>setPanel(null)}><strong>{task.title}</strong><small>{task.content_id} · {(task as any).source?.yingxu_handoff?.stale?'修改后待重新交付':(task as any).source?.yingxu_handoff?'已交付发布工作区':'继续创作'}</small><span>打开 →</span></Link>)}</div><button className="btn primary" onClick={()=>setPanel('create')}>＋ 新建视频</button></>:<><p>先给视频起个名字，再进入映序编辑文案、选择场景和编排分镜。</p><label className="field-label" htmlFor="new-video-title">视频名称</label><input id="new-video-title" className="field" value={title} maxLength={200} onChange={e=>setTitle(e.target.value)} placeholder="例如：AI 客服如何落地"/><p>已有内容？可从<Link to="/topics/douyin">原选题中心</Link>或<Link to="/articles">文章任务</Link>带入。已有文档可以在下一步上传。</p>{error&&<p role="alert">{error}</p>}<button className="btn primary" disabled={busy||!title.trim()} onClick={()=>void create()}>{busy?'正在创建…':'创建并开始写稿 →'}</button></>}
 </section></div></div>}
 </div>;
}
