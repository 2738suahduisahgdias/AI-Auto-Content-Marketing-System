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
});
