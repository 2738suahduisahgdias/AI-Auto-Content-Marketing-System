import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import DemoWorkbench from './DemoWorkbench';
import { sections } from './model';

vi.mock('./OriginalWorkspace',()=>({default:({path}:{path:string})=><div data-testid="original-workspace">原后台业务组件 {path}</div>}));
vi.mock('./OriginalTopics',()=>({default:()=> <div>原系统选题页面在独立测试中验证，直接复用原页面和原后台数据接口，保留完整选题管理流程。</div>}));
const nav=()=>within(screen.getByRole('navigation',{name:'后台导航'}));
beforeEach(()=>{cleanup();localStorage.clear();location.hash='';vi.restoreAllMocks()});
afterEach(()=>cleanup());
describe('完整后台改造预览',()=>{
 it('除原选题独立工作区外，演示入口不调用真实后端',()=>{
  const network=vi.spyOn(globalThis,'fetch');render(<DemoWorkbench/>);
  for(const item of sections.flatMap(s=>s.items)){
   fireEvent.click(nav().getByRole('button',{name:new RegExp(item[1])}));
   if(item[0]==='topics')expect(screen.getByRole('main')).toHaveTextContent('直接复用原页面');
   else if(['accounts','competitors','social','retrospective','knowledge','settings','setup'].includes(item[0]))expect(screen.getByTestId('original-workspace')).toHaveTextContent('原后台业务组件');
   else expect(screen.getByRole('main').textContent!.length).toBeGreaterThan(50);
  }
  expect(network).not.toHaveBeenCalled();
 });
 it('排期只是演示草稿，可删除，不需要强制勾选',()=>{
  const network=vi.spyOn(globalThis,'fetch');render(<DemoWorkbench/>);
  fireEvent.click(nav().getByRole('button',{name:'发布与排期'}));
  fireEvent.click(screen.getByRole('button',{name:'加入演示排期'}));
  expect(screen.getByText('草稿 · 未发送')).toBeVisible();
  fireEvent.click(screen.getByRole('button',{name:/移除排期/}));
  expect(screen.getByRole('heading',{name:'还没有排期'})).toBeVisible();
  expect(network).not.toHaveBeenCalled();
 });
 it('内容项目直接打开原映序工作台，不展示简化分镜编辑器',()=>{
 render(<DemoWorkbench/>);fireEvent.click(nav().getByRole('button',{name:'内容项目'}));
 expect(document.querySelector('iframe')).toBeNull();
 expect(document.querySelector('.yx-native-toolbar')).toBeNull();
 expect(document.querySelector('.yx-native [data-page]')).toBeNull();
 expect(screen.getByText('规格与节奏')).toBeVisible();
 fireEvent.click(screen.getByRole('button',{name:/规格与节奏/}));
 expect(document.querySelector('.yx-native #main')?.textContent?.length).toBeGreaterThan(200);
 expect(screen.queryByLabelText('制作方式 · 镜头覆盖')).not.toBeInTheDocument();
 });

 it('今日工作读取实际映序草稿，继续创作保持标题和阶段一致',()=>{
 localStorage.setItem('yingxu-demo-v1',JSON.stringify({manuscript:{title:'我的真实草稿',text:'测试文案',versions:[]},stage:0,topics:[],shots:[],drafts:{},brand:{},models:{},workflowV3:true,authoringV1:true}));
 render(<DemoWorkbench/>);
 expect(screen.getByRole('heading',{name:'我的真实草稿'})).toBeVisible();
 expect(screen.getByText('上次编辑：规格与节奏')).toBeVisible();
 expect(screen.queryByRole('button',{name:'新建项目'})).not.toBeInTheDocument();
 expect(screen.queryByText('一款咖啡杯的日常')).not.toBeInTheDocument();
 fireEvent.click(screen.getByRole('button',{name:'继续创作'}));
 expect(document.querySelector('.yx-native #main')).toHaveTextContent('我的真实草稿');
 expect(document.querySelector('.yx-native .step.active')).toHaveTextContent('规格与节奏');
 });

});
