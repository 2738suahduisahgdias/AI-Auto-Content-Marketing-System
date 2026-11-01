import type {Task} from '../lib/types';
export function seedYingxuTask(task:Task):Record<string,any>{
 const saved=(task as any).source?.yingxu?.snapshot;
 if(saved)return saved;
 const audio=[...task.files].sort((a,b)=>b.id-a.id).find(file=>file.kind==='audio');
 return {stage:-1,workflowV3:true,authoringV1:true,topics:[],selected:[],
 manuscript:{title:task.title,text:task.scripts.master||task.scripts.douyin||task.scripts.wechat_channels||task.scripts.xiaohongshu||'',source:'task',versions:[]},
 ...(audio?{voice:audio.original_name,voiceUrl:audio.url,voiceFileId:audio.id,voiceDuration:audio.media_info?.duration_seconds,rhythm:'旁白驱动'}:{}),
 shots:(task.asset_plan||[]).map((item,index)=>{const file=task.files.find(f=>f.id===item.file_id);const video=/\.(mp4|mov)$/i.test(file?.original_name||'');const duration=video&&file?.media_info?.duration_seconds||Math.max(1,Number(item.end_seconds||5)-Number(item.start_seconds||0));return {
 title:item.name||'原分镜 '+(index+1),label:'原素材计划',text:item.narration||item.text||'',desc:item.description||'',duration,
 source:file?(video?'人工上传':'素材库'):'Remotion 代码',status:file?'已上传':'待制作',image:index%4,
 ...(file?{fileId:file.id,fileName:file.original_name,media:file.url,mediaType:video?'video/mp4':'image/jpeg',locked:true}:{}),
 ...(video?{actualDuration:duration}:{}),originalPlan:item};})};
}
