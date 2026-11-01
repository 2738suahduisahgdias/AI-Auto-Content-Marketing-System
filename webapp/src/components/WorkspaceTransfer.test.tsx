import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import WorkspaceTransfer from './WorkspaceTransfer';
const mockApi=vi.hoisted(()=>vi.fn());vi.mock('../lib/api',()=>({api:mockApi,errorText:(e:Error)=>e.message,jsonOptions:(method:string,payload:unknown)=>({method,body:JSON.stringify(payload)})}));
afterEach(()=>{cleanup();mockApi.mockReset()});
it('恢复只提交新路径，不切换或覆盖当前工作区',async()=>{
 mockApi.mockResolvedValue({path:'/Volumes/restored',note:'已恢复到新目录'});render(<WorkspaceTransfer/>);
 fireEvent.change(screen.getByLabelText('新的导出／恢复目录'),{target:{value:'/Volumes/restored'}});
 fireEvent.change(screen.getByLabelText('迁移包目录'),{target:{value:'/Volumes/package'}});
 fireEvent.click(screen.getByText('校验并恢复到新目录'));
 await waitFor(()=>expect(mockApi).toHaveBeenCalledWith('/api/workspace/restore',{method:'POST',body:JSON.stringify({destination:'/Volumes/restored',package:'/Volumes/package'})}));
 expect(await screen.findByText('已恢复到新目录 · /Volumes/restored')).toBeTruthy();
});
