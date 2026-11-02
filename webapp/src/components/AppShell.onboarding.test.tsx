import {render,screen,within,cleanup,fireEvent} from '@testing-library/react';
import {MemoryRouter} from 'react-router-dom';
import {it,expect,vi,afterEach} from 'vitest';
import {AppShell} from './AppShell';
import {api} from '@/lib/api';
vi.mock('@/lib/api',()=>({api:vi.fn()}));
vi.mock('@/AppContext',()=>({useApp:()=>({resources:{},loading:false,loadError:'',notice:null})}));
afterEach(()=>{cleanup();vi.resetAllMocks()});
it('keeps returning users links below Settings without large entry cards',async()=>{
 vi.mocked(api).mockResolvedValue({onboarding:{completed:true}});
 render(<MemoryRouter><AppShell>工作内容</AppShell></MemoryRouter>);
 const nav=screen.getByRole('navigation',{name:'主导航'});
 fireEvent.click(within(nav).getByRole('button',{name:'设置'}));
 expect(await within(nav).findByRole('link',{name:'离线授权'})).toHaveAttribute('href','/activation');
 expect(within(nav).getByRole('link',{name:'新手引导'})).toHaveAttribute('href','/welcome');
 expect(screen.queryByRole('navigation',{name:'授权与入门'})).toBeNull();
});

it('keeps setup links in settings even when the guide is unfinished',async()=>{
 vi.mocked(api).mockResolvedValue({onboarding:{completed:false}});
 render(<MemoryRouter><AppShell>工作内容</AppShell></MemoryRouter>);
 expect(screen.queryByRole('navigation',{name:'授权与入门'})).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'设置'}));
 expect(screen.getByRole('link',{name:'新手引导'})).toHaveAttribute('href','/welcome');
});
