import {useEffect,useState} from 'react';
import {api,errorText,jsonOptions} from '../lib/api';
import {Card,Input,Button,ErrorBox} from './ui';
import LocalFileButton from './LocalFileButton';
export default function MediaTools(){
 const [paths,setPaths]=useState<Record<string,string>>({}),[error,setError]=useState(''),[message,setMessage]=useState('');
 useEffect(()=>{api('/api/media-tools').then(r=>setPaths(r.paths)).catch(e=>setError(errorText(e)))},[]);
 async function save(){try{await api('/api/media-tools',jsonOptions('POST',paths));setMessage('路径已保存，请运行下面的真实测试；保存路径不等于能力已通过。');setError('')}catch(e){setError(errorText(e))}}
 return <Card className="media-tools"><h2>本地模型环境位置</h2><p>系统语音和 Remotion 使用客户端能力。自动字幕需要 faster-whisper；音色克隆需要 OpenVoice/MeloTTS 与模型文件。这些环境不能由 Codex CLI 配置替代。可选择本机已安装环境，默认位置在当前工作区 tools 目录；未安装时仍可上传录音和 SRT。</p>{Object.entries({whisper_python:'字幕环境 Python',openvoice_python:'音色环境 Python',openvoice_root:'OpenVoice 模型文件夹'}).map(([key,label])=><div key={key} className="media-tool-field"><label>{label}<Input value={paths[key]||''} onChange={e=>setPaths({...paths,[key]:e.target.value})}/></label><LocalFileButton folder={key==='openvoice_root'} onSelect={p=>setPaths({...paths,[key]:p})}/></div>)}<Button onClick={()=>void save()}>保存环境位置</Button>{message&&<p role="status">{message}</p>}{error&&<ErrorBox>{error}</ErrorBox>}</Card>
}
