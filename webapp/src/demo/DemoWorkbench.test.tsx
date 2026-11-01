import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import DemoWorkbench from './DemoWorkbench';
import { sections, templates } from './model';

const nav=()=>within(screen.getByRole('navigation',{name:'后台导航'}));
beforeEach(()=>{cleanup();localStorage.clear();location.hash='';vi.restoreAllMocks()});
afterEach(()=>cleanup());
describe('完整后台改造预览',()=>{
 it('全部业务入口均能打开，且不调用真实后端',()=>{
  const network=vi.spyOn(globalThis,'fetch');render(<DemoWorkbench/>);
  for(const item of sections.flatMap(s=>s.items)){
   fireEvent.click(nav().getByRole('button',{name:new RegExp(item[1])}));
   expect(screen.getByRole('main').textContent!.length).toBeGreaterThan(50);
  }
  expect(network).not.toHaveBeenCalled();
 });
 it('创建广告项目使用视频模型默认路线，单稿可以进入制作',()=>{
  render(<DemoWorkbench/>);fireEvent.click(screen.getByRole('button',{name:'新建项目'}));
  fireEvent.change(screen.getByLabelText('项目名称'),{target:{value:'广告验收'}});
  fireEvent.change(screen.getByLabelText('内容场景'),{target:{value:'产品广告'}});
  fireEvent.click(screen.getByRole('button',{name:'创建并编辑简报'}));
  fireEvent.click(screen.getByRole('button',{name:'编辑文案 →'}));
  expect(screen.getByRole('button',{name:'进入视频制作 →'})).toBeDisabled();
  fireEvent.change(screen.getByRole('textbox',{name:'视频文案'}),{target:{value:'只需要一份有效文案'}});
  fireEvent.click(screen.getByRole('button',{name:'进入视频制作 →'}));
  expect(screen.getByLabelText('制作方式 · 镜头覆盖')).toHaveValue('AI 视频');
  expect(screen.getByRole('button',{name:'上传人物／物品参考图'})).toBeVisible();
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
 });
 it('文案保存后重新挂载恢复，文章转视频不覆盖原文',()=>{
  render(<DemoWorkbench/>);fireEvent.click(nav().getByRole('button',{name:'文章与文案'}));
  fireEvent.change(screen.getByRole('textbox',{name:'文章内容'}),{target:{value:'原文章\n原始正文'}});
  fireEvent.click(screen.getByRole('button',{name:'复制为视频文案 →'}));
  fireEvent.click(screen.getByRole('button',{name:/2\s*文案编辑/}));
  expect(screen.getByRole('textbox',{name:'视频文案'})).toHaveValue('原文章\n原始正文');
  fireEvent.change(screen.getByRole('textbox',{name:'视频文案'}),{target:{value:'视频改稿'}});
  fireEvent.click(screen.getByRole('button',{name:/^保存演示$/}));
  cleanup();render(<DemoWorkbench/>);
  fireEvent.click(screen.getByRole('button',{name:/2\s*文案编辑/}));
  expect(screen.getByRole('textbox',{name:'视频文案'})).toHaveValue('视频改稿');
  fireEvent.click(nav().getByRole('button',{name:'文章与文案'}));
  expect(screen.getByRole('textbox',{name:'文章内容'})).toHaveValue('原文章\n原始正文');
 });
 it('未配置 AI 提供依赖入口，不假报生成成功',()=>{
  render(<DemoWorkbench/>);fireEvent.click(screen.getByRole('button',{name:'继续创作'}));
  fireEvent.click(screen.getByRole('button',{name:/2\s*文案编辑/}));
  fireEvent.click(screen.getByRole('button',{name:'AI 辅助写作'}));
  const dialog=screen.getByRole('dialog');expect(dialog).toHaveTextContent('API');
  fireEvent.click(within(dialog).getByRole('button',{name:'前往对应配置'}));
  expect(screen.getByRole('heading',{name:'能力与设置'})).toBeVisible();
  expect(screen.getAllByPlaceholderText('演示版不输入真实密钥；正式版使用系统安全存储')[0]).toBeDisabled();
 });
 it('模板只应用当前项目镜头，返回制作可见效果提示词',()=>{
  render(<DemoWorkbench/>);fireEvent.click(nav().getByRole('button',{name:'模板与效果'}));
  fireEvent.click(screen.getAllByRole('button',{name:'查看效果与提示词'})[2]);
  fireEvent.click(screen.getByRole('button',{name:'应用到当前镜头'}));
  expect(screen.getByLabelText('画面与效果提示词')).toHaveValue(templates[2].prompt);
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
});
