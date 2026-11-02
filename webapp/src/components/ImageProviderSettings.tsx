import {useEffect,useState} from 'react';
import {api,errorText} from '../lib/api';
import {Button,Card,ErrorBox} from './ui';
export default function ImageProviderSettings({onRefresh}:{onRefresh?:()=>Promise<void>}={}){
 const [status,setStatus]=useState<any>(null),[error,setError]=useState(''),[checking,setChecking]=useState(false),[checked,setChecked]=useState(false);
 async function load(){if(checking)return;setChecking(true);try{setStatus(await api('/api/articles/image-provider'));await onRefresh?.();setError('');setChecked(true)}catch(e){setError(errorText(e))}finally{setChecking(false)}}
 useEffect(()=>{void load()},[]);
 return <Card><h2>文章生图 · Codex CLI</h2><p>复用本机 Codex 登录和内置 image_gen，不需要填写 API Key。点击文章中的“生成图片”后，仅发送该位置的提示词，结果保存到本地素材库。</p>{error&&<ErrorBox>{error}</ErrorBox>}<p aria-live="polite">{!status?'正在检测 Codex CLI…':status.configured?'已找到 Codex CLI。登录和额度由 Codex 账户管理，实际生图结果以任务状态为准。':'未找到 Codex CLI，请先安装并登录。'}</p><Button disabled={checking} onClick={()=>void load()}>{checking?'正在重新检测…':'刷新 CLI 状态'}</Button>{checked&&!checking&&<p role="status">检测已完成，页面连接状态已刷新。</p>}</Card>
}
