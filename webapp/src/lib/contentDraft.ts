import {useEffect,useRef,useState,type Dispatch,type SetStateAction} from 'react';
import {api,jsonOptions,errorText} from './api';
const legacyPrefix='yingxu:content-draft:v1:';
let workspace='';
type RecordValue={data:unknown;revision:number;pending:boolean};
const records=new Map<string,RecordValue>();
const queues=new Map<string,Promise<void>>();
const errors=new Map<string,string>();
const prefix=()=>workspace?`yingxu:content-draft:v2:${workspace}:`:legacyPrefix;
const changed=(key:string)=>window.dispatchEvent(new CustomEvent('yingxu:draft-status',{detail:key}));
function backup(key:string,value:RecordValue){localStorage.setItem(prefix()+key,JSON.stringify({schema:1,...value,saved_at:new Date().toISOString()}));}
export async function initializeContentDrafts(){
 const data=await api<{workspace_id:string;legacy_prefixes?:string[];drafts:{key:string;data:unknown;revision:number}[]}>('/api/v2/content-drafts');
 workspace=data.workspace_id;records.clear();errors.clear();
 for(const row of data.drafts)records.set(row.key,{data:row.data,revision:row.revision,pending:false});
 // Recover pending backups only inside this workspace. Legacy unscoped backups are left untouched.
 try{
 for(let i=0;i<localStorage.length;i++){
  const storageKey=localStorage.key(i);if(!storageKey?.startsWith(prefix()))continue;
  try{const cached=JSON.parse(localStorage.getItem(storageKey)||'null');const key=storageKey.slice(prefix().length);
   if(cached?.pending){const remote=records.get(key);records.set(key,{data:cached.data,revision:cached.revision,pending:true});
    if((remote?.revision||0)!==cached.revision)errors.set(key,'另一窗口已更新草稿；本机未同步内容已保留，请导出后核对。');else persist(key);
   }
  }catch{/* malformed browser backup never replaces the database */}
 }
 // Import only old backups whose task identity belongs to this database. Never adopt generic drafts from another workspace.
 const legacyKeys=Array.from({length:localStorage.length},(_,i)=>localStorage.key(i)).filter((k):k is string=>Boolean(k?.startsWith(legacyPrefix)));
 for(const storageKey of legacyKeys){const key=storageKey.slice(legacyPrefix.length);if(records.has(key)||!data.legacy_prefixes?.some(p=>key.startsWith(p)))continue;try{const old=JSON.parse(localStorage.getItem(storageKey)||'null');if(old?.schema===1&&'data' in old)writeContentDraft(key,old.data)}catch{}}
 }catch{/* Database drafts remain available when browser storage is disabled. */}
}
function persist(key:string){
 const prior=queues.get(key)||Promise.resolve();
 const next=prior.then(async()=>{
  const record=records.get(key);if(!record?.pending||errors.has(key))return;
  const sent=record.data;
  try{
   const result=await api<{revision:number}>('/api/v2/content-drafts',jsonOptions('PUT',{key,data:sent,expected_revision:record.revision}));
   const current=records.get(key)!;current.revision=result.revision;current.pending=current.data!==sent;
   errors.delete(key);try{backup(key,current)}catch{/* the database is the durable copy */}
  }catch(e){errors.set(key,'自动保存到本地项目失败：'+errorText(e)+'；当前输入保留在本页和可用的浏览器备份中。');}
  changed(key);
 }).finally(()=>{if(queues.get(key)===next)queues.delete(key)});
 queues.set(key,next);changed(key);
}
export async function flushContentDrafts(){
 for(const [key,record] of records)if(record.pending&&!errors.has(key))persist(key);
 while(queues.size)await Promise.all([...queues.values()]);
 if([...records].some(([key,r])=>r.pending||errors.has(key)))throw Error('存在未同步的草稿，请先处理自动保存提示，暂不能切换工作区。');
}
export function draftPersistenceErrors(){return [...errors.values()];}
export function hasContentDraft(key:string){if(records.has(key))return true;try{return Boolean(localStorage.getItem(prefix()+key))}catch{return false}}
export function readContentDraft<T>(key:string,fallback:T):T{
 if(!key)return fallback;
 if(records.has(key))return records.get(key)!.data as T;
 if(workspace)return fallback;
 try{const raw=localStorage.getItem(prefix()+key);if(!raw)return fallback;const value=JSON.parse(raw);return value.schema===1&&Object.prototype.hasOwnProperty.call(value,'data')?value.data as T:fallback}catch{return fallback}
}
export function writeContentDraft(key:string,data:unknown){
 if(!key)return;
 if(!workspace){backup(key,{data,revision:0,pending:true});return;}
 const record={data,revision:records.get(key)?.revision||0,pending:true};records.set(key,record);
 try{backup(key,record)}catch{/* still attempt the durable database write */}
 // Conflicts require explicit resolution; ordinary connection failures can retry on the next edit.
 if(!errors.get(key)?.includes('另一窗口'))errors.delete(key);
 persist(key);
}
export function useContentDraft<T>(key:string,initial:T):[T,Dispatch<SetStateAction<T>>,string]{
 const [state,setState]=useState(()=>({key,value:readContentDraft(key,initial)}));const [error,setError]=useState('');
 const latest=useRef(state);latest.current=state;
 if(state.key!==key){const next={key,value:readContentDraft(key,initial)};latest.current=next;setState(next);}
 useEffect(()=>{const listener=()=>setError(errors.get(key)||'');window.addEventListener('yingxu:draft-status',listener);listener();return()=>window.removeEventListener('yingxu:draft-status',listener)},[key]);
 const setValue:Dispatch<SetStateAction<T>>=update=>{
  const previous=latest.current.key===key?latest.current.value:readContentDraft(key,initial);
  const value=typeof update==='function'?(update as (v:T)=>T)(previous):update;
  try{writeContentDraft(key,value);setError(errors.get(key)||'')}catch{setError('自动保存失败：本机浏览器存储不可用或空间不足，请导出内容，勿关闭页面。')}
  const next={key,value};latest.current=next;setState(next);
 };
 return [state.key===key?state.value:latest.current.value,setValue,error];
}
window.addEventListener('beforeunload',event=>{if(workspace&&[...records.values()].some(r=>r.pending)){event.preventDefault();event.returnValue='';}});
