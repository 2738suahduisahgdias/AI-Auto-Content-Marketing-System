import {cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {MemoryRouter} from 'react-router-dom';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import Today from './Today';
const mocks=vi.hoisted(()=>({api:vi.fn(),refresh:vi.fn(),notify:vi.fn()}));
vi.mock('@/lib/api',async()=>({...await vi.importActual<typeof import('@/lib/api')>('@/lib/api'),api:mocks.api}));
vi.mock('@/AppContext',()=>({useApp:()=>({resources:{core:{topics:[]},topics:{sources:{},jobs:[],recommendations:{all:[{id:'rec1',title:'AI客服如何落地',reason:'品牌匹配',angle:'先讲知识库',content_format:'video',memory_basis:'当前主要依据采集内容推荐'}]}}},refresh:mocks.refresh,notify:mocks.notify})}));
beforeEach(()=>{mocks.refresh.mockResolvedValue(undefined);mocks.api.mockImplementation((path:string)=>Promise.resolve(path==='/api/v2/work-overview'?{generated_at:'today',worker:{running:true},groups:[{key:'video',total:1,items:[{id:'original',title:'真实任务',state:'draft',next:'继续映序制作',href:'/tasks/original'}]},{key:'jobs',total:8,items:[{id:'technical',title:'topics.sync',href:'/settings'}]}]}:{}))});
afterEach(cleanup);
describe('Today',()=>{
 it('keeps original content links and hides technical execution tasks',async()=>{
  render(<MemoryRouter><Today/></MemoryRouter>);
  expect(await screen.findByRole('link',{name:/真实任务/})).toHaveAttribute('href','/tasks/original');
  expect(screen.queryByText('topics.sync')).not.toBeInTheDocument();
  expect(screen.queryByText('全部 Agent 的工作进度')).not.toBeInTheDocument();
 });
 it('generates one cross-platform recommendation and shows selected evidence',async()=>{
  render(<MemoryRouter><Today/></MemoryRouter>);
  fireEvent.click(screen.getByRole('button',{name:'生成今日推荐'}));
  await waitFor(()=>expect(mocks.api).toHaveBeenCalledWith('/api/topics/recommend',expect.objectContaining({body:JSON.stringify({agent:'all'})})));
  expect(screen.getByText('品牌匹配')).toBeInTheDocument();
  expect(screen.getByRole('button',{name:'用这个选题写文章'})).toBeInTheDocument();
 });
});
