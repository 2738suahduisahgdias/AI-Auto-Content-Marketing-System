import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import WechatConnection from './WechatConnection';
import {api} from '@/lib/api';
vi.mock('@/lib/api',async()=>({...await vi.importActual<typeof import('@/lib/api')>('@/lib/api'),api:vi.fn()}));
afterEach(()=>{cleanup();vi.useRealTimers();vi.clearAllMocks()});
it('automatically confirms a scanned QR without asking the user to click another button',async()=>{
 vi.useFakeTimers();vi.mocked(api).mockResolvedValueOnce({status:'wait',qrcode_url:'https://liteapp.weixin.qq.com/q/test'}).mockResolvedValueOnce({status:'connected'});
 await act(async()=>{render(<WechatConnection/>)});
 await act(async()=>{await vi.advanceTimersByTimeAsync(3100)});
 expect(api).toHaveBeenCalledWith('/api/topics/wechat/client/poll',expect.objectContaining({method:'POST'}));
 expect(screen.getByText('已连接')).toBeInTheDocument();
 expect(screen.queryByRole('link',{name:'打开微信扫码页'})).not.toBeInTheDocument();
});
it('requires an explicit second confirmation before disconnecting',async()=>{
 vi.mocked(api).mockResolvedValue({status:'connected'});render(<WechatConnection/>);
 await screen.findByText('已连接');fireEvent.click(screen.getByText('更换账号或断开连接'));fireEvent.click(screen.getByRole('button',{name:'断开并重新连接'}));
 expect(api).not.toHaveBeenCalledWith('/api/topics/wechat/client/disconnect',expect.anything());
 expect(screen.getByRole('dialog')).toBeInTheDocument();fireEvent.click(screen.getByRole('button',{name:'保留连接'}));
 expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});
it('does not offer an expired scan link',async()=>{
 vi.mocked(api).mockResolvedValue({status:'expired',qrcode_url:'https://liteapp.weixin.qq.com/q/old'});render(<WechatConnection/>);
 await waitFor(()=>expect(screen.getByText('二维码已过期')).toBeInTheDocument());expect(screen.queryByRole('link',{name:'打开微信扫码页'})).not.toBeInTheDocument();
});
