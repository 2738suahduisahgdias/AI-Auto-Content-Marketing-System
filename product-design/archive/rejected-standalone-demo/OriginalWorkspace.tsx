import {MemoryRouter,Routes,Route,NavLink} from 'react-router-dom';
import {AppProvider,useApp} from '../AppContext';
import Knowledge from '../pages/Knowledge';
import CollectionKnowledge from '../pages/CollectionKnowledge';
import PublishKnowledge from '../pages/PublishKnowledge';
import Settings from '../pages/Settings';
import Setup from '../pages/Setup';
import AccountAnalytics from '../pages/AccountAnalytics';
import Competitors from '../pages/Competitors';
import SocialData from '../pages/SocialData';
import Retrospective from '../pages/Retrospective';
function Pages(){const {loading,loadError,notice}=useApp();return <div className="yd-original-topics">{notice&&<div role="status">{notice.text}</div>}{loading?<p>正在读取原后台…</p>:loadError?<div role="alert">{loadError}</div>:<Routes><Route path="/knowledge" element={<Knowledge/>}/><Route path="/knowledge/collection" element={<CollectionKnowledge/>}/><Route path="/knowledge/publishing" element={<PublishKnowledge/>}/><Route path="/settings" element={<Settings/>}/><Route path="/setup" element={<Setup/>}/><Route path="/accounts/:view?" element={<><nav className="yd-tabs">{[['','总览'],['douyin','抖音'],['xiaohongshu','小红书'],['wechat_channels','视频号'],['wechat_official_account','公众号']].map(([id,name])=><NavLink key={id} className="yd-button" to={'/accounts/'+id}>{name}</NavLink>)}</nav><AccountAnalytics/></>}/><Route path="/competitors" element={<Competitors/>}/><Route path="/social" element={<SocialData/>}/><Route path="/retrospective" element={<Retrospective/>}/><Route path="*" element={<p>请选择原工作区入口</p>}/></Routes>}</div>}
export default function OriginalWorkspace({path}:{path:string}){return <MemoryRouter initialEntries={[path]}><AppProvider><Pages/></AppProvider></MemoryRouter>}
