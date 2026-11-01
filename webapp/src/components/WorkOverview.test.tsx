import {render,screen,fireEvent,waitFor,cleanup} from '@testing-library/react';
import {MemoryRouter} from 'react-router-dom';
import {it,expect,vi,beforeEach,afterEach} from 'vitest';
import {api} from '../lib/api';
import WorkOverview from './WorkOverview';
vi.mock('../lib/api',()=>({api:vi.fn(),errorText:(e:Error)=>e.message}));
beforeEach(()=>vi.resetAllMocks());
afterEach(cleanup);
const data={generated_at:'2026-11-01T01:00:00Z',boundary:'只读汇总',worker:{running:false,allowed_kinds:null},groups:[{key:'topics',label:'选题 Agent',total:0,items:[]},{key:'video',label:'视频 Agent',total:1,items:[{id:'original-123',title:'原系统视频',state:'draft',next:'继续映序制作',href:'/tasks/original-123',attention:false}]}]};
it('opens original workspaces and preserves last snapshot when refresh fails',async()=>{
 vi.mocked(api).mockResolvedValueOnce(data).mockRejectedValueOnce(new Error('连接失败'));
 render(<MemoryRouter><WorkOverview/></MemoryRouter>);
 fireEvent.click(await screen.findByRole('button',{name:/视频 Agent/}));
 expect(screen.getByRole('link',{name:/原系统视频/})).toHaveAttribute('href','/tasks/original-123');
 expect(screen.getByText(/本地执行器未启动/)).toBeInTheDocument();
 fireEvent.click(screen.getByRole('button',{name:'刷新工作进度'}));
 expect(await screen.findByRole('alert')).toHaveTextContent('下方保留上次快照');
 expect(screen.getByRole('link',{name:/原系统视频/})).toBeInTheDocument();
});
it('does not disguise unavailable backend as no work',async()=>{
 vi.mocked(api).mockRejectedValue(new Error('本地服务未连接'));
 render(<MemoryRouter><WorkOverview/></MemoryRouter>);
 await waitFor(()=>expect(screen.getByRole('alert')).toHaveTextContent('本地服务未连接'));
 expect(screen.queryByText(/暂无未完成工作/)).not.toBeInTheDocument();
});
