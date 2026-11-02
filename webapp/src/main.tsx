import React from "react";
import {initializeContentDrafts} from "@/lib/contentDraft";
import ReactDOM from "react-dom/client";
import {BrowserRouter} from "react-router-dom";
import {AppProvider} from "@/AppContext";
import App from "@/App";
import "@/styles.css";
import "./migration/theme.css";
import "./design-system.css";
const preview=location.pathname.startsWith('/demo');
if(preview&&location.hash){const routes:Record<string,string>={home:'/',projects:'/tasks',studio:'/tasks',topics:'/topics/douyin',articles:'/articles',knowledge:'/knowledge',settings:'/settings',publish:'/publish',review:'/review',accounts:'/accounts',setup:'/setup'};const legacyRoute=routes[location.hash.slice(1)];if(legacyRoute)history.replaceState(null,'','/demo'+legacyRoute);}
async function start(){if(preview){await fetch('/session-bootstrap',{credentials:'same-origin'});}await initializeContentDrafts();ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><BrowserRouter basename={preview?'/demo':undefined}><AppProvider><App migratedVideo/></AppProvider></BrowserRouter></React.StrictMode>)}
void start().catch(()=>{document.getElementById('root')!.textContent='本地服务未连接，请启动后台后刷新。'});
