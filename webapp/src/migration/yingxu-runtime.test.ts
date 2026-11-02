import {afterEach,describe,expect,it,vi} from 'vitest';
import {fireEvent,waitFor,within} from '@testing-library/dom';
import {mountYingxu} from './yingxu-runtime';
let dispose:(()=>void)|undefined;
afterEach(()=>{dispose?.();document.body.innerHTML='';localStorage.clear()});
describe('原系统中的映序编辑器',()=>{
 it('使用原选题入口，版本写回任务，AI仅返回候选',async()=>{
 const root=document.createElement('div');document.body.append(root);
 root.innerHTML='<span id="crumb"></span><small id="saved"></small><div id="main"></div><div id="modal" hidden></div><div id="toast"></div><input id="upload" type="file">';
 const navigate=vi.fn(),persist=vi.fn().mockResolvedValue({}),generateText=vi.fn().mockResolvedValue('真实接口候选'),change=vi.fn();
 dispose=mountYingxu(root,vi.fn(),vi.fn(),navigate,{initial:{stage:-1,workflowV3:true,authoringV1:true,topics:[],shots:[],manuscript:{title:'AI 客服如何落地',text:'已有原稿',versions:[]}},onChange:change,upload:vi.fn(),persist,generateText,sourceLabel:'原选题中心 · topic_1'});
 const ui=within(root);
 expect(ui.getByText('本任务来源：原选题中心 · topic_1')).toBeTruthy();
 expect(ui.queryByText('保存选题')).toBeNull();expect(root.querySelector('iframe')).toBeNull();
 fireEvent.click(ui.getByText('前往原选题中心'));expect(navigate).toHaveBeenCalledWith('topics');
 fireEvent.click(ui.getByText('保存文案版本'));await waitFor(()=>expect(persist).toHaveBeenCalledTimes(1));
 fireEvent.click(ui.getByText('生成起草候选'));await waitFor(()=>expect(ui.getByText('真实接口候选')).toBeTruthy());
 expect((root.querySelector('#manuscript-text') as HTMLTextAreaElement).value).toBe('已有原稿');
 expect(localStorage.getItem('yingxu-demo-v1')).toBeNull();
 expect(change.mock.lastCall?.[0].manuscript.versions[0].text).toBe('已有原稿');
 });
 it('单镜预览传递选择的序号而不是重复渲染开头',async()=>{
   const root=document.createElement('div');document.body.append(root);
   root.innerHTML='<span id="crumb"></span><small id="saved"></small><div id="main"></div><div id="modal" hidden></div><div id="toast"></div><input id="upload" type="file">';
   const renderVideo=vi.fn().mockResolvedValue({});
   dispose=mountYingxu(root,vi.fn(),vi.fn(),vi.fn(),{initial:{stage:2,workflowV3:true,authoringV1:true,shots:[{title:'实拍',text:'第一镜',source:'人工上传',duration:2},{title:'讲解',text:'第二镜',source:'Remotion 代码',duration:6}],manuscript:{title:'录音验收',text:'原稿',versions:[]}},onChange:vi.fn(),upload:vi.fn(),renderVideo});
   const buttons=within(root).getAllByText('渲染此镜预览');
   fireEvent.click(buttons[1]);
   await waitFor(()=>expect(renderVideo).toHaveBeenCalledWith(true,1));
 });

 it('本地录音默认引用并写回同一任务文件 ID',async()=>{
   const root=document.createElement('div');document.body.append(root);
   root.innerHTML='<span id="crumb"></span><small id="saved"></small><div id="main"></div><div id="modal" hidden></div><div id="toast"></div><input id="upload" type="file">';
   const change=vi.fn(),importLocal=vi.fn().mockResolvedValue({id:42,url:'/api/files/42/media',original_name:'voice.wav',media_info:{mime_type:'audio/wav',duration_seconds:8}});
   dispose=mountYingxu(root,vi.fn(),vi.fn(),vi.fn(),{initial:{stage:0,rhythm:"旁白驱动",topics:[],workflowV3:true,authoringV1:true,shots:[],manuscript:{title:'录音',text:'原稿',versions:[]}},onChange:change,upload:vi.fn(),importLocal});
   const button=within(root).getByText('上传旁白');
   expect(button).toBeTruthy();fireEvent.click(button);
   fireEvent.change(root.querySelector('#local-material-path')!,{target:{value:'/Volumes/media/voice.wav'}});
   fireEvent.click(within(root).getByText('添加素材'));
   await waitFor(()=>expect(importLocal).toHaveBeenCalledWith('/Volumes/media/voice.wav','audio',false,'audio/*'));
   await waitFor(()=>expect(change.mock.lastCall?.[0].voiceFileId).toBe(42));
 });

});

it('all video stages remain clickable without eval under strict CSP',async()=>{
 const root=document.createElement('div');document.body.append(root);
 root.innerHTML='<span id="crumb"></span><small id="saved"></small><div id="main"></div><div id="modal" hidden></div><div id="toast"></div><input id="upload" type="file">';
 const blocked=vi.spyOn(globalThis,'eval').mockImplementation(()=>{throw Error('CSP forbids eval')});
 try {
 dispose=mountYingxu(root,vi.fn(),vi.fn(),vi.fn(),{initial:{stage:-1,workflowV3:true,authoringV1:true,topics:[],shots:[],manuscript:{title:'验收',text:'原稿',versions:[]}},onChange:vi.fn(),upload:vi.fn()});
 await waitFor(()=>expect(root.querySelector('[data-yx-click]')).toBeNull());
 for(const label of ['规格与节奏','文案与分镜','样片与制作','合成与检查','交付发布 Agent','选题与文案']) {
   const button=within(root).getByRole('button',{name:new RegExp("^[1-6✓]\\s*"+label+"$")});
   const before=root.querySelector('#main')!.innerHTML;fireEvent.click(button);
   await waitFor(()=>expect(root.querySelector('#main')!.innerHTML).not.toBe(before));
 }
 expect(blocked).not.toHaveBeenCalled();
 } finally {blocked.mockRestore()}
});
