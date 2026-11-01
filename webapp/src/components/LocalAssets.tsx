import {useEffect,useState} from 'react';
import {api,errorText,jsonOptions} from '../lib/api';
import {Button,Card,Input,ErrorBox} from './ui';
type Asset={id:string;source:{kind?:string;path?:string;original_name?:string};storage_key:string;available:boolean;problem?:string};
export default function LocalAssets(){
 const [items,setItems]=useState<Asset[]>([]),[path,setPath]=useState(''),[copy,setCopy]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(''),[target,setTarget]=useState<string|null>(null);
 async function load(){const data=await api('/api/v2/local-assets');setItems(data.assets)}
 useEffect(()=>{void load().catch(e=>setError(errorText(e)))},[]);
 async function save(){setBusy(true);setError('');try{await api(target?`/api/v2/local-assets/${encodeURIComponent(target)}/relink`:'/api/v2/local-assets',jsonOptions('POST',{path,copy}));await load();setPath('');setTarget(null)}catch(e){setError(errorText(e))}finally{setBusy(false)}}
 return <Card className="settings-local-assets"><h2>本地素材</h2><Button disabled={busy} onClick={()=>void load().catch(e=>setError(errorText(e)))}>刷新文件状态</Button><p>默认引用原文件，不重复占用磁盘。外接硬盘断开或文件移动后，可重新定位到内容相同的文件。</p><p>本地网页版请粘贴完整文件路径；此处不会上传到云端。</p>{error&&<ErrorBox>{error}</ErrorBox>}<label>{target?'原素材的新位置':'视频、音频、图片或字幕路径'}<Input value={path} onChange={e=>setPath(e.target.value)} placeholder="/Volumes/EXTERNAL_USB/素材/视频.mp4" disabled={busy}/></label>{!target&&<label><input type="checkbox" checked={copy} onChange={e=>setCopy(e.target.checked)}/> 复制进本地素材库</label>}<div><Button disabled={busy||!path.trim()} onClick={()=>void save()}>{busy?'正在检查文件…':target?'验证并重新定位':'导入素材'}</Button>{target&&<Button disabled={busy} onClick={()=>{setTarget(null);setPath('')}}>取消</Button>}</div><ul className="local-assets-list">{items.map(item=><li key={item.id}><strong>{item.source.path||item.source.original_name||item.storage_key}</strong><p>{item.available?'文件可用':item.problem} · {item.source.kind==='local_reference'?'引用原文件':'本地副本'}</p>{item.source.kind==='local_reference'&&<Button disabled={busy} onClick={()=>{setTarget(item.id);setPath('')}}>重新定位</Button>}</li>)}</ul></Card>
}
