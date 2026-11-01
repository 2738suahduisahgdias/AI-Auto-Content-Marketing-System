import { MemoryRouter, NavLink, Route, Routes, useLocation } from 'react-router-dom';
import { AppProvider, useApp } from '../AppContext';
import Topics from '../pages/Topics';
import { useEffect } from 'react';
import './original-topics.css';
function OriginalDestination(){const {pathname}=useLocation();useEffect(()=>{window.location.assign(pathname)},[pathname]);return <p>正在打开原系统工作区…</p>}
function Content(){const {notice}=useApp();return <div className="yd-original-topics"><div className="yd-origin">原系统选题工作区 · 直接复用原页面、数据与操作</div><nav className="yd-tabs" aria-label="选题来源">{[['industry','行业热点'],['douyin','抖音选题'],['xiaohongshu','小红书选题'],['wechat','视频号选题']].map(([id,title])=><NavLink key={id} className={({isActive})=>isActive?'yd-button primary':'yd-button'} to={'/topics/'+id}>{title}</NavLink>)}</nav><p className="yd-muted">本区连接原后台；同步、下载、保存与创建任务按原系统执行。需原服务运行及有效登录，AI 推荐与下载沿用原环境配置。</p>{notice&&<div role="status" className="yd-callout">{notice.text}</div>}<Routes><Route path="/topics/:source" element={<Topics/>}/><Route path="*" element={<OriginalDestination/>}/></Routes></div>}
export default function OriginalTopics(){return <MemoryRouter initialEntries={['/topics/douyin']}><AppProvider><Content/></AppProvider></MemoryRouter>}
