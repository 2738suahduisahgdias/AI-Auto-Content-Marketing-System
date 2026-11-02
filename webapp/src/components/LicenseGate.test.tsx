import {render,screen,cleanup} from '@testing-library/react';
import {MemoryRouter,Routes,Route} from 'react-router-dom';
import {it,expect,vi,afterEach} from 'vitest';
import LicenseGate from './LicenseGate';
import {api} from '../lib/api';
vi.mock('../lib/api',()=>({api:vi.fn(),errorText:String}));
afterEach(()=>{cleanup();sessionStorage.clear();vi.resetAllMocks()});
function mount(path:string,onboarding:Record<string,boolean>){
 vi.mocked(api).mockResolvedValue({mode:'required',status:'valid',onboarding});
 render(<MemoryRouter initialEntries={[path]}><LicenseGate><Routes><Route path="/" element={<p>今日工作内容</p>}/><Route path="/tasks/existing" element={<p>已有视频内容</p>}/><Route path="/welcome" element={<p>首次引导内容</p>}/></Routes></LicenseGate></MemoryRouter>);
}
it('does not interrupt existing task links with onboarding',async()=>{mount('/tasks/existing',{completed:false,presented:false});expect(await screen.findByText('已有视频内容')).toBeTruthy()});
it('does not repeat onboarding after presentation across browser sessions',async()=>{mount('/',{completed:false,presented:true});expect(await screen.findByText('今日工作内容')).toBeTruthy()});
it('still offers first time guidance on home',async()=>{mount('/',{completed:false,presented:false});expect(await screen.findByText('首次引导内容')).toBeTruthy()});
