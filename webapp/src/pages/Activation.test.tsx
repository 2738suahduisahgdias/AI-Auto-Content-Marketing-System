import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {MemoryRouter,Route,Routes} from 'react-router-dom';
import {afterEach,expect,it,vi} from 'vitest';
import Activation from './Activation';
import {api} from '../lib/api';
vi.mock('../lib/api',()=>({api:vi.fn(),jsonOptions:(method:string,body:unknown)=>({method,body:JSON.stringify(body)}),errorText:(e:Error)=>e.message}));
const state={mode:'required',status:'unactivated',configured:true,requestCode:'YXREQ1.test',onboarding:{completed:false}};
afterEach(()=>{cleanup();vi.clearAllMocks()});
it('keeps the input retryable when activation fails, and opens guide only after success',async()=>{
 vi.mocked(api).mockResolvedValueOnce(state).mockRejectedValueOnce(Error('授权签名无效')).mockResolvedValueOnce({...state,status:'valid'});
 render(<MemoryRouter><Routes><Route path="/" element={<Activation/>}/><Route path="/welcome" element={<p>新手引导已打开</p>}/></Routes></MemoryRouter>);
 await screen.findByDisplayValue('YXREQ1.test');
 fireEvent.change(screen.getByLabelText('粘贴完整授权码'),{target:{value:'test-token'}});
 fireEvent.click(screen.getByRole('button',{name:'验证并激活'}));
 await screen.findByText('授权签名无效');expect(screen.getByDisplayValue('test-token')).toBeInTheDocument();
 fireEvent.click(screen.getByRole('button',{name:'验证并激活'}));
 await screen.findByText('新手引导已打开');
});
it('does not enable activation without a configured issuer public key',async()=>{
 vi.mocked(api).mockResolvedValue({...state,configured:false});render(<MemoryRouter><Activation/></MemoryRouter>);
 await screen.findByText(/尚未配置签发公钥/);fireEvent.change(screen.getByLabelText('粘贴完整授权码'),{target:{value:'anything'}});
 await waitFor(()=>expect(screen.getByRole('button',{name:'验证并激活'})).toBeDisabled());
});
