import {useEffect,useRef,useState} from 'react';
import {api,errorText,jsonOptions} from '../lib/api';
import {Button,ErrorBox,Input} from './ui';
type Asset={id:string;mime_type:string;storage_key:string;available:boolean;source:{path?:string;original_name?:string}};
export default function ArticleImagePicker({assetId,onSelect,disabled}:{assetId?:string;onSelect:(id:string)=>void;disabled:boolean}){
 const [assets,setAssets]=useState<Asset[]>([]),[path,setPath]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const callback=useRef(onSelect);callback.current=onSelect;
 async function load(){const result=await api('/api/v2/local-assets');setAssets(result.assets.filter((a:Asset)=>['image/png','image/jpeg','image/webp'].includes(a.mime_type)))}
 useEffect(()=>{void load().catch(e=>setError(errorText(e)))},[]);
 async function importImage(){setBusy(true);setError('');try{if(!/\.(png|jpe?g|webp)$/i.test(path.trim()))throw new Error('请选择 PNG、JPEG 或 WebP 图片');const result=await api('/api/v2/local-assets',jsonOptions('POST',{path:path.trim(),copy:false}));await load();callback.current(result.asset_id);setPath('')}catch(e){setError(errorText(e))}finally{setBusy(false)}}
 return <fieldset disabled={disabled||busy} className="article-image-picker"><legend>采用的本地图片</legend>{error&&<ErrorBox>{error}</ErrorBox>}<label>从素材库选择<select value={assetId||''} onChange={e=>onSelect(e.target.value)}><option value="">未采用图片</option>{assetId&&!assets.some(a=>a.id===assetId)&&<option value={assetId}>{assetId}</option>}{assets.map(a=><option key={a.id} value={a.id} disabled={!a.available}>{a.source.original_name||a.source.path||a.storage_key}{a.available?'':'（文件未连接）'}</option>)}</select></label><label>或引用原图片路径<Input value={path} onChange={e=>setPath(e.target.value)} placeholder="/Volumes/EXTERNAL_USB/图片/封面.png"/></label><Button disabled={!path.trim()||busy||disabled} onClick={()=>void importImage()}>{busy?'正在检查图片…':'导入并采用'}</Button>{assetId&&<><img src={`/api/v2/assets/${encodeURIComponent(assetId)}/content`} alt="已选择配图预览" style={{display:'block',maxWidth:320,maxHeight:240,objectFit:'contain',marginTop:12}}/><p>点击“保存正文与配图计划”后才会写入文章版本。</p></>}</fieldset>
}
