"""A real, non-destructive directing proposal for the existing Yingxu project."""
import copy
import hashlib
import json
import math
import re
from content_workbench.domain.errors import DomainError

SOURCES={'Remotion 代码','AI 视频','人工上传','图生视频','素材库'}

def narration(document):
    # Explicit section headings are structure, not narration; blank lines alone are not shots.
    return re.sub(r'^[ \t]*(?:#{1,4}[ \t]*)?S\d{1,3}[ \t]*[｜|:：][ \t]*[^\n]*\n?', '', document, flags=re.M).strip()

def context(task):
    snapshot=task.get('source',{}).get('yingxu',{}).get('snapshot',{})
    manuscript=snapshot.get('manuscript') or {}
    text=narration(str(manuscript.get('text') or ''))
    if not text:raise DomainError('DIRECTOR_SCRIPT_REQUIRED','先输入完整文案，再生成视频方案',422)
    audio=next((f for f in task.get('files',[]) if f['id']==snapshot.get('voiceFileId')),None)
    audio_seconds=(audio or {}).get('media_info',{}).get('duration_seconds')
    has_voice=snapshot.get('rhythm')=='旁白驱动' and isinstance(audio_seconds,(float,int)) and not isinstance(audio_seconds,bool) and audio_seconds>0
    raw=snapshot.get('targetDuration')
    target=float(audio_seconds) if has_voice else float(raw) if isinstance(raw,(int,float)) and not isinstance(raw,bool) and raw>0 else max(6,round(len(text)/4.5,2))
    if not math.isfinite(target) or target>3600:raise DomainError('DIRECTOR_DURATION_INVALID','请将单个项目控制在一小时以内，或拆分为多个项目',422)
    locked=[{'locked_index':i,'shot':copy.deepcopy(s)} for i,s in enumerate(snapshot.get('shots') or []) if s.get('locked')]
    brief={key:snapshot[key] for key in ('scene','audience','goal','structure','effectName','effectPrompt','template','brand','reference','format','rhythm') if key in snapshot}
    return {'title':manuscript.get('title') or task['title'],'document':manuscript.get('text',''),'narration_text':text,
            'brief':brief,'default_engine':snapshot.get('defaultEngine') or 'Remotion 代码',
            'target_duration_seconds':target,'duration_source':'uploaded_narration' if has_voice else 'user_target' if raw else 'estimated_narration',
            'locked_shots':locked}

def canonical(value):return re.sub(r'\s+','',value)

def validate_plan(raw, request):
    shots=raw.get('shots') if isinstance(raw,dict) else None
    if not isinstance(shots,list) or not 2<=len(shots)<=40:raise ValueError('必须返回2～40个有叙事结构的镜头')
    result=[];seen=set();locked={x['locked_index']:x['shot'] for x in request['locked_shots']}
    for i,s in enumerate(shots):
        if not isinstance(s,dict):raise ValueError('镜头必须是对象')
        keys=('title','label','text','purpose','desc','motion','emphasis','sound_effect')
        if any(not isinstance(s.get(k),str) for k in keys):raise ValueError('镜头字段不完整')
        if any(not s[k].strip() for k in ('text','purpose','desc','motion')):raise ValueError('镜头必须有原文、叙事目的、具体画面与动作')
        d=s.get('duration')
        if isinstance(d,bool) or not isinstance(d,(int,float)) or not math.isfinite(d) or d<=0:raise ValueError('镜头时长无效')
        item={k:s[k].strip() for k in keys};item['duration']=float(d)
        index=s.get('locked_index')
        if index is not None:
            if isinstance(index,bool) or index not in locked or index in seen:raise ValueError('锁定镜头引用缺失或重复')
            seen.add(index);original=copy.deepcopy(locked[index]);original.update({k:item[k] for k in ('purpose','motion','emphasis','sound_effect')});item=original
        else:
            source=s.get('source') or request['default_engine']
            if source not in SOURCES:raise ValueError('镜头来源无效')
            item.update(source=source,status='待制作',image=i%4)
        item['action']=item.get('motion','');item['sound']='建议：'+item.get('sound_effect','') if item.get('sound_effect') else ''
        result.append(item)
    if seen!=set(locked):raise ValueError('必须保留所有锁定素材')
    if canonical(''.join(s['text'] for s in result))!=canonical(request['narration_text']):raise ValueError('口播原文被改写、遗漏或重复，请按原文完整分配镜头')
    fixed=sum(float(s.get('actualDuration') or s['duration']) for s in result if s.get('locked'))
    free=[s for s in result if not s.get('locked')]
    remaining=request['target_duration_seconds']-fixed
    if free and remaining<=0:raise ValueError('完整锁定素材已经超过目标时长，请先调整旁白或素材')
    weight=sum(float(s['duration']) for s in free)
    for s in result:
        s['duration']=round(float(s.get('actualDuration') or s['duration']),3) if s.get('locked') else round(float(s['duration'])/weight*remaining,3)
        if s['duration']<0.1:raise ValueError('镜头过短，请合并镜头')
    if free:free[-1]['duration']=round(free[-1]['duration']+request['target_duration_seconds']-sum(s['duration'] for s in result),3)
    if not isinstance(raw.get('style_summary'),str) or not raw['style_summary'].strip():raise ValueError('缺少整条视频的统一视觉方案')
    palette=raw.get('palette') or {}
    if not isinstance(palette,dict) or any(not isinstance(palette.get(k),str) or not re.fullmatch(r'#[0-9A-Fa-f]{6}',palette[k]) for k in ('background','text','accent')):raise ValueError('必须提供符合本片视觉要求的十六进制三色 palette')
    return {'palette':palette,'style_summary':raw['style_summary'],'timing_note':str(raw.get('timing_note') or ''),'shots':result,
            'duration_seconds':round(sum(s['duration'] for s in result),3),'duration_source':request['duration_source'],
            'alignment':'proportional_narration' if request['duration_source']=='uploaded_narration' else 'planned'}

def generate_plan(task, generate):
    request=context(task);serialized=json.dumps(request,ensure_ascii=False,sort_keys=True)
    if len(serialized)>50000:raise DomainError('DIRECTOR_INPUT_TOO_LARGE','文案或素材说明过长，请分为多个项目',422)
    error=''
    for attempt in range(2):
        response=generate(serialized+ ('\n上次校验失败，请按原文修正完整方案：'+error if error else '')).strip()
        if response.startswith('```') and response.endswith('```'):response='\n'.join(response.splitlines()[1:-1])
        try:
            plan=validate_plan(json.loads(response),request)
            return {'candidate':plan,'revision':task.get('source',{}).get('yingxu',{}).get('revision',0),
                    'input_hash':hashlib.sha256(serialized.encode()).hexdigest()}
        except (ValueError,TypeError,KeyError) as e:error=str(e)
    raise DomainError('DIRECTOR_OUTPUT_INVALID','编导方案未通过校验，原文与原分镜保持不变：'+error,502)
