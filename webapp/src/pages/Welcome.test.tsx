import {cleanup,fireEvent,render,screen} from '@testing-library/react';
import {MemoryRouter,Route,Routes} from 'react-router-dom';
import {afterEach,expect,it,vi} from 'vitest';
import Welcome from './Welcome';
import {api} from '../lib/api';
vi.mock('../AppContext',()=>({useApp:()=>({refresh:vi.fn().mockResolvedValue(undefined)})}));
vi.mock('../lib/api',()=>({api:vi.fn(),jsonOptions:(method:string,body:unknown)=>({method,body:JSON.stringify(body)}),errorText:(e:Error)=>e.message}));
afterEach(()=>{cleanup();vi.clearAllMocks()});
it('resumes saved onboarding and opens the original task returned by the server',async()=>{
 vi.mocked(api).mockImplementation(async(path)=>path==='/api/v2/license'?{mode:'required',status:'valid',onboarding:{steps:['storage','environment','capabilities'],completed:false,projectId:'old-task'}}:path==='/api/v2/license/first-project'?{projectId:'old-task'}:{dependencies:[]});
 render(<MemoryRouter><Routes><Route path="/" element={<Welcome/>}/><Route path="/tasks/:id" element={<p>原映序编辑器</p>}/></Routes></MemoryRouter>);
 fireEvent.click(await screen.findByRole('button',{name:'继续我的第一条视频'}));
 await screen.findByText('原映序编辑器');
 expect(api).toHaveBeenCalledWith('/api/v2/license/first-project',expect.objectContaining({method:'POST'}));
});
