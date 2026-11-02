import {beforeEach,expect,it,vi} from 'vitest';
import {fireEvent,render,screen,waitFor,cleanup} from '@testing-library/react';
import {MemoryRouter,Routes,Route} from 'react-router-dom';
import YingxuVideoWorkspace from './YingxuVideoWorkspace';
const store=vi.hoisted(()=>({tasks:[] as any[],refresh:vi.fn(),request:vi.fn()}));
vi.mock('../AppContext',()=>({useApp:()=>({resources:{core:{tasks:store.tasks}},refresh:store.refresh})}));
vi.mock('../lib/api',()=>({api:(...args:any[])=>store.request(...args),jsonOptions:(method:string,payload:any)=>({method,body:JSON.stringify(payload)})}));
const makeTask=(id:string,title:string)=>({content_id:id,title,state:'topic_approved',scripts:{master:'保留原稿'},files:[],asset_plan:[],events:[],updated_at:id});
function open(path:string){return render(<MemoryRouter initialEntries={[path]}><Routes><Route path="/tasks/:id?" element={<YingxuVideoWorkspace/>}/></Routes></MemoryRouter>)}
beforeEach(()=>{cleanup();store.tasks=[];store.refresh.mockReset();store.request.mockReset()});
it('整个任务页面使用映序，项目切换读取同一套原任务',async()=>{
 store.tasks=[makeTask('20261101-001','第一条视频'),makeTask('20261101-002','第二条视频')];
 open('/tasks/20261101-001');
 expect(screen.queryByLabelText('任务筛选')).toBeNull();expect(document.querySelector('.tasks-layout')).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'第一条视频 ⌄'}));
 expect(screen.getByRole('dialog',{name:'切换视频项目'})).toBeTruthy();
 fireEvent.click(screen.getByRole('link',{name:/第二条视频/}));
 await waitFor(()=>expect(screen.getByRole('button',{name:'第二条视频 ⌄'})).toBeTruthy());
 expect(screen.queryByRole('dialog')).toBeNull();expect(screen.getByLabelText('正文')).toHaveValue('保留原稿');
});
it('映序新建视频使用原接口并进入文案步骤',async()=>{
 store.request.mockImplementation(async()=>{const task=makeTask('20261101-003','新视频');store.tasks=[task];return task});
 open('/tasks');fireEvent.click(screen.getByRole('button',{name:'新建视频'}));
 fireEvent.change(screen.getByLabelText('视频名称'),{target:{value:'新视频'}});
 fireEvent.click(screen.getByRole('button',{name:'创建并开始写稿 →'}));
 await waitFor(()=>expect(screen.getByRole('button',{name:'新视频 ⌄'})).toBeTruthy());
 expect(store.request.mock.calls[0][0]).toBe('/api/tasks');expect(screen.queryByText('发布方式')).toBeNull();
});

it('仅浏览六步不会变成内容修改，实际编辑自动保留草稿',async()=>{
 store.tasks=[makeTask('20261102-099','导航检查')];
 open('/tasks/20261102-099');
 expect(screen.queryByText(/本机草稿已自动保留/)).toBeNull();
 for(const name of ['规格与节奏','文案与分镜','样片与制作','合成与检查','交付发布 Agent','选题与文案']){
   fireEvent.click(screen.getByRole('button',{name:new RegExp('^[1-6]\\s*'+name+'$')}));
   expect(screen.queryByText(/本机草稿已自动保留/)).toBeNull();
   expect(document.querySelectorAll('.step.done')).toHaveLength(0);
 }
 fireEvent.input(screen.getByLabelText('正文'),{target:{value:'修改后的真实正文'}});
 await waitFor(()=>expect(screen.getByText(/本机草稿已自动保留/)).toBeTruthy());
 expect(store.request).not.toHaveBeenCalled();
});
it('检查阶段优先展示关联成片，不显示森林演示图',()=>{
 const task=makeTask('20261102-098','成片预览');
 Object.assign(task,{files:[{id:7,kind:'video',original_name:'客服.mp4',url:'/api/files/7/media'}],source:{yingxu_handoff:{file_id:7}}});
 store.tasks=[task];open('/tasks/20261102-098');
 fireEvent.click(screen.getByRole('button',{name:/^5\s*合成与检查$/}));
 expect(screen.getByLabelText('当前项目成片')).toHaveAttribute('src','/api/files/7/media');
 expect(document.querySelector('#preview-img')).toBeNull();
});
