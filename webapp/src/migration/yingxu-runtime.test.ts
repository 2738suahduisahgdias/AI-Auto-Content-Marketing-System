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

it('uses a real whole-video directing proposal and preserves original shots until adopted',async()=>{
 const root=document.createElement('div');document.body.append(root);root.innerHTML='<span id="crumb"></span><small id="saved"></small><div id="main"></div><div id="modal" hidden></div><div id="toast"></div><input id="upload" type="file">';
 const candidate={palette:{background:'#111111',text:'#EEEEEE',accent:'#D7B56D'},shots:[{title:'第一幕',text:'第一句。',purpose:'提出问题',desc:'曲线下降',motion:'绘制曲线',duration:3,source:'Remotion 代码'},{title:'第二幕',text:'第二句。',purpose:'解释机制',desc:'路径重连',motion:'线条接续',duration:3,source:'Remotion 代码'}],duration_seconds:6,style_summary:'黑白线条',timing_note:'前后递进',duration_source:'uploaded_narration'};
 const planVideo=vi.fn().mockResolvedValue({candidate,input_hash:'real-input'}),change=vi.fn();
 dispose=mountYingxu(root,vi.fn(),vi.fn(),vi.fn(),{initial:{stage:0,workflowV3:true,authoringV1:true,topics:[],shots:[{title:'旧分镜',text:'旧段落',duration:30,source:'Remotion 代码'}],manuscript:{title:'知识讲解',text:'第一句。\n\n第二句。',versions:[]}},onChange:change,upload:vi.fn(),planVideo});
 fireEvent.click(within(root).getByRole('button',{name:'AI 生成视频方案 →'}));
 await waitFor(()=>expect(within(root).getByText('整片编导方案 · 尚未采用')).toBeTruthy());
 expect(planVideo).toHaveBeenCalledTimes(1);expect(change.mock.lastCall?.[0].shots[0].title).toBe('旧分镜');
 fireEvent.click(within(root).getByText('采用此方案（原分镜保留历史）'));
 expect(change.mock.lastCall?.[0].directorPlan.palette).toEqual(candidate.palette);expect(change.mock.lastCall?.[0].shots).toHaveLength(2);expect(change.mock.lastCall?.[0].storyboardHistory[0].shots[0].title).toBe('旧分镜');
 expect(change.mock.lastCall?.[0].shots.map((s:any)=>s.text).join('')).toBe('第一句。第二句。');
});

it('renders a real sample into the sample player without a fake arrangement confirmation',async()=>{
 const root=document.createElement('div');document.body.append(root);root.innerHTML='<span id="crumb"></span><small id="saved"></small><div id="main"></div><div id="modal" hidden></div><div id="toast"></div><input id="upload" type="file">';
 const renderVideo=vi.fn().mockResolvedValue({id:9,url:'/api/files/9/media',original_name:'real-preview.mp4',media_info:{yingxu_preview:true}});
 dispose=mountYingxu(root,vi.fn(),vi.fn(),vi.fn(),{initial:{stage:2,workflowV3:true,authoringV1:true,topics:[],shots:[{title:'代码画面',text:'讲解',duration:6,source:'Remotion 代码'}],manuscript:{title:'视频',text:'讲解',versions:[]}},onChange:vi.fn(),upload:vi.fn(),renderVideo});
 expect(within(root).queryByText('确认编排，继续分段制作')).toBeNull();
 fireEvent.click(within(root).getByRole('button',{name:'渲染前 6 秒样片'}));
 await waitFor(()=>expect(root.querySelector('video[aria-label="真实渲染样片"]')?.getAttribute('src')).toBe('/api/files/9/media'));
 expect(renderVideo).toHaveBeenCalledWith(true,undefined);
});


it('checks a real code film against narration duration without demo missing-asset or 30-second warnings',()=>{
 const root=document.createElement('div');document.body.append(root);root.innerHTML='<span id="crumb"></span><small id="saved"></small><div id="main"></div><div id="modal" hidden></div><div id="toast"></div><input id="upload" type="file">';
 dispose=mountYingxu(root,vi.fn(),vi.fn(),vi.fn(),{initial:{stage:3,reviewed:true,workflowV3:true,authoringV1:true,topics:[],voiceFileId:1,voiceDuration:147,rhythm:'旁白驱动',nativeFinal:{id:10,url:'/api/files/10/media',stale:false},shots:[{title:'代码画面',text:'完整原稿',duration:147,source:'Remotion 代码',status:'待制作'}],manuscript:{title:'视频',text:'完整原稿',versions:[]}},onChange:vi.fn(),upload:vi.fn()});
 expect(within(root).getByText('真实成片已生成 · 1 个代码镜头')).toBeTruthy();
 expect(within(root).getByText('147 秒 / 旁白实际时长 147 秒')).toBeTruthy();
 expect(root.textContent).not.toContain('目标 30 秒');expect(root.textContent).not.toContain('个分镜待准备');expect(root.textContent).not.toContain('未配置录音');
});
