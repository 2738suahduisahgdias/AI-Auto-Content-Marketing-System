import {act,cleanup,renderHook} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
const server=vi.hoisted(()=>({workspace:'workspace-A',drafts:new Map<string,{data:unknown;revision:number}>()}));
vi.mock('./api',()=>({jsonOptions:(method:string,payload:unknown)=>({method,body:JSON.stringify(payload)}),errorText:(e:Error)=>e.message,api:vi.fn(async(_path:string,options?:RequestInit)=>{
 if(!options)return {workspace_id:server.workspace,drafts:[...server.drafts].map(([key,r])=>({key,...r}))};
 const p=JSON.parse(String(options.body));const old=server.drafts.get(p.key);if((old?.revision||0)!==p.expected_revision)throw Error('另一窗口已更新');
 server.drafts.set(p.key,{data:p.data,revision:p.expected_revision+1});return {revision:p.expected_revision+1};
})}));
import {initializeContentDrafts,useContentDraft,flushContentDrafts,readContentDraft} from './contentDraft';
afterEach(()=>{cleanup();localStorage.clear();server.drafts.clear()});
it('retains content in the database with browser cache removed and after port change',async()=>{
 await initializeContentDrafts();const h=renderHook(()=>useContentDraft('article:new:title',''));
 act(()=>h.result.current[1]('数据库草稿'));await act(async()=>{await flushContentDrafts()});h.unmount();
 localStorage.clear();await initializeContentDrafts();expect(readContentDraft('article:new:title','')).toBe('数据库草稿');
});
it('isolates workspaces and rejects stale-window writes',async()=>{
 server.workspace='A';await initializeContentDrafts();const h=renderHook(()=>useContentDraft('same-key',''));
 act(()=>h.result.current[1]('A 内容'));await act(async()=>{await flushContentDrafts()});h.unmount();
 server.workspace='B';server.drafts.clear();await initializeContentDrafts();expect(readContentDraft('same-key','B 默认')).toBe('B 默认');
 server.drafts.set('same-key',{data:'其他窗口',revision:1});const b=renderHook(()=>useContentDraft('same-key',''));
 act(()=>b.result.current[1]('本窗口'));await act(async()=>{await expect(flushContentDrafts()).rejects.toThrow()});
 expect(b.result.current[2]).toContain('另一窗口');expect(server.drafts.get('same-key')?.data).toBe('其他窗口');
});
