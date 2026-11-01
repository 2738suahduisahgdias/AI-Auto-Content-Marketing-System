import {useState} from 'react';
import {api,errorText,jsonOptions} from '../lib/api';
import {Button,Card,Input,ErrorBox} from './ui';
export default function WorkspaceTransfer(){
 const [destination,setDestination]=useState(''),[source,setSource]=useState(''),[busy,setBusy]=useState(false),[message,setMessage]=useState(''),[error,setError]=useState('');
 async function run(action:'export'|'restore'){setBusy(true);setMessage('');setError('');try{const result=await api<any>('/api/workspace/'+action,jsonOptions('POST',{destination:destination.trim(),package:source.trim()}));setMessage(result.note+' · '+result.path)}catch(e){setError(errorText(e))}finally{setBusy(false)}}
 return <Card><h2>项目备份与换电脑</h2><p>打包当前工作区的文章、视频项目、版本和素材，外置引用文件也会复制进迁移包。恢复只写入新目录，不覆盖当前系统。大文件处理期间请保持硬盘连接。</p><p>新电脑需重新激活、登录平台和配置模型连接；迁移包保存在本地，不上传云端。</p><label>新的导出／恢复目录<Input value={destination} onChange={e=>setDestination(e.target.value)} placeholder="/Volumes/EXTERNAL_USB/映序备份-新目录" disabled={busy}/></label><Button disabled={busy||!destination.trim()} onClick={()=>void run('export')}>导出完整工作区</Button><details><summary>从迁移包恢复</summary><label>迁移包目录<Input value={source} onChange={e=>setSource(e.target.value)} disabled={busy}/></label><Button disabled={busy||!source.trim()||!destination.trim()} onClick={()=>void run('restore')}>校验并恢复到新目录</Button></details>{busy&&<p role="status">正在复制并校验文件，请勿拔出硬盘…</p>}{message&&<p role="status">{message}</p>}{error&&<ErrorBox>{error}</ErrorBox>}</Card>
}
