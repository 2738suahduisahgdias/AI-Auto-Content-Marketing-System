import {useState} from 'react';
import {api,errorText,jsonOptions} from '../lib/api';
import {Button,ErrorBox} from './ui';
export default function LocalFileButton({onSelect,folder=false,disabled=false}:{onSelect:(path:string)=>void;folder?:boolean;disabled?:boolean}){
 const [busy,setBusy]=useState(false),[error,setError]=useState('');
 async function choose(){setBusy(true);setError('');try{const data=await api('/api/local-picker',jsonOptions('POST',{kind:folder?'folder':'file'}));if(data.path)onSelect(data.path)}catch(e){setError(errorText(e))}finally{setBusy(false)}}
 return <><Button disabled={disabled||busy} onClick={()=>void choose()}>{busy?'等待选择…':folder?'选择文件夹':'选择本地文件'}</Button>{error&&<ErrorBox>{error}</ErrorBox>}</>;
}
