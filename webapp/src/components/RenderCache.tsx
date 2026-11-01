import {useEffect,useState} from 'react';
import {api,errorText,jsonOptions} from '../lib/api';
import {Button,Card,Input,ErrorBox} from './ui';
type Cache={bytes:number;files:number;reclaimable_bytes:number;protected_files:number;limit_gb:number;path:string;removed_bytes?:number};
const size=(value:number)=>(value/1024/1024).toFixed(1)+' MB';
export default function RenderCache(){
 const [cache,setCache]=useState<Cache|null>(null),[limit,setLimit]=useState('20'),[busy,setBusy]=useState(false),[error,setError]=useState(''),[message,setMessage]=useState('');
 async function load(){const result=await api<Cache>('/api/yingxu-cache');setCache(result);setLimit(String(result.limit_gb))}
 useEffect(()=>{void load().catch(e=>setError(errorText(e)))},[]);
 async function change(action:'limit'|'clear'){setBusy(true);setError('');setMessage('');try{const result=await api<Cache>('/api/yingxu-cache',jsonOptions('POST',{action,limit_gb:Number(limit)}));setCache(result);setMessage(action==='clear'?`已释放 ${size(result.removed_bytes||0)}，下次渲染会重建所需缓存。`:'容量上限已保存；不会自动删除素材。')}catch(e){setError(errorText(e))}finally{setBusy(false)}}
 return <Card><h2>渲染缓存</h2><p>只清理可重新生成的映序渲染输入；原素材、配乐和成片保留。正在渲染时暂停清理。</p>{error&&<ErrorBox>{error}</ErrorBox>}{message&&<p role="status">{message}</p>}{cache&&<><p>已使用 {size(cache.bytes)} · {cache.files} 个文件 · 可清理 {size(cache.reclaimable_bytes)}</p>{cache.protected_files>0&&<p>{cache.protected_files} 个文件已被作为素材引用，清理时保留。</p>}<p className="muted">缓存位置：{cache.path}</p><label>缓存上限（GB）<Input type="number" min={1} max={1000} value={limit} onChange={e=>setLimit(e.target.value)} disabled={busy}/></label><div className="actions"><Button disabled={busy||!Number.isInteger(Number(limit))||Number(limit)<1||Number(limit)>1000} onClick={()=>void change('limit')}>保存容量</Button><Button disabled={busy||!cache.reclaimable_bytes} onClick={()=>void change('clear')}>清理可重建缓存</Button><Button disabled={busy} onClick={()=>void load().catch(e=>setError(errorText(e)))}>刷新占用</Button></div></>}</Card>
}
