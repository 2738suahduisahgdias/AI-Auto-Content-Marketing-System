import {useRef,useState,type Dispatch,type SetStateAction} from 'react';
const prefix='yingxu:content-draft:v1:';
export function readContentDraft<T>(key:string,fallback:T):T{
 if(!key)return fallback;
 try{const raw=localStorage.getItem(prefix+key);if(!raw)return fallback;const value=JSON.parse(raw);return value.schema===1&&Object.prototype.hasOwnProperty.call(value,'data')?value.data as T:fallback}catch{return fallback}
}
export function writeContentDraft(key:string,data:unknown){if(!key)return;localStorage.setItem(prefix+key,JSON.stringify({schema:1,saved_at:new Date().toISOString(),data}));}
export function useContentDraft<T>(key:string,initial:T):[T,Dispatch<SetStateAction<T>>,string]{
 const [state,setState]=useState(()=>({key,value:readContentDraft(key,initial)}));const [error,setError]=useState('');
 const latest=useRef(state);latest.current=state;
 if(state.key!==key){const next={key,value:readContentDraft(key,initial)};latest.current=next;setState(next);}
 const setValue:Dispatch<SetStateAction<T>>=update=>{
  const previous=latest.current.key===key?latest.current.value:readContentDraft(key,initial);
  const value=typeof update==='function'?(update as (v:T)=>T)(previous):update;
  try{writeContentDraft(key,value);setError('')}catch{setError('自动保存失败：本机浏览器存储不可用或空间不足，请导出内容，勿关闭页面。')}
  const next={key,value};latest.current=next;setState(next);
 };
 return [state.key===key?state.value:latest.current.value,setValue,error];
}
