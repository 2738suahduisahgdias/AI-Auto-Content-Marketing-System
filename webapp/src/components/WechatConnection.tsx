import {useEffect,useRef,useState} from 'react';
import {api,errorText,jsonOptions} from '@/lib/api';
import {Badge,Button,Card,ErrorBox,Field,Input,Modal} from '@/components/ui';
type State={status?:string;qrcode_url?:string;error?:string};
export default function WechatConnection(){
 const [client,setClient]=useState<State>({}),[busy,setBusy]=useState(false),[error,setError]=useState(''),[code,setCode]=useState(''),[confirm,setConfirm]=useState(false);
 const pending=useRef(false);
 useEffect(()=>{void api<State>('/api/topics/wechat/client').then(setClient).catch(e=>setError(errorText(e)))},[]);
 async function action(kind:'login'|'poll'|'disconnect'){
  if(pending.current)return;pending.current=true;setBusy(true);
  try{const value=await api<State>(`/api/topics/wechat/client/${kind}`,jsonOptions('POST',{code:kind==='poll'?code:''}));setClient(value);setError('');if(kind==='disconnect')setConfirm(false)}catch(e){setError(errorText(e))}finally{pending.current=false;setBusy(false)}
 }
 useEffect(()=>{if(!['wait','scaned','scanned','scaned_but_redirect'].includes(client.status||''))return;const timer=setInterval(()=>void action('poll'),3000);return()=>clearInterval(timer)},[client.status]);
 const connected=client.status==='connected';const expired=client.status==='expired';
 return <Card id="wechat-connect"><div className="section-heading"><div><h2>微信机器人连接</h2><p>只在首次连接、失效或更换账号时操作；已有选题不会因断开而删除。</p></div><Badge tone={connected?'green':'orange'}>{connected?'已连接':expired?'二维码已过期':client.status==='disconnected'?'未连接':'等待扫码确认'}</Badge></div>
 {error&&<ErrorBox>{error}</ErrorBox>}{client.error&&<ErrorBox>{client.error}</ErrorBox>}
 {connected?<><p>现在可以给机器人发送文字或链接，内容保存后会回复“已保存到待分类”。</p><a className="button" href="/demo/topics/wechat">查看微信选题</a><details><summary>更换账号或断开连接</summary><p>仅需临时检查连接时，请勿断开。断开后需要重新扫码。</p><Button disabled={busy} onClick={()=>setConfirm(true)}>断开并重新连接</Button></details></>:<><p>先生成二维码，再打开微信官方扫码页，用手机微信扫码并确认；本页会自动检查结果。</p><div className="button-row"><Button disabled={busy} onClick={()=>void action('login')}>{busy?'正在处理…':client.qrcode_url?'重新生成二维码':'生成连接二维码'}</Button>{client.qrcode_url&&!expired&&/^https:\/\/(liteapp\.weixin\.qq\.com|weixin\.qq\.com)\//.test(client.qrcode_url)&&<a className="button button-primary" href={client.qrcode_url} target="_blank" rel="noreferrer">打开微信扫码页</a>}<Button disabled={busy} onClick={()=>void action('poll')}>检查连接</Button></div>{expired&&<p role="status">旧二维码已失效，请重新生成，不要继续使用旧链接。</p>}{client.status==='need_verifycode'&&<Field label="微信显示的配对码"><Input value={code} onChange={e=>setCode(e.target.value)}/></Field>}{client.status==='binded_redirect'&&<ErrorBox>微信提示已有绑定，请按官方扫码页面提示确认账号或更换连接，再生成新二维码。</ErrorBox>}</>}
 <Modal open={confirm} onOpenChange={setConfirm} title="确认断开微信机器人？" description="断开后将暂停接收新消息，需要重新扫码连接；已保存选题不会删除。"><div className="button-row"><Button disabled={busy} onClick={()=>setConfirm(false)}>保留连接</Button><Button disabled={busy} onClick={()=>void action('disconnect')}>{busy?'正在断开…':'确认断开'}</Button></div></Modal></Card>;
}
