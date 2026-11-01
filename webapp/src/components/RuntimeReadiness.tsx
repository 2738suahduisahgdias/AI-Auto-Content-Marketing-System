import {useEffect,useState} from 'react';
import {api,errorText} from '../lib/api';
import {Button,Card,ErrorBox} from './ui';
type Report={checked_at:string;worker_running:boolean;boundary:string;capabilities:{name:string;status:string;missing_dependencies:string[];inactive_executors:string[];note:string}[]};
export default function RuntimeReadiness(){
 const [report,setReport]=useState<Report|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 async function load(){setBusy(true);try{setReport(await api('/api/v2/runtime-readiness'));setError('')}catch(e){setError(errorText(e))}finally{setBusy(false)}}
 useEffect(()=>{void load()},[]);
 return <Card className="settings-runtime-readiness"><div className="section-heading"><h2>真实运行检查</h2><Button disabled={busy} onClick={()=>void load()}>{busy?'检查中…':'重新检查本机'}</Button></div>{error&&<ErrorBox>{error}</ErrorBox>}{report&&<><p>执行进程：{report.worker_running?'在线（按能力检查可执行范围）':'未启动'} · {new Date(report.checked_at).toLocaleString()}</p><div style={{overflowX:'auto'}}><table><thead><tr><th>功能</th><th>状态</th><th>问题与下一步</th></tr></thead><tbody>{report.capabilities.map(row=><tr key={row.name}><td>{row.name}</td><td>{{blocked:'有阻塞',requires_validation:'待实跑验证',not_implemented:'待开发'}[row.status]||row.status}</td><td>{row.missing_dependencies.length>0&&<p>缺少依赖：{row.missing_dependencies.map(key=>({codex_cli:'Codex CLI',text_cli:'Kimi CLI',ffmpeg:'FFmpeg / FFprobe',node:'Node.js',remotion:'Remotion 依赖',browser_python:'浏览器自动化 Python 环境'}[key]||key)).join('、')}</p>}{row.inactive_executors.length>0&&<p>执行器未启用：{row.inactive_executors.join('、')}</p>}<p>{row.note}</p></td></tr>)}</tbody></table></div><p>{report.boundary}</p></>}</Card>
}
