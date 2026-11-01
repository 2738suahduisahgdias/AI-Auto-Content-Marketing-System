import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,describe,expect,it,vi} from 'vitest';
import RenderCache from './RenderCache';
const mockApi=vi.hoisted(()=>vi.fn());
vi.mock('../lib/api',()=>({api:mockApi,errorText:(e:Error)=>e.message,jsonOptions:(method:string,payload:unknown)=>({method,body:JSON.stringify(payload)})}));
afterEach(()=>{cleanup();mockApi.mockReset()});
const cache={bytes:1024,files:2,reclaimable_bytes:512,protected_files:1,limit_gb:20,path:'/Volumes/cache'};
describe('RenderCache',()=>{
 it('saves a capacity and sends only the cache clear action',async()=>{
  mockApi.mockResolvedValue(cache);render(<RenderCache/>);
  fireEvent.change(await screen.findByLabelText('缓存上限（GB）'),{target:{value:'40'}});
  fireEvent.click(screen.getByRole('button',{name:'保存容量'}));
  await waitFor(()=>expect(mockApi).toHaveBeenCalledWith('/api/yingxu-cache',{method:'POST',body:JSON.stringify({action:'limit',limit_gb:40})}));
  await screen.findByText('容量上限已保存；不会自动删除素材。');
  fireEvent.click(screen.getByRole('button',{name:'清理可重建缓存'}));
  await waitFor(()=>expect(mockApi).toHaveBeenCalledWith('/api/yingxu-cache',{method:'POST',body:JSON.stringify({action:'clear',limit_gb:40})}));
  expect(screen.getByText('1 个文件已被作为素材引用，清理时保留。')).toBeTruthy();
 });
 it('shows busy-render failure without claiming cleanup success',async()=>{
  mockApi.mockResolvedValueOnce(cache).mockRejectedValueOnce(new Error('正在渲染，请稍后重试'));
  render(<RenderCache/>);fireEvent.click(await screen.findByRole('button',{name:'清理可重建缓存'}));
  expect(await screen.findByText('正在渲染，请稍后重试')).toBeTruthy();
  expect(screen.queryByText(/已释放/)).toBeNull();
 });
});
