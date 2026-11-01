# Local isolated preview only (8876). Creates acceptance records; never point at production.
from pathlib import Path
exec((Path(__file__).with_name('verify-migration-http.py')).read_text().split("article=call")[0])
task=call('/api/tasks','POST',{'title':'AI 客服如何落地 · 真实渲染验收','content':'先梳理知识，再连接业务，最后灰度上线。'})
shots=[{'title':t,'label':t,'text':text,'desc':text,'duration':4,'source':'Remotion 代码','status':'待生成','image':i} for i,(t,text) in enumerate([('知识准备','整理高频问题，明确回答边界。'),('连接业务','接入订单和工单，保留人工转接。'),('灰度上线','小范围测试，再逐步扩大覆盖。')])]
snapshot={'stage':2,'shots':shots,'topics':[],'workflowV3':True,'authoringV1':True,'format':'1080 × 1920 · 竖屏','rhythm':'音乐驱动 · 无旁白','manuscript':{'title':task['title'],'text':task['scripts']['douyin'],'versions':[]}}
task=call('/api/tasks/'+task['content_id']+'/yingxu','PUT',{'revision':0,'snapshot':snapshot})
Path('/tmp/migration-render-task.txt').write_text(task['content_id'])
for preview in (True,False):
 file=call('/api/tasks/'+task['content_id']+'/yingxu-render','POST',{'revision':1,'preview':preview})
 assert abs(file['media_info']['duration_seconds']-(10 if preview else 12))<.2,file
 print(json.dumps({'task_id':task['content_id'],'preview':preview,'file_id':file['id'],'duration':file['media_info']['duration_seconds']},ensure_ascii=False),flush=True)
 if not preview:
  handoff=call('/api/tasks/'+task['content_id']+'/yingxu-handoff','POST',{'file_id':file['id'],'revision':1})
  assert not handoff['published_at']
  print('真实成片交付待审核通过',flush=True)
