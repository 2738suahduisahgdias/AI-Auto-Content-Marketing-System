import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,describe,expect,it,vi} from 'vitest';
import LocalAssets from './LocalAssets';
const mockApi=vi.hoisted(()=>vi.fn());
vi.mock('../lib/api',()=>({api:mockApi,errorText:(e:Error)=>e.message,jsonOptions:(method:string,payload:unknown)=>({method,body:JSON.stringify(payload)})}));
afterEach(()=>{cleanup();mockApi.mockReset()});
describe('LocalAssets',()=>{
 it('imports as reference without requiring copy selection',async()=>{
  mockApi.mockResolvedValue({assets:[]});render(<LocalAssets/>);
  fireEvent.change(screen.getByLabelText('视频、音频、图片或字幕路径'),{target:{value:'/Volumes/media/test.mp4'}});
  fireEvent.click(screen.getByRole('button',{name:'导入素材'}));
  await waitFor(()=>expect(mockApi).toHaveBeenCalledWith('/api/v2/local-assets',{method:'POST',body:JSON.stringify({path:'/Volumes/media/test.mp4',copy:false})}));
 });
 it('retains the entered path after failed fingerprint validation',async()=>{
  mockApi.mockResolvedValueOnce({assets:[{id:'asset-1',source:{kind:'local_reference',path:'/old.mp4'},storage_key:'local-reference/asset-1',available:false,problem:'文件未连接'}]}).mockRejectedValueOnce(new Error('文件内容不一致'));
  render(<LocalAssets/>);fireEvent.click(await screen.findByRole('button',{name:'重新定位'}));
  fireEvent.change(screen.getByLabelText('原素材的新位置'),{target:{value:'/wrong.mp4'}});
  fireEvent.click(screen.getByRole('button',{name:'验证并重新定位'}));
  expect(await screen.findByText('文件内容不一致')).toBeInTheDocument();
  expect(screen.getByLabelText('原素材的新位置')).toHaveValue('/wrong.mp4');
 });
});
