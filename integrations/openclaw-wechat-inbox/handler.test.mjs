import test from 'node:test';
import assert from 'node:assert/strict';
import {handleInbound} from './handler.mjs';
const event={channel:'openclaw-weixin', senderId:'owner', messageId:'actual-id', content:'原始消息'};
const env={CONTENT_AGENT_WECHAT_SENDER_ID:'owner'};
for (const status of ['saved','duplicate']) test(status+' needs persisted receipt', async()=>{
  let args; const out=await handleInbound(event,{}, {env,run:async(...a)=>{args=a;return {stdout:JSON.stringify({status,id:'record',ingest_status:'saved'})}}});
  assert.equal(out.text,'已保存到待分类');assert.equal(JSON.parse(args[1][0]).msgid,'openclaw-weixin:actual-id');
});
test('cannot acknowledge tool error or malformed response',async()=>{
  for(const stdout of ['{}','not json',JSON.stringify({status:'saved'})]) {
    const out=await handleInbound(event,{}, {env,run:async()=>({stdout})});assert.match(out.text,/保存失败/);
  }
});
test('missing provider ID fails closed',async()=>{const out=await handleInbound({...event,messageId:undefined},{},{env,run:()=>{throw Error('must not run')}});assert.match(out.text,/保存失败/)});
test('other senders, channels and groups are untouched',async()=>{
  for (const e of [{...event,senderId:'other'},{...event,channel:'other'},{...event,isGroup:true}])
    assert.equal(await handleInbound(e,{}, {env,run:()=>{throw Error('must not run')}}),undefined);
});
test('timeout never reports success',async()=>{assert.match((await handleInbound(event,{}, {env,run:async()=>{throw Error('timeout')}})).text,/保存失败/)});
