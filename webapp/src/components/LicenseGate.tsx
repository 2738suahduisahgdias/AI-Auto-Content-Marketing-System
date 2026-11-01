import {useEffect,useState,type ReactNode} from 'react';
import {useLocation,useNavigate} from 'react-router-dom';
import {api,errorText} from '../lib/api';
import {Busy,ErrorBox} from './ui';
export default function LicenseGate({children}:{children:ReactNode}){
 const [ready,setReady]=useState(false),[error,setError]=useState('');const navigate=useNavigate();const location=useLocation();
 useEffect(()=>{let alive=true;api<any>('/api/v2/license').then(data=>{if(!alive)return;if(data.mode==='required'&&location.pathname!=='/activation'){
 if(data.status!=='valid'&&!sessionStorage.getItem('yx-read-only'))navigate('/activation',{replace:true});
 else if(data.status==='valid'&&!data.onboarding.completed&&!sessionStorage.getItem('yx-guide-session')){sessionStorage.setItem('yx-guide-session','1');navigate('/welcome',{replace:true})}
 }setReady(true)}).catch(e=>{if(alive)setError(errorText(e))});return()=>{alive=false}},[]);
 return error?<ErrorBox>{error}<button onClick={()=>window.location.reload()}>重新连接</button></ErrorBox>:ready?<>{children}</>:<Busy/>;
}
