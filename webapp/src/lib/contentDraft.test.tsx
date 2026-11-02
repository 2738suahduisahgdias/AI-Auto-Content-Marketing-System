import {act,cleanup,renderHook} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {useContentDraft} from './contentDraft';
afterEach(()=>{cleanup();vi.restoreAllMocks()});
it('retains edited and generated content across an immediate reload',()=>{
 const first=renderHook(()=>useContentDraft('article:one:revision1',{text:'server',images:[]}));
 act(()=>first.result.current[1]({text:'AI result with edits',images:[]}));first.unmount();
 const reopened=renderHook(()=>useContentDraft('article:one:revision1',{text:'server',images:[]}));
 expect(reopened.result.current[0].text).toBe('AI result with edits');
});
it('isolates projects and does not overwrite a new server generation with an old draft',()=>{
 const h=renderHook(({key})=>useContentDraft(key,'server-new'),{initialProps:{key:'a:old-version'}});
 act(()=>h.result.current[1]('local old'));
 h.rerender({key:'b:old-version'});expect(h.result.current[0]).toBe('server-new');
 h.rerender({key:'a:new-version'});expect(h.result.current[0]).toBe('server-new');
 h.rerender({key:'a:old-version'});expect(h.result.current[0]).toBe('local old');
});
it('reports a disk storage failure while retaining the editor content',()=>{
 vi.spyOn(Storage.prototype,'setItem').mockImplementation(()=>{throw new Error('quota')});
 const h=renderHook(()=>useContentDraft('failure','old'));
 act(()=>h.result.current[1]('do not lose this'));
 expect(h.result.current[0]).toBe('do not lose this');expect(h.result.current[2]).toContain('自动保存失败');
});
