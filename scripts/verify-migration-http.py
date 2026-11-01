# Local isolated preview only (8876). Creates acceptance records; never point at production.
import urllib.request,urllib.error,http.cookiejar,json,subprocess,uuid
from pathlib import Path
base='http://127.0.0.1:8876'
jar=http.cookiejar.CookieJar();client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
client.open(base+'/').read();token=''
def call(path,method='GET',data=None,binary=None):
 global token
 body=binary if binary is not None else json.dumps(data).encode() if data is not None else None
 headers={'Content-Type':'application/octet-stream' if binary is not None else 'application/json','X-CSRF-Token':token,'Idempotency-Key':str(uuid.uuid4())}
 try:r=json.load(client.open(urllib.request.Request(base+path,data=body,method=method,headers=headers)))
 except urllib.error.HTTPError as e:raise RuntimeError(str(e.code)+' '+e.read().decode())
 if r.get('csrf_token'):token=r['csrf_token']
 return r
bootstrap=call('/api/topics/bootstrap');core=call('/api/bootstrap')
article=call('/api/articles','POST',{'title':'迁移验收：AI客服如何落地','brief':{'text':'隔离预览验收'}})
article=call('/api/articles/'+article['id']+'/revisions','POST',{'kind':'draft','payload':{'text':'先梳理知识，再连接业务，最后灰度上线。'},'expected_version':article['version']})['item']
task=call('/api/tasks','POST',{'title':'迁移验收：AI客服如何落地','article_id':article['id'],'article_revision_id':article['active_revisions']['draft']})
assert task['source']['article_id']==article['id']
snapshot={'stage':0,'shots':[],'topics':[],'workflowV3':True,'authoringV1':True,'manuscript':{'title':task['title'],'text':task['scripts']['douyin'],'versions':[]}}
updated=call('/api/tasks/'+task['content_id']+'/yingxu','PUT',{'revision':0,'snapshot':snapshot})
assert updated['source']['yingxu']['revision']==1
try:call('/api/tasks/'+task['content_id']+'/yingxu','PUT',{'revision':0,'snapshot':snapshot});raise AssertionError('conflict accepted')
except RuntimeError as e:assert str(e).startswith('409')
video=Path('/tmp/migration-acceptance.mp4')
subprocess.run(['/usr/local/bin/ffmpeg','-y','-f','lavfi','-i','color=c=orange:s=320x180:d=1','-c:v','libx264','-pix_fmt','yuv420p',str(video)],capture_output=True,check=True)
file=call('/api/tasks/'+task['content_id']+'/yingxu-files?kind=video&filename=acceptance.mp4','POST',binary=video.read_bytes())
assert file['media_info']['duration_seconds']>0
submitted=call('/api/tasks/'+task['content_id']+'/yingxu-handoff','POST',{'file_id':file['id'],'revision':1})
assert submitted['source']['yingxu_handoff']['file_id']==file['id']
assert not submitted['published_at']
again=call('/api/tasks/'+task['content_id']+'/yingxu-handoff','POST',{'file_id':file['id'],'revision':1})
assert again['source']['yingxu_handoff']==submitted['source']['yingxu_handoff']
original=call('/api/articles/'+article['id'])
assert original['active_revisions']['draft']==article['active_revisions']['draft']
items=[i for values in bootstrap['sources'].values() for i in values if not i.get('archived')]
if items:
 chosen=items[0]
 from_topic=call('/api/topics/items/'+chosen['id']+'/create-task','POST',{})
 assert from_topic['source']['research_item_id']==chosen['id']
print(json.dumps({'article_to_video':'passed','saved_revision_and_conflict':'passed','real_video_upload_probe':'passed','handoff_file_and_revision':'passed','duplicate_handoff':'passed','article_unchanged':'passed','topic_to_task':'passed' if items else 'no snapshot','task_id':task['content_id'],'file_id':file['id']},ensure_ascii=False))
