# Isolated preview only; generates a test tone and uses the HTTP acceptance clip.
from pathlib import Path
exec(Path(__file__).with_name('verify-migration-http.py').read_text().split('article=call')[0])
task=call('/api/tasks','POST',{'title':'实拍与音乐接入验收','content':'实拍按真实时长，配乐读取原任务文件。'})
video=call('/api/tasks/'+task['content_id']+'/yingxu-files?kind=asset&filename=live.mp4','POST',binary=Path('/tmp/migration-acceptance.mp4').read_bytes())
subprocess.run(['/usr/local/bin/ffmpeg','-y','-f','lavfi','-i','sine=frequency=220:duration=2','/tmp/migration-music.wav'],capture_output=True,check=True)
music=call('/api/tasks/'+task['content_id']+'/yingxu-files?kind=asset&filename=test-tone.wav','POST',binary=Path('/tmp/migration-music.wav').read_bytes())
snapshot={'shots':[{'source':'人工上传','fileId':video['id'],'duration':99,'text':'实际只有一秒','title':'真实素材时长'}],'rhythm':'音乐驱动 · 无旁白','bgmFileId':music['id'],'manuscript':{'title':task['title'],'text':'实际只有一秒'}}
call('/api/tasks/'+task['content_id']+'/yingxu','PUT',{'revision':0,'snapshot':snapshot})
rendered=call('/api/tasks/'+task['content_id']+'/yingxu-render','POST',{'revision':1})
assert abs(rendered['media_info']['duration_seconds']-1)<.2
assert any(s['codec_type']=='audio' for s in rendered['media_info']['streams'])
assert rendered['media_info']['yingxu_revision']==1
snapshot['shots'][0]['text']='修改文案后旧成片应拒绝交付'
call('/api/tasks/'+task['content_id']+'/yingxu','PUT',{'revision':1,'snapshot':snapshot})
try:call('/api/tasks/'+task['content_id']+'/yingxu-handoff','POST',{'revision':2,'file_id':rendered['id']});raise AssertionError('accepted old render')
except RuntimeError as e:assert str(e).startswith('409')
print(json.dumps({'real_duration_override':True,'new_assets_with_cached_bundle':True,'audio_stream':True,'stale_render_rejected':True,'task_id':task['content_id']},ensure_ascii=False))
