import {useEffect,useState} from 'react';
import {api,errorText} from '../lib/api';
import {Button,Card,ErrorBox} from './ui';
export default function ImageProviderSettings({onRefresh}:{onRefresh?:()=>Promise<void>}={}){
 const [status,setStatus]=useState<any>(null),[error,setError]=useState(''),[checking,setChecking]=useState(false),[checked,setChecked]=useState(false);
 async function load(){if(checking)return;setChecking(true);try{setStatus(await api('/api/articles/image-provider'));await onRefresh?.();setError('');setChecked(true)}catch(e){setError(errorText(e))}finally{setChecking(false)}}
 useEffect(()=>{void load()},[]);
 return <Card><h2>文章插画与本地渲染</h2><p>文章插画 Agent 生成原创 SVG 矢量插画，客户端内置 Remotion 输出 PNG。模型服务和模型名称可在 Agent 配置中心独立修改；本地渲染不需要图像 API。</p>{error&&<ErrorBox>{error}</ErrorBox>}<p aria-live="polite">{!status?'正在读取模型配置…':status.configured?`${status.engine} · ${status.model==='default_unpinned'?'当前默认模型':status.model}。实际结果以任务状态和生成文件为准。`:'当前模型服务不可用，请到 Agent 配置中心检查服务、模型和登录状态。'}</p><Button disabled={checking} onClick={()=>void load()}>{checking?'正在重新检测…':'刷新模型状态'}</Button>{checked&&!checking&&<p role="status">检测已完成，页面连接状态已刷新。</p>}</Card>
}
