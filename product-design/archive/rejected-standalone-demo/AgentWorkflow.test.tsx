import {afterEach,expect,it} from 'vitest';
import {cleanup,fireEvent,render,screen} from '@testing-library/react';
import {useState} from 'react';
import AgentWorkflow,{defaultAgentState} from './AgentWorkflow';
afterEach(cleanup);
function Harness(){const [state,set]=useState(defaultAgentState);const [page,go]=useState('articles');return <AgentWorkflow page={page} state={state} set={set} go={go} article="绝对保证效果" title="测试标题"/>}
it('文章送检后可以检查并进入发布准备，填写请求不会报告成功',()=>{render(<Harness/>);fireEvent.click(screen.getByText('将文章送入质检'));fireEvent.click(screen.getByText('检查当前文章（本地基础检查）'));expect(screen.getByRole('status')).toHaveTextContent('绝对保证');fireEvent.click(screen.getByText('前往发布准备'));fireEvent.click(screen.getByText('引用当前文章正文'));expect(screen.getByLabelText('发布正文')).toHaveValue('绝对保证效果');fireEvent.click(screen.getByText('打开后台并填写（待接入）'));expect(screen.queryByText('填写成功')).not.toBeInTheDocument()});
it('修改规则使旧检查结果失效',()=>{render(<Harness/>);fireEvent.click(screen.getByText('将文章送入质检'));fireEvent.click(screen.getByText('检查当前文章（本地基础检查）'));fireEvent.change(screen.getByLabelText('质检规则'),{target:{value:'新增规则'}});expect(screen.getByRole('status')).toHaveTextContent('已过期')});
