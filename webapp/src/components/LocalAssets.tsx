import LocalFileButton from './LocalFileButton';
import {useEffect,useState} from 'react';
import {api,errorText,jsonOptions} from '../lib/api';
import {Button,Card,Input,ErrorBox} from './ui';
type Asset={id:string;source:{kind?:string;path?:string;original_name?:string};storage_key:string;available:boolean;problem?:string};
export default function LocalAssets(){
 const [visible,setVisible]=useState(10);
 const [filter,setFilter]=useState('media');
 const [items,setItems]=useState<Asset[]>([]),[path,setPath]=useState(''),[copy,setCopy]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(''),[target,setTarget]=useState<string|null>(null);
 const shown=items.filter(item=>filter==='all'||/\.(mp4|mov|mkv|webm|mp3|wav|m4a|aac|flac|png|jpe?g|webp|srt)$/i.test(item.source.original_name||item.source.path||item.storage_key));
 async function load(){const data=await api('/api/v2/local-assets');setItems(data.assets)}
 useEffect(()=>{void load().catch(e=>setError(errorText(e)))},[]);
 async function save(){setBusy(true);setError('');try{await api(target?`/api/v2/local-assets/${encodeURIComponent(target)}/relink`:'/api/v2/local-assets',jsonOptions('POST',{path,copy}));await load();setPath('');setTarget(null)}catch(e){setError(errorText(e))}finally{setBusy(false)}}
 return <Card className="settings-local-assets"><h2>本地素材</h2><Button disabled={busy} onClick={()=>void load().catch(e=>setError(errorText(e)))}>刷新文件状态</Button><p>默认引用原文件，不重复占用磁盘。外接硬盘断开或文件移动后，可重新定位到内容相同的文件。</p><p>选择本地文件后导入；文件保留在本机，不上传云端。</p>{error&&<ErrorBox>{error}</ErrorBox>}<label>{target?'原素材的新位置':'视频、音频、图片或字幕路径'}<Input value={path} onChange={e=>setPath(e.target.value)} placeholder="/Volumes/EXTERNAL_USB/素材/视频.mp4" disabled={busy}/></label><LocalFileButton onSelect={setPath} disabled={busy}/>{!target&&<label><input type="checkbox" checked={copy} onChange={e=>setCopy(e.target.checked)}/> 复制进本地素材库</label>}<div><Button disabled={busy||!path.trim()} onClick={()=>void save()}>{busy?'正在检查文件…':target?'验证并重新定位':'导入素材'}</Button>{target&&<Button disabled={busy} onClick={()=>{setTarget(null);setPath('')}}>取消</Button>}</div><label>素材类型<select value={filter} onChange={e=>{setFilter(e.target.value);setVisible(10)}}><option value="media">视频、声音、图片、字幕</option><option value="all">全部（含文档与导出包）</option></select></label><ul className="local-assets-list">{shown.slice(0,visible).map(item=><li key={item.id}><strong>{(item.source.original_name||item.source.path||item.storage_key).split(/[\\/]/).pop()}</strong><details><summary>文件位置</summary><code>{item.source.path||item.storage_key}</code></details><p>{item.available?'文件可用':item.problem} · {item.source.kind==='local_reference'?'引用原文件':'本地副本'}</p>{item.source.kind==='local_reference'&&<Button disabled={busy} onClick={()=>{setTarget(item.id);setPath('')}}>重新定位</Button>}</li>)}</ul>{visible<shown.length&&<Button onClick={()=>setVisible(n=>n+10)}>显示更多素材（剩余 {shown.length-visible}）</Button>}</Card>
}
